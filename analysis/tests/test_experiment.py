"""Experiment harness: job keys, cached runs, the time budget and the PNG writer (T1.4)."""

import hashlib
import json
import struct
import zlib
from pathlib import Path

import numpy as np
import pytest
from painterly_analysis import experiment
from painterly_analysis.experiment import Job, job_key, load, run_jobs
from painterly_analysis.io import write_png
from painterly_analysis.oracle import oracle_binary


@pytest.fixture
def cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Send every render of the test to a temporary cache."""
    root = tmp_path / "cache"
    monkeypatch.setenv("PAINTERLY_CACHE", str(root))
    return root


def test_job_key_is_stable_and_order_independent() -> None:
    a = Job.make("a", 3, size=64, passes=2, chain="image")
    b = Job.make("a", 3, chain="image", passes=2, size=64)
    assert a == b
    assert job_key(a) == job_key(b) == job_key(a)
    assert len(job_key(a)) == 16
    # The key is the sha256 of the canonical JSON that job_key documents. The test recomputes it
    # from the binary's bytes; "1" is the meta.json contract version.
    binary_sha256 = hashlib.sha256(oracle_binary().read_bytes()).hexdigest()
    canonical = json.dumps(
        {
            "options": {"chain": "image", "passes": 2, "size": 64},
            "seed": 3,
            "oracle_version": "1",
            "oracle_sha256": binary_sha256,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    assert job_key(a) == hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]
    # A different seed is a different render.
    assert job_key(Job.make("a", 4, size=64, passes=2, chain="image")) != job_key(a)


def test_run_jobs_renders_a_64_square_job_once(
    cache: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[int] = []
    real_run_many = experiment.run_many

    def counting_run_many(jobs, workers=None):
        calls.append(len(jobs))
        return real_run_many(jobs, workers=workers)

    monkeypatch.setattr(experiment, "run_many", counting_run_many)
    job = Job.make("t64", 0, size=64, passes=1)
    first = run_jobs([job])
    assert (first.completed, first.remaining) == (1, 0)
    assert calls == [1]
    second = run_jobs([job])
    assert (second.completed, second.remaining) == (1, 0)
    assert calls == [1]  # the second call renders nothing
    assert load(job).sum.shape == (64, 64, 3)


def test_budget_zero_starts_nothing(cache: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def must_not_run(jobs, workers=None):
        raise AssertionError("no job may start when budget_seconds=0")

    monkeypatch.setattr(experiment, "run_many", must_not_run)
    jobs = [Job.make("t32", seed, size=32, passes=1) for seed in (0, 1)]
    status = run_jobs(jobs, budget_seconds=0)
    assert (status.completed, status.remaining) == (0, 2)


def _png_chunks(data: bytes) -> list[tuple[bytes, bytes]]:
    """Split a PNG file into (type, data) chunks, checking each CRC-32."""
    assert data.startswith(b"\x89PNG\r\n\x1a\n")
    chunks = []
    pos = 8
    while pos < len(data):
        (length,) = struct.unpack(">I", data[pos : pos + 4])
        kind = data[pos + 4 : pos + 8]
        body = data[pos + 8 : pos + 8 + length]
        (crc,) = struct.unpack(">I", data[pos + 8 + length : pos + 12 + length])
        assert zlib.crc32(kind + body) == crc
        chunks.append((kind, body))
        pos += 12 + length
    assert pos == len(data)
    return chunks


def test_write_png_round_trips_through_zlib(tmp_path: Path) -> None:
    img = np.random.default_rng(0).integers(0, 256, size=(5, 7, 3), dtype=np.uint8)
    path = tmp_path / "round_trip.png"
    write_png(path, img)
    chunks = _png_chunks(path.read_bytes())
    assert [kind for kind, _ in chunks] == [b"IHDR", b"IDAT", b"IEND"]
    ihdr = dict(chunks)[b"IHDR"]
    # width, height, bit depth 8, colour type 2 (RGB), compression 0, filter 0, interlace 0.
    assert struct.unpack(">IIBBBBB", ihdr) == (7, 5, 8, 2, 0, 0, 0)
    raw = zlib.decompress(dict(chunks)[b"IDAT"])
    scanlines = np.frombuffer(raw, dtype=np.uint8).reshape(5, 1 + 3 * 7)
    assert np.all(scanlines[:, 0] == 0)
    assert np.array_equal(scanlines[:, 1:].reshape(5, 7, 3), img)
