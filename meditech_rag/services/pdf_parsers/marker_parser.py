from __future__ import annotations

import os

import config


class MarkerParser:
    name = "marker"

    @staticmethod
    def available() -> bool:
        try:
            import marker  # type: ignore  # noqa: F401

            return True
        except Exception:
            return False

    def parse(self, path: str, profile: str | None = None) -> dict:
        if not self.available():
            raise RuntimeError("Marker parser is not installed.")
        raise RuntimeError(
            "Marker integration is configured as an optional local backend, but this environment "
            "does not expose a stable CLI/API binding for this project yet."
        )

    def placeholder_result(self, path: str, profile: str | None = None) -> dict:
        return {
            "filename": os.path.basename(path),
            "source_path": path,
            "page_count": 0,
            "pages": [],
            "parser_used": self.name,
            "parser_profile": profile or config.PARSER_PROFILE,
            "fallback_used": False,
            "blocks_count": 0,
            "metadata": {"parser_backend": self.name, "available": False},
        }
