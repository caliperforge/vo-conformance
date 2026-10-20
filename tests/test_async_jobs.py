from pathlib import Path

import pytest
import requests
from astroquery.utils.tap.model.job import Job
from pyvo.dal.exceptions import DALServiceError
from pyvo.dal.tap import AsyncTAPJob

from vo_conformance.checks.async_jobs import (
    BEHAVIOUR,
    CLIENTS,
    SERVICES,
    astroquery_outcome,
    check,
    pyvo_outcome,
)
from vo_conformance.runner import record, run_cell

FIXTURES = Path(__file__).resolve().parent / "fixtures"
JOB = "http://example.com/tap/async/1"


@pytest.fixture
def no_sleep(monkeypatch):
    monkeypatch.setattr("pyvo.dal.tap.sleep", lambda _: None)
    monkeypatch.setattr("time.sleep", lambda _: None)


def pyvo_job(requests_mock, *phases):
    requests_mock.get(JOB, [{"content": (FIXTURES / f"{p}.xml").read_bytes()} for p in phases])
    requests_mock.post(f"{JOB}/phase", status_code=200)
    requests_mock.get(f"{JOB}/results/result", content=(FIXTURES / "result.xml").read_bytes())
    return AsyncTAPJob(JOB)


class FakeResponse:
    status = 200
    reason = "OK"

    def __init__(self, body):
        self.body = body

    def read(self):
        return self.body

    def getheaders(self):
        return []


class FakeConn:
    def __init__(self, phases):
        self.phases = list(phases)

    def execute_tapget(self, subcontext, verbose=False):
        if subcontext == "async/1/phase":
            return FakeResponse((self.phases.pop(0) if len(self.phases) > 1 else self.phases[0]).encode())
        assert subcontext == "async/1/results/result"
        return FakeResponse((FIXTURES / "result.xml").read_bytes())

    def execute_tappost(self, subcontext, data, verbose=False):
        assert (subcontext, data) == ("async/1/phase", "PHASE=RUN")
        return FakeResponse(b"")

    def check_launch_response_status(self, response, debug, expected):
        return response.status != expected


def astroquery_job(local, *phases):
    job = Job(True, connhandler=FakeConn(phases))
    job.jobid = "1"  # pyright: ignore[reportAttributeAccessIssue]  # astroquery's __init__ sets None
    job.set_phase(local)
    return job


def test_pyvo_passes_on_completed(requests_mock, no_sleep):
    assert pyvo_outcome(pyvo_job(requests_mock, "QUEUED", "QUEUED", "EXECUTING", "COMPLETED")) == "pass"


@pytest.mark.parametrize("phase", ["PENDING", "HELD", "SUSPENDED"])
def test_pyvo_fails_on_inactive_phase(requests_mock, no_sleep, phase):
    with pytest.raises(DALServiceError, match="Job is not active"):
        pyvo_job(requests_mock, "QUEUED", phase).run().wait()
    assert pyvo_outcome(pyvo_job(requests_mock, "QUEUED", phase)) == "fail"


def test_pyvo_network_error_propagates(requests_mock, no_sleep):
    job = pyvo_job(requests_mock, "QUEUED")
    requests_mock.post(f"{JOB}/phase", exc=requests.ConnectionError)
    with pytest.raises(DALServiceError):
        pyvo_outcome(job)


@pytest.mark.parametrize(
    ("local", "phases", "outcome"),
    [
        ("EXECUTING", ["EXECUTING", "EXECUTING", "COMPLETED"], "pass"),
        ("PENDING", ["PENDING", "COMPLETED"], "pass"),
        ("EXECUTING", ["HELD", "HELD", "COMPLETED"], "fail"),
        ("EXECUTING", ["SUSPENDED", "SUSPENDED", "COMPLETED"], "fail"),
    ],
)
def test_astroquery_outcome(no_sleep, local, phases, outcome):
    assert astroquery_outcome(astroquery_job(local, *phases)) == outcome


def test_astroquery_fails_when_service_left_job_pending(no_sleep):
    assert astroquery_outcome(astroquery_job("EXECUTING", "PENDING", "COMPLETED")) == "fail"


@pytest.mark.live
@pytest.mark.parametrize("service", SERVICES)
@pytest.mark.parametrize("client", CLIENTS)
def test_live(client, service):
    record(run_cell(client, service, BEHAVIOUR, check))
