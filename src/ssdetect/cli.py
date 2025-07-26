"""Command-line interface for ssdetect."""
import sys
from pathlib import Path

import click

from ssdetect.classifier import ImageClassifier
from ssdetect.utils import setup_logging


@click.command()
@click.argument("directory", type=click.Path(exists=True, file_okay=False, path_type=Path), default=".")
@click.option("--move", type=click.Path(path_type=Path), help="Move screenshots to this directory")
@click.option("--copy", type=click.Path(path_type=Path), help="Copy screenshots to this directory")
@click.option("--dry-run", is_flag=True, help="Show what would be done without actually doing it")
@click.option("--json", "output_json", is_flag=True, help="Output in JSON format for scripts")
@click.option("--script", is_flag=True, help="Disable rich UI for script usage")
@click.option("--workers", type=click.IntRange(1, 32), default=8, help="Number of worker processes (default: 8)")
def cli(directory: Path, move: Path | None, copy: Path | None, dry_run: bool, output_json: bool, script: bool, workers: int):
    """Classify images as screenshots or other.
    
    Scans DIRECTORY (default: current directory) for images and classifies them
    as screenshots or other images using the screenshot_detector library.
    """
    # Validate mutually exclusive options
    if move and copy:
        click.echo("Error: --move and --copy cannot be used together", err=True)
        sys.exit(1)
    
    # Setup logging based on output format
    logger = setup_logging(json_output=output_json, script_mode=script)
    
    # Create classifier instance
    classifier = ImageClassifier(
        logger=logger,
        move_to=move,
        copy_to=copy,
        dry_run=dry_run,
        json_output=output_json,
        script_mode=script,
        num_workers=workers
    )
    
    # Run classification
    try:
        exit_code = classifier.process_directory(directory)
        sys.exit(exit_code)
    except KeyboardInterrupt:
        logger.info("Classification interrupted by user")
        sys.exit(130)  # Standard exit code for SIGINT
    except Exception as e:
        logger.error("Unexpected error", error=str(e), exc_info=True)
        sys.exit(1)