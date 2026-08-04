from __future__ import annotations

import json
from pathlib import Path, PurePosixPath

from src.frame import Frame, Image
from src.inputs.base import InputContext, SourceFrame, empty_scene
from src.traces import Trace


ANNOTATION_FILES = {
    "sample": "corner_case.json",
    "val": "annotations.json",
}


class CodaSource:
    """Load one image from a local CODA subset."""

    def __init__(
        self,
        dataset_directory: Path,
        *,
        subset: str,
        image_id: int,
    ) -> None:
        self.dataset_directory = Path(dataset_directory)
        if subset not in ANNOTATION_FILES:
            raise ValueError(f"Unsupported CODA subset: {subset}")
        self.subset = subset
        if image_id < 0:
            raise ValueError("CODA image ID must be non-negative")
        self.image_id = image_id

    def load(self, context: InputContext) -> SourceFrame:
        del context  # CODA images are durable source files.
        annotation_path = self.dataset_directory / ANNOTATION_FILES[self.subset]
        try:
            document = json.loads(annotation_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"Invalid CODA annotation file {annotation_path}: {exc}"
            ) from exc

        if not isinstance(document, dict):
            raise ValueError(
                f"CODA annotation file is not an object: {annotation_path}"
            )
        images = document.get("images")
        if not isinstance(images, list):
            raise ValueError(
                f"CODA annotation file has no image list: {annotation_path}"
            )

        matches: list[dict[str, object]] = []
        for record in images:
            if not isinstance(record, dict):
                raise ValueError(
                    f"CODA annotation file has a non-object image record: "
                    f"{annotation_path}"
                )
            record_id = record.get("id")
            if (
                isinstance(record_id, int)
                and not isinstance(record_id, bool)
                and record_id == self.image_id
            ):
                matches.append(record)

        if not matches:
            raise IndexError(f"CODA image ID does not exist: {self.image_id}")
        if len(matches) > 1:
            raise ValueError(f"CODA image ID is duplicated: {self.image_id}")

        file_name = matches[0].get("file_name")
        if not isinstance(file_name, str) or not file_name:
            raise ValueError(f"CODA image {self.image_id} has no filename")
        relative_path = PurePosixPath(file_name)
        if (
            relative_path.is_absolute()
            or len(relative_path.parts) != 1
            or relative_path.name in {"", ".", ".."}
            or "\\" in file_name
        ):
            raise ValueError(
                f"CODA image {self.image_id} has an unsafe filename: {file_name}"
            )

        image_path = self.dataset_directory / "images" / file_name
        if not image_path.is_file():
            raise FileNotFoundError(f"CODA image does not exist: {image_path}")

        print(
            f"[input:coda] selected subset={self.subset} "
            f"image_id={self.image_id}"
        )
        return SourceFrame(
            frame=Frame(
                image=Image(image_path),
                graph=empty_scene(source="coda", timestamp_ns=None),
            ),
            traces=(
                Trace.json(
                    "source.json",
                    {
                        "kind": "coda",
                        "subset": self.subset,
                        "image_id": self.image_id,
                        "file_name": file_name,
                    },
                ),
            ),
        )
