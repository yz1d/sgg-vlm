from __future__ import annotations

import argparse
from datetime import UTC, datetime
from pathlib import Path

from src.clients import GroundingDinoProClient, LiteLlmClient
from src.config import load_config
from src.inputs import Av2Source, VideoSource
from src.pipeline import Pipeline
from src.stages import (
    ObjectDetectionStage,
    RelationExtractionStage,
    RoadLayoutExtractionStage,
    WeatherExtractionStage,
)

DEFAULT_AV2_ROOT = Path("inputs/av2/sensor")
DEFAULT_VIDEO_ROOT = Path("inputs/videos")
DEFAULT_OUTPUT_ROOT = Path("outputs")
DEFAULT_MODEL_CONFIG = Path("models.yaml")


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a scene graph for one frame")
    subparsers = parser.add_subparsers(dest="source", required=True)

    video = subparsers.add_parser(
        "video", help="Load one frame from a file in inputs/videos"
    )
    video.add_argument("filename", type=_base_filename)
    video.add_argument("--timestamp", type=float, default=0.0)
    video.add_argument("--output", type=Path)

    av2 = subparsers.add_parser(
        "av2", help="Load one ring_front_center frame from an AV2 Sensor log"
    )
    av2.add_argument("log_id")
    av2.add_argument("--split", choices=("train", "val"), default="val")
    av2.add_argument("--dataset-root", type=Path, default=DEFAULT_AV2_ROOT)
    av2.add_argument("--frame", type=int, default=0)
    av2.add_argument("--output", type=Path)

    for source_parser in (video, av2):
        source_parser.add_argument(
            "--model-config", type=Path, default=DEFAULT_MODEL_CONFIG
        )
        source_parser.add_argument(
            "--vlm-platform",
            help="VLM platform for road-layout and relation extraction",
        )

    arguments = parser.parse_args()
    output = arguments.output or _new_run_directory()
    try:
        if arguments.source == "video":
            source = VideoSource(
                DEFAULT_VIDEO_ROOT / arguments.filename,
                timestamp_seconds=arguments.timestamp,
            )
        else:
            source = Av2Source(
                arguments.dataset_root / arguments.split / arguments.log_id,
                camera_frame_index=arguments.frame,
            )
        config = load_config(arguments.model_config)
        vlm_client = LiteLlmClient(config.select(arguments.vlm_platform))
        detector = GroundingDinoProClient()
        Pipeline(
            (
                ObjectDetectionStage(detector),
                RoadLayoutExtractionStage(vlm_client),
                RelationExtractionStage(vlm_client),
                WeatherExtractionStage(vlm_client),
            )
        ).run(source, output_root=output)
    except (FileNotFoundError, IndexError, OSError, RuntimeError, ValueError) as exc:
        parser.error(str(exc))
    return 0


def _base_filename(value: str) -> str:
    path = Path(value)
    if path.is_absolute() or path.name != value or value in {"", ".", ".."}:
        raise argparse.ArgumentTypeError("video must be a base filename")
    return value


def _new_run_directory() -> Path:
    timestamp = datetime.now(UTC).strftime("%Y-%m-%dT%H-%M-%S-%fZ")
    return DEFAULT_OUTPUT_ROOT / timestamp


if __name__ == "__main__":
    raise SystemExit(main())
