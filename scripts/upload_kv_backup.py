"""Upload only age ciphertext and integrity metadata to a dedicated Workers KV namespace.

Cloudflare writes remain disabled until separate activation. Keys are immutable;
an ambiguous write response is resolved by reading the key, never by blind retry.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.cloudflare_account_guard import require_dedicated_account

BACKUP_CONFIRMATION = "BACKUP APPROVED CIPHERTEXT ONLY"
CHUNK_BYTES = 16 * 1024 * 1024
MAX_KV_VALUE_BYTES = 25 * 1024 * 1024
MAX_CIPHERTEXT_BYTES = 64 * 1024 * 1024


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *_args, **_kwargs):
        raise RuntimeError("kv_redirect_rejected")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class KVBackupStore:
    def __init__(
        self,
        *,
        mode: str,
        endpoint: str,
        account_id: str,
        namespace_id: str,
        token: str,
        opener=None,
    ) -> None:
        if mode not in ("local", "live"):
            raise ValueError("kv_mode_invalid")
        if not re.fullmatch(r"[0-9a-f]{32}", namespace_id):
            raise ValueError("kv_namespace_invalid")
        if not token or any(character.isspace() for character in token):
            raise ValueError("kv_token_required")
        parts = urlsplit(endpoint)
        if mode == "local":
            if (
                parts.scheme != "http"
                or parts.hostname != "127.0.0.1"
                or not parts.port
            ):
                raise ValueError("local_kv_endpoint_required")
        else:
            if not re.fullmatch(r"[0-9a-f]{32}", account_id):
                raise ValueError("kv_account_invalid")
            require_dedicated_account(account_id)
            if endpoint != "https://api.cloudflare.com/client/v4":
                raise ValueError("approved_kv_endpoint_required")
        if (
            parts.username
            or parts.password
            or parts.query
            or parts.fragment
            or parts.path.rstrip("/") not in ("", "/client/v4")
        ):
            raise ValueError("kv_origin_invalid")
        self.mode = mode
        self.account_id = account_id
        self.namespace_id = namespace_id
        self.token = token
        self.endpoint = endpoint.rstrip("/")
        self.opener = opener or build_opener(_NoRedirect(), ProxyHandler({}))

    def _url(self, key: str) -> str:
        if not re.fullmatch(r"scam-radar-backup/[0-9a-f]{32}/[a-z0-9.-]+", key):
            raise ValueError("kv_key_invalid")
        return (
            f"{self.endpoint}/accounts/{self.account_id}/storage/kv/namespaces/"
            f"{self.namespace_id}/values/{quote(key, safe='')}"
        )

    def _request(
        self, method: str, key: str, payload: bytes | None = None
    ) -> tuple[int, bytes]:
        request = Request(
            self._url(key),
            data=payload,
            method=method,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/octet-stream",
                "Accept": "application/json",
            },
        )
        try:
            with self.opener.open(request, timeout=30) as response:
                body = response.read(MAX_CIPHERTEXT_BYTES + 1)
                if len(body) > MAX_CIPHERTEXT_BYTES:
                    raise RuntimeError("kv_response_too_large")
                return response.status, body
        except HTTPError as error:
            error.close()
            return error.code, b""
        except URLError as error:
            raise RuntimeError("kv_transport_failed") from error

    def _get(self, key: str) -> bytes | None:
        status, body = self._request("GET", key)
        if status == 404:
            return None
        if status != 200:
            raise RuntimeError(f"kv_read_failed_{status}")
        return body

    def _put_verified(self, key: str, value: bytes) -> None:
        if len(value) > MAX_KV_VALUE_BYTES:
            raise ValueError("kv_value_too_large")
        existing = self._get(key)
        if existing is not None:
            if existing != value:
                raise RuntimeError("kv_immutable_key_conflict")
            return
        try:
            status, body = self._request("PUT", key, value)
        except RuntimeError:
            status, body = 0, b""
        if status == 200:
            try:
                if json.loads(body).get("success") is not True:
                    raise RuntimeError("kv_write_rejected")
            except (ValueError, AttributeError) as error:
                raise RuntimeError("kv_write_response_invalid") from error
        elif status not in (0, 429, 500, 502, 503, 504):
            raise RuntimeError(f"kv_write_failed_{status}")
        for attempt in range(4):
            remote = self._get(key)
            if remote == value:
                return
            if remote is not None:
                raise RuntimeError("kv_remote_hash_mismatch")
            if attempt < 3:
                time.sleep(0.25 * (attempt + 1))
        raise RuntimeError("kv_write_unverified")

    def upload(self, manifest_path: Path) -> dict[str, str]:
        path = manifest_path.resolve()
        if (
            not path.is_relative_to(ROOT / "work")
            or path.suffix != ".json"
            or manifest_path.is_symlink()
        ):
            raise ValueError("work_backup_manifest_required")
        if path.stat().st_size > 16_384:
            raise ValueError("kv_manifest_too_large")
        manifest = json.loads(path.read_text())
        if not isinstance(manifest, dict):
            raise TypeError("kv_manifest_type_invalid")
        object_id = manifest.get("object_id")
        if (
            manifest.get("schema") != "scam-radar-encrypted-backup-v1"
            or set(manifest)
            != {
                "schema",
                "object_id",
                "ciphertext_name",
                "ciphertext_sha256",
                "ciphertext_bytes",
                "created_at",
                "encryption",
                "format",
                "scope",
            }
            or not isinstance(object_id, str)
            or not re.fullmatch(r"[0-9a-f]{32}", object_id)
            or path.name != f"{object_id}.json"
            or manifest.get("ciphertext_name") != f"{object_id}.age"
            or manifest.get("encryption") != "age-v1.3.2"
            or manifest.get("format") != "pg_dump-custom"
            or not isinstance(manifest.get("created_at"), str)
            or manifest.get("scope")
            != (
                "synthetic_local_only"
                if self.mode == "local"
                else "approved_production"
            )
        ):
            raise ValueError("kv_manifest_invalid")
        ciphertext = path.with_suffix(".age")
        if ciphertext.is_symlink() or not ciphertext.is_file():
            raise ValueError("age_ciphertext_missing")
        with ciphertext.open("rb") as stream:
            if stream.read(22) != b"age-encryption.org/v1\n":
                raise ValueError("age_ciphertext_header_invalid")
        size = ciphertext.stat().st_size
        if size < 22 or size > MAX_CIPHERTEXT_BYTES:
            raise ValueError("kv_ciphertext_size_out_of_range")
        if manifest.get("ciphertext_bytes") != size or not re.fullmatch(
            r"[0-9a-f]{64}", str(manifest.get("ciphertext_sha256"))
        ):
            raise ValueError("kv_manifest_size_or_hash_invalid")
        with ciphertext.open("rb") as stream:
            local_hash = hashlib.sha256()
            for data in iter(lambda: stream.read(1024 * 1024), b""):
                local_hash.update(data)
        if local_hash.hexdigest() != manifest["ciphertext_sha256"]:
            raise ValueError("kv_local_ciphertext_hash_mismatch")
        base = f"scam-radar-backup/{object_id}"
        full_hash = hashlib.sha256()
        chunks = []
        with ciphertext.open("rb") as stream:
            index = 0
            while data := stream.read(CHUNK_BYTES):
                full_hash.update(data)
                key = f"{base}/chunk-{index:04d}"
                self._put_verified(key, data)
                chunks.append({"key": key, "sha256": _sha256(data), "bytes": len(data)})
                index += 1
        if full_hash.hexdigest() != local_hash.hexdigest():
            raise RuntimeError("kv_ciphertext_changed_during_upload")
        envelope = {
            "schema": "scam-radar-kv-backup-v1",
            "manifest": manifest,
            "chunks": chunks,
        }
        encoded = json.dumps(envelope, sort_keys=True, separators=(",", ":")).encode()
        self._put_verified(f"{base}/manifest.json", encoded)
        return {
            "object_id": object_id,
            "ciphertext_sha256": full_hash.hexdigest(),
            "namespace_id": self.namespace_id,
        }

    def download(self, object_id: str, destination: Path) -> Path:
        if not re.fullmatch(r"[0-9a-f]{32}", object_id):
            raise ValueError("kv_object_id_invalid")
        target = destination.resolve()
        if (
            not target.is_relative_to(ROOT / "work")
            or target.exists()
            or destination.is_symlink()
        ):
            raise ValueError("new_work_restore_destination_required")
        base = f"scam-radar-backup/{object_id}"
        encoded = self._get(f"{base}/manifest.json")
        if encoded is None or len(encoded) > 16_384:
            raise RuntimeError("kv_backup_manifest_missing_or_large")
        envelope = json.loads(encoded)
        manifest = envelope.get("manifest")
        chunks = envelope.get("chunks")
        if (
            envelope.get("schema") != "scam-radar-kv-backup-v1"
            or not isinstance(manifest, dict)
            or manifest.get("schema") != "scam-radar-encrypted-backup-v1"
            or manifest.get("object_id") != object_id
            or manifest.get("scope")
            != (
                "synthetic_local_only"
                if self.mode == "local"
                else "approved_production"
            )
            or manifest.get("ciphertext_name") != f"{object_id}.age"
            or not isinstance(chunks, list)
            or not 1 <= len(chunks) <= 4
            or not isinstance(manifest.get("ciphertext_bytes"), int)
            or not 22 <= manifest["ciphertext_bytes"] <= MAX_CIPHERTEXT_BYTES
        ):
            raise RuntimeError("kv_backup_manifest_invalid")
        target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        temporary = target.with_name(f".{target.name}.{uuid4().hex}.part")
        digest = hashlib.sha256()
        total = 0
        try:
            descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, "wb") as stream:
                for index, info in enumerate(chunks):
                    expected_key = f"{base}/chunk-{index:04d}"
                    if not isinstance(info, dict) or info.get("key") != expected_key:
                        raise RuntimeError("kv_chunk_sequence_invalid")
                    data = self._get(expected_key)
                    if (
                        data is None
                        or len(data) > CHUNK_BYTES
                        or len(data) != info.get("bytes")
                        or _sha256(data) != info.get("sha256")
                    ):
                        raise RuntimeError("kv_chunk_hash_mismatch")
                    stream.write(data)
                    digest.update(data)
                    total += len(data)
            if total != manifest[
                "ciphertext_bytes"
            ] or digest.hexdigest() != manifest.get("ciphertext_sha256"):
                raise RuntimeError("kv_ciphertext_hash_mismatch")
            with temporary.open("rb") as stream:
                if stream.read(22) != b"age-encryption.org/v1\n":
                    raise RuntimeError("kv_age_header_invalid")
            temporary.replace(target)
        finally:
            temporary.unlink(missing_ok=True)
        return target


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "action", choices=("upload", "download"), nargs="?", default="upload"
    )
    parser.add_argument("--mode", choices=("local", "live"), required=True)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--object-id")
    parser.add_argument("--destination", type=Path)
    parser.add_argument("--account-id", required=True)
    parser.add_argument("--namespace-id", required=True)
    parser.add_argument("--endpoint", required=True)
    args = parser.parse_args()
    if (
        args.mode == "live"
        and args.action == "upload"
        and (
            os.getenv("SCAM_RADAR_BACKUP_ENABLED") != "true"
            or os.getenv("SCAM_RADAR_LIVE_ACTIVATION_APPROVED") != "true"
            or os.getenv("SCAM_RADAR_BACKUP_CONFIRMATION") != BACKUP_CONFIRMATION
        )
    ):
        raise ValueError("kv_backup_activation_required")
    if (
        args.mode == "live"
        and args.action == "download"
        and (os.getenv("SCAM_RADAR_BACKUP_RECOVERY_APPROVED") != "true")
    ):
        raise ValueError("kv_recovery_activation_required")
    store = KVBackupStore(
        mode=args.mode,
        endpoint=args.endpoint,
        account_id=args.account_id,
        namespace_id=args.namespace_id,
        token=os.getenv("SCAM_RADAR_KV_TOKEN", ""),
    )
    if args.action == "upload":
        if args.manifest is None:
            raise ValueError("kv_manifest_required")
        result = store.upload(args.manifest)
        print(json.dumps(result, sort_keys=True))
    else:
        if args.object_id is None or args.destination is None:
            raise ValueError("kv_download_arguments_required")
        store.download(args.object_id, args.destination)
        print(json.dumps({"object_id": args.object_id, "status": "verified"}))


if __name__ == "__main__":
    main()
