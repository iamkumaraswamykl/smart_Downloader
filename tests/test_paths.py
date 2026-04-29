from pathlib import Path

from smart_organizer.organizer import _unique_path


def test_unique_path_returns_original_when_available(tmp_path):
    target = tmp_path / "file.txt"
    assert _unique_path(target) == target


def test_unique_path_adds_counter_when_needed(tmp_path):
    target = tmp_path / "file.txt"
    target.write_text("first", encoding="utf-8")
    assert _unique_path(target) == tmp_path / "file (1).txt"

