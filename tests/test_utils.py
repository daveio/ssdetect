# trunk-ignore-all(bandit/B101)

from ssdetect.utils import copy_file, find_image_files, move_file


def test_find_image_files(temp_dir):
    """Test finding image files in a directory."""
    # Create some dummy files
    (temp_dir / "image1.jpg").touch()
    (temp_dir / "image2.png").touch()
    (temp_dir / "not_image.txt").touch()
    (temp_dir / "subdir").mkdir()
    (temp_dir / "subdir" / "image3.webp").touch()

    images = find_image_files(temp_dir)
    assert len(images) == 3
    filenames = [p.name for p in images]
    assert "image1.jpg" in filenames
    assert "image2.png" in filenames
    assert "image3.webp" in filenames
    assert "not_image.txt" not in filenames


def test_move_file(temp_dir):
    """Test moving a file."""
    src = temp_dir / "test.jpg"
    src.touch()
    dst_dir = temp_dir / "dest"

    moved_path = move_file(src, dst_dir)

    assert moved_path.exists()
    assert moved_path.parent == dst_dir
    assert not src.exists()


def test_move_file_conflict(temp_dir):
    """Test moving a file with name conflict."""
    src = temp_dir / "test.jpg"
    src.touch()
    dst_dir = temp_dir / "dest"
    dst_dir.mkdir()
    (dst_dir / "test.jpg").touch()

    moved_path = move_file(src, dst_dir)

    assert moved_path.name == "test_1.jpg"
    assert moved_path.exists()


def test_copy_file(temp_dir):
    """Test copying a file."""
    src = temp_dir / "test.jpg"
    src.touch()
    dst_dir = temp_dir / "dest"

    copied_path = copy_file(src, dst_dir)

    assert copied_path.exists()
    assert copied_path.parent == dst_dir
    assert src.exists()
