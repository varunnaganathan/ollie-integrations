"""Resumable gzip-NDJSON upload client for the Ollie import API."""

from __future__ import annotations

import gzip
import hashlib
import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Iterable

from .records import canonical_json


class UploadError(RuntimeError):
    pass


@dataclass(frozen=True)
class Chunk:
    index: int
    body: bytes
    checksum: str
    records: int


def make_chunks(records: Iterable[dict[str, Any]], chunk_records: int) -> list[Chunk]:
    if chunk_records < 1:
        raise ValueError("chunk_records must be positive")
    chunks: list[Chunk] = []
    batch: list[bytes] = []
    for record in records:
        batch.append(canonical_json(record) + b"\n")
        if len(batch) == chunk_records:
            chunks.append(_chunk(len(chunks), batch))
            batch = []
    if batch:
        chunks.append(_chunk(len(chunks), batch))
    return chunks


def _chunk(index: int, lines: list[bytes]) -> Chunk:
    body = gzip.compress(b"".join(lines), compresslevel=6, mtime=0)
    return Chunk(
        index=index,
        body=body,
        checksum=hashlib.sha256(body).hexdigest(),
        records=len(lines),
    )


# Chunk PUTs run mandatory server-side Presidio redaction; cold hosts + large
# batches routinely exceed a 60s client read. urllib.urlopen only accepts a
# single numeric timeout (unlike requests' (connect, read) tuple).
_DEFAULT_TIMEOUT = 300.0
_DEFAULT_CHUNK_RETRIES = 3


def _timeout() -> float:
    raw = os.environ.get("OLLIE_IMPORT_READ_TIMEOUT") or os.environ.get(
        "OLLIE_IMPORT_TIMEOUT", _DEFAULT_TIMEOUT
    )
    return max(30.0, float(raw))


