#!/usr/bin/env python3
"""
DOCKER DAEMON STANDARDS – ENFORCER & AUDITOR (LINUX)
==================================================

Implements Docker security standards safely and idempotently.

STANDARDS IMPLEMENTED
--------------------
2.1 Docker Daemon Configuration (ENFORCED)
- User namespace remapping
- Disable inter-container communication
- Enable live restore
- Enable no-new-privileges
- Container log rotation limits

2.2 Prohibited Docker Practices (AUDITED)
- Privileged containers
- Mounting /var/run/docker.sock
- Mounting host root (/)
- Docker usage as root

MODES
-----
sudo python3 scripts/2_docker_daemon_standards.py --apply     Apply daemon configuration + audit (default)
sudo python3 scripts/2_docker_daemon_standards.py --check     Audit only (no changes)
sudo python3 scripts/2_docker_daemon_standards.py --dry-run   Show changes without applying

SUPPORTED
---------
Ubuntu LTS / Debian Stable

WARNING
-------
• Requires root
• Docker daemon restart required in apply mode
• No containers are stopped automatically
"""

import os
import sys
import json
import subprocess
from pathlib import Path
from datetime import datetime

# ---------------- CONFIG ----------------
DAEMON_JSON = "/etc/docker/daemon.json"
REPORT_FILE = "/var/log/docker-daemon-compliance.txt"
MODE = "--apply" if len(sys.argv) == 1 else sys.argv[1]

DESIRED_DAEMON_CONFIG = {
    "userns-remap": "default",
    "icc": False,
    "live-restore": True,
    "no-new-privileges": True,
    "log-driver": "json-file",
    "log-opts": {
        "max-size": "10m",
        "max-file": "3"
    }
}

# ---------------- UTILS ----------------
def require_root():
    if os.geteuid() != 0:
        print("❌ This script must be run as root.")
        sys.exit(1)

def run(cmd):
    if MODE == "--dry-run":
        print(f"[DRY-RUN] {cmd}")
        return
    subprocess.run(cmd, shell=True, check=True)

def exists(cmd):
    return subprocess.run(
        cmd,
        shell=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    ).returncode == 0

def report(line):
    print(line)
    with open(REPORT_FILE, "a") as f:
        f.write(line + "\n")

def header(title):
    report(f"\n=== {title} ===")

# ---------------- DAEMON HELPERS ----------------
def load_current_daemon_config():
    if Path(DAEMON_JSON).exists():
        with open(DAEMON_JSON) as f:
            return json.load(f)
    return {}

def daemon_config_compliant(current):
    for key, value in DESIRED_DAEMON_CONFIG.items():
        if current.get(key) != value:
            return False
    return True

# ---------------- APPLY ----------------
def apply_daemon_config():
    header("APPLYING DOCKER DAEMON CONFIGURATION")

    Path("/etc/docker").mkdir(exist_ok=True)

    current = load_current_daemon_config()
    updated = current.copy()
    updated.update(DESIRED_DAEMON_CONFIG)

    if current != updated:
        report("[INFO] Docker daemon configuration requires update")
        if MODE != "--dry-run":
            with open(DAEMON_JSON, "w") as f:
                json.dump(updated, f, indent=2)
        run("systemctl restart docker")
        report("[OK] Docker daemon configuration applied")
    else:
        report("[OK] Docker daemon configuration already compliant")

# ---------------- AUDIT ----------------
def audit_daemon_config():
    header("DAEMON CONFIGURATION AUDIT")

    current = load_current_daemon_config()
    for key, value in DESIRED_DAEMON_CONFIG.items():
        status = "PASS" if current.get(key) == value else "FAIL"
        report(f"[{status}] {key}")

def audit_running_containers():
    header("RUNNING CONTAINER AUDIT")

    if not exists("docker ps"):
        report("[WARN] Docker not running or not accessible")
        return

    result = subprocess.run(
        "docker ps -q",
        shell=True,
        capture_output=True,
        text=True
    )

    containers = result.stdout.splitlines()
    if not containers:
        report("[OK] No running containers detected")
        return

    for cid in containers:
        inspect = subprocess.run(
            f"docker inspect {cid}",
            shell=True,
            capture_output=True,
            text=True
        )
        data = json.loads(inspect.stdout)[0]
        name = data["Name"].lstrip("/")

        if data["HostConfig"].get("Privileged"):
            report(f"[FAIL] Privileged container: {name}")

        for m in data.get("Mounts", []):
            src = m.get("Source", "")
            if src in ["/", "/var/run/docker.sock"]:
                report(f"[FAIL] Dangerous mount in {name}: {src}")

def audit_root_docker_access():
    header("ROOT DOCKER ACCESS AUDIT")

    if exists("docker ps"):
        report("[WARN] Docker CLI usable as root")
        report("       Recommendation: restrict docker.sock via group")
    else:
        report("[OK] Docker CLI not usable as root")

# ---------------- MAIN ----------------
def main():
    if MODE not in ["--apply", "--check", "--dry-run"]:
        print("Usage: docker_daemon_standards.py [--apply | --check | --dry-run]")
        sys.exit(1)

    require_root()

    with open(REPORT_FILE, "w") as f:
        f.write(f"Docker Daemon Compliance Report - {datetime.now()}\n")

    if MODE == "--apply":
        apply_daemon_config()

    audit_daemon_config()
    audit_running_containers()
    audit_root_docker_access()

    print("\n🎉 DOCKER DAEMON STANDARDS COMPLETE")
    print(f"📋 Report: {REPORT_FILE}")

if __name__ == "__main__":
    main()
