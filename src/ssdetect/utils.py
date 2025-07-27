"""Utility functions for ssdetect."""

import logging
import shutil
import sys
from pathlib import Path

import structlog
from rich.console import Console
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)

# Supported image extensions
IMAGE_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".bmp",
    ".gif",
    ".webp",
    ".tiff",
    ".tif",
    ".heic",
    ".heif",
    ".avif",
}


def setup_logging(
    json_output: bool = False, script_mode: bool = False
) -> structlog.BoundLogger:
    """Setup structured logging based on output mode."""
    if json_output:
        # JSON output for scripting
        processors = [
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.add_log_level,
            structlog.processors.JSONRenderer(),
        ]
    elif script_mode:
        # Simple console output for scripts (no colors/rich formatting)
        processors = [
            structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S"),
            structlog.processors.add_log_level,
            structlog.processors.KeyValueRenderer(key_order=["event", "file"]),
        ]
    else:
        # Rich console output for interactive use
        processors = [
            structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S"),
            structlog.processors.add_log_level,
            structlog.dev.ConsoleRenderer(),
        ]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )

    return structlog.get_logger()


def find_image_files(directory: Path) -> list[Path]:
    """Recursively find all image files in a directory."""
    image_files = []

    # Get all files recursively
    for file_path in directory.rglob("*"):
        if file_path.is_file():
            # Check if the file extension (case-insensitive) is in our supported list
            if file_path.suffix.lower() in IMAGE_EXTENSIONS:
                image_files.append(file_path)

    return sorted(image_files)


def create_progress_bar(total: int, script_mode: bool = False) -> Progress | None:
    """Create a Rich progress bar for tracking processing."""
    if script_mode:
        return None

    return Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        TimeRemainingColumn(),
        console=Console(stderr=True),  # Use stderr to keep stdout clean
        transient=False,
    )


def move_file(src: Path, dst_dir: Path) -> Path:
    """Move a file to a destination directory, preserving relative path structure.

    Also moves associated XMP sidecar files if they exist.
    """
    # Create destination directory if it doesn't exist (thread-safe)
    try:
        dst_dir.mkdir(parents=True, exist_ok=True)
    except FileExistsError:
        # Race condition: another process created it
        pass

    # Preserve original filename
    dst_path = dst_dir / src.name

    # Handle name conflicts
    if dst_path.exists():
        counter = 1
        stem = src.stem
        suffix = src.suffix
        while dst_path.exists():
            dst_path = dst_dir / f"{stem}_{counter}{suffix}"
            counter += 1

    # Move the main file
    shutil.move(str(src), str(dst_path))

    # Check for XMP sidecar files (case-insensitive)
    xmp_files = []
    # Look for any file with same stem but different suffix
    for file in src.parent.iterdir():
        if file.stem == src.stem and file.suffix.lower() == ".xmp":
            xmp_files.append(file)

    # Move XMP sidecars if they exist
    for xmp_src in xmp_files:
        xmp_dst = dst_path.parent / f"{dst_path.stem}{xmp_src.suffix}"
        try:
            shutil.move(str(xmp_src), str(xmp_dst))
        except Exception:
            # If XMP move fails, don't fail the entire operation
            pass

    return dst_path


def copy_file(src: Path, dst_dir: Path) -> Path:
    """Copy a file to a destination directory, preserving relative path structure.

    Also copies associated XMP sidecar files if they exist.
    """
    # Create destination directory if it doesn't exist (thread-safe)
    try:
        dst_dir.mkdir(parents=True, exist_ok=True)
    except FileExistsError:
        # Race condition: another process created it
        pass

    # Preserve original filename
    dst_path = dst_dir / src.name

    # Handle name conflicts
    if dst_path.exists():
        counter = 1
        stem = src.stem
        suffix = src.suffix
        while dst_path.exists():
            dst_path = dst_dir / f"{stem}_{counter}{suffix}"
            counter += 1

    # Copy the main file
    shutil.copy2(str(src), str(dst_path))

    # Check for XMP sidecar files (case-insensitive)
    xmp_files = []
    # Look for any file with same stem but different suffix
    for file in src.parent.iterdir():
        if file.stem == src.stem and file.suffix.lower() == ".xmp":
            xmp_files.append(file)

    # Copy XMP sidecars if they exist
    for xmp_src in xmp_files:
        xmp_dst = dst_path.parent / f"{dst_path.stem}{xmp_src.suffix}"
        try:
            shutil.copy2(str(xmp_src), str(xmp_dst))
        except Exception:
            # If XMP copy fails, don't fail the entire operation
            pass

    return dst_path
