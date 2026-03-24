# src/main.py
"""Legacy compatibility entrypoint.

Prefer running `python src/runner.py` for interactive menu and test execution modes.
"""

from app.application import run_full_application


def main() -> int:
    """Run the full simulation app and return a process exit code."""
    return run_full_application()


if __name__ == "__main__":
    raise SystemExit(main())
