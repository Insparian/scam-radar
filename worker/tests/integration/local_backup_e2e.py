"""Real local pg_dump → age → S3 protocol upload → decrypt/inspect rehearsal."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from scripts.backup_database import backup  # noqa: E402
from scripts.upload_encrypted_backup import CiphertextStore  # noqa: E402


def run(container: str, docker: str, age_directory: Path, rclone: Path) -> None:
    if not container.startswith("supabase_db_scam-radar-"):
        raise ValueError("named_synthetic_database_required")
    output = ROOT / "work/launch-readiness" / f"backup-e2e-{uuid4().hex[:12]}"
    output.mkdir(mode=0o700)
    identity = output / "synthetic-identity.txt"
    keygen = age_directory / "age-keygen"
    age = age_directory / "age"
    subprocess.run(
        [str(keygen), "-o", str(identity)],
        capture_output=True,
        check=True,
        timeout=15,
    )
    identity.chmod(0o600)
    recipient = subprocess.run(
        [str(keygen), "-y", str(identity)],
        capture_output=True,
        text=True,
        check=True,
        timeout=15,
    ).stdout.strip()
    manifest = backup(
        mode="local",
        destination=output / "encrypted",
        age=age,
        recipient=recipient,
        docker=docker,
        container=container,
    )
    object_id = str(manifest["object_id"])
    encrypted = output / "encrypted" / f"{object_id}.age"
    manifest_path = output / "encrypted" / f"{object_id}.json"
    s3_root = output / "s3-root"
    bucket = "synthetic-private-backups"
    (s3_root / bucket).mkdir(parents=True)
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        port = reservation.getsockname()[1]
    endpoint = f"http://127.0.0.1:{port}"
    env = os.environ.copy()
    env["RCLONE_AUTH_KEY"] = '"synthetic-access,synthetic-secret"'
    server = subprocess.Popen(
        [str(rclone), "serve", "s3", "--addr", f"127.0.0.1:{port}", str(s3_root)],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        for _attempt in range(50):
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                    break
            except OSError as error:
                if server.poll() is not None:
                    raise RuntimeError("local_s3_server_exited") from error
                time.sleep(0.1)
        else:
            raise RuntimeError("local_s3_server_not_ready")
        store = CiphertextStore(
            mode="local",
            endpoint=endpoint,
            account_id="",
            bucket=bucket,
            access_key_id="synthetic-access",
            secret_access_key="synthetic-secret",
            rclone=rclone,
        )
        first = store.upload(manifest_path)
        second = store.upload(manifest_path)
        if first != second:
            raise AssertionError("backup_upload_replay_changed_receipt")
        remote_ciphertext = s3_root / bucket / encrypted.name
        remote_manifest = s3_root / bucket / manifest_path.name
        if (
            remote_ciphertext.read_bytes() != encrypted.read_bytes()
            or json.loads(remote_manifest.read_text()) != manifest
        ):
            raise AssertionError("remote_ciphertext_or_manifest_mismatch")
        bad = output / "tampered"
        bad.mkdir()
        shutil.copy2(manifest_path, bad / manifest_path.name)
        damaged = bad / encrypted.name
        shutil.copy2(encrypted, damaged)
        with damaged.open("r+b") as stream:
            stream.seek(-1, os.SEEK_END)
            previous = stream.read(1)
            stream.seek(-1, os.SEEK_END)
            stream.write(bytes([previous[0] ^ 1]))
        try:
            store.upload(bad / manifest_path.name)
        except ValueError as error:
            if str(error) != "backup_ciphertext_manifest_mismatch":
                raise
        else:
            raise AssertionError("tampered_ciphertext_was_uploaded")
        decrypted = subprocess.run(
            [str(age), "-d", "-i", str(identity), str(remote_ciphertext)],
            capture_output=True,
            check=True,
            timeout=60,
        ).stdout
        toc = subprocess.run(
            [docker, "exec", "-i", container, "pg_restore", "-l"],
            input=decrypted,
            capture_output=True,
            check=True,
            timeout=60,
        ).stdout
        if b"SCHEMA" not in toc or b"TABLE DATA" not in toc:
            raise AssertionError("restored_ciphertext_not_a_complete_custom_archive")
        if list(output.rglob("*.dump")):
            raise AssertionError("raw_dump_file_created")
        report = {
            "scope": "synthetic_local_only",
            "object_id": object_id,
            "ciphertext_sha256": manifest["ciphertext_sha256"],
            "s3_endpoint": "127.0.0.1",
            "uploaded_twice_without_duplicate": True,
            "tampered_ciphertext_rejected": True,
            "decrypted_archive_valid": True,
            "raw_dump_file_created": False,
        }
        (output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
        print(
            "GREEN synthetic PostgreSQL → age ciphertext → localhost S3 → "
            "idempotent verify → tamper rejection → decrypted custom archive; "
            f"report={output.relative_to(ROOT)}/report.json"
        )
    finally:
        server.terminate()
        try:
            server.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server.kill()
            server.wait()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--container", required=True)
    parser.add_argument("--docker", required=True)
    parser.add_argument("--age-directory", type=Path, required=True)
    parser.add_argument("--rclone", type=Path, required=True)
    args = parser.parse_args()
    run(args.container, args.docker, args.age_directory.resolve(), args.rclone.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
