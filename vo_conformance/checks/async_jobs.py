import requests
from astroquery.utils.tap.core import TapPlus
from astroquery.utils.tap.model.job import Job
from pyvo.dal.exceptions import DALAccessError
from pyvo.dal.tap import AsyncTAPJob

BEHAVIOUR = "async_jobs"
CLIENTS = ("pyvo", "astroquery")
SERVICES = {
    "CADC": (
        "https://ws.cadc-ccda.hia-iha.nrc-cnrc.gc.ca/argus",
        "select top 3 observationID from caom2.Observation where collection='IRIS'",
    ),
    "IRSA": ("https://irsa.ipac.caltech.edu/TAP", "SELECT TOP 5 ra,dec FROM cosmos2015"),
    "ARI": (
        "https://gaia.ari.uni-heidelberg.de/tap",
        "SELECT TOP 5 source_id, ra, dec, phot_g_mean_mag FROM gaiadr3.gaia_source WHERE phot_g_mean_mag < 6 ORDER BY phot_g_mean_mag",
    ),
}


def pyvo_outcome(job: AsyncTAPJob) -> str:
    try:
        job.run().wait()
        job.raise_if_error()
        job.fetch_result()
    except DALAccessError as e:
        if isinstance(e.__context__, requests.RequestException):
            raise
        return "fail"
    return "pass"


def astroquery_outcome(job: Job) -> str:
    if job.get_phase() != "PENDING" and job.get_phase(update=True) == "PENDING":
        return "fail"
    _, phase = job.wait_for_job_end()
    if phase != "COMPLETED":
        return "fail"
    job.get_results()
    return "pass"


def check(client: str, service: str) -> str:
    url, query = SERVICES[service]
    if client == "pyvo":
        return pyvo_outcome(AsyncTAPJob.create(url, query))
    return astroquery_outcome(TapPlus(url=url).launch_job_async(query, background=True))
