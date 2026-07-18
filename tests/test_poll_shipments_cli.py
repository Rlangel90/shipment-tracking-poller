import poll_shipments
from poller.pipeline import PollResult


class _FakeConn:
    def close(self):
        pass


def _patch_common(monkeypatch, captured, run_impl=None):
    monkeypatch.setattr(poll_shipments.psycopg, "connect", lambda database_url: _FakeConn())

    def default_run(conn, carrier_api_url, force_ids=None):
        captured["carrier_api_url"] = carrier_api_url
        captured["force_ids"] = force_ids
        return PollResult(polled=1, updated=1, newly_terminal=0, skipped=2, failed=0)

    monkeypatch.setattr(poll_shipments, "run", run_impl or default_run)


def test_main_runs_with_no_force_ids_by_default(monkeypatch):
    captured = {}
    _patch_common(monkeypatch, captured)
    monkeypatch.delenv("FORCE_REPOLL_IDS", raising=False)

    exit_code = poll_shipments.main([])

    assert exit_code == 0
    assert captured["force_ids"] == []


def test_main_collects_repeated_force_id_flags(monkeypatch):
    captured = {}
    _patch_common(monkeypatch, captured)
    monkeypatch.delenv("FORCE_REPOLL_IDS", raising=False)

    poll_shipments.main(["--force-id", "SHP-000001", "--force-id", "SHP-000002"])

    assert captured["force_ids"] == ["SHP-000001", "SHP-000002"]


def test_main_reads_force_ids_from_env_var(monkeypatch):
    captured = {}
    _patch_common(monkeypatch, captured)
    monkeypatch.setenv("FORCE_REPOLL_IDS", "SHP-000003,SHP-000004")

    poll_shipments.main([])

    assert captured["force_ids"] == ["SHP-000003", "SHP-000004"]


def test_main_combines_cli_and_env_force_ids(monkeypatch):
    captured = {}
    _patch_common(monkeypatch, captured)
    monkeypatch.setenv("FORCE_REPOLL_IDS", "SHP-000003")

    poll_shipments.main(["--force-id", "SHP-000001"])

    assert captured["force_ids"] == ["SHP-000001", "SHP-000003"]


def test_main_uses_carrier_api_url_from_env(monkeypatch):
    captured = {}
    _patch_common(monkeypatch, captured)
    monkeypatch.delenv("FORCE_REPOLL_IDS", raising=False)
    monkeypatch.setenv("CARRIER_API_URL", "http://carrier.example.test")

    poll_shipments.main([])

    assert captured["carrier_api_url"] == "http://carrier.example.test"
