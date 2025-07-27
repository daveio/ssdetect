"""Core classification logic for ssdetect."""

import multiprocessing as mp
import queue
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np
import structlog
from PIL import Image
from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from scipy import signal
from screenshot_detector.screenshot_detector import check_img

from ssdetect.utils import (
    copy_file,
    create_progress_bar,
    find_image_files,
    move_file,
)

# Global variables for worker processes
ocr_reader = None
detection_mode = None
ocr_chars_threshold = None
ocr_quality_threshold = None
worker_logger = None
extra_heuristics = None


def worker_init(
    mode: str,
    ocr_chars: int,
    ocr_quality: float,
    use_gpu: bool,
    use_extra_heuristics: bool,
) -> None:
    """Initialize worker process with detection mode and OCR settings."""
    global ocr_reader, detection_mode, ocr_chars_threshold, ocr_quality_threshold, worker_logger, extra_heuristics

    # Import structlog in worker process
    import structlog

    # Set up logger for worker process
    worker_logger = structlog.get_logger().bind(worker_pid=mp.current_process().pid)

    detection_mode = mode
    ocr_chars_threshold = ocr_chars
    ocr_quality_threshold = ocr_quality
    extra_heuristics = use_extra_heuristics

    # Initialize EasyOCR if needed
    if mode in ("ocr", "both"):
        try:
            import warnings

            import easyocr
            import torch

            # Suppress the pin_memory warning on MPS
            if torch.backends.mps.is_available():
                warnings.filterwarnings(
                    "ignore",
                    message=".*pin_memory.*MPS.*",
                    category=UserWarning,
                    module="torch.utils.data.dataloader",
                )

            # Check if GPU should be used and is available
            gpu_available = False
            if use_gpu:
                if torch.backends.mps.is_available():
                    # MPS is available on Apple Silicon
                    gpu_available = True
                    worker_logger.info(
                        "Using Apple Silicon GPU (MPS) for OCR acceleration"
                    )
                elif torch.cuda.is_available():
                    # CUDA is available (NVIDIA GPU)
                    gpu_available = True
                    worker_logger.info("Using NVIDIA GPU (CUDA) for OCR acceleration")
                else:
                    worker_logger.warning("GPU requested but not available, using CPU")

            # Initialize with English language support
            # Note: EasyOCR's gpu parameter expects True/False, not device type
            # It will automatically use MPS on Apple Silicon if available
            ocr_reader = easyocr.Reader(["en"], gpu=gpu_available)
        except Exception as e:
            # If OCR initialization fails, log the error
            worker_logger.error("Failed to initialize OCR", error=str(e))
            ocr_reader = None


@dataclass
class ProcessResult:
    """Result from processing a single image."""

    image_path: Path
    index: int
    is_screenshot: bool
    error: Optional[str] = None
    destination: Optional[Path] = None


def classify_with_horizontal(img_array: np.ndarray) -> bool:
    """Classify image using horizontal edge detection.

    Args:
        img_array: Grayscale image as numpy array

    Returns:
        True if screenshot detected
    """
    # Apply the same kernel as screenshot_detector
    kernel = np.array([[-1, -1, -1], [0, 0, 0], [+1, +1, +1]])

    # Convolve to detect horizontal edges
    dst = signal.convolve2d(img_array, kernel, boundary="symm", mode="same")
    dst = np.absolute(dst)

    # Normalize to 0-10 range
    # Handle edge case where image has no variation
    if dst.min() == dst.max():
        dst2 = np.zeros_like(dst, dtype=int)
    else:
        dst2 = np.interp(dst, (dst.min(), dst.max()), (0, 10)).astype(int)

    # Check for horizontal lines
    list_index = check_img(dst2)

    # If we found horizontal lines, it's a screenshot
    return len(list_index) >= 1


