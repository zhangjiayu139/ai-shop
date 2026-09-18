#!/usr/bin/env python3
"""Safely enable TaoAi reseller mode on an existing deployment."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
from datetime import datetime, timezone

import yaml


DEFAULT_ROOT = Path("/opt/taoai-shop")
DEFAULT_MAIN_HOST = "shop.edujerry.icu"
LOCAL_MAIN_HOSTS = ["localhost", "127.0.0.1", "::1"]


def run(*args: str, cwd: Path | None = None) -> str:
    return subprocess.check_output(args, cwd=cwd, text=True).strip()


def build_reseller_config(config: dict, main_host: str) -> dict:
    if not isinstance(config, dict):
        raise ValueError("config.yml root must be a mapping")

    reseller = config.setdefault("reseller", {})
    if not isinstance(reseller, dict):
        raise ValueError("config.yml reseller must be a mapping")

    existing_hosts = reseller.get("main_hosts") or []
    if not isinstance(existing_hosts, list):
        raise ValueError("reseller.main_hosts must be a list")

    main_hosts: list[str] = []
    for host in [main_host, *LOCAL_MAIN_HOSTS, *existing_hosts]:
        normalized = str(host).strip().lower().rstrip(".")
        if normalized and normalized not in main_hosts:
            main_hosts.append(normalized)

    reseller.update(
        enabled=True,
        main_hosts=main_hosts,
        trusted_forwarded_host=False,
        self_apply_enabled=True,
        settlement_confirm_days=7,
    )
    reseller.setdefault("subdomain_base", "")
    return config


def summary(config: dict) -> dict:
    reseller = config["reseller"]
    return {
        "enabled": reseller["enabled"],
        "main_hosts": reseller["main_hosts"],
        "trusted_forwarded_host": reseller["trusted_forwarded_host"],
        "subdomain_base": reseller.get("subdomain_base", ""),
        "self_apply_enabled": reseller["self_apply_enabled"],
        "settlement_confirm_days": reseller["settlement_confirm_days"],
    }


def atomic_write_yaml(path: Path, config: dict) -> None:
    stat = path.stat()
    with tempfile.NamedTemporaryFile("w", dir=path.parent, delete=False) as handle:
        yaml.safe_dump(config, handle, allow_unicode=True, sort_keys=False)
        temp_path = Path(handle.name)
    os.chmod(temp_path, stat.st_mode & 0o777)
    os.chown(temp_path, stat.st_uid, stat.st_gid)
    os.replace(temp_path, path)


def wait_healthy(timeout_seconds: int = 120) -> None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        try:
            if run("docker", "inspect", "taoai-shop-app", "--format", "{{.State.Health.Status}}") == "healthy":
                return
        except subprocess.CalledProcessError:
            pass
        time.sleep(2)
    raise RuntimeError("taoai-shop-app did not become healthy in time")


def recreate_app(root: Path) -> None:
    subprocess.check_call(
        ["docker", "compose", "up", "-d", "--no-deps", "--force-recreate", "app"],
        cwd=root,
    )
    wait_healthy()


def apply(root: Path, main_host: str) -> Path:
    if os.geteuid() != 0:
        raise PermissionError("apply mode must run as root")

    config_path = root / "config.yml"
    changes_dir = root / "changes"
    changes_dir.mkdir(mode=0o700, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_path = changes_dir / f"config.before-reseller-{stamp}.yml"
    shutil.copy2(config_path, backup_path)
    os.chmod(backup_path, 0o600)

    config = yaml.safe_load(config_path.read_text())
    updated = build_reseller_config(config, main_host)
    try:
        atomic_write_yaml(config_path, updated)
        subprocess.check_call(["docker", "compose", "config", "--quiet"], cwd=root)
        recreate_app(root)
        run("curl", "-fsS", f"https://{main_host}/health")
    except Exception:
        shutil.copy2(backup_path, config_path)
        recreate_app(root)
        raise
    return backup_path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--main-host", default=DEFAULT_MAIN_HOST)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    config_path = args.root / "config.yml"
    config = yaml.safe_load(config_path.read_text())
    updated = build_reseller_config(config, args.main_host)
    if not args.apply:
        print(json.dumps(summary(updated), ensure_ascii=False, indent=2))
        return

    backup_path = apply(args.root, args.main_host)
    final_config = yaml.safe_load(config_path.read_text())
    print(json.dumps(summary(final_config), ensure_ascii=False, indent=2))
    print(f"backup={backup_path}")
    print("health=healthy")


if __name__ == "__main__":
    main()
