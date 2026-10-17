import json
from dataclasses import asdict, dataclass
from pathlib import Path

OUTCOMES = ("pass", "fail", "not supported")
MATRIX = Path(__file__).resolve().parent.parent / "results" / "matrix.jsonl"


@dataclass(frozen=True)
class Row:
    client: str
    service: str
    behaviour: str
    outcome: str

    def __post_init__(self) -> None:
        if self.outcome not in OUTCOMES:
            raise ValueError(f"outcome must be one of {OUTCOMES}, got {self.outcome!r}")


def record(row: Row, path: Path = MATRIX) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as f:
        f.write(json.dumps(asdict(row)) + "\n")
