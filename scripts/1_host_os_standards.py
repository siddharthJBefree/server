#!/usr/bin/env python3
"""
HOST OPERATING SYSTEM STANDARDS - ENFORCER & AUDITOR (LINUX)
===========================================================

MODES
-----
sudo python3 1_host_os_standards.py --apply     Apply standards (default)
sudo python3 1_host_os_standards.py --check     Audit-only (no changes)
sudo python3 1_host_os_standards.py --dry-run   Show commands without executing

FEATURES
--------
✔ Least-privilege Docker access (doc_user)
✔ User Namespace Remapping Prep (dockremap)  <-- NEW
✔ Dedicated Docker user/group
✔ Firewall + Fail2ban
✔ Automatic updates
✔ System log monitoring
✔ Compliance reporting

SUPPORTED
---------
Ubuntu LTS / Debian Stable
"""

import os
import sys
import subprocess
from pathlib import Path
from datetime import datetime

# ---------------- CONFIG ----------------
DOCKER_USER = "doc_user"
DOCKER_GROUP = "doc_group"
DOCKER_REMAP_USER = "dockremap"  # Standard user for userns-remap
ALLOWED_PORTS = ["22", "80", "443"]

REPORT_FILE = "/var/log/docker-host-compliance.txt"
MODE = "--apply" if len(sys.argv) == 1 else sys.argv[1]

# ---------------- UTILS ----------------
def is_root():
    return os.geteuid() == 0

def run(cmd):
    if MODE == "--dry-run":
        print(f"[DRY-RUN] {cmd}")
        return
    subprocess.run(cmd, shell=True, check=True)

def exists(cmd):
    return subprocess.run(
        cmd, shell=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    ).returncode == 0

def file_contains(path, text):
    """Checks if a file contains a specific string."""
    if not os.path.exists(path):
        return False
    try:
        with open(path, 'r') as f:
            return text in f.read()
    except Exception:
        return False

def append_if_missing(path, text):
    """Appends text to a file only if it's missing."""
    if not file_contains(path, text):
        if MODE == "--dry-run":
            print(f"[DRY-RUN] Append '{text}' to {path}")
        else:
            with open(path, "a") as f:
                f.write(text + "\n")
            print(f"✔ Appended configuration to {path}")

def report(line):
    print(line)
    with open(REPORT_FILE, "a") as f:
        f.write(line + "\n")

def header(title):
    report(f"\n=== {title} ===")

# ---------------- AUDIT ----------------
def audit():
    header("AUDIT RESULTS")

    checks = {
        "Docker user exists":
            exists(f"id {DOCKER_USER}"),
        "Docker group exists":
            exists(f"getent group {DOCKER_GROUP}"),
        "Remap user (dockremap) exists":
            exists(f"id {DOCKER_REMAP_USER}"),
        "Subuid configured":
            file_contains("/etc/subuid", f"{DOCKER_REMAP_USER}:100000:65536"),
        "Subgid configured":
            file_contains("/etc/subgid", f"{DOCKER_REMAP_USER}:100000:65536"),
        "Root login disabled":
            exists("passwd -S root | grep L"),
        "Firewall enabled":
            exists("ufw status | grep -q active"),
        "Fail2ban running":
            exists("systemctl is-active fail2ban"),
        "Auto updates enabled":
            exists("systemctl is-enabled unattended-upgrades"),
    }

    for item, ok in checks.items():
        report(f"[{'PASS' if ok else 'FAIL'}] {item}")

# ---------------- APPLY ----------------
def apply():
    if not is_root():
        print("❌ Must be run as root")
        sys.exit(1)

    header("APPLYING STANDARDS")

    # 1. Main Docker User / Group
    run(f"getent group {DOCKER_GROUP} || groupadd {DOCKER_GROUP}")
    run(f"id {DOCKER_USER} || useradd -m -s /bin/bash {DOCKER_USER}")
    run(f"usermod -aG {DOCKER_GROUP} {DOCKER_USER}")

    # 2. Namespace Remapping User (dockremap)
    # Necessary for "userns-remap": "default" in daemon.json
    if not exists(f"id {DOCKER_REMAP_USER}"):
        run(f"adduser --system --no-create-home --group {DOCKER_REMAP_USER}")
        print(f"✔ Created system user: {DOCKER_REMAP_USER}")
    
    # Configure subuid/subgid range (100000-165536)
    remap_config = f"{DOCKER_REMAP_USER}:100000:65536"
    append_if_missing("/etc/subuid", remap_config)
    append_if_missing("/etc/subgid", remap_config)

    # 3. Docker Daemon Hardening (Base)
    # Note: Full hardening is enforced in script 2, but we prep the override here
    override = "/etc/systemd/system/docker.service.d/override.conf"
    Path(os.path.dirname(override)).mkdir(parents=True, exist_ok=True)
    if MODE != "--dry-run":
        Path(override).write_text(
            f"[Service]\nExecStart=\nExecStart=/usr/bin/dockerd --group={DOCKER_GROUP}\n"
        )
    run("systemctl daemon-reexec")
    
    # 4. Host Security
    run("passwd -l root") # Lock root account

    # Firewall & Tools
    run("apt update && apt install -y ufw fail2ban unattended-upgrades rsyslog logrotate")
    
    # UFW Configuration
    run("ufw default deny incoming")
    run("ufw default allow outgoing")
    for p in ALLOWED_PORTS:
        run(f"ufw allow {p}")
    
    # Only enable if not already active to avoid disrupting connection
    if not exists("ufw status | grep -q active"):
        run("ufw --force enable")

    # Fail2ban
    run("systemctl enable --now fail2ban")

    # Logs Persistence
    journald = "/etc/systemd/journald.conf"
    append_if_missing(journald, "Storage=persistent")
    run("systemctl restart systemd-journald")

    report("✔ APPLY COMPLETE")

# ---------------- MAIN ----------------
def main():
    if MODE not in ["--apply", "--check", "--dry-run"]:
        print("Usage: script.py [--apply | --check | --dry-run]")
        sys.exit(1)

    with open(REPORT_FILE, "w") as f:
        f.write(f"Compliance Report - {datetime.now()}\n")

    if MODE == "--check":
        audit()
    else:
        apply()
        audit()

if __name__ == "__main__":
    main()