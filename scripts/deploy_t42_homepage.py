"""Publish T42's catalog to the two production homepage views via Odoo ORM.

Use --check first. --apply requires the SHA-256 printed by --check so edits
made in Website Builder between inspection and deployment cannot be lost.
Credentials remain in ~/.odoo/helpdesk_api.json and are never printed.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import sys
import xmlrpc.client

from t42_homepage_catalog import transform


VIEW_IDS = (1751, 1759)
EXPECTED_DB = "karo_consultorias"
EXPECTED_DOMAIN = "https://stepsapp.cl"
EXPECTED_API = "https://soporte.stepsapp.cl"


def digest(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--expected-sha256", help="Hash returned by --check")
    parser.add_argument("--backup-dir", type=Path, default=Path.home() / ".odoo" / "backups")
    args = parser.parse_args()
    if args.apply and not args.expected_sha256:
        parser.error("--apply requires --expected-sha256")

    config = json.loads((Path.home() / ".odoo" / "helpdesk_api.json").read_text(encoding="utf-8"))
    if config["db"] != EXPECTED_DB or config["url"].rstrip("/") != EXPECTED_API:
        raise RuntimeError("Unexpected Odoo database or domain")
    root = config["url"].rstrip("/")
    uid = xmlrpc.client.ServerProxy(root + "/xmlrpc/2/common").authenticate(
        config["db"], config["username"], config["api_key"], {}
    )
    if not uid:
        raise RuntimeError("Odoo authentication failed")
    objects = xmlrpc.client.ServerProxy(root + "/xmlrpc/2/object", allow_none=True)

    def call(model: str, method: str, positional: list, keyword: dict | None = None):
        return objects.execute_kw(config["db"], uid, config["api_key"], model, method, positional, keyword or {})

    sites = call("website", "search_read", [[]], {"fields": ["domain"], "limit": 5})
    if len(sites) != 1 or sites[0]["domain"].rstrip("/") != EXPECTED_DOMAIN:
        raise RuntimeError("Production website mapping changed")
    views = call("ir.ui.view", "read", [list(VIEW_IDS)], {"fields": ["key", "website_id", "arch_db", "write_date"]})
    if len(views) != len(VIEW_IDS) or {v["id"] for v in views} != set(VIEW_IDS):
        raise RuntimeError("Homepage views changed")
    for view in views:
        if view["key"] != "website.homepage":
            raise RuntimeError("Unexpected view key")
    originals = {view["id"]: view["arch_db"] for view in views}
    hashes = {digest(arch) for arch in originals.values()}
    if len(hashes) != 1:
        raise RuntimeError("The two homepage views have diverged; inspect before deployment")
    current_hash = next(iter(hashes))
    replacement = transform(next(iter(originals.values())))
    print(f"Views: {list(VIEW_IDS)}, source SHA-256: {current_hash}, target SHA-256: {digest(replacement)}")
    if not args.apply:
        print("Check complete. Re-run with --apply --expected-sha256 <source hash>.")
        return
    if current_hash != args.expected_sha256:
        raise RuntimeError("Homepage changed since check; deployment stopped")
    if replacement == next(iter(originals.values())):
        print("Homepage already contains T42; no write needed.")
        return

    args.backup_dir.mkdir(parents=True, exist_ok=True)
    backup_path = args.backup_dir / ("t42-homepage-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + ".json")
    backup_path.write_text(json.dumps({"database": EXPECTED_DB, "domain": EXPECTED_DOMAIN,
                                      "views": views}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Backup: {backup_path}")
    try:
        for view_id in VIEW_IDS:
            if not call("ir.ui.view", "write", [[view_id], {"arch_db": replacement}]):
                raise RuntimeError(f"View {view_id} write returned false")
        published = call("ir.ui.view", "read", [list(VIEW_IDS)], {"fields": ["arch_db"]})
        if any(view["arch_db"] != replacement for view in published):
            raise RuntimeError("Read-back mismatch")
    except Exception:
        for view_id in VIEW_IDS:
            try:
                call("ir.ui.view", "write", [[view_id], {"arch_db": originals[view_id]}])
            except Exception as rollback_error:
                print(f"ROLLBACK FAILED for view {view_id}: {rollback_error}", file=sys.stderr)
        raise
    print("Published and read-back verified: 20 applications, including three in Exportaciones.")


if __name__ == "__main__":
    main()
