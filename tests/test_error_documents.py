from pathlib import Path

import pytest
import requests
from astroquery.utils.tap.core import TapPlus
from pyvo.dal.exceptions import DALFormatError

from vo_conformance.checks.error_documents import (
    BEHAVIOUR,
    CLIENTS,
    QUERY,
    SERVICES,
    check,
    outcome,
    service_message,
)
from vo_conformance.runner import record, run_cell

FIXTURES = Path(__file__).resolve().parent / "fixtures"
VOTABLE = (FIXTURES / "error_votable.xml").read_bytes()
PLAIN = (FIXTURES / "error_plain.txt").read_bytes()
URL = "http://example.com/tap"


@pytest.fixture
def service(monkeypatch):
    monkeypatch.setitem(SERVICES, "TEST", URL)
    return "TEST"


class FakeResponse:
    reason = "OK"

    def __init__(self, status, body):
        self.status = status
        self.body = body

    def read(self):
        return self.body

    def getheaders(self):
        return []


class FakeConn:
    def __init__(self, status, body):
        self.response = FakeResponse(status, body)

    def execute_tappost(self, subcontext, data, verbose=False):
        assert subcontext == "sync"
        return self.response

    def check_launch_response_status(self, response, debug, expected, raise_exception=True):
        return response.status != expected

    def get_file_from_header(self, headers):
        return None

    def get_suitable_extension(self, headers):
        return ".vot"


def astroquery_outcome(status, body):
    tap = TapPlus(url=URL, connhandler=FakeConn(status, body))
    return outcome(lambda: tap.launch_job(QUERY), service_message(body))


@pytest.mark.parametrize("status", [200, 400])
def test_pyvo_passes_on_votable_error(requests_mock, service, status):
    requests_mock.post(f"{URL}/sync", status_code=status, content=VOTABLE)
    assert check("pyvo", service) == ("pass", None)


def test_pyvo_passes_on_plain_error(requests_mock, service):
    requests_mock.post(
        f"{URL}/sync", status_code=500, content=PLAIN, headers={"Content-Type": "text/plain"}
    )
    assert check("pyvo", service) == ("pass", None)


@pytest.mark.parametrize(("status", "body"), [(400, VOTABLE), (500, PLAIN)])
def test_astroquery_passes(status, body):
    assert astroquery_outcome(status, body) == ("pass", None)


def test_astroquery_fails_on_votable_error_at_200():
    result, note = astroquery_outcome(200, VOTABLE)
    assert result == "fail"
    assert note is not None and note.startswith("ValueError")


def test_service_message():
    assert service_message(VOTABLE) == "Table vo_conformance_no_such_table not found"
    assert service_message(PLAIN) == "Table vo_conformance_no_such_table not found"


@pytest.mark.parametrize("body", [(FIXTURES / "result.xml").read_bytes(), b"", b"  \n"])
def test_service_message_refuses_no_message(body):
    with pytest.raises(ValueError):
        service_message(body)


def test_no_error_raised_fails():
    assert outcome(lambda: None, "x") == ("fail", "no error raised")


@pytest.mark.parametrize(
    ("text", "note"),
    [("first\nsecond", "RuntimeError: first"), ("y" * 300, ("RuntimeError: " + "y" * 300)[:200])],
)
def test_note_is_type_and_first_line_capped(text, note):
    def run():
        raise RuntimeError(text)

    assert outcome(run, "x") == ("fail", note)


def test_pyvo_network_error_propagates(requests_mock, service):
    requests_mock.post(f"{URL}/sync", [{"content": VOTABLE}, {"exc": requests.ConnectionError}])
    with pytest.raises(DALFormatError):
        check("pyvo", service)


def test_astroquery_network_error_propagates():
    def run():
        raise ConnectionRefusedError

    with pytest.raises(ConnectionRefusedError):
        outcome(run, "x")


@pytest.mark.live
@pytest.mark.parametrize("service", SERVICES)
@pytest.mark.parametrize("client", CLIENTS)
def test_live(client, service):
    record(run_cell(client, service, BEHAVIOUR, check))
