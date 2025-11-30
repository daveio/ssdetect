import shutil
import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests."""
    temp_dir = tempfile.mkdtemp()
    yield Path(temp_dir)
    shutil.rmtree(temp_dir)


@pytest.fixture
def sample_image(temp_dir):
    """Create a dummy image file."""
    image_path = temp_dir / "test_image.png"
    # Create a simple file, doesn't need to be a real image for file op tests
    image_path.write_bytes(b"fake image content")
    return image_path
