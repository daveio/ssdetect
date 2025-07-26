# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

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
uv run ssdetect --dry-run input/      # Preview without moving files
uv run ssdetect --workers=4 input/    # Adjust worker processes (default: 8)
uv run ssdetect --no-gpu input/       # Disable GPU acceleration for OCR
```

### Testing

```bash
# Test with sample images
uv run ssdetect --dry-run --horizontal input/
uv run ssdetect --dry-run --ocr --workers=1 input/

# Test file operations
uv run ssdetect --dry-run --move output/ input/
uv run ssdetect --dry-run --copy output/ input/
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

## Dependencies

- **screenshot_detector**: Git dependency for horizontal edge detection
- **easyocr**: OCR engine with GPU acceleration support
- **click**: CLI framework
- **rich**: Terminal UI for progress bars
- **structlog**: Structured logging
- **scipy/numpy**: Image processing
- **uv**: Fast Python package manager and runner

## Important Notes

- OCR mode is significantly slower but more accurate than horizontal detection
- First image in each worker takes longer due to OCR model loading
- GPU acceleration (MPS/CUDA) provides significant performance improvement for OCR
- The tool processes images recursively in the given directory
- Supports common image formats: jpg, jpeg, png, bmp, gif, webp, tiff, heic, avif
