"""Command-line interface for ssdetect."""

import sys
from pathlib import Path

import click

from ssdetect.classifier import ImageClassifier
from ssdetect.utils import setup_logging


@click.command()
@click.argument(
    "directory",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=".",
)
@click.option(
    "--move", type=click.Path(path_type=Path), help="Move screenshots to this directory"
)
@click.option(
    "--copy", type=click.Path(path_type=Path), help="Copy screenshots to this directory"
)
@click.option(
    "--json", "output_json", is_flag=True, help="Output in JSON format for scripts"
)
@click.option("--script", is_flag=True, help="Disable rich UI for script usage")
@click.option(
    "--workers",
    type=click.IntRange(1, 32),
    default=8,
    help="Number of worker processes (default: 8)",
)
@click.option(
    "--ocr", "detection_mode", flag_value="ocr", help="Use only OCR-based detection"
)
@click.option(
    "--horizontal",
    "detection_mode",
    flag_value="horizontal",
    help="Use only horizontal edge detection",
)
@click.option(
    "--both",
    "detection_mode",
    flag_value="both",
    default=True,
    help="Use both detection methods (default)",
)
@click.option(
    "--ocr-chars",
    type=int,
    default=10,
    help="Minimum characters for OCR detection (default: 10)",
)
@click.option(
    "--ocr-quality",
    type=click.FloatRange(0.0, 1.0),
    default=0.6,
    help="Minimum average confidence for OCR (default: 0.6)",
)
@click.option(
    "--no-gpu", is_flag=True, help="Disable GPU acceleration for OCR (use CPU only)"
)
@click.option(
    "--extra-heuristics/--no-extra-heuristics",
    default=True,
    help="Enable/disable experimental heuristics for OCR detection (enabled by default)",
)
def cli(
    directory: Path,
    move: Path | None,
    copy: Path | None,
    output_json: bool,
    script: bool,
    workers: int,
    detection_mode: str,
    ocr_chars: int,
    ocr_quality: float,
    no_gpu: bool,
    extra_heuristics: bool,
):
    """Classify images as screenshots or other.

    Scans DIRECTORY (default: current directory) for images and classifies them
    as screenshots or other images using the screenshot_detector library.
    """
    # Validate mutually exclusive options
    if move and copy:
        click.echo("Error: --move and --copy cannot be used together", err=True)
        sys.exit(1)

    # Validate OCR parameters
    if detection_mode in ("ocr", "both"):
        if ocr_chars < 1:
            click.echo("Error: --ocr-chars must be at least 1", err=True)
            sys.exit(1)
        if not (0.0 <= ocr_quality <= 1.0):
            click.echo("Error: --ocr-quality must be between 0.0 and 1.0", err=True)
            sys.exit(1)

    # Setup logging based on output format
    logger = setup_logging(json_output=output_json, script_mode=script)

    # Create classifier instance
    classifier = ImageClassifier(
        logger=logger,
        move_to=move,
        copy_to=copy,
        json_output=output_json,
        script_mode=script,
        num_workers=workers,
        detection_mode=detection_mode,
        ocr_chars=ocr_chars,
        ocr_quality=ocr_quality,
        use_gpu=not no_gpu,
        extra_heuristics=extra_heuristics,
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
