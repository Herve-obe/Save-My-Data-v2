"""Tests pour core/comparator.py — détection NEW / MODIFIED / UNCHANGED / ORPHAN."""

import os
from pathlib import Path

import pytest

from core.comparator import compare, FileStatus


def _make(path: Path, content: bytes = b"data") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


def _status(results, name: str) -> FileStatus:
    for r in results:
        if r.target_path.name == name:
            return r.status
    raise KeyError(f"{name!r} not found in results")


def test_new_file(tmp_path):
    src = tmp_path / "src"
    tgt = tmp_path / "tgt"
    _make(src / "new.txt", b"new content")
    results = compare(src, tgt)
    assert len(results) == 1
    assert results[0].status == FileStatus.NEW


def test_orphan_file(tmp_path):
    src = tmp_path / "src"
    tgt = tmp_path / "tgt"
    src.mkdir()
    _make(tgt / "orphan.txt", b"orphan")
    results = compare(src, tgt)
    orphans = [r for r in results if r.status == FileStatus.ORPHAN]
    assert len(orphans) == 1


def test_modified_by_size(tmp_path):
    src = tmp_path / "src"
    tgt = tmp_path / "tgt"
    _make(src / "file.txt", b"longer content here")
    _make(tgt / "file.txt", b"short")
    results = compare(src, tgt)
    assert results[0].status == FileStatus.MODIFIED


def test_unchanged_file(tmp_path):
    src = tmp_path / "src"
    tgt = tmp_path / "tgt"
    content = b"same content"
    _make(src / "file.txt", content)
    _make(tgt / "file.txt", content)
    src_mtime = (src / "file.txt").stat().st_mtime
    os.utime(tgt / "file.txt", (src_mtime, src_mtime))
    results = compare(src, tgt)
    assert results[0].status == FileStatus.UNCHANGED


def test_modified_by_hash(tmp_path):
    """Même taille, mtime différent de > 2s, contenu différent → MODIFIED."""
    src = tmp_path / "src"
    tgt = tmp_path / "tgt"
    _make(src / "file.txt", b"content_A")
    _make(tgt / "file.txt", b"content_B")
    src_mtime = (src / "file.txt").stat().st_mtime
    os.utime(tgt / "file.txt", (src_mtime, src_mtime - 10))
    results = compare(src, tgt)
    assert results[0].status == FileStatus.MODIFIED


def test_unchanged_by_hash(tmp_path):
    """Même taille, mtime différent de > 2s, contenu identique → UNCHANGED."""
    src = tmp_path / "src"
    tgt = tmp_path / "tgt"
    content = b"identical data"
    _make(src / "file.txt", content)
    _make(tgt / "file.txt", content)
    src_mtime = (src / "file.txt").stat().st_mtime
    os.utime(tgt / "file.txt", (src_mtime, src_mtime - 10))
    results = compare(src, tgt)
    assert results[0].status == FileStatus.UNCHANGED


def test_multiple_statuses(tmp_path):
    src = tmp_path / "src"
    tgt = tmp_path / "tgt"
    content = b"same"
    _make(src / "unchanged.txt", content)
    _make(src / "modified.txt", b"new version extended")
    _make(src / "new_file.txt", b"brand new")
    _make(tgt / "unchanged.txt", content)
    _make(tgt / "modified.txt", b"old version")
    _make(tgt / "orphan.txt", b"orphan")
    src_mtime = (src / "unchanged.txt").stat().st_mtime
    os.utime(tgt / "unchanged.txt", (src_mtime, src_mtime))
    results = compare(src, tgt)
    by_name = {r.target_path.name: r.status for r in results}
    assert by_name["unchanged.txt"] == FileStatus.UNCHANGED
    assert by_name["modified.txt"] == FileStatus.MODIFIED
    assert by_name["new_file.txt"] == FileStatus.NEW
    assert by_name["orphan.txt"] == FileStatus.ORPHAN


def test_filters_applied(tmp_path):
    src = tmp_path / "src"
    tgt = tmp_path / "tgt"
    _make(src / "keep.txt", b"keep")
    _make(src / "ignore.tmp", b"ignore")
    tgt.mkdir()
    results = compare(src, tgt, excluded_extensions=[".tmp"])
    assert len(results) == 1
    assert results[0].status == FileStatus.NEW
    assert results[0].target_path.name == "keep.txt"


def test_smd_tmp_not_reported_as_orphan(tmp_path):
    src = tmp_path / "src"
    tgt = tmp_path / "tgt"
    src.mkdir()
    _make(tgt / "residue.smd_tmp", b"crash residue")
    results = compare(src, tgt)
    orphans = [r for r in results if r.status == FileStatus.ORPHAN]
    assert len(orphans) == 0
