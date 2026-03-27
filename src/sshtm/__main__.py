"""Entry point for `python -m sshtm` and the `sshtm` console script."""

from __future__ import annotations

import sys


def main() -> None:
    """Launch the sshtm TUI application."""
    # Handle --version / --help before importing heavy deps
    if len(sys.argv) > 1:
        if sys.argv[1] in ("--version", "-V"):
            from sshtm import __version__

            print(f"sshtm {__version__}")
            return
        if sys.argv[1] in ("--help", "-h"):
            print(
                "sshtm — Interactive SSH tunnel manager\n"
                "\n"
                "Usage: sshtm [OPTIONS]\n"
                "\n"
                "Options:\n"
                "  -h, --help     Show this help message\n"
                "  -V, --version  Show version\n"
            )
            return

    from sshtm.app import SSHTMApp

    app = SSHTMApp()
    app.run()


if __name__ == "__main__":
    main()
