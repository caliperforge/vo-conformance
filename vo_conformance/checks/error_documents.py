import xml.etree.ElementTree as ET
from collections.abc import Callable

import requests
from astroquery.utils.tap.core import TapPlus
from pyvo.dal.exceptions import DALAccessError
from pyvo.dal.tap import TAPService

from vo_conformance.checks import async_jobs

BEHAVIOUR = "error_documents"
CLIENTS = async_jobs.CLIENTS
SERVICES = {name: url for name, (url, _) in async_jobs.SERVICES.items()}
QUERY = "SELECT TOP 1 * FROM vo_conformance_no_such_table"


def service_message(body: bytes) -> str:
    try:
        root = ET.fromstring(body)
    except ET.ParseError:
        message = body.decode().strip()
    else:
        info = root.find(".//{*}INFO[@name='QUERY_STATUS'][@value='ERROR']")
        if info is None:
            raise ValueError("no QUERY_STATUS ERROR INFO in the error document")
        message = (info.text or "").strip()
    if not message:
        raise ValueError("the service gave no error message")
    return message


def outcome(run: Callable[[], object], message: str) -> tuple[str, str | None]:
    try:
        run()
    except Exception as e:
        if isinstance(e, DALAccessError) and isinstance(e.__context__, requests.RequestException):
            raise
        if isinstance(e, OSError) and not isinstance(e, requests.HTTPError):
            raise
        if " ".join(message.split()) in " ".join(str(e).split()):
            return "pass", None
        first_line = str(e).partition("\n")[0]
        return "fail", f"{type(e).__name__}: {first_line}"[:200]
    return "fail", "no error raised"


def check(client: str, service: str) -> tuple[str, str | None]:
    url = SERVICES[service]
    data = {"REQUEST": "doQuery", "LANG": "ADQL", "QUERY": QUERY}
    message = service_message(requests.post(f"{url}/sync", data=data).content)
    if client == "pyvo":
        return outcome(lambda: TAPService(url).run_sync(QUERY), message)
    return outcome(lambda: TapPlus(url=url).launch_job(QUERY), message)
