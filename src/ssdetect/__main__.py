"""Entry point for the ssdetect CLI."""

from ssdetect.cli import cli
from ssdetect.utils import load_config


def main():
    """Main entry point."""
    config = load_config()
    cli(default_map=config)


if __name__ == "__main__":
    main()
