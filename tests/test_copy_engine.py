"""Tests pour core/copy_engine.py — copie atomique et sauvegarde incrémentale."""

import os
from pathlib import Path

import pytest

from core.copy_engine import _atomic_copy, run_backup


def _make(path: Path, content: bytes = b"data") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


# ── _atomic_copy ──────────────────────────────────────────────────────────────

def test_atomic_copy_creates_file(tmp_path):
    src = _make(tmp_path / "src" / "file.txt", b"hello")
    dst = tmp_path / "dst" / "file.txt"
    _atomic_copy(src, dst)
    assert dst.exists()
    assert dst.read_bytes() == b"hello"


def test_atomic_copy_creates_parent_dirs(tmp_path):
    src = _make(tmp_path / "src" / "file.txt", b"data")
    dst = tmp_path / "dst" / "deep" / "nested" / "file.txt"
    _atomic_copy(src, dst)
    assert dst.exists()


def test_atomic_copy_no_tmp_residue(tmp_path):
    src = _make(tmp_path / "src" / "file.txt", b"hello")
    dst = tmp_path / "dst" / "file.txt"
    _atomic_copy(src, dst)
    tmp_files = list((tmp_path / "dst").glob("*.smd_tmp"))
    assert tmp_files == []


def test_atomic_copy_raises_on_missing_src(tmp_path):
    with pytest.raises(Exception):
        _atomic_copy(tmp_path / "nonexistent.txt", tmp_path / "dst.txt")


# ── run_backup ────────────────────────────────────────────────────────────────

def test_run_backup_copies_new_files(tmp_path):
    src = tmp_path / "src"
    tgt = tmp_path / "tgt"
    _make(src / "a.txt", b"aaa")
    _make(src / "sub" / "b.txt", b"bbb")
    report = run_backup(src, tgt)
    assert len(report.files_copied) == 2
    assert len(report.errors) == 0
    assert (tgt / "a.txt").exists()
    assert (tgt / "sub" / "b.txt").exists()


def test_run_backup_unchanged_not_recopied(tmp_path):
    src = tmp_path / "src"
    tgt = tmp_path / "tgt"
    _make(src / "file.txt", b"unchanged content")
    report1 = run_backup(src, tgt)
    assert len(report1.files_copied) == 1
    report2 = run_backup(src, tgt)
    assert len(report2.files_copied) == 0
    assert report2.files_unchanged == 1


def test_run_backup_copies_modified_file(tmp_path):
    src = tmp_path / "src"
    tgt = tmp_path / "tgt"
    _make(src / "file.txt", b"version 1")
    run_backup(src, tgt)
    _make(src / "file.txt", b"version 2 -- longer")
    report = run_backup(src, tgt)
    assert len(report.files_copied) == 1
    assert (tgt / "file.txt").read_bytes() == b"version 2 -- longer"


def test_run_backup_respects_extension_filter(tmp_path):
    src = tmp_path / "src"
    tgt = tmp_path / "tgt"
    _make(src / "keep.txt", b"keep")
    _make(src / "ignore.tmp", b"ignore")
    report = run_backup(src, tgt, excluded_extensions=[".tmp"])
    assert len(report.files_copied) == 1
    assert (tgt / "keep.txt").exists()
    assert not (tgt / "ignore.tmp").exists()


def test_run_backup_respects_folder_filter(tmp_path):
    src = tmp_path / "src"
    tgt = tmp_path / "tgt"
    _make(src / "main.py", b"code")
    _make(src / "__pycache__" / "main.pyc", b"bytecode")
    report = run_backup(src, tgt, excluded_folders=["__pycache__"])
    assert len(report.files_copied) == 1
    assert (tgt / "main.py").exists()
    assert not (tgt / "__pycache__").exists()


def test_run_backup_cancellation(tmp_path):
    src = tmp_path / "src"
    tgt = tmp_path / "tgt"
    for i in range(10):
        _make(src / f"file_{i:02d}.txt", b"x" * 1000)
    calls = [0]
    def cancel_check():
        calls[0] += 1
        return calls[0] >= 2
    report = run_backup(src, tgt, cancel_check=cancel_check)
    assert report.cancelled
    assert len(report.files_copied) < 10


def test_run_backup_progress_callback(tmp_path):
    src = tmp_path / "src"
    tgt = tmp_path / "tgt"
    for i in range(3):
        _make(src / f"f{i}.txt", b"x")
    calls = []
    run_backup(src, tgt, progress_callback=lambda done, total, name: calls.append((done, total)))
    assert len(calls) == 3
    assert calls[-1][0] == calls[-1][1] == 3


def test_run_backup_report_duration(tmp_path):
    src = tmp_path / "src"
    tgt = tmp_path / "tgt"
    _make(src / "file.txt", b"data")
    report = run_backup(src, tgt)
    assert report.duration_seconds >= 0


def test_run_backup_empty_source(tmp_path):
    src = tmp_path / "src"
    tgt = tmp_path / "tgt"
    src.mkdir()
    report = run_backup(src, tgt)
    assert len(report.files_copied) == 0
    assert report.files_unchanged == 0
    assert not report.cancelled
