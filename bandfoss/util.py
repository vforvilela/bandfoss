"""Small shared helpers."""

from __future__ import annotations

import shutil


def require_tool(tool: str) -> str:
    """Return the full path of an external tool, or raise if it is not on PATH."""
    path = shutil.which(tool)
    if path is None:
        raise RuntimeError(f"'{tool}' not found on PATH. Install it to continue.")
    return path
