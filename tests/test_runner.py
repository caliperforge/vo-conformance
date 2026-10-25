import json
import socket
import subprocess
import time
from pathlib import Path

import pytest
import requests

from vo_conformance.checks import async_jobs
from vo_conformance.runner import OUTCOMES, Row, guarded, record, run_cell

ROOT = Path(__file__).resolve().parent.parent
URL = "http://example.com/tap"


def http_error(status):
    response = requests.Response()
    response.status_code = status
    response.url = f"{URL}/async"
    return requests.HTTPError(response=response)


def raising(error):
    def check(client, service):
        raise error

    return check


def passes(client, service):
    return "pass"


def fails_with_note(client, service):
    return "fail", "x"


def hangs(client, service):
    time.sleep(10)
    return "pass"


def raises(client, service):
    raise RuntimeError("network down")


def unavailable(client, service):
    raise http_error(503)


def test_record_round_trip(tmp_path):
    path = tmp_path / "matrix.jsonl"
    record(Row("pyvo", "CADC", "async_jobs", "pass"), path)
    assert [json.loads(line) for line in path.read_text().splitlines()] == [
        {"client": "pyvo", "service": "CADC", "behaviour": "async_jobs", "outcome": "pass"}
    ]


def test_record_round_trip_with_note(tmp_path):
    path = tmp_path / "matrix.jsonl"
    record(Row("pyvo", "CADC", "async_jobs", "fail", "timeout after 120 s"), path)
    assert [json.loads(line) for line in path.read_text().splitlines()] == [
        {
            "client": "pyvo",
            "service": "CADC",
            "behaviour": "async_jobs",
            "outcome": "fail",
            "note": "timeout after 120 s",
        }
    ]


def test_run_cell_returns_outcome():
    row = run_cell("pyvo", "CADC", "async_jobs", passes)
    assert row == Row("pyvo", "CADC", "async_jobs", "pass")
    assert row.note is None


def test_run_cell_returns_outcome_and_note():
    assert run_cell("pyvo", "CADC", "async_jobs", fails_with_note) == Row(
        "pyvo", "CADC", "async_jobs", "fail", "x"
    )


def test_run_cell_times_out():
    start = time.monotonic()
    row = run_cell("pyvo", "CADC", "async_jobs", hangs, limit=0.5)
    assert time.monotonic() - start < 5
    assert row == Row("pyvo", "CADC", "async_jobs", "fail", "timeout after 0.5 s")


def test_run_cell_raises_check_error():
    with pytest.raises(RuntimeError):
        run_cell("pyvo", "CADC", "async_jobs", raises)


def test_run_cell_records_service_down():
    assert run_cell("pyvo", "CADC", "async_jobs", unavailable) == Row(
        "pyvo", "CADC", "async_jobs", "service down", f"HTTP 503 {URL}/async"
    )


def test_pyvo_service_down(requests_mock, monkeypatch):
    monkeypatch.setitem(async_jobs.SERVICES, "TEST", (URL, "SELECT 1"))
    requests_mock.post(f"{URL}/async", status_code=503, text="temporarily unavailable: null")
    assert guarded(async_jobs.check, "pyvo", "TEST") == ("service down", f"HTTP 503 {URL}/async")
    requests_mock.post(f"{URL}/async", exc=requests.ConnectionError)
    assert guarded(async_jobs.check, "pyvo", "TEST") == ("service down", "ConnectionError")


@pytest.mark.parametrize(
    ("error", "note"),
    [
        (requests.HTTPError("Error 503:\ntemporarily unavailable: null"), "HTTP 503"),
        (ConnectionRefusedError(), "ConnectionRefusedError"),
        (socket.gaierror(), "gaierror"),
    ],
)
def test_astroquery_service_down(error, note):
    assert guarded(raising(error), "astroquery", "CADC") == ("service down", note)


@pytest.mark.parametrize(
    "error",
    [
        requests.Timeout(),
        requests.ConnectTimeout(),
        TimeoutError(),
        http_error(404),
        requests.HTTPError("Error 400: "),
        RuntimeError(),
    ],
)
def test_guarded_raises(error):
    with pytest.raises(type(error)):
        guarded(raising(error), "pyvo", "CADC")


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
