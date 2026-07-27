default:
    @just --list

# List AV2 Sensor logs and their local download status.
av2-list split="val":
    uv run python scripts/av2_downloader.py --list --split "{{ split }}"

# Download a randomly selected AV2 Sensor log.
av2-download-random split="val":
    uv run python scripts/av2_downloader.py --split "{{ split }}"

# Download a specific AV2 Sensor log.
av2-download log split="val":
    uv run python scripts/av2_downloader.py "{{ log }}" --split "{{ split }}"

# Generate a scene graph for one AV2 front-camera frame.
av2 log frame="0" split="val":
    uv run python -m src.main av2 "{{ log }}" --split "{{ split }}" --frame "{{ frame }}"

# Generate a scene graph for one video frame.
video filename timestamp="0":
    uv run python -m src.main video "{{ filename }}" --timestamp "{{ timestamp }}"
