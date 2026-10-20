import json
import multiprocessing
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path

OUTCOMES = ("pass", "fail", "not supported")
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


def run_cell(
    client: str, service: str, behaviour: str, check: Callable[[str, str], str], limit: float = LIMIT
) -> Row:
    with multiprocessing.Pool(1) as pool:
        try:
            outcome = pool.apply_async(check, (client, service)).get(limit)
        except multiprocessing.TimeoutError:
            return Row(client, service, behaviour, "fail", f"timeout after {limit} s")
    return Row(client, service, behaviour, outcome)
