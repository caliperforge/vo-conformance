from io import BytesIO
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import numpy as np
import pytest
import requests
from astropy.io import fits
from astroquery.cadc import CadcClass

from vo_conformance.checks.datalink_cutout import (
    BEHAVIOUR,
    CLIENTS,
    SERVICES,
    astroquery_cutout,
    check,
    outcome,
    size_outcome,
)
from vo_conformance.runner import record, run_cell

FIXTURES = Path(__file__).resolve().parent / "fixtures"
OBSCORE = (FIXTURES / "obscore.xml").read_bytes()
DATALINK = (FIXTURES / "datalink.xml").read_bytes()
URL = "http://example.com/tap"
DATALINK_URL = "http://example.com/datalink"
SODA_URL = "http://example.com/soda/sync"


def fits_bytes(hdu):
    out = BytesIO()
    hdu.writeto(out)
    return out.getvalue()


def image(n):
    hdu = fits.PrimaryHDU(np.zeros((n, n), dtype=np.float32))
    hdu.header["CDELT1"] = -0.025
    hdu.header["CDELT2"] = 0.025
    return fits_bytes(hdu)


CUTOUT = image(8)


@pytest.fixture(autouse=True)
def vocabulary(monkeypatch):
    monkeypatch.setattr("pyvo.utils.vocabularies.get_vocabulary", lambda name: {"terms": {}})


@pytest.fixture
def replay(requests_mock):
    requests_mock.post(f"{URL}/sync", content=OBSCORE)
    requests_mock.get(DATALINK_URL, content=DATALINK)
    return requests_mock


@pytest.fixture
def service(monkeypatch):
    monkeypatch.setitem(SERVICES, "TEST", URL)
    return "TEST"


@pytest.fixture
def downloads(monkeypatch):
    targets = []

    def get_readable_fileobj(target, **kwargs):
        targets.append(target)
        return BytesIO(CUTOUT)

    monkeypatch.setattr("astroquery.utils.commons.get_readable_fileobj", get_readable_fileobj)
    return targets


def astroquery_outcome():
    cadc = CadcClass(url=URL, auth_session=requests.Session())
    cadc._data_link_url = DATALINK_URL
    return outcome(lambda: astroquery_cutout(cadc))


def test_pyvo_passes(replay, service):
    replay.get(SODA_URL, content=CUTOUT)
    assert check("pyvo", service) == ("pass", None)
    assert parse_qs(urlsplit(replay.last_request.url).query)["CIRCLE"] == ["150.1 2.2 0.1"]


def test_astroquery_passes(replay, downloads):
    assert astroquery_outcome() == ("pass", None)
    (target,) = downloads
    assert urlsplit(target).path == "/soda/sync"
    shape, *circle = parse_qs(urlsplit(target).query)["POS"][0].split()
    assert shape == "CIRCLE"
    assert [float(v) for v in circle] == pytest.approx([150.1, 2.2, 0.1], abs=1e-4)


@pytest.mark.parametrize(
    ("data", "note"),
    [
        (image(500), "axis 1 spans 12.5 deg, asked 0.2"),
        (b"", "OSError"),
        (b"not a FITS file", "OSError"),
        (fits_bytes(fits.PrimaryHDU(np.zeros((8, 8)))), "no CDELT1"),
        (fits_bytes(fits.PrimaryHDU()), "no image HDU"),
    ],
)
def test_size_outcome_refuses(data, note):
    result, got = size_outcome(data)
    assert result == "fail"
    assert got is not None and got.startswith(note)


def test_no_cutout_link_fails(requests_mock, service, downloads):
    requests_mock.post(f"{URL}/sync", content=OBSCORE)
    requests_mock.get(DATALINK_URL, content=DATALINK.replace(b"#cutout", b"#preview"))
    assert check("pyvo", service) == ("fail", "no #cutout link")
    assert astroquery_outcome() == ("fail", "no #cutout link")
    assert downloads == []


def test_pyvo_soda_error_fails(replay, service):
    replay.get(SODA_URL, status_code=500)
    result, note = check("pyvo", service)
    assert result == "fail"
    assert note is not None and note.startswith("DALServiceError")


def test_pyvo_network_error_propagates(replay, service):
    replay.get(SODA_URL, exc=requests.ConnectionError)
    with pytest.raises(requests.ConnectionError):
        check("pyvo", service)


@pytest.mark.live
@pytest.mark.parametrize("service", SERVICES)
@pytest.mark.parametrize("client", CLIENTS)
def test_live(client, service):
    record(run_cell(client, service, BEHAVIOUR, check))
