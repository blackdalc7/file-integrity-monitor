"""Allow ``python -m fim`` to run the CLI."""

from fim.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
