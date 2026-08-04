from __future__ import annotations

import argparse
import re
import subprocess
import time
from pathlib import Path

from src.clients import LiteLlmClient, VlmObjectDetectionClient
from src.config import load_config
from src.inputs import Av2Source, CodaSource, VideoSource
from src.pipeline import Pipeline
from src.stages import (
    ObjectDetectionStage,
    RelationExtractionStage,
    RoadLayoutExtractionStage,
    WeatherExtractionStage,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
AV2_ROOT = REPOSITORY_ROOT / "inputs/av2/sensor"
CODA_ROOT = REPOSITORY_ROOT / "inputs/coda"
VIDEO_ROOT = REPOSITORY_ROOT / "inputs/videos"
OUTPUT_ROOT = REPOSITORY_ROOT / "outputs"
MODEL_CONFIG = REPOSITORY_ROOT / "models.yaml"


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a scene graph for one frame")
    subparsers = parser.add_subparsers(dest="source", required=True)

    video = subparsers.add_parser(
        "video", help="Load one frame from a file in inputs/videos"
    )
    video.add_argument("filename", type=_base_filename)
    video.add_argument("--timestamp", type=float, default=0.0)

    av2 = subparsers.add_parser(
        "av2", help="Load one ring_front_center frame from an AV2 Sensor log"
    )
    av2.add_argument("log_id")
    av2.add_argument("--split", choices=("train", "val"), default="val")
    av2.add_argument("--frame", type=int, default=0)

    coda = subparsers.add_parser(
        "coda", help="Load one front-camera image from CODA"
    )
    coda.add_argument("image_id", type=int)
    coda.add_argument("--subset", choices=("sample", "val"), default="val")

    arguments = parser.parse_args()
    try:
        if arguments.source == "video":
            source = VideoSource(
                VIDEO_ROOT / arguments.filename,
                timestamp_seconds=arguments.timestamp,
            )
        elif arguments.source == "av2":
            source = Av2Source(
                AV2_ROOT / arguments.split / arguments.log_id,
                camera_frame_index=arguments.frame,
            )
        else:
            source = CodaSource(
                CODA_ROOT / arguments.subset,
                subset=arguments.subset,
                image_id=arguments.image_id,
            )
        config = load_config(MODEL_CONFIG)
        platform = config.select()
        detection_vlm_client = LiteLlmClient(
            platform,
            timeout_seconds=config.timeout_seconds,
            max_tokens=config.max_tokens,
            reasoning=config.reasoning.detection,
        )
        extraction_vlm_client = LiteLlmClient(
            platform,
            timeout_seconds=config.timeout_seconds,
            max_tokens=config.max_tokens,
            reasoning=config.reasoning.extraction,
        )
        run_directory = _new_run_directory(
            source=arguments.source,
            vlm=config.default_platform,
        )
        detector = VlmObjectDetectionClient(detection_vlm_client)
        Pipeline(
            (
                ObjectDetectionStage(detector),
                RoadLayoutExtractionStage(extraction_vlm_client),
                RelationExtractionStage(extraction_vlm_client),
                WeatherExtractionStage(extraction_vlm_client),
            )
        ).run(source, output_root=run_directory)
    except (FileNotFoundError, IndexError, OSError, RuntimeError, ValueError) as exc:
        parser.error(str(exc))
    return 0


def _base_filename(value: str) -> str:
    path = Path(value)
    if path.is_absolute() or path.name != value or value in {"", ".", ".."}:
        raise argparse.ArgumentTypeError("video must be a base filename")
    return value


def _new_run_directory(*, source: str, vlm: str) -> Path:
    revision = _effective_revision()
    timestamp = int(time.time())
    return OUTPUT_ROOT / f"{timestamp}-{revision}-{source}-{vlm}"


def _effective_revision() -> str:
    jj_error: str
    try:
        result = subprocess.run(
            (
                "jj",
                "log",
                "-r",
                "@",
                "--no-graph",
                "-T",
                "commit_id.short(8)",
            ),
            cwd=REPOSITORY_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        jj_error = "jj is not installed"
    except subprocess.CalledProcessError as exc:
        jj_error = exc.stderr.strip() or str(exc)
    else:
        revision = result.stdout.strip()
        if re.fullmatch(r"[0-9a-f]{8}", revision):
            return revision
        jj_error = f"invalid revision {revision!r}"

    print(f"[run] jj revision unavailable: {jj_error}. fallback=git")
    try:
        result = subprocess.run(
            ("git", "rev-parse", "--verify", "HEAD"),
            cwd=REPOSITORY_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as exc:
        raise RuntimeError(
            f"Run name has no revision. jj: {jj_error}. git is not installed"
        ) from exc
    except subprocess.CalledProcessError as exc:
        git_error = exc.stderr.strip() or str(exc)
        raise RuntimeError(
            f"Run name has no revision. jj: {jj_error}. git: {git_error}"
        ) from exc

    revision = result.stdout.strip()
    if not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", revision):
        raise RuntimeError(
            f"Run name has no revision. jj: {jj_error}. "
            f"git returned an invalid revision: {revision!r}"
        )
    return revision[:7]


if __name__ == "__main__":
    raise SystemExit(main())
