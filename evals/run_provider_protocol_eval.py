"""Fair local protocol evaluation; never interprets mock output as model quality."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "worker/src"))
from scam_radar.llm.configured import evaluation_provider


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", choices=["glm", "qwen", "gemini"], required=True)
    parser.add_argument("--local-endpoint", required=True)
    parser.add_argument("--cases", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    raw = args.cases.read_bytes()
    cases = json.loads(raw)
    if not isinstance(cases, list) or not 1 <= len(cases) <= 50:
        raise ValueError("eval_case_limit")
    provider = evaluation_provider(
        ROOT,
        args.candidate,
        local_endpoint=args.local_endpoint,
        max_calls=min(100, 2 * len(cases)),
    )
    results = []
    for case in cases:
        started = time.monotonic()
        try:
            output = provider.classify(case["id"], case["text"])
            matched = output.relevant == case["expected_relevant"]
            status = "valid"
        except (ValueError, RuntimeError):
            matched, status = False, "failed"
        results.append(
            {
                "id": case["id"],
                "status": status,
                "matched": matched,
                "latency_ms": round((time.monotonic() - started) * 1000),
            }
        )
    report = {
        "candidate": args.candidate,
        "model": provider.model,
        "dataset_sha256": hashlib.sha256(raw).hexdigest(),
        "calls": provider.calls,
        "launch_qualified": False,
        "scope": "local_protocol_only",
        "results": results,
    }
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(
        f"local protocol eval: cases={len(cases)} calls={provider.calls} launch_qualified=false"
    )
    return 0 if all(item["matched"] for item in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
