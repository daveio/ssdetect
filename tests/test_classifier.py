from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from ssdetect.classifier import (
    ImageClassifier,
    classify_with_horizontal,
    classify_with_ocr,
)


@pytest.fixture
def mock_logger():
    return MagicMock()


@pytest.fixture
def classifier(mock_logger):
    return ImageClassifier(logger=mock_logger, script_mode=True)


def test_classify_with_horizontal_screenshot():
    """Test horizontal classification with a screenshot-like image."""
    # Create an image with horizontal lines
    img = np.zeros((100, 100))
    img[20:22, :] = 255  # Horizontal line
    img[50:52, :] = 255  # Horizontal line

    # We need to mock check_img since it's from an external library
    with patch("ssdetect.classifier.check_img", return_value=[0, 1]):
        assert classify_with_horizontal(img) is True


def test_classify_with_horizontal_not_screenshot():
    """Test horizontal classification with a non-screenshot image."""
    img = np.random.randint(0, 255, (100, 100))

    with patch("ssdetect.classifier.check_img", return_value=[]):
        assert classify_with_horizontal(img) is False


@patch("ssdetect.classifier.ocr_reader")
def test_classify_with_ocr_screenshot(mock_reader, temp_dir):
    """Test OCR classification for a screenshot."""
    # Mock OCR results: (bbox, text, confidence)
    mock_reader.readtext.return_value = [
        ([[0, 0], [10, 0], [10, 10], [0, 10]], "System Settings", 0.9),
        ([[0, 20], [10, 20], [10, 30], [0, 30]], "Display", 0.95),
    ]

    # Create a dummy image file so Image.open works
    image_path = temp_dir / "test.png"
    from PIL import Image

    Image.new("RGB", (100, 100)).save(image_path)

    # Initialize globals for the worker
    import ssdetect.classifier as clf

    clf.ocr_reader = mock_reader
    clf.ocr_chars_threshold = 10
    clf.ocr_quality_threshold = 0.6
    clf.extra_heuristics = False
    clf.ocr_resize_factor = 1.0

    is_screenshot, error = classify_with_ocr(image_path)
    assert error is None
    assert is_screenshot is True


@patch("ssdetect.classifier.ocr_reader")
def test_classify_with_ocr_not_screenshot(mock_reader, temp_dir):
    """Test OCR classification for a non-screenshot."""
    mock_reader.readtext.return_value = [
        ([[0, 0], [10, 0], [10, 10], [0, 10]], "cat", 0.5),
    ]

    image_path = temp_dir / "test.png"
    from PIL import Image

    Image.new("RGB", (100, 100)).save(image_path)

    import ssdetect.classifier as clf

    clf.ocr_reader = mock_reader
    clf.ocr_chars_threshold = 10
    clf.ocr_quality_threshold = 0.6
    clf.ocr_resize_factor = 1.0

    is_screenshot, error = classify_with_ocr(image_path)
    assert error is None
    assert is_screenshot is False
