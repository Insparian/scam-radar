"""Exercise the KV backup protocol without sending network requests."""

import hashlib
import json
from io import BytesIO
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import unquote

import pytest
from scripts import upload_kv_backup as kv


class Response(BytesIO):
    status = 200


class LocalKV:
    def __init__(self):
        self.values = {}
        self.writes = 0

    def open(self, request, timeout):
        assert timeout == 30
        key = unquote(request.full_url.rsplit("/values/", 1)[1])
        if request.get_method() == "GET":
            if key not in self.values:
                raise HTTPError(request.full_url, 404, "missing", {}, None)
            return Response(self.values[key])
        assert request.get_method() == "PUT"
        self.writes += 1
        self.values[key] = request.data
        return Response(b'{"success":true}')


class DelayedVisibilityKV(LocalKV):
    def __init__(self, hidden_reads):
        super().__init__()
        self.hidden_reads = hidden_reads
        self.delayed_key = None

    def open(self, request, timeout):
        key = unquote(request.full_url.rsplit("/values/", 1)[1])
        if request.get_method() == "GET" and key == self.delayed_key and self.hidden_reads > 0:
            self.hidden_reads -= 1
            raise HTTPError(request.full_url, 404, "cached-miss", {}, None)
        response = super().open(request, timeout)
        if request.get_method() == "PUT" and self.delayed_key is None:
            self.delayed_key = key
        return response


def backup_fixture(root: Path, scope="synthetic_local_only") -> Path:
    folder = root / "work" / "kv-test"
    folder.mkdir(parents=True)
    object_id = "a" * 32
    data = b"age-encryption.org/v1\n" + b"synthetic-ciphertext-only" * 4
    (folder / f"{object_id}.age").write_bytes(data)
    manifest = {
        "schema": "scam-radar-encrypted-backup-v1",
        "object_id": object_id,
        "ciphertext_name": f"{object_id}.age",
        "ciphertext_bytes": len(data),
        "ciphertext_sha256": hashlib.sha256(data).hexdigest(),
        "scope": scope,
        "created_at": "2026-10-07T00:00:00+00:00",
        "encryption": "age-v1.3.2",
        "format": "pg_dump-custom",
    }
    path = folder / f"{object_id}.json"
    path.write_text(json.dumps(manifest))
    return path


def store(opener):
    return kv.KVBackupStore(
        mode="local",
        endpoint="http://127.0.0.1:8765",
        account_id="b" * 32,
        namespace_id="c" * 32,
        token="synthetic-token",
        opener=opener,
    )


def test_chunked_backup_verified_and_idempotent(tmp_path, monkeypatch):
    monkeypatch.setattr(kv, "ROOT", tmp_path)
    monkeypatch.setattr(kv, "CHUNK_BYTES", 32)
    manifest = backup_fixture(tmp_path)
    fake = LocalKV()
    client = store(fake)
    result = client.upload(manifest)
    assert result["object_id"] == "a" * 32
    envelope = json.loads(fake.values[f"scam-radar-backup/{'a' * 32}/manifest.json"])
    assert len(envelope["chunks"]) > 1
    reconstructed = b"".join(fake.values[item["key"]] for item in envelope["chunks"])
    assert reconstructed == manifest.with_suffix(".age").read_bytes()
    writes = fake.writes
    client.upload(manifest)
    assert fake.writes == writes
    restored = tmp_path / "work" / "recovered.age"
    assert client.download("a" * 32, restored) == restored
    assert restored.read_bytes() == manifest.with_suffix(".age").read_bytes()


def test_tampered_ciphertext_rejected_before_write(tmp_path, monkeypatch):
    monkeypatch.setattr(kv, "ROOT", tmp_path)
    manifest = backup_fixture(tmp_path)
    manifest.with_suffix(".age").write_bytes(b"age-encryption.org/v1\nchanged")
    fake = LocalKV()
    with pytest.raises(ValueError, match=r"size_or_hash|hash_mismatch"):
        store(fake).upload(manifest)
    assert fake.writes == 0


def test_existing_key_conflict_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(kv, "ROOT", tmp_path)
    manifest = backup_fixture(tmp_path)
    fake = LocalKV()
    fake.values[f"scam-radar-backup/{'a' * 32}/chunk-0000"] = b"tampered"
    with pytest.raises(RuntimeError, match="immutable_key_conflict"):
        store(fake).upload(manifest)
    assert fake.writes == 0


def test_cached_missing_key_waits_for_readback_without_rewriting(tmp_path, monkeypatch):
    monkeypatch.setattr(kv, "ROOT", tmp_path)
    waits = []
    monkeypatch.setattr(kv.time, "sleep", waits.append)
    manifest = backup_fixture(tmp_path)
    fake = DelayedVisibilityKV(hidden_reads=7)

    store(fake).upload(manifest)

    assert waits == list(kv.READBACK_RETRY_DELAYS)
    assert fake.writes == 2  # one chunk and the final manifest


def test_unverified_write_never_publishes_manifest(tmp_path, monkeypatch):
    monkeypatch.setattr(kv, "ROOT", tmp_path)
    monkeypatch.setattr(kv.time, "sleep", lambda _seconds: None)
    manifest = backup_fixture(tmp_path)
    fake = DelayedVisibilityKV(hidden_reads=8)

    with pytest.raises(RuntimeError, match="kv_write_unverified"):
        store(fake).upload(manifest)

    assert fake.writes == 1
    assert f"scam-radar-backup/{'a' * 32}/manifest.json" not in fake.values


def test_corrupt_remote_chunk_rejected_on_download(tmp_path, monkeypatch):
    monkeypatch.setattr(kv, "ROOT", tmp_path)
    monkeypatch.setattr(kv, "CHUNK_BYTES", 32)
    manifest = backup_fixture(tmp_path)
    fake = LocalKV()
    client = store(fake)
    client.upload(manifest)
    fake.values[f"scam-radar-backup/{'a' * 32}/chunk-0000"] = b"tampered"
    restored = tmp_path / "work" / "corrupt.age"
    with pytest.raises(RuntimeError, match="chunk_hash_mismatch"):
        client.download("a" * 32, restored)
    assert not restored.exists()


def test_live_mode_rejects_non_dedicated_account():
    with pytest.raises(ValueError, match="cloudflare_account_mismatch"):
        kv.KVBackupStore(
            mode="live",
            endpoint="https://api.cloudflare.com/client/v4",
            account_id="d" * 32,
            namespace_id="c" * 32,
            token="synthetic-token",
        )
    reviewed_id = json.loads((kv.ROOT / "config/cloudflare-account.json").read_text())[
        "dedicated_account_id"
    ]
    client = kv.KVBackupStore(
        mode="live",
        endpoint="https://api.cloudflare.com/client/v4",
        account_id=reviewed_id,
        namespace_id="c" * 32,
        token="synthetic-token",
        opener=LocalKV(),
    )
    assert client.account_id == reviewed_id
