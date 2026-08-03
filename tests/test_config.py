from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from src.config import load_config


class ConfigTest(unittest.TestCase):
    def test_loads_and_selects_vlm_platform(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "models.yaml"
            path.write_text(
                """default_platform: primary
platforms:
  primary:
    model: "  provider/model  "
    api_key_env: API_KEY
    timeout_seconds: 30
    parameters:
      max_tokens: 2048
""",
                encoding="utf-8",
            )

            config = load_config(path)

        selected = config.select()
        self.assertEqual(selected.model, "provider/model")
        self.assertEqual(selected.timeout_seconds, 30.0)
        self.assertEqual(selected.parameters, {"max_tokens": 2048})

    def test_rejects_unknown_default_platform(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "models.yaml"
            path.write_text(
                """default_platform: missing
platforms:
  primary:
    model: provider/model
    api_key_env: API_KEY
""",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(
                ValueError,
                "default_platform must name a configured VLM platform",
            ):
                load_config(path)

    def test_rejects_unknown_fields(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "models.yaml"
            path.write_text(
                """default_platform: primary
platforms:
  primary:
    model: provider/model
    api_key_env: API_KEY
    unexpected: value
""",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "unexpected"):
                load_config(path)


if __name__ == "__main__":
    unittest.main()
