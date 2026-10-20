import json
import subprocess
from pathlib import Path

import pytest

from vo_conformance.runner import OUTCOMES, Row, record

ROOT = Path(__file__).resolve().parent.parent


def test_record_round_trip(tmp_path):
    path = tmp_path / "matrix.jsonl"
    record(Row("pyvo", "CADC", "async_jobs", "pass"), path)
    assert [json.loads(line) for line in path.read_text().splitlines()] == [
        {"client": "pyvo", "service": "CADC", "behaviour": "async_jobs", "outcome": "pass"}
    ]


def test_record_appends(tmp_path):
    path = tmp_path / "matrix.jsonl"
    record(Row("pyvo", "CADC", "async_jobs", "pass"), path)
    record(Row("astroquery", "CADC", "async_jobs", "fail"), path)
    clients = [json.loads(line)["client"] for line in path.read_text().splitlines()]
    assert clients == ["pyvo", "astroquery"]


def test_rejects_unknown_outcome(tmp_path):
    path = tmp_path / "matrix.jsonl"
    with pytest.raises(ValueError):
        record(Row("pyvo", "CADC", "async_jobs", "error"), path)
    assert not path.exists()


@pytest.mark.parametrize("outcome", OUTCOMES)
def test_accepts_outcome(outcome):
    assert Row("pyvo", "CADC", "async_jobs", outcome).outcome == outcome


def test_matrix_is_gitignored():
    args = ["git", "check-ignore", "-q", "results/matrix.jsonl"]
    assert subprocess.run(args, check=False, cwd=ROOT).returncode == 0


def test_dated_results_are_tracked():
    args = ["git", "check-ignore", "-q", "results/2026-10-19.jsonl"]
    assert subprocess.run(args, check=False, cwd=ROOT).returncode == 1
