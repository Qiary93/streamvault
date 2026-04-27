"""
update_manager.py — host-update orchestration via a shared state directory.

The backend container has the host's project directory mounted at /host/repo
and the host has a systemd path-watcher that fires `streamvault-updater.service`
whenever /host/repo/.update-state/requested appears.

State files (all under /host/repo/.update-state/):
    requested         touched by us → triggers host systemd
    request.json      job parameters (mode: update|rollback, target_sha)
    status.json       written by host systemd, read by us
    log.txt           rolling log of the latest update job
    history.json      append-only audit log of past update jobs
"""
from __future__ import annotations

import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

REPO_PATH = Path(os.environ.get("HOST_REPO_PATH") or "/host/repo")
STATE_DIR = REPO_PATH / ".update-state"
STATUS_FILE = STATE_DIR / "status.json"
REQUEST_FILE = STATE_DIR / "requested"
REQUEST_PARAMS = STATE_DIR / "request.json"
LOG_FILE = STATE_DIR / "log.txt"
HISTORY_FILE = STATE_DIR / "history.json"
CHANGELOG_FILE = REPO_PATH / "CHANGELOG.md"


def is_supported() -> bool:
    return REPO_PATH.exists() and (REPO_PATH / ".git").exists()


def _run(args: list[str], cwd: Optional[Path] = None, timeout: int = 30) -> tuple[int, str]:
    try:
        proc = subprocess.run(
            args, cwd=str(cwd or REPO_PATH),
            capture_output=True, text=True, timeout=timeout,
            env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
        )
        return proc.returncode, (proc.stdout + proc.stderr).strip()
    except FileNotFoundError as e:
        return 127, str(e)
    except subprocess.TimeoutExpired:
        return 124, "timeout"


def _read_changelog_snippet(latest_short: str = "") -> Optional[str]:
    """Return the top H2 section from CHANGELOG.md (typically the latest release)."""
    if not CHANGELOG_FILE.exists():
        return None
    try:
        text = CHANGELOG_FILE.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return None
    # Take everything from the first ## heading until the next ## (or end).
    match = re.search(r"^(##\s+.*?)(?=\n##\s+|\Z)", text, flags=re.M | re.S)
    if not match:
        return None
    section = match.group(1).strip()
    # Cap length so we don't ship huge payloads
    return section[:4000]


def check_for_updates() -> dict:
    if not is_supported():
        return {"supported": False, "message": "Host repository is not mounted into the backend container."}
    
    rc, _ = _run(["git", "fetch", "--quiet", "origin"], timeout=60)
    fetched = rc == 0
    
    rc, branch = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"], timeout=10)
    branch = branch.strip() if rc == 0 else "main"
    
    rc, current_sha = _run(["git", "rev-parse", "HEAD"], timeout=10)
    rc2, current_short = _run(["git", "rev-parse", "--short", "HEAD"], timeout=10)
    
    upstream_ref = f"origin/{branch}"
    rc, latest_sha = _run(["git", "rev-parse", upstream_ref], timeout=10)
    if rc != 0:
        return {
            "supported": True, "current_sha": current_sha, "current_short": current_short,
            "latest_sha": "", "behind": 0, "fetched": fetched, "branch": branch,
            "message": f"Could not resolve {upstream_ref}: {latest_sha}",
        }
    
    rc, count = _run(["git", "rev-list", "--count", f"HEAD..{upstream_ref}"], timeout=15)
    behind = int(count.strip()) if rc == 0 and count.strip().isdigit() else 0
    
    commits: list[dict] = []
    if behind > 0:
        rc, log_out = _run(
            ["git", "log", "--no-merges", "--pretty=format:%h\u001f%s\u001f%an\u001f%ar",
             f"HEAD..{upstream_ref}", "--max-count=20"], timeout=15,
        )
        if rc == 0 and log_out:
            for line in log_out.splitlines():
                parts = line.split("\u001f")
                if len(parts) == 4:
                    commits.append({"sha": parts[0], "subject": parts[1], "author": parts[2], "when": parts[3]})
    
    return {
        "supported": True,
        "current_sha": current_sha, "current_short": current_short,
        "latest_sha": latest_sha, "latest_short": latest_sha[:7] if latest_sha else "",
        "behind": behind, "branch": branch, "fetched": fetched,
        "commits": commits,
        "changelog": _read_changelog_snippet(latest_sha[:7] if latest_sha else ""),
        "auto_update_enabled": (REPO_PATH / ".update-state").exists(),
    }


def _enqueue_request(payload: dict) -> dict:
    if not is_supported():
        return {"ok": False, "message": "Auto-update not supported on this install."}
    if not STATE_DIR.exists():
        return {"ok": False, "message": "Auto-update state directory missing — re-run install.sh on the VPS."}
    
    now = datetime.now(timezone.utc).isoformat()
    payload = {**payload, "requested_at": now, "status": "queued"}
    REQUEST_PARAMS.write_text(json.dumps(payload, indent=2))
    STATUS_FILE.write_text(json.dumps({"status": "queued", "stage": "queued",
                                       "message": "Waiting for host updater…",
                                       "started_at": now, "mode": payload.get("mode", "update")}, indent=2))
    REQUEST_FILE.write_text(now)
    return {"ok": True, "message": "Update queued — host watcher fires within ~2s.", "requested_at": now}


def request_update() -> dict:
    return _enqueue_request({"mode": "update"})


def request_rollback(target_sha: str) -> dict:
    if not target_sha or len(target_sha) < 7:
        return {"ok": False, "message": "Invalid target SHA"}
    return _enqueue_request({"mode": "rollback", "target_sha": target_sha})


def get_status() -> dict:
    if not is_supported():
        return {"supported": False, "status": "unsupported"}
    if not STATUS_FILE.exists():
        return {"supported": True, "status": "idle"}
    try:
        data = json.loads(STATUS_FILE.read_text())
    except Exception as e:
        return {"supported": True, "status": "unknown", "error": str(e)}
    if LOG_FILE.exists():
        try:
            data["log_tail"] = "\n".join(LOG_FILE.read_text().splitlines()[-60:])
        except Exception:
            pass
    return {"supported": True, **data}


def get_history(limit: int = 20) -> list[dict]:
    if not is_supported() or not HISTORY_FILE.exists():
        return []
    try:
        data = json.loads(HISTORY_FILE.read_text())
        items = data if isinstance(data, list) else []
    except Exception:
        return []
    return items[-limit:][::-1]
