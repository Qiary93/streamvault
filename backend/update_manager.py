"""
update_manager.py — host-update orchestration via a shared state directory.

The backend container has the host's project directory mounted at /host/repo
and the host has a systemd path-watcher that fires `streamvault-updater.service`
whenever /host/repo/.update-state/requested appears.

Files we read/write:
  /host/repo/.update-state/requested   (touched by us → triggers host systemd)
  /host/repo/.update-state/status.json (written by host systemd, read by us)

If /host/repo isn't mounted (e.g., dev preview environment), all check/apply
endpoints return a graceful "auto-update not available" message instead of
failing.
"""
from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

REPO_PATH = Path(os.environ.get("HOST_REPO_PATH") or "/host/repo")
STATE_DIR = REPO_PATH / ".update-state"
STATUS_FILE = STATE_DIR / "status.json"
REQUEST_FILE = STATE_DIR / "requested"
LOG_FILE = STATE_DIR / "log.txt"


def is_supported() -> bool:
    """True if the host repo is mounted and looks like a git checkout."""
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


def check_for_updates() -> dict:
    """git fetch + count commits behind upstream. Returns a structured result."""
    if not is_supported():
        return {"supported": False, "message": "Host repository is not mounted into the backend container."}
    
    # Fetch latest refs (anonymous; HTTPS public repo expected).
    rc, out = _run(["git", "fetch", "--quiet", "origin"], timeout=60)
    fetched = rc == 0
    
    # Current branch + sha
    rc, branch = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"], timeout=10)
    branch = branch.strip() if rc == 0 else "main"
    
    rc, current_sha = _run(["git", "rev-parse", "HEAD"], timeout=10)
    rc2, current_short = _run(["git", "rev-parse", "--short", "HEAD"], timeout=10)
    
    upstream_ref = f"origin/{branch}"
    rc, latest_sha = _run(["git", "rev-parse", upstream_ref], timeout=10)
    if rc != 0:
        return {
            "supported": True,
            "current_sha": current_sha or "",
            "current_short": current_short or "",
            "latest_sha": "",
            "behind": 0,
            "fetched": fetched,
            "branch": branch,
            "message": f"Could not resolve {upstream_ref}: {latest_sha}",
        }
    
    # Count commits behind upstream
    rc, count = _run(["git", "rev-list", "--count", f"HEAD..{upstream_ref}"], timeout=15)
    behind = int(count.strip()) if rc == 0 and count.strip().isdigit() else 0
    
    # List the new commits (one per line, %h|%s|%an|%ar)
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
        "current_sha": current_sha,
        "current_short": current_short,
        "latest_sha": latest_sha,
        "latest_short": latest_sha[:7] if latest_sha else "",
        "behind": behind,
        "branch": branch,
        "fetched": fetched,
        "commits": commits,
        "auto_update_enabled": (REPO_PATH / ".update-state").exists(),
    }


def request_update() -> dict:
    """Drop a request file → systemd path watcher fires the updater service."""
    if not is_supported():
        return {"ok": False, "message": "Auto-update not supported on this install. Use 'git pull' manually."}
    
    state_dir = REPO_PATH / ".update-state"
    if not state_dir.exists():
        return {
            "ok": False,
            "message": (
                "Auto-update state directory is missing. Re-run install.sh to install the "
                "host-side systemd updater (this is a one-time step for older installs)."
            ),
        }
    
    now = datetime.now(timezone.utc).isoformat()
    payload = {"requested_at": now, "status": "queued"}
    STATUS_FILE.write_text(json.dumps(payload, indent=2))
    REQUEST_FILE.write_text(now)
    return {"ok": True, "message": "Update queued — host watcher will pick it up within ~2 seconds.", "requested_at": now}


def get_status() -> dict:
    """Return the latest update job status as written by the host systemd service."""
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
