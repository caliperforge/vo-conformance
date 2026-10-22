# vo-conformance
Which astronomy data clients handle which IVOA standard behaviours correctly, tested against Rubin's and other archives' public services

## Running

- `uv run pytest` runs the offline tests.
- `uv run pytest -m live` runs the live checks and appends to `results/matrix.jsonl`.

Each row is a JSON object with `client`, `service`, `behaviour`, `outcome` and an optional `note`, where `outcome` is one of `pass`, `fail` or `not supported`. A cell that runs past 120 s is `fail` with `note` `timeout after 120 s`.

## Daily results

`.github/workflows/daily.yml` runs the live checks at 11:00 UTC each day and commits the rows to `results/<YYYY-MM-DD>.jsonl`. One row is one client's outcome on one behaviour against one service on that date (UTC), with the fields above.

## Async jobs (UWS 1.1)

Behaviour `async_jobs`: pyvo (`AsyncTAPJob`) and astroquery (`TapPlus`) each submit an async TAP query to CADC, IRSA, ARI and MAST, wait for the job to end and fetch its result.

- `pass`: the client reaches COMPLETED and reads the result VOTable.
- `fail`: the client raises its own error, or stops waiting in a phase other than COMPLETED, or reports a job as running that the service still holds in PENDING. Network errors are raised, not recorded.

PENDING, HELD and SUSPENDED are covered by offline replays only.

## Error documents

Behaviour `error_documents`: a failed query is the most common thing users hit, and the service's own error message is what tells them why. pyvo (`TAPService.run_sync`) and astroquery (`TapPlus.launch_job`) each send CADC, IRSA, ARI and MAST a sync TAP query on a table that does not exist. The check first fetches the service's raw error response and takes its message: the text of the `QUERY_STATUS` `ERROR` INFO when the response is a VOTable, or the whole body otherwise.

- `pass`: the client raises an error whose text contains the service's message.
- `fail`: the client raises an error without that message, and `note` holds the error's type and first line; or the client raises no error. Network errors are raised, not recorded. A service that gives no message gets no row.

VOTable errors at HTTP 200 and 400 and plain-text errors at HTTP 500 are covered by offline replays only.
