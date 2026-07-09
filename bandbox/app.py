"""Entry point do BandBox."""

from __future__ import annotations

import sys


def main() -> int:
    from .ui.main_window import run
    return run()


if __name__ == "__main__":
    sys.exit(main())
