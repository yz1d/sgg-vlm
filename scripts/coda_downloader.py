from __future__ import annotations

import argparse
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from zipfile import BadZipFile, ZipFile

import requests


DATASET_ROOT = Path(__file__).resolve().parents[1] / "inputs/coda"


@dataclass(frozen=True, slots=True)
class CodaDownload:
    url: str
    archive_root: PurePosixPath
    annotation_file: str
    archive_size: int
    image_count: int


DOWNLOADS = {
    "sample": CodaDownload(
        url="https://coda-dataset.github.io/assets/file/coda_sample.zip",
        archive_root=PurePosixPath("CODA/sample"),
        annotation_file="corner_case.json",
        archive_size=43_274_731,
        image_count=100,
    ),
    "val": CodaDownload(
        url=(
            "https://drive.usercontent.google.com/download"
            "?id=12JxBdidDFppFMg8mJXsOCpxfotSGRDyO"
            "&export=download&confirm=t"
        ),
        archive_root=PurePosixPath("."),
        annotation_file="annotations.json",
        archive_size=437_070_684,
        image_count=4_884,
    ),
}


def download_subset(subset: str) -> None:
    download = DOWNLOADS[subset]
    destination = DATASET_ROOT / subset
    if _is_complete(destination, download):
        print(f"[coda:download] subset already exists: {destination}")
        return
    if destination.exists():
        raise OSError(f"CODA subset directory is incomplete: {destination}")

    DATASET_ROOT.mkdir(parents=True, exist_ok=True)
    print(f"[coda:download] started subset={subset} url={download.url}")
    with tempfile.TemporaryDirectory(
        prefix=f".coda-{subset}-", dir=DATASET_ROOT
    ) as workspace_text:
        workspace = Path(workspace_text)
        archive_path = workspace / f"coda-{subset}.zip"
        received = _download_archive(download.url, archive_path)
        if received != download.archive_size:
            raise OSError(
                f"CODA {subset} archive size is {received} bytes. "
                f"Expected {download.archive_size} bytes"
            )

        subset_directory = workspace / subset
        image_count = _extract_subset(
            archive_path,
            subset_directory,
            download,
        )
        subset_directory.replace(destination)

    print(
        f"[coda:download] finished subset={subset} "
        f"images={image_count} destination={destination}"
    )


def _download_archive(url: str, destination: Path) -> int:
    received = 0
    with requests.get(url, stream=True, timeout=(10, 120)) as response:
        response.raise_for_status()
        with destination.open("wb") as output:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    output.write(chunk)
                    received += len(chunk)
    return received


def _extract_subset(
    archive_path: Path,
    destination: Path,
    download: CodaDownload,
) -> int:
    extracted: set[PurePosixPath] = set()
    image_count = 0
    with ZipFile(archive_path) as archive:
        for member in archive.infolist():
            path = PurePosixPath(member.filename)
            try:
                relative_path = path.relative_to(download.archive_root)
            except ValueError:
                continue
            if member.is_dir() or not relative_path.parts:
                continue

            is_annotation = relative_path == PurePosixPath(
                download.annotation_file
            )
            is_image = (
                len(relative_path.parts) == 2
                and relative_path.parts[0] == "images"
                and relative_path.suffix.lower() == ".jpg"
            )
            if not is_annotation and not is_image:
                continue
            if relative_path in extracted:
                raise ValueError(f"Duplicate CODA archive member: {relative_path}")
            extracted.add(relative_path)

            output_path = destination.joinpath(*relative_path.parts)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(member) as source, output_path.open("wb") as output:
                shutil.copyfileobj(source, output)
            if is_image:
                image_count += 1

    annotation_path = destination / download.annotation_file
    if not annotation_path.is_file():
        raise ValueError("CODA archive has no annotation file")
    if image_count != download.image_count:
        raise ValueError(
            f"CODA archive contains {image_count} images. "
            f"Expected {download.image_count} images"
        )
    return image_count


def _is_complete(directory: Path, download: CodaDownload) -> bool:
    if not (directory / download.annotation_file).is_file():
        return False
    return sum(1 for _ in (directory / "images").glob("*.jpg")) == download.image_count


def main() -> None:
    parser = argparse.ArgumentParser(description="Download a CODA image subset")
    parser.add_argument("subset", choices=tuple(DOWNLOADS))
    arguments = parser.parse_args()
    try:
        download_subset(arguments.subset)
    except (BadZipFile, OSError, ValueError, requests.RequestException) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
