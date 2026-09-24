from __future__ import annotations

import gzip
import json
from pathlib import Path

import pytest

from ollie_langfuse_import.records import InputError, load_dump, select_records
from ollie_langfuse_import.redact import Redactor
from ollie_langfuse_import.upload import OllieImportClient, make_chunks

FIXTURES = Path(__file__).parent / "fixtures"


def test_load_json_and_select_newest_unique_deterministically():
    records = load_dump(FIXTURES / "langfuse-export.json")
    selected = select_records(records, 1000)
    assert [record["id"] for record in selected] == ["trace-new", "trace-old"]
    assert selected[1]["timestamp"] == "2026-09-02T10:00:00Z"


def test_load_ndjson_and_reject_bad_line(tmp_path):
    assert len(load_dump(FIXTURES / "langfuse-export.ndjson")) == 2
    bad = tmp_path / "bad.ndjson"
    bad.write_text('{"ok": true}\nnot-json\n')
    with pytest.raises(InputError, match="line 2"):
        load_dump(bad)


def test_limit_is_capped_at_1000():
    with pytest.raises(ValueError, match="between 1 and 1000"):
        select_records([{"id": "one"}], 1001)


def test_redaction_is_recursive_schema_blind_and_stable():
    redactor = Redactor(b"same import")
    value = {
        "user_id": "customer-123",
        "sessionId": "session-alice",
        "message": "alice@example.com then alice@example.com; 123-45-6789",
        "metadata": {
            "api_key": "ordinary-looking-value",
            "nested": ["Bearer abcdefghijklmnop", "10.20.30.40"],
        },
    }
    result = redactor.value(value)
    first, second = result["message"].split(" then ")[0], result["message"].split(
        " then "
    )[1].split(";")[0]
    assert first == second
    assert "alice@example.com" not in json.dumps(result)
    assert "123-45-6789" not in json.dumps(result)
    assert "ordinary-looking-value" not in json.dumps(result)
    assert "abcdefghijklmnop" not in json.dumps(result)
    assert "10.20.30.40" not in json.dumps(result)
    assert "customer-123" not in json.dumps(result)
    assert "session-alice" not in json.dumps(result)


def test_security_limits_auto_truncate():
    redactor = Redactor(b"import")
    huge = redactor.value("x" * 100_001)
    assert len(huge) == 100_000
    assert redactor.truncated_strings == 1

    selected = select_records(
        [{"id": "one", "observations": [{"id": str(i)} for i in range(5_001)]}],
        1,
    )
    assert len(selected) == 1
    assert len(selected[0]["observations"]) == 5_000
    assert selected[0]["_ollie_trim"]["observations_truncated"] == 1


def test_chunks_are_deterministic_gzip_ndjson():
    records = [{"id": "a"}, {"id": "b"}]
    first = make_chunks(records, 1)
    second = make_chunks(records, 1)
    assert [chunk.checksum for chunk in first] == [
        chunk.checksum for chunk in second
    ]
    assert json.loads(gzip.decompress(first[0].body)) == {"id": "a"}


class _Response:
    def __init__(self, value):
        self.body = json.dumps(value).encode()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def read(self):
        return self.body


def test_upload_resumes_chunks_and_sends_checksums(monkeypatch):
    requests = []

    def urlopen(request, timeout):
        requests.append(request)
        if request.full_url.endswith("/v1/imports/langfuse"):
            return _Response({"id": "import-1"})
        if request.method == "GET":
            return _Response({"uploaded_chunks": [0]})
        if request.method == "PUT":
            return _Response({"accepted": True})
        return _Response({"id": "import-1", "status": "complete"})

    monkeypatch.setattr("urllib.request.urlopen", urlopen)
    chunks = make_chunks([{"id": "a"}, {"id": "b"}], 1)
    result = OllieImportClient("ollie-secret", "https://ollie.test").upload(chunks, 2)

    put_requests = [request for request in requests if request.method == "PUT"]
    assert len(put_requests) == 1
    assert put_requests[0].full_url.endswith("/chunks/1")
    headers = {key.lower(): value for key, value in put_requests[0].headers.items()}
    assert headers["content-encoding"] == "gzip"
    assert headers["x-checksum-sha256"] == chunks[1].checksum
    assert result["status"] == "complete"
    assert all(b"ollie-secret" not in (request.data or b"") for request in requests)
