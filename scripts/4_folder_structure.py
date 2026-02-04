#!/usr/bin/env python3
"""
HOMELAB FOLDER STRUCTURE - ENFORCER (ENV AWARE)
===============================================
Enforces Section 13: Folder Structure.
Reads configuration from a local .env file.
"""

import os
import sys
from pathlib import Path

# ---------------- CONFIG LOADER ----------------
def load_env(env_path):
    config = {}
    if not os.path.exists(env_path):
        print(f"❌ Error: .env file not found at {env_path}")
        print("Please create it with SERVER_ROOT, PUID, and PGID.")
        sys.exit(1)
    
    print(f"Loading config from {env_path}...")
    with open(env_path, "r") as f:
        for line in f:
            # Skip comments and empty lines
            if line.strip().startswith("#") or not line.strip():
                continue
            if "=" in line:
                key, value = line.strip().split("=", 1)
                config[key.strip()] = value.strip()
    return config

# ---------------- SETUP ----------------
ENV_FILE = Path(__file__).parent / "../.env"
CONFIG = load_env(ENV_FILE)

# Extract values with fallbacks or errors
try:
    SERVER_ROOT = Path(CONFIG["SERVER_ROOT"])
    PUID = CONFIG["PUID"]
    PGID = CONFIG["PGID"]
except KeyError as e:
    print(f"❌ Error: Missing {e} in .env file.")
    sys.exit(1)

STRUCTURE = [
    "apps",
    "secrets",
    "networks",
    "backups/snapshots",
    "backups/databases",
    "backups/restore",
    "scripts",
    "logs/docker"
]

# ---------------- EXECUTION ----------------
def run(cmd):
    # print(f"[EXEC] {cmd}") # Uncomment for verbose debug
    os.system(cmd)

def apply():
    if os.geteuid() != 0:
        print("❌ Must run as root to set permissions (chown/chmod)")
        sys.exit(1)

    print(f"=== Target: {SERVER_ROOT} ===")
    print(f"=== Owner:  User {PUID} / Group {PGID} ===")
    
    # 1. Create Base Directory
    if not SERVER_ROOT.exists():
        try:
            SERVER_ROOT.mkdir(parents=True, exist_ok=True)
            print(f"✔ Created root: {SERVER_ROOT}")
        except Exception as e:
            print(f"❌ Failed to create root: {e}")
            sys.exit(1)

    # 2. Create Subdirectories
    for folder in STRUCTURE:
        path = SERVER_ROOT / folder
        path.mkdir(parents=True, exist_ok=True)
        print(f"✔ Verified/Created: {folder}")

    # 3. Create Placeholder Files
    (SERVER_ROOT / "compose.yaml").touch()
    (SERVER_ROOT / "networks/docker-networks.yaml").touch()

    # 4. Enforce Ownership (Using PUID/PGID from .env)
    print("\n=== Enforcing Permissions ===")
    
    # Set global ownership to PUID:PGID
    run(f"chown -R {PUID}:{PGID} {SERVER_ROOT}")
    
    # Standard 6.1: Secrets must be strict (Root owned)
    secrets_dir = SERVER_ROOT / "secrets"
    run(f"chown -R root:root {secrets_dir}")
    run(f"chmod -R 700 {secrets_dir}")
    print(f"✔ Secured: {secrets_dir} (Root only)")

    # Standard Directory Permissions (775 allows group write, good for automation)
    # We exclude secrets dir from this bulk change
    run(f"find {SERVER_ROOT} -type d -not -path '*/secrets*' -exec chmod 775 {{}} +")
    run(f"find {SERVER_ROOT} -type f -not -path '*/secrets*' -exec chmod 664 {{}} +")
    
    print("\n🎉 Folder Structure Enforced based on .env configuration.")

if __name__ == "__main__":
    apply()