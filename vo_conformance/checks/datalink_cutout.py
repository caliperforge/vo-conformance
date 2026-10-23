import urllib.error
from collections.abc import Callable
from io import BytesIO

import requests
from astropy import units as u
from astropy.coordinates import SkyCoord
from astropy.io import fits
from astroquery.cadc import CadcClass
from astroquery.utils.commons import FileContainer
from pyvo.dal.adhoc import DatalinkRecord
from pyvo.dal.exceptions import DALAccessError
from pyvo.dal.tap import TAPService

from vo_conformance.checks import async_jobs

BEHAVIOUR = "datalink_cutout"
CLIENTS = async_jobs.CLIENTS
SERVICES = {"CADC": async_jobs.SERVICES["CADC"][0]}
RADIUS = 0.1
QUERY = "SELECT TOP 1 obs_publisher_did, s_ra, s_dec, access_url, access_format FROM ivoa.ObsCore WHERE obs_collection = 'IRIS' AND dataproduct_type = 'image'"


def pyvo_cutout(service: TAPService) -> bytes | None:
    row = service.run_sync(QUERY).getrecord(0)
    link = next(row.getdatalink().bysemantics("#cutout"), None)
    if not isinstance(link, DatalinkRecord):
        return None
    return link.processed(circle=(row["s_ra"], row["s_dec"], RADIUS)).read()


def astroquery_cutout(cadc: CadcClass) -> bytes | None:
    table = cadc.exec_sync(QUERY)
    table.rename_column("obs_publisher_did", "publisherID")
    centre = SkyCoord(table["s_ra"][0], table["s_dec"][0], unit="deg")
    urls = cadc.get_image_list(table, centre, RADIUS * u.deg)
    if not urls:
        return None
    return FileContainer(urls[0], encoding="binary").get_string()


def note(e: Exception) -> str:
    first_line = str(e).partition("\n")[0]
    return f"{type(e).__name__}: {first_line}"[:200]


def size_outcome(data: bytes) -> tuple[str, str | None]:
    try:
        hdus = fits.open(BytesIO(data))
    except OSError as e:
        return "fail", note(e)
    images = (hdu for hdu in hdus if isinstance(hdu, (fits.PrimaryHDU, fits.ImageHDU)))
    image = next((hdu for hdu in images if len(hdu.shape) >= 2), None)
    if image is None:
        return "fail", "no image HDU"
    for i in (1, 2):
        cdelt = image.header.get(f"CDELT{i}")
        if not isinstance(cdelt, (int, float)):
            return "fail", f"no CDELT{i}"
        cdelt = abs(cdelt)
        extent = image.shape[-i] * cdelt
        if abs(extent - 2 * RADIUS) > 2 * cdelt:
            return "fail", f"axis {i} spans {extent:g} deg, asked {2 * RADIUS:g}"
    return "pass", None


def outcome(cutout: Callable[[], bytes | None]) -> tuple[str, str | None]:
    try:
        data = cutout()
    except (DALAccessError, urllib.error.HTTPError) as e:
        if isinstance(e.__context__, requests.RequestException):
            raise
        return "fail", note(e)
    if data is None:
        return "fail", "no #cutout link"
    return size_outcome(data)


def check(client: str, service: str) -> tuple[str, str | None]:
    url = SERVICES[service]
    if client == "pyvo":
        return outcome(lambda: pyvo_cutout(TAPService(url)))
    return outcome(lambda: astroquery_cutout(CadcClass(url=url)))
