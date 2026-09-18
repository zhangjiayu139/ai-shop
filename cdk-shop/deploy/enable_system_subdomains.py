#!/usr/bin/env python3
"""Enable TaoAi system subdomains with a Cloudflare Origin certificate."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
import os
import shutil
import subprocess
import tempfile
import time

import yaml


SHOP_ROOT = Path("/opt/taoai-shop")
CADDY_ROOT = Path("/opt/gpt-cdk")
CADDYFILE = CADDY_ROOT / "Caddyfile"
CONFIG_FILE = SHOP_ROOT / "config.yml"
CERT_FILE = CADDY_ROOT / "caddy-data/taoai-origin/wildcard-edujerry.pem"
KEY_FILE = CADDY_ROOT / "caddy-data/taoai-origin/wildcard-edujerry.key"
MAIN_HOST = "shop.edujerry.icu"
SUBDOMAIN_BASE = "edujerry.icu"
PROBE_HOST = "reseller-probe-20260918.edujerry.icu"
PROXIED_COMPATIBILITY_HOST = "sub.edujerry.icu"
SHOP_START = "# BEGIN TAOAI-SHOP"
SHOP_END = "# END TAOAI-SHOP"
WILDCARD_START = "# BEGIN TAOAI-RESELLER-WILDCARD"
WILDCARD_END = "# END TAOAI-RESELLER-WILDCARD"


def output(*args: str, cwd: Path | None = None) -> str:
    return subprocess.check_output(args, cwd=cwd, text=True).strip()


def call(*args: str, cwd: Path | None = None) -> None:
    subprocess.check_call(args, cwd=cwd)


def build_wildcard_caddyfile(source: str) -> str:
    has_start = WILDCARD_START in source
    has_end = WILDCARD_END in source
    if has_start != has_end:
        raise ValueError("incomplete wildcard reseller block markers")
    if has_start:
        return source
    start = source.find(SHOP_START)
    end = source.find(SHOP_END, start)
    if start < 0 or end < 0:
        raise ValueError("TaoAi shop Caddy block markers not found")
    end += len(SHOP_END)
    shop_section = source[start:end]
    opening = f"{MAIN_HOST} {{"
    if shop_section.count(opening) != 1:
        raise ValueError("unexpected TaoAi shop host block")
    wildcard_section = shop_section.replace(SHOP_START, WILDCARD_START, 1)
    wildcard_section = wildcard_section.replace(SHOP_END, WILDCARD_END, 1)
    wildcard_section = wildcard_section.replace(
        opening,
        "*.edujerry.icu {\n"
        "    tls /data/taoai-origin/wildcard-edujerry.pem "
        "/data/taoai-origin/wildcard-edujerry.key",
        1,
    )
    return source[:end] + "\n\n" + wildcard_section + source[end:]


def build_shop_config(source: str) -> str:
    config = yaml.safe_load(source)
    if not isinstance(config, dict) or not isinstance(config.get("reseller"), dict):
        raise ValueError("reseller configuration is missing")
    reseller = config["reseller"]
    if reseller.get("enabled") is not True:
        raise ValueError("reseller mode must be enabled first")
    main_hosts = [str(value).strip().lower().rstrip(".") for value in reseller.get("main_hosts", [])]
    if MAIN_HOST not in main_hosts:
        raise ValueError("main storefront host is missing")
    reseller["subdomain_base"] = SUBDOMAIN_BASE
    return yaml.safe_dump(config, allow_unicode=True, sort_keys=False)


def replace_preserving_metadata(path: Path, content: str, preserve_inode: bool = False) -> None:
    stat = path.stat()
    if preserve_inode:
        path.write_text(content)
        os.chmod(path, stat.st_mode & 0o777)
        os.chown(path, stat.st_uid, stat.st_gid)
        return
    with tempfile.NamedTemporaryFile("w", dir=path.parent, delete=False) as handle:
        handle.write(content)
        temp_path = Path(handle.name)
    os.chmod(temp_path, stat.st_mode & 0o777)
    os.chown(temp_path, stat.st_uid, stat.st_gid)
    os.replace(temp_path, path)


def verify_certificate() -> None:
    if not CERT_FILE.is_file() or not KEY_FILE.is_file():
        raise FileNotFoundError("Cloudflare Origin certificate or private key is missing")
    call("openssl", "x509", "-in", str(CERT_FILE), "-checkend", "2592000", "-noout")
    cert_text = output("openssl", "x509", "-in", str(CERT_FILE), "-noout", "-ext", "subjectAltName")
    if "DNS:*.edujerry.icu" not in cert_text:
        raise ValueError("Origin certificate does not cover *.edujerry.icu")
    cert_public = output("openssl", "x509", "-in", str(CERT_FILE), "-pubkey", "-noout")
    key_public = output("openssl", "pkey", "-in", str(KEY_FILE), "-pubout")
    if cert_public != key_public:
        raise ValueError("Origin certificate and private key do not match")


def wait_app_healthy(timeout_seconds: int = 120) -> None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        try:
            if output("docker", "inspect", "taoai-shop-app", "--format", "{{.State.Health.Status}}") == "healthy":
                return
        except subprocess.CalledProcessError:
            pass
        time.sleep(2)
    raise RuntimeError("taoai-shop-app did not become healthy in time")


def reload_caddy() -> None:
    call("docker", "exec", "gpt-cdk-caddy", "caddy", "validate", "--config", "/etc/caddy/Caddyfile")
    call("docker", "exec", "gpt-cdk-caddy", "caddy", "reload", "--config", "/etc/caddy/Caddyfile")


def recreate_app() -> None:
    call("docker", "compose", "up", "-d", "--no-deps", "--force-recreate", "app", cwd=SHOP_ROOT)
    wait_app_healthy()


def public_status(host: str, path: str = "/") -> str:
    return output("curl", "-sS", "-o", "/dev/null", "-w", "%{http_code}", f"https://{host}{path}")


def wait_public_status(host: str, path: str, expected: str, timeout_seconds: int = 60) -> None:
    deadline = time.monotonic() + timeout_seconds
    last_status = "unavailable"
    while time.monotonic() < deadline:
        try:
            last_status = public_status(host, path)
            if last_status == expected:
                return
        except subprocess.CalledProcessError:
            last_status = "request_failed"
        time.sleep(2)
    raise RuntimeError(f"unexpected public status for {host}{path}: {last_status}, expected {expected}")


def wait_public_tls(host: str, timeout_seconds: int = 60) -> str:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        try:
            status = public_status(host)
            if status != "000":
                return status
        except subprocess.CalledProcessError:
            pass
        time.sleep(2)
    raise RuntimeError(f"public TLS verification failed for {host}")


def apply() -> tuple[Path, Path]:
    if os.geteuid() != 0:
        raise PermissionError("this script must run as root")
    verify_certificate()

    current_caddy = CADDYFILE.read_text()
    current_config = CONFIG_FILE.read_text()
    next_caddy = build_wildcard_caddyfile(current_caddy)
    next_config = build_shop_config(current_config)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    caddy_changes = CADDY_ROOT / "changes"
    shop_changes = SHOP_ROOT / "changes"
    caddy_changes.mkdir(mode=0o700, exist_ok=True)
    shop_changes.mkdir(mode=0o700, exist_ok=True)
    caddy_backup = caddy_changes / f"Caddyfile.before-reseller-wildcard-{stamp}"
    config_backup = shop_changes / f"config.before-reseller-wildcard-{stamp}.yml"
    shutil.copy2(CADDYFILE, caddy_backup)
    shutil.copy2(CONFIG_FILE, config_backup)
    os.chmod(caddy_backup, 0o600)
    os.chmod(config_backup, 0o600)

    try:
        replace_preserving_metadata(CADDYFILE, next_caddy, preserve_inode=True)
        reload_caddy()
        replace_preserving_metadata(CONFIG_FILE, next_config)
        recreate_app()
        wait_public_status(MAIN_HOST, "/health", "200")
        wait_public_status(PROBE_HOST, "/api/v1/public/config", "404")
        wait_public_tls(PROXIED_COMPATIBILITY_HOST)
    except Exception:
        shutil.copyfile(caddy_backup, CADDYFILE)
        reload_caddy()
        shutil.copy2(config_backup, CONFIG_FILE)
        recreate_app()
        raise
    return caddy_backup, config_backup


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if not args.apply:
        verify_certificate()
        build_wildcard_caddyfile(CADDYFILE.read_text())
        build_shop_config(CONFIG_FILE.read_text())
        print(f"planned_subdomain_base={SUBDOMAIN_BASE}")
        print("certificate_and_config_check=ok")
        return

    caddy_backup, config_backup = apply()
    print(f"caddy_backup={caddy_backup}")
    print(f"config_backup={config_backup}")
    print(f"subdomain_base={SUBDOMAIN_BASE}")
    print(f"main_health={public_status(MAIN_HOST, '/health')}")
    print(f"unassigned_domain={public_status(PROBE_HOST, '/api/v1/public/config')}")
    print(f"proxied_compatibility_host={public_status(PROXIED_COMPATIBILITY_HOST)}")


if __name__ == "__main__":
    main()
