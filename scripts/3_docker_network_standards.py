#!/usr/bin/env python3
"""
DOCKER NETWORK STANDARDS – ENFORCER & AUDITOR (LINUX)
===================================================

Ensures Docker network segmentation standards are met.

STANDARDS IMPLEMENTED
--------------------
3.1 Network Types
- frontend_net   : Public-facing (reverse proxy only)
- backend_net    : Internal services (internal-only)
- monitoring_net : Monitoring stack (internal-only)

3.2 Network Rules
- Internal networks must not have external connectivity
- Networks must exist before container deployment
- Containers must explicitly join required networks
- Network misuse is audited (not auto-fixed)

MODES
-----
--apply     Create missing networks + audit (default)
--check     Audit only (no changes)
--dry-run   Show actions without executing

SAFETY
------
✔ Idempotent
✔ No container restarts
✔ No container disconnections
✔ No network deletions
"""

import os
import sys
import subprocess
import json
from datetime import datetime

# ---------------- CONFIG ----------------
MODE = "--apply" if len(sys.argv) == 1 else sys.argv[1]
REPORT_FILE = "/var/log/docker-network-compliance.txt"

NETWORKS = {
    "frontend_net": {
        "internal": False,
        "description": "Public-facing reverse proxy network"
    },
    "backend_net": {
        "internal": True,
        "description": "Internal application and database network"
    },
    "monitoring_net": {
        "internal": True,
        "description": "Internal monitoring and observability network"
    }
}

# ---------------- UTILS ----------------
def require_root():
    if os.geteuid() != 0:
        print("❌ Must be run as root")
        sys.exit(1)

def run(cmd):
    if MODE == "--dry-run":
        print(f"[DRY-RUN] {cmd}")
        return ""
    return subprocess.run(cmd, shell=True, capture_output=True, text=True).stdout

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

# ---------------- NETWORK HELPERS ----------------
def network_exists(name):
    return exists(f"docker network inspect {name}")

def inspect_network(name):
    output = subprocess.run(
        f"docker network inspect {name}",
        shell=True,
        capture_output=True,
        text=True
    ).stdout
    return json.loads(output)[0]

# ---------------- APPLY ----------------
def apply_networks():
    header("NETWORK CREATION & VALIDATION")

    for name, cfg in NETWORKS.items():
        if not network_exists(name):
            report(f"[INFO] Network missing, creating: {name}")
            cmd = f"docker network create {'--internal ' if cfg['internal'] else ''}{name}"
            run(cmd)
            report(f"[OK] Network created: {name}")
        else:
            report(f"[OK] Network exists: {name}")

        data = inspect_network(name)
        actual_internal = data.get("Internal")

        if actual_internal == cfg["internal"]:
            report(f"[PASS] {name} internal={actual_internal}")
        else:
            report(f"[FAIL] {name} internal={actual_internal} (expected {cfg['internal']})")

# ---------------- AUDIT ----------------
def audit_container_networks():
    header("CONTAINER NETWORK AUDIT")

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
        networks = list(data["NetworkSettings"]["Networks"].keys())

        if len(networks) == 0:
            report(f"[WARN] Container '{name}' has no network attached")

        if len(networks) > 1:
            report(f"[WARN] Container '{name}' attached to multiple networks: {networks}")

        for net in networks:
            if net not in NETWORKS:
                report(f"[WARN] Container '{name}' uses unmanaged network: {net}")

        if "frontend_net" in networks and name.lower() not in ["traefik", "nginx", "caddy"]:
            report(f"[WARN] Non-proxy container attached to frontend_net: {name}")

# ---------------- MAIN ----------------
def main():
    if MODE not in ["--apply", "--check", "--dry-run"]:
        print("Usage: docker_network_standards.py [--apply | --check | --dry-run]")
        sys.exit(1)

    require_root()

    with open(REPORT_FILE, "w") as f:
        f.write(f"Docker Network Compliance Report - {datetime.now()}\n")

    if MODE == "--apply":
        apply_networks()
    else:
        header("NETWORK CONFIGURATION CHECK")
        for name, cfg in NETWORKS.items():
            if not network_exists(name):
                report(f"[FAIL] Missing network: {name}")
            else:
                data = inspect_network(name)
                report(
                    f"[{'PASS' if data['Internal'] == cfg['internal'] else 'FAIL'}] "
                    f"{name} internal={data['Internal']}"
                )

    audit_container_networks()

    print("\n🎉 DOCKER NETWORK STANDARDS COMPLETE")
    print(f"📋 Report: {REPORT_FILE}")

if __name__ == "__main__":
    main()
