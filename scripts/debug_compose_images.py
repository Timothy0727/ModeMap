#!/usr/bin/env python3
"""Debug helper: log docker compose image/build state to session log."""

from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path

LOG_PATH = Path(__file__).resolve().parents[1] / ".cursor" / "debug-6e709b.log"
SESSION = "6e709b"


def log(hypothesis_id: str, location: str, message: str, data: dict) -> None:
    entry = {
        "sessionId": SESSION,
        "runId": "post-fix",
        "hypothesisId": hypothesis_id,
        "location": location,
        "message": message,
        "data": data,
        "timestamp": int(time.time() * 1000),
    }
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


def run(cmd: list[str]) -> str:
    return subprocess.run(cmd, capture_output=True, text=True, check=False).stdout.strip()


def main() -> None:
    services = run(["docker", "compose", "config", "--services"]).splitlines()
    images_out = run(["docker", "compose", "images", "--format", "json"])
    ps_out = run(["docker", "compose", "ps", "-a", "--format", "json"])

    built_services = {"api", "worker"}
    pulled_services = {"postgres", "redis"}

    for svc in services:
        has_build = svc in built_services
        log(
            "A",
            "scripts/debug_compose_images.py:service",
            "compose service config",
            {"service": svc, "expects_local_build": has_build, "expects_pull_only": svc in pulled_services},
        )

    # Hypothesis A: up -d without --build leaves stale container images
    for line in images_out.splitlines():
        if not line.strip():
            continue
        parsed = json.loads(line)
        records = parsed if isinstance(parsed, list) else [parsed]
        for img in records:
            if not isinstance(img, dict):
                continue
            log(
                "A",
                "scripts/debug_compose_images.py:images",
                "compose image record",
                {
                    "container": img.get("Container"),
                    "repository": img.get("Repository"),
                    "createdSince": img.get("CreatedSince"),
                    "id": img.get("ID"),
                },
            )

    # Hypothesis B/C: worker exits because celery app missing
    for line in ps_out.splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if row.get("Service") == "worker":
            log(
                "C",
                "scripts/debug_compose_images.py:worker_ps",
                "worker container status",
                {"state": row.get("State"), "status": row.get("Status"), "image": row.get("Image")},
            )
        if row.get("Service") == "api":
            log(
                "B",
                "scripts/debug_compose_images.py:api_ps",
                "api container status",
                {"state": row.get("State"), "status": row.get("Status"), "image": row.get("Image")},
            )

    worker_logs = run(["docker", "compose", "logs", "worker", "--tail", "5"])
    log(
        "C",
        "scripts/debug_compose_images.py:worker_logs",
        "worker recent logs",
        {"tail": worker_logs[-500:] if worker_logs else ""},
    )

    images_cmd = run(["docker", "compose", "images"])
    log(
        "D",
        "scripts/debug_compose_images.py:compose_images",
        "docker compose images result",
        {
            "ok": "Error response from daemon" not in images_cmd,
            "output": images_cmd[:500] if images_cmd else "",
        },
    )


if __name__ == "__main__":
    main()
