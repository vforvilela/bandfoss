"""Permite `python -m bandbox`."""

import sys

from .app import main

if __name__ == "__main__":
    sys.exit(main())