def classify_with_ocr(image_path: Path) -> tuple[bool, Optional[str]]:
    """Classify image using OCR text detection with advanced heuristics.

    Args:
        image_path: Path to the image

    Returns:
        Tuple of (is_screenshot, error_message)
    """
    global ocr_reader, ocr_chars_threshold, ocr_quality_threshold, worker_logger, extra_heuristics

    if ocr_reader is None:
        return False, "OCR not initialized"

    try:
        # Load image to get dimensions
        img = Image.open(image_path)
        img_array = np.array(img)
        img_height, img_width = img_array.shape[:2]

        # Read text from image
        results = ocr_reader.readtext(img_array)

        if not results:
            return False, None

        # Basic metrics
        total_chars = sum(len(text) for _, text, _ in results)
        avg_confidence = sum(conf for _, _, conf in results) / len(results)

        # Advanced metrics for better screenshot detection
        high_conf_regions = sum(1 for _, _, conf in results if conf > 0.7)
        large_text_blocks = sum(1 for _, text, _ in results if len(text) > 20)

        # Check if text is in bottom third (common for captions)
        bottom_third_y = img_height * 2 / 3
        bottom_text_regions = sum(
            1 for bbox, _, _ in results if min(pt[1] for pt in bbox) > bottom_third_y
        )
        has_bottom_text = bottom_text_regions > len(results) / 2

        # Calculate text density
        text_density = total_chars / len(results) if results else 0

        # Screenshot scoring heuristic
        is_screenshot = False

        # Method 1: Traditional threshold check (always used)
        if (
            total_chars >= ocr_chars_threshold
            and avg_confidence >= ocr_quality_threshold
        ):
            is_screenshot = True

        # Additional heuristics only if enabled
        elif extra_heuristics:
            # Method 2: High-quality caption detection
            # Look for high-confidence text blocks in typical caption positions
            # But also check for coherent text (high text density)
            if (
                high_conf_regions >= 2
                and large_text_blocks >= 2
                and has_bottom_text
                and total_chars >= 30
                and text_density > 10
            ):
                is_screenshot = True

            # Method 3: High text density with reasonable confidence
            # Screenshots tend to have dense, readable text
            elif text_density > 15 and avg_confidence > 0.45 and total_chars >= 50:
                is_screenshot = True

        if worker_logger:
            worker_logger.debug(
                "OCR classification complete",
                image=str(image_path),
                total_chars=total_chars,
                avg_confidence=avg_confidence,
                high_conf_regions=high_conf_regions,
                large_text_blocks=large_text_blocks,
                has_bottom_text=has_bottom_text,
                text_density=text_density,
                is_screenshot=is_screenshot,
            )

        return is_screenshot, None

    except Exception as e:
        return False, f"OCR failed: {str(e)}"


def classify_image_worker(image_path: Path) -> tuple[bool, Optional[str]]:
    """Worker function to classify a single image.

    Returns:
        Tuple of (is_screenshot, error_message)
    """
    global detection_mode

    try:
        # Handle horizontal detection
        if detection_mode in ("horizontal", "both"):
            # Load image as grayscale
            img = Image.open(image_path).convert("L")
            img_array = np.array(img)

            is_screenshot_horizontal = classify_with_horizontal(img_array)

            # If horizontal detection found it and we're not in 'both' mode, return
            if detection_mode == "horizontal":
                return is_screenshot_horizontal, None

            # In 'both' mode, if horizontal detected it, it's a screenshot
            if is_screenshot_horizontal:
                return True, None

        # Handle OCR detection
        if detection_mode in ("ocr", "both"):
            is_screenshot_ocr, error = classify_with_ocr(image_path)

            if error:
                return False, error

            return is_screenshot_ocr, None

        # Should not reach here
        return False, None

    except MemoryError:
        return False, "Image too large to process"
    except OSError as e:
        return False, f"Failed to open image: {str(e)}"
    except Exception as e:
        return False, f"Failed to classify: {str(e)}"


def process_image_task(
    args: tuple[Path, int, Optional[Path], Optional[Path]],
) -> ProcessResult:
    """Process a single image (classify and optionally move/copy).

    Args:
        args: Tuple of (image_path, index, move_to, copy_to)

    Returns:
        ProcessResult object
    """
    image_path, index, move_to, copy_to = args

    # Classify the image
    is_screenshot, error = classify_image_worker(image_path)

    if error:
        return ProcessResult(image_path, index, False, error)

    # Handle move/copy if needed
    destination = None
    if is_screenshot and (move_to or copy_to):
        try:
            if move_to:
                destination = move_file(image_path, move_to)
            elif copy_to:
                destination = copy_file(image_path, copy_to)
        except Exception as e:
            return ProcessResult(
                image_path, index, is_screenshot, f"Failed to move/copy: {str(e)}"
            )

    return ProcessResult(image_path, index, is_screenshot, None, destination)


