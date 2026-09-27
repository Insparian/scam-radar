"""Stream one PostgreSQL custom archive into age; never write a raw dump file.

The live path is disabled until the separate backup activation. The local path
reads only an explicitly named synthetic Supabase container.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
POSTGRES_IMAGE = "postgres:17.9@sha256:2a0d0fe14825b0939f78a8cad5cd4e6aa68bf94d0e5dd96e24b6d23af4315545"
BACKUP_CONFIRMATION = "BACKUP APPROVED CIPHERTEXT ONLY"


def _work_destination(path: Path) -> Path:
    target = path.resolve()
    if not target.is_relative_to(ROOT / "work") or target.exists():
        raise ValueError("new_work_backup_destination_required")
    return target


def _pg_environment(mode: str) -> dict[str, str]:
    required = ("PGHOST", "PGPORT", "PGUSER", "PGDATABASE", "PGPASSWORD", "PGSSLMODE")
    env = {key: os.getenv(key, "") for key in required}
    if mode == "live":
        direct = re.fullmatch(r"db\.[a-z0-9]+\.supabase\.co", env["PGHOST"])
        session_pooler = re.fullmatch(
            r"[a-z0-9-]+(?:\.[a-z0-9-]+)*\.pooler\.supabase\.com", env["PGHOST"]
        )
        if not direct and not session_pooler:
            raise ValueError("approved_supabase_postgres_host_required")
        if env["PGPORT"] != "5432" or env["PGSSLMODE"] != "verify-full":
            raise ValueError("secure_direct_postgres_required")
        if env["PGDATABASE"] != "postgres" or not env["PGUSER"].startswith("postgres"):
            raise ValueError("approved_postgres_database_required")
        if not env["PGPASSWORD"]:
            raise ValueError("postgres_password_required")
        env["PGSSLROOTCERT"] = "/run/secrets/supabase-ca.pem"
    return env


def _client_command(
    mode: str,
    docker: str,
    container: str | None,
    ca_file: Path | None,
    application: list[str],
) -> list[str]:
    if mode == "local":
        if container is None or not re.fullmatch(
            r"supabase_db_scam-radar-[a-z0-9-]+", container
        ):
            raise ValueError("named_synthetic_database_required")
        return [
            docker,
            "exec",
            "-i",
            container,
            *application,
        ]
    if ca_file is None:
        raise ValueError("supabase_ca_certificate_required")
    return [
        docker,
        "run",
        "--rm",
        "--pull=never",
        "--network=host",
        "--read-only",
        "--cap-drop=ALL",
        "--security-opt=no-new-privileges",
        "--mount",
        f"type=bind,src={ca_file},dst=/run/secrets/supabase-ca.pem,readonly",
        "-e",
        "PGHOST",
        "-e",
        "PGPORT",
        "-e",
        "PGUSER",
        "-e",
        "PGDATABASE",
        "-e",
        "PGPASSWORD",
        "-e",
        "PGSSLMODE",
        "-e",
        "PGSSLROOTCERT",
        POSTGRES_IMAGE,
        *application,
    ]


def backup(
    *,
    mode: str,
    destination: Path,
    age: Path,
    recipient: str,
    docker: str,
    container: str | None = None,
) -> dict[str, object]:
    if mode not in ("local", "live"):
        raise ValueError("backup_mode_invalid")
    if mode == "live" and (
        os.getenv("SCAM_RADAR_BACKUP_ENABLED") != "true"
        or os.getenv("SCAM_RADAR_LIVE_ACTIVATION_APPROVED") != "true"
        or os.getenv("SCAM_RADAR_BACKUP_CONFIRMATION") != BACKUP_CONFIRMATION
    ):
        raise ValueError("external_backup_activation_required")
    if not re.fullmatch(r"age1[023456789acdefghjklmnpqrstuvwxyz]{58}", recipient):
        raise ValueError("age_recipient_invalid")
    target = _work_destination(destination)
    if not age.is_file() or not os.access(age, os.X_OK):
        raise ValueError("age_binary_required")
    version = subprocess.run(
        [str(age), "--version"], capture_output=True, text=True, timeout=5, check=False
    )
    if version.returncode or "v1.3.2" not in version.stdout:
        raise ValueError("pinned_age_version_required")
    pg_env = _pg_environment(mode) if mode == "live" else {}
    ca_file = None
    if mode == "live":
        ca_name = os.getenv("SCAM_RADAR_PG_CA_FILE", "")
        ca_file = Path(ca_name).resolve() if ca_name else None
        if (
            ca_file is None
            or not ca_file.is_file()
            or not ca_file.is_relative_to(ROOT / "work")
        ):
            raise ValueError("work_supabase_ca_certificate_required")
    target.mkdir(parents=True, mode=0o700)
    object_id = uuid4().hex
    ciphertext = target / f"{object_id}.age"
    try:
        env = {
            key: os.environ[key]
            for key in ("PATH", "HOME", "TMPDIR")
            if key in os.environ
        }
        env.update(pg_env)
        if mode == "live":
            preflight = subprocess.run(
                _client_command(
                    mode,
                    docker,
                    container,
                    ca_file,
                    ["psql", "-Atqc", "show server_version_num"],
                ),
                env=env,
                capture_output=True,
                check=False,
                timeout=30,
            )
            if preflight.returncode or not preflight.stdout.strip().isdigit():
                raise RuntimeError("postgres_version_preflight_failed")
            server_major = int(preflight.stdout.strip()) // 10000
            if not 15 <= server_major <= 17:
                raise RuntimeError("postgres_client_server_version_incompatible")
        dump = subprocess.Popen(
            _client_command(
                mode,
                docker,
                container,
                ca_file,
                ["pg_dump", "-U", "postgres", "-d", "postgres", "-Fc"]
                if mode == "local"
                else ["pg_dump", "-Fc", "--no-password"],
            ),
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            env=env,
        )
        if dump.stdout is None:
            raise RuntimeError("pg_dump_stream_missing")
        encrypted = subprocess.Popen(
            [str(age), "-r", recipient, "-o", str(ciphertext)],
            stdin=dump.stdout,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=env,
        )
        dump.stdout.close()
        try:
            age_status = encrypted.wait(timeout=300)
            dump_status = dump.wait(timeout=300)
        except subprocess.TimeoutExpired as error:
            encrypted.kill()
            dump.kill()
            encrypted.wait()
            dump.wait()
            raise RuntimeError("backup_stream_timeout") from error
        if age_status or dump_status:
            raise RuntimeError("backup_stream_failed")
        header = b"age-encryption.org/v1\n"
        with ciphertext.open("rb") as stream:
            if stream.read(len(header)) != header:
                raise RuntimeError("age_ciphertext_header_invalid")
        digest = hashlib.sha256()
        size = 0
        with ciphertext.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                size += len(chunk)
                digest.update(chunk)
        if size < 100:
            raise RuntimeError("age_ciphertext_too_short")
        manifest: dict[str, object] = {
            "schema": "scam-radar-encrypted-backup-v1",
            "object_id": object_id,
            "ciphertext_name": ciphertext.name,
            "ciphertext_sha256": digest.hexdigest(),
            "ciphertext_bytes": size,
            "created_at": datetime.now(UTC).isoformat(),
            "encryption": "age-v1.3.2",
            "format": "pg_dump-custom",
            "scope": "synthetic_local_only"
            if mode == "local"
            else "approved_production",
        }
        (target / f"{object_id}.json").write_text(
            json.dumps(manifest, sort_keys=True, indent=2) + "\n"
        )
        return manifest
    except BaseException:
        ciphertext.unlink(missing_ok=True)
        raise


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("local", "live"), required=True)
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--age-binary", type=Path, required=True)
    parser.add_argument("--recipient", required=True)
    parser.add_argument("--docker", default="docker")
    parser.add_argument("--container")
    args = parser.parse_args()
    try:
        result = backup(
            mode=args.mode,
            destination=args.destination,
            age=args.age_binary,
            recipient=args.recipient,
            docker=args.docker,
            container=args.container,
        )
    except (ValueError, RuntimeError, OSError, subprocess.SubprocessError) as error:
        print(f"backup_rejected:{error}", file=sys.stderr)
        return 1
    print(
        "encrypted_backup_ok object_id="
        + str(result["object_id"])
        + " ciphertext_sha256="
        + str(result["ciphertext_sha256"])
        + " uploaded=false"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