class OllieImportClient:
    def __init__(self, api_key: str, base_url: str):
        if not api_key:
            raise UploadError("OLLIE_API_KEY is required")
        if not base_url.lower().startswith(("https://", "http://")):
            raise UploadError("OLLIE_BASE_URL must be an http(s) URL")
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")

    def _request(
        self,
        method: str,
        path: str,
        *,
        body: bytes | None = None,
        headers: dict[str, str] | None = None,
        retries: int = 0,
    ) -> dict[str, Any]:
        request_headers = {
            "X-API-Key": self.api_key,
            "Accept": "application/json",
            "User-Agent": "ollie-langfuse-import/0.1",
        }
        request_headers.update(headers or {})
        request = urllib.request.Request(
            self.base_url + path,
            data=body,
            method=method,
            headers=request_headers,
        )
        attempts = max(1, retries + 1)
        last_exc: BaseException | None = None
        data = b""
        for attempt in range(attempts):
            try:
                with urllib.request.urlopen(request, timeout=_timeout()) as response:
                    data = response.read()
                break
            except urllib.error.HTTPError as exc:
                raise UploadError(f"Ollie import API returned HTTP {exc.code}") from exc
            except TimeoutError as exc:
                last_exc = exc
                if attempt + 1 >= attempts:
                    raise UploadError(
                        "Ollie import API timed out while reading the response "
                        f"(method={method} path={path}). Try smaller --chunk-records "
                        "or raise OLLIE_IMPORT_TIMEOUT."
                    ) from exc
                time.sleep(min(8.0, 1.5 * (attempt + 1)))
            except urllib.error.URLError as exc:
                reason = getattr(exc, "reason", None)
                if isinstance(reason, TimeoutError) or (
                    reason is not None and "timed out" in str(reason).lower()
                ):
                    last_exc = exc
                    if attempt + 1 >= attempts:
                        raise UploadError(
                            "Ollie import API timed out "
                            f"(method={method} path={path}). Try smaller "
                            "--chunk-records or raise OLLIE_IMPORT_TIMEOUT."
                        ) from exc
                    time.sleep(min(8.0, 1.5 * (attempt + 1)))
                    continue
                raise UploadError("could not reach the Ollie import API") from exc
        else:
            raise UploadError("could not reach the Ollie import API") from last_exc
        if not data:
            return {}
        try:
            payload = json.loads(data)
        except json.JSONDecodeError as exc:
            raise UploadError("Ollie import API returned invalid JSON") from exc
        if not isinstance(payload, dict):
            raise UploadError("Ollie import API returned an unexpected response")
        return payload

    def _json(
        self, method: str, path: str, value: dict[str, Any], idempotency_key: str
    ) -> dict[str, Any]:
        return self._request(
            method,
            path,
            body=canonical_json(value),
            headers={
                "Content-Type": "application/json",
                "Idempotency-Key": idempotency_key,
            },
            retries=2,
        )

    @staticmethod
    def _uploaded_indices(status: dict[str, Any]) -> set[int]:
        raw = status.get("uploaded_chunks", status.get("uploadedChunks", []))
        uploaded = {item for item in raw if isinstance(item, int)}
        chunks = status.get("chunks", [])
        if isinstance(chunks, list):
            for item in chunks:
                if (
                    isinstance(item, dict)
                    and item.get("status") in {"accepted", "uploaded", "complete"}
                    and isinstance(item.get("index"), int)
                ):
                    uploaded.add(item["index"])
        return uploaded

    def upload(self, chunks: list[Chunk], record_count: int) -> dict[str, Any]:
        if not chunks:
            raise UploadError("no accepted records to upload")
        content_checksum = hashlib.sha256(
            "".join(chunk.checksum for chunk in chunks).encode()
        ).hexdigest()
        import_key = f"langfuse-{content_checksum}"
        create_payload: dict[str, Any] = {
            "record_count": record_count,
            "chunk_count": len(chunks),
            "content_sha256": content_checksum,
            "content_type": "application/x-ndjson",
            "content_encoding": "gzip",
        }
        if os.environ.get("OLLIE_AGENT_ID"):
            create_payload["agent_id"] = os.environ["OLLIE_AGENT_ID"]
        created = self._json(
            "POST",
            "/v1/imports/langfuse",
            create_payload,
            import_key,
        )
        import_id = created.get("id", created.get("import_id"))
        if not isinstance(import_id, str) or not import_id:
            raise UploadError("Ollie import API did not return an import id")

        status = self._request("GET", f"/v1/imports/{import_id}")
        uploaded = self._uploaded_indices(status)
        chunk_retries = int(
            os.environ.get("OLLIE_IMPORT_CHUNK_RETRIES", _DEFAULT_CHUNK_RETRIES)
        )
        for chunk in chunks:
            if chunk.index in uploaded:
                continue
            print(
                f"uploading chunk {chunk.index + 1}/{len(chunks)} "
                f"({chunk.records} records, {len(chunk.body)} bytes gzip)…",
                flush=True,
            )
            self._request(
                "PUT",
                f"/v1/imports/{import_id}/chunks/{chunk.index}",
                body=chunk.body,
                headers={
                    "Content-Type": "application/x-ndjson",
                    "Content-Encoding": "gzip",
                    "Content-Length": str(len(chunk.body)),
                    "X-Checksum-SHA256": chunk.checksum,
                    "Idempotency-Key": f"{import_key}-chunk-{chunk.index}",
                },
                retries=max(0, chunk_retries),
            )
        return self._json(
            "POST",
            f"/v1/imports/{import_id}/complete",
            {
                "content_sha256": content_checksum,
                "chunks": [
                    {
                        "index": chunk.index,
                        "sha256": chunk.checksum,
                        "records": chunk.records,
                    }
                    for chunk in chunks
                ],
            },
            f"{import_key}-complete",
        )

    def poll(self, import_id: str, interval_seconds: float = 2.0) -> dict[str, Any]:
        """Poll durable work progress until a complete, partial, or failed result exists."""
        terminal = {"completed", "partial", "failed", "cancelled"}
        last_progress = -1
        while True:
            status = self._request("GET", f"/v1/imports/{import_id}")
            progress = int(status.get("progress") or 0)
            if progress != last_progress:
                print(
                    f"analysis {progress}% ({status.get('current_stage') or status.get('stage') or 'working'})",
                    flush=True,
                )
                last_progress = progress
            if str(status.get("status") or "").lower() in terminal:
                return status
            time.sleep(max(0.2, interval_seconds))