class ImageClassifier:
    """Handles image classification and file operations."""

    def __init__(
        self,
        logger: structlog.BoundLogger,
        move_to: Path | None = None,
        copy_to: Path | None = None,
        json_output: bool = False,
        script_mode: bool = False,
        num_workers: int = 8,
        detection_mode: str = "both",
        ocr_chars: int = 10,
        ocr_quality: float = 0.6,
        use_gpu: bool = True,
        extra_heuristics: bool = False,
    ):
        """Initialize the classifier."""
        self.logger = logger
        self.move_to = move_to
        self.copy_to = copy_to
        self.json_output = json_output
        self.script_mode = script_mode
        self.num_workers = num_workers
        self.detection_mode = detection_mode
        self.ocr_chars = ocr_chars
        self.ocr_quality = ocr_quality
        self.use_gpu = use_gpu
        self.extra_heuristics = extra_heuristics

        # Statistics (protected by lock for thread safety)
        self.total_files = 0
        self.screenshots = 0
        self.other_images = 0
        self.errors = 0
        self.stats_lock = threading.Lock()

        # For non-script mode
        self.console = Console(stderr=True) if not script_mode else None

    def process_directory(self, directory: Path) -> int:
        """Process all images in the given directory.

        Returns:
            Exit code: 0 for success, 1 if there were errors.
        """
        self.logger.info("Scanning directory for images", directory=str(directory))

        # Find all image files
        try:
            image_files = find_image_files(directory)
            self.total_files = len(image_files)
        except Exception as e:
            self.logger.error(
                "Failed to scan directory", directory=str(directory), error=str(e)
            )
            return 1

        if self.total_files == 0:
            self.logger.warning("No image files found", directory=str(directory))
            return 0

        self.logger.info(
            "Found images to process",
            count=self.total_files,
            workers=self.num_workers,
            detection_mode=self.detection_mode,
            ocr_chars=(
                self.ocr_chars if self.detection_mode in ("ocr", "both") else None
            ),
            ocr_quality=(
                self.ocr_quality if self.detection_mode in ("ocr", "both") else None
            ),
        )

        # Process files
        if self.script_mode or self.json_output:
            # Simple processing without Rich UI
            self._process_files_simple(image_files)
        else:
            # Rich UI with progress bar and live display
            self._process_files_rich(image_files)

        # Log summary
        self._log_summary()

        # Return exit code based on errors
        return 1 if self.errors > 0 else 0

    def _process_files_simple(self, image_files: list[Path]) -> None:
        """Process files without Rich UI using multiprocessing."""
        # Prepare tasks
        tasks = [
            (path, i, self.move_to, self.copy_to)
            for i, path in enumerate(image_files, 1)
        ]

        # Process with multiprocessing using worker initialization
        with mp.Pool(
            processes=self.num_workers,
            initializer=worker_init,
            initargs=(
                self.detection_mode,
                self.ocr_chars,
                self.ocr_quality,
                self.use_gpu,
                self.extra_heuristics,
            ),
        ) as pool:
            results = pool.map(process_image_task, tasks)

        # Process results
        for result in results:
            self._handle_result(result)

    def _process_files_rich(self, image_files: list[Path]) -> None:
        """Process files with Rich UI using multiprocessing."""
        progress = create_progress_bar(self.total_files, self.script_mode)

        if progress is None:
            self._process_files_simple(image_files)
            return

        # Queue for results from worker processes (with max size to prevent memory issues)
        result_queue = queue.Queue(maxsize=self.num_workers * 2)

        # Store recent results for display
        recent_results = []
        results_lock = threading.Lock()

        # Worker thread to collect results
        def result_collector(pool, tasks):
            try:
                for result in pool.imap_unordered(process_image_task, tasks):
                    result_queue.put(result)
            except Exception as e:
                self.logger.error("Result collector failed", error=str(e))

        # Function to generate table from recent results
        def create_results_table():
            table = Table(title="Classification Results (last 10)")
            table.add_column("File", style="cyan")
            table.add_column("Result", style="green")
            table.add_column("Action", style="yellow")

            with results_lock:
                for res in recent_results[-10:]:
                    classification = "screenshot" if res.is_screenshot else "other"
                    if res.error:
                        classification = "error"

                    action = "none"
                    if res.is_screenshot and not res.error:
                        if self.move_to:
                            action = "moved"
                        elif self.copy_to:
                            action = "copied"

                    table.add_row(str(res.image_path.name), classification, action)

            return table

        with Live(console=self.console, refresh_per_second=4) as live:
            task = progress.add_task("Classifying images...", total=self.total_files)

            # Prepare tasks
            tasks = [
                (path, i, self.move_to, self.copy_to)
                for i, path in enumerate(image_files, 1)
            ]

            # Start processing in pool with worker initialization
            with mp.Pool(
                processes=self.num_workers,
                initializer=worker_init,
                initargs=(
                    self.detection_mode,
                    self.ocr_chars,
                    self.ocr_quality,
                    self.use_gpu,
                    self.extra_heuristics,
                ),
            ) as pool:
                # Start collector thread
                collector = threading.Thread(
                    target=result_collector, args=(pool, tasks)
                )
                collector.start()

                # Process results as they come in
                processed = 0
                while processed < self.total_files:
                    try:
                        result = result_queue.get(timeout=0.1)
                        self._handle_result(result)

                        # Update progress
                        progress.update(task, advance=1)
                        processed += 1

                        # Add to recent results
                        with results_lock:
                            recent_results.append(result)

                        # Update display
                        layout = Layout()
                        layout.split_column(
                            Layout(progress, size=3),
                            Layout(
                                Panel(
                                    create_results_table(),
                                    title="Classification Results",
                                    border_style="blue",
                                )
                            ),
                        )
                        live.update(layout)

                    except queue.Empty:
                        continue

                # Wait for collector to finish with timeout
                collector.join(timeout=30.0)
                if collector.is_alive():
                    self.logger.error("Result collector thread did not finish in time")

    def _handle_result(self, result: ProcessResult) -> None:
        """Handle a processing result."""
        if result.error:
            with self.stats_lock:
                self.errors += 1
            self.logger.error(
                "Failed to process image",
                file=str(result.image_path),
                index=result.index,
                error=result.error,
            )
        else:
            # Update statistics
            with self.stats_lock:
                if result.is_screenshot:
                    self.screenshots += 1
                    classification = "screenshot"
                else:
                    self.other_images += 1
                    classification = "other"

            # Determine action
            action = "none"
            if result.is_screenshot and (self.move_to or self.copy_to):
                if self.move_to:
                    action = "moved"
                elif self.copy_to:
                    action = "copied"

            # Log result
            log_data = {
                "file": str(result.image_path),
                "index": result.index,
                "classification": classification,
                "action": action,
            }

            if result.destination:
                log_data["destination"] = str(result.destination)

            self.logger.info("Processed image", **log_data)

    def _log_summary(self) -> None:
        """Log a summary of the processing results."""
        summary_data = {
            "total_files": self.total_files,
            "screenshots": self.screenshots,
            "other_images": self.other_images,
            "errors": self.errors,
        }

        if self.move_to:
            summary_data["action"] = "moved"
            summary_data["destination"] = str(self.move_to)
        elif self.copy_to:
            summary_data["action"] = "copied"
            summary_data["destination"] = str(self.copy_to)

        self.logger.info("Classification complete", **summary_data)

        # For non-script, non-JSON mode, also print a nice summary table
        if not self.script_mode and not self.json_output and self.console:
            table = Table(title="Summary", show_header=False)
            table.add_column("Metric", style="cyan")
            table.add_column("Value", style="green")

            table.add_row("Total Files", str(self.total_files))
            table.add_row("Screenshots", str(self.screenshots))
            table.add_row("Other Images", str(self.other_images))
            table.add_row("Errors", str(self.errors))

            if self.move_to or self.copy_to:
                action = "Moved to" if self.move_to else "Copied to"
                destination = str(self.move_to or self.copy_to)
                table.add_row(action, destination)

            self.console.print("\n")
            self.console.print(table)
