import json
import multiprocessing
import re
import socket
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path

import requests

OUTCOMES = ("pass", "fail", "not supported", "service down")
MATRIX = Path(__file__).resolve().parent.parent / "results" / "matrix.jsonl"
LIMIT = 120


@dataclass(frozen=True)
class Row:
    client: str
    service: str
    behaviour: str
    outcome: str
    note: str | None = None

    def __post_init__(self) -> None:
        if self.outcome not in OUTCOMES:
            raise ValueError(f"outcome must be one of {OUTCOMES}, got {self.outcome!r}")


def record(row: Row, path: Path = MATRIX) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as f:
        f.write(json.dumps({k: v for k, v in asdict(row).items() if v is not None}) + "\n")


def down(e: BaseException) -> str | None:
    for x in (e, e.__context__):
        if isinstance(x, requests.HTTPError):
            if x.response is not None and x.response.status_code >= 500:
                return f"HTTP {x.response.status_code} {x.response.url}"
            if x.response is None and (m := re.match(r"Error (5\d\d)", str(x))):
                return f"HTTP {m[1]}"
        elif isinstance(x, requests.ConnectionError) and not isinstance(x, requests.Timeout):
            url = f" {x.request.url}" if x.request is not None else ""
            return f"{type(x).__name__}{url}"
        elif isinstance(x, (ConnectionError, socket.gaierror)):
            return type(x).__name__
    return None


def guarded(
    check: Callable[[str, str], str | tuple[str, str | None]], client: str, service: str
) -> str | tuple[str, str | None]:
    try:
        return check(client, service)
    except Exception as e:
        if (note := down(e)) is None:
            raise
        return "service down", note


def run_cell(
    client: str,
    service: str,
    behaviour: str,
    check: Callable[[str, str], str | tuple[str, str | None]],
    limit: float = LIMIT,
) -> Row:
    with multiprocessing.Pool(1) as pool:
        try:
            result = pool.apply_async(guarded, (check, client, service)).get(limit)
        except multiprocessing.TimeoutError:
            return Row(client, service, behaviour, "fail", f"timeout after {limit} s")
    if isinstance(result, str):
        return Row(client, service, behaviour, result)
    return Row(client, service, behaviour, *result)
