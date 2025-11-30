# ssdetect

ssdetect is a command-line tool that classifies images as screenshots or regular images using two surprisingly effective methods: horizontal edge detection (fast but sometimes wrong) and OCR-based text detection (slow but annoyingly accurate).

## Why This Exists

Whether you're organizing your digital hoarding collection or building some ML pipeline that needs to know the difference between a photo of your cat and a screenshot of your cat, ssdetect has you covered.

## Installation

```bash
# Install dependencies
uv sync

# Or if you're feeling adventurous, install it somewhere
uv build && pip install dist/*.whl
```

## Usage

### Basic Usage

```bash
# Analyze current directory
uv run ssdetect

# Analyze a specific directory
uv run ssdetect /path/to/your/digital/chaos

# Just analyze without moving/copying (default behavior)
uv run ssdetect input/
```

### Detection Modes

Pick your poison:

```bash
# Fast but sometimes confused by horizontal lines in nature photos
uv run ssdetect --horizontal input/

# Slow but superb
uv run ssdetect --ocr input/

# Both methods
uv run ssdetect --both input/  # (this is the default, obviously)
```

### File Management

Because apparently classification isn't enough:

```bash
# Move screenshots to a designated shame folder
uv run ssdetect --move screenshots/ input/

# Copy them instead (commitment issues?)
uv run ssdetect --copy screenshots/ input/

# Adjust worker count (beware of OCR mode on a CPU)
uv run ssdetect --workers=4 input/
```

> [!NOTE]
> When moving or copying images, any associated XMP sidecar files (metadata files used by photo editing software) are automatically moved/copied along with the main image file. This preserves your edits and metadata.

### OCR Fine-Tuning

For when the defaults aren't good enough for your special use case:

```bash
# Require more characters before declaring "yep, that's text"
uv run ssdetect --ocr-chars=20 input/

# Be more picky about text quality (generally not a great idea)
uv run ssdetect --ocr-quality=0.6 input/

# Disable GPU because you hate performance. Don't use this on
# Apple Silicon - the MPS module is considered a GPU.
uv run ssdetect --no-gpu input/

# Disable experimental heuristics (enabled by default)
# (experimental heuristics help reduce false positives on images with engraved/natural text)
uv run ssdetect --ocr --no-extra-heuristics input/

# Resize images before OCR for better performance (default: 1.0, no resize)
# Use values < 1.0 to speed up OCR on large images
uv run ssdetect --ocr-resize=0.5 input/
```

### Output Formats

```bash
# JSON output for when you need to feed this into another tool
uv run ssdetect --json input/

# Script mode (disables the fancy progress bars)
uv run ssdetect --script input/
```

### Configuration Files

You can set default options in a configuration file instead of passing them on the command line every time:

**Option 1: Add to `pyproject.toml`:**

```toml
[tool.ssdetect]
ocr-chars = 20
ocr-quality = 0.8
ocr-resize = 0.5
detection-mode = "both"
```

**Option 2: Create `ssdetect.toml` in the current directory:**

```toml
[ssdetect]
ocr-chars = 20
ocr-quality = 0.8
ocr-resize = 0.5
```

> [!NOTE]
> Configuration file values are used as defaults. Command-line arguments will override these settings. Keys use dashes (e.g., `ocr-chars`), which are automatically converted to match CLI option names.

## How It Works

### Method 1: Horizontal Edge Detection

Uses scipy convolution to detect horizontal lines because screenshots love their nice straight UI elements. Fast and 95% accurate per the authors. For proper screenshots, that's true, but if it's a smaller _subset_ of the screen... it struggles.

### Method 2: OCR Text Detection

Runs EasyOCR on everything and counts characters like an obsessive librarian. If it finds enough readable text with decent confidence, it's probably a screenshot. Text in photos tends to be messier.

By default (disable with `--no-extra-heuristics`), it also looks for:

- Multiple large text blocks (>20 characters) with high confidence
- Text concentrated in typical caption positions (bottom third of image)
- High text density (characters per region) indicating coherent sentences

### Method 3: Both (Default)

Runs horizontal detection first (because speed), then falls back to OCR if needed. It's like having a fast intern and a thorough expert working together.

## Performance Notes

- We load the model upfront in each worker process.
- GPU acceleration actually works (MPS on Apple Silicon, CUDA on NVIDIA).
- Workers persist throughout processing to avoid re-initializing OCR models repeatedly.
- Rich UI updates without blocking the actual work (revolutionary!).
- PyTorch pin_memory warnings on Apple Silicon are suppressed (they're harmless).

## Supported Formats

The usual suspects: `jpg`, `jpeg`, `png`, `bmp`, `gif`, `webp`, `tiff`, `heic`, `heif`, `avif`

> [!NOTE]
> HEIC/HEIF support is provided through the `pillow-heif` plugin which is automatically installed.

## Dependencies

- **screenshot_detector**: Some random Git repo that does the horizontal edge magic
- **easyocr**: The OCR heavy lifter (warning: downloads models on first run)
- **pillow-heif**: Enables HEIC/HEIF support for those iPhone photos
- **click**: Because argparse is apparently too mainstream
- **rich**: For those fancy terminal UIs that make you feel like a hacker
- **structlog**: Structured logging because plain print statements are for peasants
- **scipy/numpy**: The mathematical backbone of our hubris
- **opencv-python**: For advanced image preprocessing (installed but currently unused)

## Exit Codes

- `0`: Everything worked (shocking!)
- `1`: Something went wrong (see logs for details)
- `130`: User got impatient and hit Ctrl+C

## Development

### Running Tests

The project includes a comprehensive test suite:

```bash
# Run all tests
uv run pytest

# Run tests with verbose output
uv run pytest -v

# Run specific test file
uv run pytest tests/test_classifier.py
```

### Continuous Integration

GitHub Actions automatically runs the test suite on every push and pull request to the `main` branch. The workflow:

- Sets up Python 3.13
- Installs dependencies using `uv`
- Runs the full test suite

### Code Quality

This project uses [Trunk](https://trunk.io) for linting and formatting:

```bash
# Check all files for linting issues
trunk check -a

# Check specific files or directories
trunk check src/

# Auto-format all files
trunk fmt -a

# Auto-format specific files or directories
trunk fmt src/
```

## Contributing

Found a bug? Congratulations, you're a beta tester! Issues and PRs welcome, though the I may judge your screenshot organization habits.

## License

[MIT](LICENSE)
