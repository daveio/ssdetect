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

    for ext in IMAGE_EXTENSIONS:
        # Case-insensitive search
        image_files.extend(directory.rglob(f"*{ext}"))
        image_files.extend(directory.rglob(f"*{ext.upper()}"))

    # Remove duplicates and sort
    return sorted(set(image_files))


def count_image_files(directory: Path) -> int:
    """Count image files without loading all into memory."""
    count = 0
    seen = set()

    for ext in IMAGE_EXTENSIONS:
        for path in directory.rglob(f"*{ext}"):
            if path not in seen:
                seen.add(path)
                count += 1
        for path in directory.rglob(f"*{ext.upper()}"):
            if path not in seen:
                seen.add(path)
                count += 1

    return count


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


def move_file(src: Path, dst_dir: Path, dry_run: bool = False) -> Path:
    """Move a file to a destination directory, preserving relative path structure."""
    # Create destination directory if it doesn't exist (thread-safe)
    if not dry_run:
        try:
            dst_dir.mkdir(parents=True, exist_ok=True)
        except FileExistsError:
            # Race condition: another process created it
            pass

    # Preserve original filename
    dst_path = dst_dir / src.name

    # Handle name conflicts (check even in dry_run to show what would happen)
    if dst_path.exists():
        counter = 1
        stem = src.stem
        suffix = src.suffix
        while dst_path.exists():
            dst_path = dst_dir / f"{stem}_{counter}{suffix}"
            counter += 1

    if not dry_run:
        shutil.move(str(src), str(dst_path))

    return dst_path


def copy_file(src: Path, dst_dir: Path, dry_run: bool = False) -> Path:
    """Copy a file to a destination directory, preserving relative path structure."""
    # Create destination directory if it doesn't exist (thread-safe)
    if not dry_run:
        try:
            dst_dir.mkdir(parents=True, exist_ok=True)
        except FileExistsError:
            # Race condition: another process created it
            pass

    # Preserve original filename
    dst_path = dst_dir / src.name

    # Handle name conflicts (check even in dry_run to show what would happen)
    if dst_path.exists():
        counter = 1
        stem = src.stem
        suffix = src.suffix
        while dst_path.exists():
            dst_path = dst_dir / f"{stem}_{counter}{suffix}"
            counter += 1

    if not dry_run:
        shutil.copy2(str(src), str(dst_path))

    return dst_path
