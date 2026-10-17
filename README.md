# vo-conformance
Which astronomy data clients handle which IVOA standard behaviours correctly, tested against Rubin's and other archives' public services

## Running

- `uv run pytest` runs the offline tests.
- `uv run pytest -m live` runs the live checks and appends to `results/matrix.jsonl`.

Each row is a JSON object with `client`, `service`, `behaviour` and `outcome`, where `outcome` is one of `pass`, `fail` or `not supported`.
