#!/usr/bin/env python3

import os
import sys
import shutil
import subprocess
import platform
from pathlib import Path

DAYS = 825


# ======================================================
# Logging
# ======================================================

def info(msg): print(f"👉 {msg}")
def ok(msg): print(f"✅ {msg}")
def warn(msg): print(f"⚠️  {msg}")

def fail(msg):
    print(f"❌ {msg}")
    sys.exit(1)


# ======================================================
# Helpers
# ======================================================

def exists(cmd):
    return shutil.which(cmd) is not None


def run(cmd, shell=False, check=True):
    try:
        subprocess.run(cmd, shell=shell, check=check)
    except Exception:
        if check:
            fail(f"Command failed: {cmd}")


# ======================================================
# OpenSSL detection
# ======================================================

def find_openssl():
    exe = shutil.which("openssl")
    if exe:
        return exe

    # windows common paths
    if platform.system() == "Windows":
        paths = [
            r"C:\Program Files\OpenSSL-Win64\bin\openssl.exe",
            r"C:\Program Files (x86)\OpenSSL-Win32\bin\openssl.exe",
            r"C:\ProgramData\chocolatey\bin\openssl.exe",
        ]
        for p in paths:
            if os.path.exists(p):
                return p

    return None


# ======================================================
# Installer (SAFE — never crashes)
# ======================================================

def install_openssl():
    system = platform.system()

    warn("OpenSSL not found. Attempting install...")

    try:

        # ---------- Linux ----------
        if system == "Linux":

            if exists("apt"):
                run(["sudo", "apt", "update"])
                run(["sudo", "apt", "install", "-y", "openssl"])

            elif exists("dnf"):
                run(["sudo", "dnf", "install", "-y", "openssl"])

        # ---------- macOS ----------
        elif system == "Darwin":

            if exists("brew"):
                run(["brew", "install", "openssl"])

        # ---------- Windows ----------
        elif system == "Windows":

            # IMPORTANT: DO NOT CHECK RETURN CODE
            if exists("winget"):
                info("Installing via winget (ignoring exit codes)...")
                subprocess.run(
                    "winget install -e --id ShiningLight.OpenSSL.Light -h",
                    shell=True
                )

            elif exists("choco"):
                info("Installing via chocolatey...")
                subprocess.run(
                    "choco install openssl -y",
                    shell=True
                )

        # Never fail here — just try detection later

    except Exception:
        pass


# ======================================================
# Config
# ======================================================

def create_config(domain, path):
    path.write_text(f"""
[req]
prompt = no
default_bits = 2048
default_md = sha256
distinguished_name = dn
x509_extensions = v3_req

[dn]
CN={domain}

[v3_req]
subjectAltName = @alt_names

[alt_names]
DNS.1 = {domain}
DNS.2 = *.{domain}
""")


# ======================================================
# Generate certificate
# ======================================================

def generate(domain):

    openssl = find_openssl()

    if not openssl:
        install_openssl()
        openssl = find_openssl()

    if not openssl:
        fail(
            "\nOpenSSL still not detected.\n"
            "👉 Restart terminal OR install manually:\n"
            "https://slproweb.com/products/Win32OpenSSL.html\n"
        )

    ok(f"Using OpenSSL → {openssl}")

    cert_dir = Path(f"../certificates/{domain}")
    cert_dir.mkdir(exist_ok=True)

    key = cert_dir / f"{domain}.key"
    crt = cert_dir / f"{domain}.crt"
    cnf = cert_dir / f"{domain}.cnf"

    create_config(domain, cnf)

    info("Generating certificate...")

    run([
        openssl,
        "req",
        "-x509",
        "-nodes",
        "-days", str(DAYS),
        "-newkey", "rsa:2048",
        "-keyout", str(key),
        "-out", str(crt),
        "-config", str(cnf)
    ])

    ok("Certificate created successfully!\n")
    print(f"🔑 {key}")
    print(f"📜 {crt}")


# ======================================================
# Main
# ======================================================

if __name__ == "__main__":

    if len(sys.argv) != 2:
        print("Usage: python generate_certificate.py sid.lab")
        sys.exit(1)

    generate(sys.argv[1])
