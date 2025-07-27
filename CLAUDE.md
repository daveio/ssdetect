# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Important Notes for Claude

- **NO --dry-run FLAG**: This tool does NOT have a `--dry-run` option. The default behavior is read-only (just classification). Files are only moved/copied when `--move` or `--copy` flags are explicitly used.
- **USE --script FLAG**: When running ssdetect, always use the `--script` flag for cleaner output that's easier to parse. This disables the Rich UI and outputs simple lines to stdout/stderr.

## Project Overview

`ssdetect` is a command-line tool for classifying images as screenshots or regular images using two detection methods:

1. **Horizontal edge detection** - Detects horizontal lines common in screenshots using the `screenshot_detector` library
2. **OCR-based detection** - Uses EasyOCR to detect text and classify based on character count and confidence

## Commands

### Development

```bash
# Install dependencies (using uv)
uv sync

# Run the tool
uv run ssdetect [OPTIONS] [DIRECTORY]

# Run specific detection modes
uv run ssdetect --horizontal input/    # Edge detection only
uv run ssdetect --ocr input/          # OCR only (slower, more accurate)
uv run ssdetect --both input/         # Both methods (default)

# Common options
uv run ssdetect --script input/       # Analyze with clean output (recommended for Claude)
uv run ssdetect --workers=4 input/    # Adjust worker processes (default: 8)
uv run ssdetect --no-gpu input/       # Disable GPU acceleration for OCR

# OCR tuning options
uv run ssdetect --ocr-chars=20 input/        # Minimum character count (default: 10)
uv run ssdetect --ocr-quality=0.5 input/     # Minimum confidence (default: 0.6)
uv run ssdetect --extra-heuristics input/    # Enable experimental heuristics
```

### Testing

```bash
# Test with sample images (read-only by default)
uv run ssdetect --script --horizontal input/
uv run ssdetect --script --ocr --workers=1 input/

# Test file operations (ACTUALLY MOVES/COPIES FILES)
uv run ssdetect --script --move output/ input/
uv run ssdetect --script --copy output/ input/
```

## Architecture

### Core Components

1. **CLI Layer** (`cli.py`)
   - Entry point with Click-based interface
   - Parameter validation (OCR thresholds, mutually exclusive options)
   - Logging setup based on output mode (JSON, script, or rich UI)

2. **Classification Engine** (`classifier.py`)
   - `ImageClassifier`: Main orchestrator with thread-safe statistics
   - Multiprocessing pool with persistent worker initialization
   - Two processing modes: simple (for scripts) and rich (with progress UI)
   - Worker processes initialized once with EasyOCR to avoid repeated model loading

3. **Detection Methods**
   - `classify_with_horizontal()`: Uses scipy convolution for edge detection
   - `classify_with_ocr()`: Uses EasyOCR to count text characters and confidence
     - Basic mode: Simple threshold check (chars >= threshold AND confidence >= threshold)
     - With `--extra-heuristics`: Additional checks for caption-like text patterns
   - Combined mode runs horizontal first, then OCR if needed (OR logic)

### Multiprocessing Design

- **Worker Initialization**: Each worker process gets its own OCR reader instance via `worker_init()`
- **GPU Support**: Automatically detects Apple Silicon MPS or NVIDIA CUDA
- **Thread Safety**: Statistics updates protected by locks, file operations handle race conditions
- **Queue Management**: Bounded queue prevents memory issues, collector thread with timeout

### Key Implementation Details

- Workers persist throughout processing to avoid repeated OCR model initialization
- Rich UI uses a separate thread to collect results without blocking workers
- File operations (move/copy) handle name conflicts with incrementing counters
- Structured logging with worker PIDs for debugging multiprocessing issues
- Graceful error handling for OCR initialization failures
- PyTorch pin_memory warnings are suppressed on Apple Silicon (MPS)
- Extra heuristics look for text patterns common in screenshots:
  - Multiple large text blocks (>20 characters)
  - Text in bottom third of image (caption position)
  - High text density (characters per region > 15)

## Dependencies

- **screenshot_detector**: Git dependency for horizontal edge detection
- **easyocr**: OCR engine with GPU acceleration support
- **click**: CLI framework
- **rich**: Terminal UI for progress bars
- **structlog**: Structured logging
- **scipy/numpy**: Image processing
- **opencv-python**: Advanced image preprocessing (installed for future enhancements)
- **uv**: Fast Python package manager and runner

## Important Notes

- OCR mode is significantly slower but more accurate than horizontal detection
- First image in each worker takes longer due to OCR model loading
- GPU acceleration (MPS/CUDA) provides significant performance improvement for OCR
- The tool processes images recursively in the given directory
- Supports common image formats: jpg, jpeg, png, bmp, gif, webp, tiff, heic, avif
