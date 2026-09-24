from __future__ import annotations

import json

from ollie_langfuse_import import cli
from ollie_langfuse_import.langfuse_api import fetch_traces


class _Response:
    def __init__(self, value):
        self.body = json.dumps(value).encode()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def read(self, *_args):
        return self.body


def test_from_langfuse_uses_basic_auth_and_paginates(monkeypatch):
    requests = []

    def urlopen(request, timeout):
        requests.append(request)
        if "/observations?" in request.full_url:
            return _Response({"data": [], "meta": {"totalPages": 1}})
        if "page=1" in request.full_url:
            return _Response({"data": [{"id": "one"}], "meta": {"totalPages": 2}})
        return _Response({"data": [{"id": "two"}], "meta": {"totalPages": 2}})

    monkeypatch.setattr("urllib.request.urlopen", urlopen)
    records = fetch_traces("public", "private", "https://langfuse.test", 2)
    assert [item["trace_id"] for item in records] == ["one", "two"]
    trace_requests = [request for request in requests if "/traces?" in request.full_url]
    assert len(trace_requests) == 2
    assert trace_requests[0].get_header("Authorization").startswith("Basic ")
    assert all("private" not in request.full_url for request in requests)
    assert all("observations" in record for record in records)


def test_cli_redacts_before_upload(monkeypatch, tmp_path):
    snapshot = tmp_path / "snapshot.json"
    snapshot.write_text(
        json.dumps(
            [
                {
                    "id": "trace-1",
                    "timestamp": "2026-09-01T00:00:00Z",
                    "input": "alice@example.com",
                }
            ]
        )
    )
    captured = {}

    class FakeClient:
        def __init__(self, api_key, base_url):
            assert api_key == "ollie-key"
            assert base_url == "https://ollie.test"

        def upload(self, chunks, record_count):
            captured["body"] = chunks[0].body
            return {"id": "import-1", "status": "complete"}

    monkeypatch.setenv("OLLIE_API_KEY", "ollie-key")
    monkeypatch.setenv("OLLIE_BASE_URL", "https://ollie.test")
    monkeypatch.setattr(cli, "OllieImportClient", FakeClient)
    result = cli.run([str(snapshot)])
    assert result["status"] == "complete"

    import gzip

    uploaded = gzip.decompress(captured["body"])
    assert b"alice@example.com" not in uploaded
    assert b"OLLIE_REDACTED_EMAIL" in uploaded


def test_main_does_not_echo_credentials(monkeypatch, capsys):
    monkeypatch.setenv("OLLIE_API_KEY", "do-not-print")
    monkeypatch.delenv("OLLIE_BASE_URL", raising=False)
    assert cli.main(["missing.json"]) == 2
    output = capsys.readouterr()
    assert "do-not-print" not in output.out + output.err
