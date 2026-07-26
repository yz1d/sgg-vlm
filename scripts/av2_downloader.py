from __future__ import annotations

import argparse
import secrets
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from urllib.parse import quote
from xml.etree import ElementTree

import requests

S3_ENDPOINT = "https://argoverse.s3.amazonaws.com"
SENSOR_PREFIX = "datasets/av2/sensor"
DEFAULT_DATASET_ROOT = Path("inputs/av2/sensor")
FRONT_CAMERA_PATH = "sensors/cameras/ring_front_center"
REQUIRED_FILES = (
    "annotations.feather",
    "city_SE3_egovehicle.feather",
    "calibration/egovehicle_SE3_sensor.feather",
    "calibration/intrinsics.feather",
)


@dataclass(frozen=True, slots=True)
class S3Object:
    key: str
    size: int


def list_objects(prefix: str, session: requests.Session) -> list[S3Object]:
    objects: list[S3Object] = []
    continuation_token: str | None = None
    while True:
        parameters = {"list-type": "2", "prefix": prefix}
        if continuation_token is not None:
            parameters["continuation-token"] = continuation_token
        response = session.get(S3_ENDPOINT, params=parameters, timeout=(10, 60))
        response.raise_for_status()
        page, continuation_token = _parse_list_page(response.text)
        objects.extend(page)
        if continuation_token is None:
            return objects


def _parse_list_page(xml: str) -> tuple[list[S3Object], str | None]:
    root = ElementTree.fromstring(xml)
    namespace = {"s3": "http://s3.amazonaws.com/doc/2006-03-01/"}
    objects: list[S3Object] = []
    for content in root.findall("s3:Contents", namespace):
        key = content.findtext("s3:Key", namespaces=namespace)
        size = content.findtext("s3:Size", namespaces=namespace)
        if key is not None and size is not None:
            objects.append(S3Object(key, int(size)))
    token = root.findtext(
        "s3:NextContinuationToken", default=None, namespaces=namespace
    )
    return objects, token


def list_log_ids(split: str) -> list[str]:
    prefix = f"{SENSOR_PREFIX}/{split}/"
    log_ids: list[str] = []
    continuation_token: str | None = None
    with requests.Session() as session:
        while True:
            parameters = {
                "list-type": "2",
                "prefix": prefix,
                "delimiter": "/",
            }
            if continuation_token is not None:
                parameters["continuation-token"] = continuation_token
            response = session.get(
                S3_ENDPOINT, params=parameters, timeout=(10, 60)
            )
            response.raise_for_status()
            root = ElementTree.fromstring(response.text)
            namespace = {"s3": "http://s3.amazonaws.com/doc/2006-03-01/"}
            for common_prefix in root.findall("s3:CommonPrefixes", namespace):
                value = common_prefix.findtext("s3:Prefix", namespaces=namespace)
                if value is not None:
                    log_id = value.removeprefix(prefix).rstrip("/")
                    if log_id:
                        log_ids.append(log_id)
            continuation_token = root.findtext(
                "s3:NextContinuationToken",
                default=None,
                namespaces=namespace,
            )
            if continuation_token is None:
                return sorted(set(log_ids))


def discover_log(log_id: str, split: str) -> tuple[str, list[S3Object]]:
    prefix = f"{SENSOR_PREFIX}/{split}/{log_id}/"
    with requests.Session() as session:
        objects: list[S3Object] = []
        for relative_path in REQUIRED_FILES:
            key = prefix + relative_path
            match = next(
                (item for item in list_objects(key, session) if item.key == key),
                None,
            )
            if match is None:
                raise FileNotFoundError(
                    f"Required AV2 object does not exist: s3://argoverse/{key}"
                )
            objects.append(match)
        objects.extend(list_objects(prefix + FRONT_CAMERA_PATH + "/", session))
    if len(objects) == len(REQUIRED_FILES):
        raise FileNotFoundError(
            f"No ring_front_center images exist for AV2 log {log_id}"
        )
    return prefix, objects


