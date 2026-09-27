"""R2/S3 adapter that accepts only validated age ciphertext and its manifest.

Live endpoints and credentials remain disabled until separate activation.
Local protocol tests use a short-lived loopback S3 server.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
BACKUP_CONFIRMATION = "BACKUP APPROVED CIPHERTEXT ONLY"


def _hash_file(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
            size += len(chunk)
    return digest.hexdigest(), size


class CiphertextStore:
    def __init__(
        self,
        *,
        mode: str,
        endpoint: str,
        account_id: str,
        bucket: str,
        access_key_id: str,
        secret_access_key: str,
        rclone: Path,
    ) -> None:
        if mode not in ("local", "live"):
            raise ValueError("backup_store_mode_invalid")
        parts = urlsplit(endpoint)
        if mode == "local":
            if (
                parts.scheme != "http"
                or parts.hostname != "127.0.0.1"
                or not parts.port
            ):
                raise ValueError("local_s3_endpoint_required")
        elif (
            not re.fullmatch(r"[0-9a-f]{32}", account_id)
            or endpoint != f"https://{account_id}.r2.cloudflarestorage.com"
        ):
            raise ValueError("approved_r2_endpoint_required")
        if (
            parts.username
            or parts.password
            or parts.path not in ("", "/")
            or parts.query
            or parts.fragment
        ):
            raise ValueError("backup_store_origin_invalid")
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]{2,62}", bucket):
            raise ValueError("backup_bucket_invalid")
        if not access_key_id or not secret_access_key:
            raise ValueError("backup_store_credentials_required")
        if not rclone.is_file() or not os.access(rclone, os.X_OK):
            raise ValueError("rclone_binary_required")
        self.mode = mode
        self.endpoint = endpoint
        self.bucket = bucket
        self.rclone = rclone
        self.environment = {
            key: os.environ[key]
            for key in ("PATH", "HOME", "TMPDIR")
            if key in os.environ
        }
        self.environment.update(
            RCLONE_CONFIG="/dev/null",
            RCLONE_CONFIG_R2_TYPE="s3",
            RCLONE_CONFIG_R2_PROVIDER="Rclone" if mode == "local" else "Cloudflare",
            RCLONE_CONFIG_R2_ENV_AUTH="false",
            RCLONE_CONFIG_R2_ACCESS_KEY_ID=access_key_id,
            RCLONE_CONFIG_R2_SECRET_ACCESS_KEY=secret_access_key,
            RCLONE_CONFIG_R2_REGION="us-east-1" if mode == "local" else "auto",
            RCLONE_CONFIG_R2_ENDPOINT=endpoint,
            RCLONE_CONFIG_R2_NO_CHECK_BUCKET="true",
        )
        version = self._run(["version"], capture=True)
        if not version.startswith(b"rclone v1.75.1\n"):
            raise ValueError("pinned_rclone_version_required")

    def _run(self, arguments: list[str], *, capture: bool = False) -> bytes:
        result = subprocess.run(
            [str(self.rclone), "--contimeout", "10s", "--timeout", "30s", *arguments],
            env=self.environment,
            stdout=subprocess.PIPE if capture else subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=120,
            check=False,
        )
        if result.returncode:
            raise RuntimeError("rclone_operation_failed")
        return result.stdout if capture else b""

    def _names(self) -> set[str]:
        listing = self._run(
            ["lsf", f"r2:{self.bucket}", "--files-only", "--max-depth", "1"],
            capture=True,
        )
        if len(listing) > 2_000_000:
            raise RuntimeError("backup_bucket_listing_too_large")
        return {line for line in listing.decode().splitlines() if line}

    def _remote_hash(self, name: str, expected_size: int) -> str:
        command = subprocess.Popen(
            [
                str(self.rclone),
                "--contimeout",
                "10s",
                "--timeout",
                "30s",
                "cat",
                f"r2:{self.bucket}/{name}",
            ],
            env=self.environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
        if command.stdout is None:
            raise RuntimeError("rclone_read_stream_missing")
        digest = hashlib.sha256()
        size = 0
        try:
            for chunk in iter(lambda: command.stdout.read(1024 * 1024), b""):
                size += len(chunk)
                if size > expected_size:
                    raise RuntimeError("remote_ciphertext_size_mismatch")
                digest.update(chunk)
        except BaseException:
            command.kill()
            command.wait()
            raise
        finally:
            command.stdout.close()
        try:
            status = command.wait(timeout=120)
        except subprocess.TimeoutExpired as error:
            command.kill()
            command.wait()
            raise RuntimeError("remote_ciphertext_read_timeout") from error
        if status or size != expected_size:
            raise RuntimeError("remote_ciphertext_unreadable")
        return digest.hexdigest()

    def _put_verified(self, local: Path, name: str, digest: str, size: int) -> None:
        if name not in self._names():
            try:
                self._run(
                    ["copyto", str(local), f"r2:{self.bucket}/{name}", "--no-traverse"]
                )
            except RuntimeError:
                # A lost response may follow a committed PUT. Inspect once;
                # never repeat an upload without proving it is absent.
                pass
        if self._remote_hash(name, size) != digest:
            raise RuntimeError("remote_ciphertext_hash_mismatch")

    def upload(self, manifest_path: Path) -> dict[str, str]:
        path = manifest_path.resolve()
        if (
            not path.is_relative_to(ROOT / "work")
            or path.suffix != ".json"
            or path.is_symlink()
        ):
            raise ValueError("work_backup_manifest_required")
        manifest = json.loads(path.read_text())
        if (
            not isinstance(manifest, dict)
            or manifest.get("schema") != "scam-radar-encrypted-backup-v1"
        ):
            raise ValueError("backup_manifest_invalid")
        object_id = manifest.get("object_id")
        if not isinstance(object_id, str) or not re.fullmatch(
            r"[0-9a-f]{32}", object_id
        ):
            raise ValueError("backup_object_id_invalid")
        if (
            path.name != f"{object_id}.json"
            or manifest.get("ciphertext_name") != f"{object_id}.age"
        ):
            raise ValueError("backup_manifest_name_mismatch")
        if manifest.get("scope") != (
            "synthetic_local_only" if self.mode == "local" else "approved_production"
        ):
            raise ValueError("backup_scope_mismatch")
        ciphertext = path.with_suffix(".age")
        if ciphertext.is_symlink() or not ciphertext.is_file():
            raise ValueError("age_ciphertext_missing")
        with ciphertext.open("rb") as stream:
            if (
                stream.read(len(b"age-encryption.org/v1\n"))
                != b"age-encryption.org/v1\n"
            ):
                raise ValueError("age_ciphertext_header_invalid")
        digest, size = _hash_file(ciphertext)
        if digest != manifest.get("ciphertext_sha256") or size != manifest.get(
            "ciphertext_bytes"
        ):
            raise ValueError("backup_ciphertext_manifest_mismatch")
        self._put_verified(ciphertext, ciphertext.name, digest, size)
        manifest_hash, manifest_size = _hash_file(path)
        self._put_verified(path, path.name, manifest_hash, manifest_size)
        return {
            "object_id": object_id,
            "ciphertext_sha256": digest,
            "bucket": self.bucket,
        }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("local", "live"), required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--rclone", type=Path, required=True)
    parser.add_argument("--endpoint", required=True)
    parser.add_argument("--account-id", default="")
    parser.add_argument("--bucket", required=True)
    args = parser.parse_args()
    if args.mode == "live" and (
        os.getenv("SCAM_RADAR_BACKUP_ENABLED") != "true"
        or os.getenv("SCAM_RADAR_LIVE_ACTIVATION_APPROVED") != "true"
        or os.getenv("SCAM_RADAR_BACKUP_CONFIRMATION") != BACKUP_CONFIRMATION
    ):
        print(
            "backup_store_rejected:external_backup_activation_required", file=sys.stderr
        )
        return 1
    try:
        store = CiphertextStore(
            mode=args.mode,
            endpoint=args.endpoint,
            account_id=args.account_id,
            bucket=args.bucket,
            access_key_id=os.getenv("SCAM_RADAR_R2_ACCESS_KEY_ID", ""),
            secret_access_key=os.getenv("SCAM_RADAR_R2_SECRET_ACCESS_KEY", ""),
            rclone=args.rclone,
        )
        result = store.upload(args.manifest)
    except (
        ValueError,
        TypeError,
        RuntimeError,
        OSError,
        subprocess.SubprocessError,
    ) as error:
        print(f"backup_store_rejected:{error}", file=sys.stderr)
        return 1
    print(
        "ciphertext_upload_verified object_id="
        + result["object_id"]
        + " sha256="
        + result["ciphertext_sha256"]
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
