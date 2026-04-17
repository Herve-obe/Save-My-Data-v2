"""Tests pour core/scanner.py — parcours et filtrage des fichiers source."""

from pathlib import Path

import pytest

from core.scanner import scan_disk


def _make(path: Path, content: bytes = b"data") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


def test_scan_yields_files(tmp_path):
    _make(tmp_path / "a.txt", b"hello")
    _make(tmp_path / "sub" / "b.txt", b"world")
    paths = {e.relative_path for e in scan_disk(tmp_path)}
    assert Path("a.txt") in paths
    assert Path("sub") / "b.txt" in paths


def test_file_entry_fields(tmp_path):
    content = b"hello world"
    f = _make(tmp_path / "test.txt", content)
    entries = list(scan_disk(tmp_path))
    assert len(entries) == 1
    e = entries[0]
    assert e.size == len(content)
    assert e.relative_path == Path("test.txt")
    assert e.path == f


def test_excludes_by_extension(tmp_path):
    _make(tmp_path / "keep.txt", b"keep")
    _make(tmp_path / "ignore.tmp", b"temp")
    names = {e.relative_path.name for e in scan_disk(tmp_path, excluded_extensions=[".tmp"])}
    assert "keep.txt" in names
    assert "ignore.tmp" not in names


def test_excludes_extension_without_leading_dot(tmp_path):
    """L'utilisateur peut saisir 'log' ou '.log' — les deux doivent fonctionner."""
    _make(tmp_path / "app.log", b"log data")
    _make(tmp_path / "data.csv", b"csv")
    names = {e.relative_path.name for e in scan_disk(tmp_path, excluded_extensions=["log"])}
    assert "app.log" not in names
    assert "data.csv" in names


def test_excludes_by_full_filename(tmp_path):
    """Noms de fichiers complets comme 'Thumbs.db' ou '.DS_Store'."""
    _make(tmp_path / "Thumbs.db", b"thumb")
    _make(tmp_path / "photo.jpg", b"jpg")
    names = {e.relative_path.name for e in scan_disk(tmp_path, excluded_extensions=["Thumbs.db"])}
    assert "Thumbs.db" not in names
    assert "photo.jpg" in names


def test_excludes_by_folder(tmp_path):
    _make(tmp_path / "ok" / "file.txt", b"ok")
    _make(tmp_path / "node_modules" / "module.js", b"js")
    entries = list(scan_disk(tmp_path, excluded_folders=["node_modules"]))
    str_paths = {str(e.relative_path) for e in entries}
    assert not any("node_modules" in p for p in str_paths)
    assert any("ok" in p for p in str_paths)


def test_excludes_nested_folder(tmp_path):
    _make(tmp_path / "src" / "__pycache__" / "mod.pyc", b"pyc")
    _make(tmp_path / "src" / "main.py", b"py")
    entries = list(scan_disk(tmp_path, excluded_folders=["__pycache__"]))
    str_paths = {str(e.relative_path) for e in entries}
    assert not any("__pycache__" in p for p in str_paths)
    assert any("main.py" in p for p in str_paths)


def test_max_size_filter(tmp_path):
    _make(tmp_path / "small.txt", b"x" * 100)
    _make(tmp_path / "large.txt", b"x" * 10_000)
    names = {e.relative_path.name for e in scan_disk(tmp_path, max_size_bytes=500)}
    assert "small.txt" in names
    assert "large.txt" not in names


def test_max_size_zero_means_no_limit(tmp_path):
    _make(tmp_path / "big.bin", b"x" * 50_000)
    entries = list(scan_disk(tmp_path, max_size_bytes=0))
    assert len(entries) == 1


def test_empty_directory(tmp_path):
    entries = list(scan_disk(tmp_path))
    assert entries == []


def test_nonexistent_root(tmp_path):
    entries = list(scan_disk(tmp_path / "does_not_exist"))
    assert entries == []