def download_object(
    item: S3Object,
    *,
    prefix: str,
    destination: Path,
) -> tuple[bool, int]:
    relative_text = item.key.removeprefix(prefix)
    relative_path = PurePosixPath(relative_text)
    if (
        relative_text == item.key
        or relative_path.is_absolute()
        or ".." in relative_path.parts
    ):
        raise ValueError(f"S3 key is outside the requested log: {item.key}")

    path = destination.joinpath(*relative_path.parts)
    if path.is_file() and path.stat().st_size == item.size:
        return False, item.size

    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_name(path.name + ".part")
    url = f"{S3_ENDPOINT}/{quote(item.key, safe='/')}"
    try:
        with requests.get(url, stream=True, timeout=(10, 120)) as response:
            response.raise_for_status()
            written = 0
            with partial.open("wb") as output:
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        output.write(chunk)
                        written += len(chunk)
        if written != item.size:
            raise OSError(
                f"Incomplete download for {item.key}: "
                f"expected {item.size} bytes, received {written}"
            )
        partial.replace(path)
    except Exception:
        partial.unlink(missing_ok=True)
        raise
    return True, item.size


def download_log(
    log_id: str,
    *,
    split: str,
    dataset_root: Path,
    workers: int,
) -> None:
    if workers < 1:
        raise ValueError("Worker count must be at least one")
    print(f"[av2:download] discovering log={log_id} split={split}")
    prefix, objects = discover_log(log_id, split)
    destination = dataset_root / split / log_id
    total_size = sum(item.size for item in objects)
    print(
        f"[av2:download] started files={len(objects)} "
        f"size={_format_bytes(total_size)} destination={destination}"
    )

    downloaded_files = 0
    downloaded_bytes = 0
    skipped_files = 0
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [
            executor.submit(
                download_object,
                item,
                prefix=prefix,
                destination=destination,
            )
            for item in objects
        ]
        for completed, future in enumerate(as_completed(futures), start=1):
            downloaded, size = future.result()
            if downloaded:
                downloaded_files += 1
                downloaded_bytes += size
            else:
                skipped_files += 1
            if completed % 50 == 0 or completed == len(objects):
                print(
                    f"[av2:download] progress files={completed}/{len(objects)}"
                )

    print(
        f"[av2:download] finished downloaded={downloaded_files} "
        f"bytes={_format_bytes(downloaded_bytes)} skipped={skipped_files}"
    )


def _is_downloaded(dataset_root: Path, split: str, log_id: str) -> bool:
    log_directory = dataset_root / split / log_id
    return all((log_directory / path).is_file() for path in REQUIRED_FILES) and any(
        (log_directory / FRONT_CAMERA_PATH).glob("*.jpg")
    )


def _format_bytes(size: int) -> str:
    value = float(size)
    for unit in ("B", "KiB", "MiB", "GiB"):
        if value < 1024 or unit == "GiB":
            return f"{value:.1f}{unit}"
        value /= 1024
    raise AssertionError("unreachable")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Download one front-camera subset of an AV2 Sensor log"
    )
    parser.add_argument(
        "log_id", nargs="?", help="AV2 log ID; a remote log is chosen randomly if omitted"
    )
    parser.add_argument("--split", choices=("train", "val"), default="val")
    parser.add_argument(
        "--dataset-root", type=Path, default=DEFAULT_DATASET_ROOT
    )
    parser.add_argument("--workers", type=int, default=12)
    parser.add_argument(
        "--list", action="store_true", help="List available log IDs without downloading"
    )
    arguments = parser.parse_args()
    try:
        if arguments.list:
            if arguments.log_id is not None:
                raise ValueError("A log ID cannot be combined with --list")
            for log_id in list_log_ids(arguments.split):
                status = (
                    "downloaded"
                    if _is_downloaded(
                        arguments.dataset_root, arguments.split, log_id
                    )
                    else "remote"
                )
                print(f"{status:10} {log_id}")
            return

        log_id = arguments.log_id
        if log_id is None:
            candidates = [
                candidate
                for candidate in list_log_ids(arguments.split)
                if not _is_downloaded(
                    arguments.dataset_root, arguments.split, candidate
                )
            ]
            if not candidates:
                raise ValueError(
                    f"No undownloaded AV2 {arguments.split} logs are available"
                )
            log_id = secrets.choice(candidates)
            print(f"[av2:download] randomly selected log={log_id}")

        download_log(
            log_id,
            split=arguments.split,
            dataset_root=arguments.dataset_root,
            workers=arguments.workers,
        )
    except (OSError, ValueError, requests.RequestException) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
