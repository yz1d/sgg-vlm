from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from typing import Sequence

from PIL import Image as PillowImage
from PIL import ImageDraw

from src.frame import Image


@dataclass(frozen=True, slots=True)
class BoxAnnotation:
    """One labeled pixel-space XYXY box to draw over an image."""

    bbox_xyxy: tuple[float, float, float, float]
    text: str
    color_key: str


def render_box_overlay(
    image: Image,
    annotations: Sequence[BoxAnnotation],
) -> bytes:
    """Render labeled boxes over a copy of the image and return PNG bytes."""

    with PillowImage.open(image.path) as source:
        canvas = source.convert("RGB")
    draw = ImageDraw.Draw(canvas)
    text_color = (20, 20, 20)
    palette = (
        (255, 99, 71),
        (64, 224, 208),
        (255, 215, 0),
        (135, 206, 250),
        (238, 130, 238),
        (144, 238, 144),
        (255, 160, 122),
        (173, 216, 230),
        (240, 230, 140),
        (221, 160, 221),
    )
    colors = {
        key: palette[index % len(palette)]
        for index, key in enumerate(
            sorted({annotation.color_key for annotation in annotations})
        )
    }

    for annotation in annotations:
        color = colors[annotation.color_key]
        x_min, y_min, x_max, y_max = annotation.bbox_xyxy
        draw.rectangle(
            (x_min, y_min, x_max, y_max),
            outline=color,
            width=1,
        )
        left, top, right, bottom = draw.textbbox((0, 0), annotation.text)
        text_width = right - left
        text_height = bottom - top
        label_x = max(0.0, x_min)
        label_y = max(0.0, y_min - text_height - 4)
        draw.rectangle(
            (
                label_x,
                label_y,
                label_x + text_width + 4,
                label_y + text_height + 4,
            ),
            fill=color,
        )
        draw.text(
            (label_x + 2, label_y + 2 - top),
            annotation.text,
            fill=text_color,
        )

    output = BytesIO()
    canvas.save(output, format="PNG")
    return output.getvalue()
