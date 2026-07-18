# shipment-tracking-poller

A recurring job that polls a carrier tracking API for shipments that
haven't reached a final state yet, updates their status in a Postgres
warehouse, and — just as importantly — knows when to *stop* polling a
shipment: once it's terminal, once it's gone stale, or on demand when an
operator forces a re-check.

This is a from-scratch demonstration build: synthetic tracking history and
a mocked carrier API. It exists to show the *pattern* — a polling job that
doesn't waste API calls chasing shipments that will never change — not to
poll a real carrier.

## The problem this demonstrates

The naive version of this job polls every shipment, every time, forever.
That wastes API quota on delivered packages that will never update again,
and it eventually gets throttled by the carrier for it. The real skill
isn't calling a tracking API — it's the policy layer that decides *which*
shipments still deserve a call: not the ones already delivered, not the
ones that have gone quiet long enough to be considered lost or stuck, but
still able to force a check on any specific shipment when someone actually
needs one.

## Architecture

```mermaid
flowchart LR
    DB[("Postgres warehouse<br/>tracked_shipments")]
    Policy["policy.should_poll()<br/>terminal? stale? forced?"]
    Carrier["mock carrier tracking API"]
    Update["db.update_shipment_status()"]
    Sched["GitHub Actions<br/>cron + workflow_dispatch force_ids"]

    DB --> Policy
    Policy -- "skip" --> DB
    Policy -- "poll" --> Carrier
    Carrier -- "per-shipment failure: keep going" --> Update
    Update --> DB
    Sched -- "FORCE_REPOLL_IDS" --> Policy
```

## Key design decisions

**Three states, one decision function.** `poller/policy.py`'s
`should_poll()` is the entire policy in one place: skip a shipment if it's
terminal (`delivered`, `returned_to_sender`, `cancelled`) or if it's gone
14+ days without a status change (`STALE_AFTER_DAYS`) — unless the caller
explicitly forces it. Every other module just executes what this function
decides; none of them re-implement the skip logic themselves.

**Staleness is a real state, not a bug.** Packages do get lost. A shipment
that hasn't moved in two weeks isn't worth an API call every single run
forever — it's flagged stale and left alone, exactly like a terminal
shipment, unless someone forces a recheck.

**Re-poll override is a first-class input, not a manual DB edit.**
`python poll_shipments.py --force-id SHP-000042` (or `FORCE_REPOLL_IDS` in
the environment, which is how the scheduled workflow's `force_ids`
`workflow_dispatch` input reaches it) bypasses the terminal/staleness skip
for specific shipments — for when a customer says "the tracking looks
wrong" and someone needs a fresh check right now.

**One bad lookup doesn't stop the run.** `poller/carrier_client.py` raises
`TrackingUnavailableError` for a failed lookup; `poller/pipeline.py` counts
it as `failed` and moves on to the next shipment, rather than treating a
single carrier hiccup as a reason to abort a batch of sixty.

**A tighter cadence than the other pipelines in this portfolio.**
`poll.yml` runs every 30 minutes, not daily — active shipments change
status throughout the day, and that's exactly the kind of job this policy
layer is built to run cheaply and often without wasting calls on shipments
that can't change anymore.

## Repository layout

```
poller/                 policy, carrier client, db queries, pipeline orchestration
mock_carrier/           Flask stand-in for the carrier tracking API
scripts/                scenario seeder (DB rows + matching tracking fixture), secrets check
tests/                  pytest suite (mirrors poller/, mock_carrier/, scripts/)
.github/workflows/      CI (pytest + Postgres service) and the scheduled poll job
poll_shipments.py       CLI entrypoint
docker-compose.yml      local Postgres for manual runs
```

## Running it locally

Requires Python 3.12+ and (optionally) Docker for a local Postgres.

```bash
git clone <this-repo>
cd shipment-tracking-poller
python -m venv .venv && source .venv/bin/activate   # .venv\Scripts\activate on Windows
pip install -r requirements-dev.txt
cp .env.example .env

# 1. Bring up a local warehouse and seed a tracking scenario (this also
#    writes mock_carrier/fixtures/tracking.json, since the seeded DB rows
#    and the mock API's data have to stay consistent with each other)
docker compose up -d postgres
python scripts/seed_warehouse.py --seed 42 --count 60

# 2. Start the mock carrier tracking API
python -m mock_carrier.server &

# 3. Run a polling pass
python poll_shipments.py
```

Forcing a re-poll of a specific shipment regardless of its terminal/stale
state:

```bash
python poll_shipments.py --force-id SHP-000001
```

Running the test suite (Postgres-backed tests skip gracefully if no
database is reachable — everything else runs regardless):

```bash
pytest
```

### Example output

```
$ python scripts/seed_warehouse.py --seed 42 --count 60
seeded 60 shipments into postgresql://postgres:postgres@localhost:5432/warehouse
wrote tracking fixture to mock_carrier/fixtures/tracking.json

$ python -m mock_carrier.server &

$ python poll_shipments.py
INFO polled 23, updated 15 (5 newly terminal), skipped 37, failed 0

$ python poll_shipments.py
INFO polled 18, updated 0 (0 newly terminal), skipped 42, failed 0
```

The second run skips more (37 → 42) because the shipments that just went
terminal on the first pass are correctly never polled again.

## Testing strategy

Test-first throughout: every module under `poller/`, `mock_carrier/`, and
`scripts/` has a matching `tests/test_*.py` written against the interface
before the implementation existed. `poller/policy.py` is pure and unit
tested directly; the carrier client is tested with `requests_mock`; the
Postgres-backed db and seeder tests run for real in CI against a service
container, and skip locally if no database is reachable.
