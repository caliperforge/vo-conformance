# vo-conformance
Which astronomy data clients handle which IVOA standard behaviours correctly, tested against Rubin's and other archives' public services

## Running

- `uv run pytest` runs the offline tests.
- `uv run pytest -m live` runs the live checks and appends to `results/matrix.jsonl`.

Each row is a JSON object with `client`, `service`, `behaviour`, `outcome` and an optional `note`, where `outcome` is one of `pass`, `fail` or `not supported`. A cell that runs past 120 s is `fail` with `note` `timeout after 120 s`.

## Async jobs (UWS 1.1)

Behaviour `async_jobs`: pyvo (`AsyncTAPJob`) and astroquery (`TapPlus`) each submit an async TAP query to CADC and IRSA, wait for the job to end and fetch its result.

- `pass`: the client reaches COMPLETED and reads the result VOTable.
- `fail`: the client raises its own error, or stops waiting in a phase other than COMPLETED, or reports a job as running that the service still holds in PENDING. Network errors are raised, not recorded.

PENDING, HELD and SUSPENDED are covered by offline replays only.
