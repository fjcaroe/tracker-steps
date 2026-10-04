"""Download ticket attachments to a private artifact directory (read-only RPC)."""
import argparse
import base64
import json
from pathlib import Path
import xmlrpc.client


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ticket", type=int, required=True)
    parser.add_argument("--config", type=Path, default=Path.home() / ".odoo/helpdesk_api.json")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.ticket <= 0:
        parser.error("ticket must be positive")
    output = args.output or Path.home() / ".codex/local-artifacts" / f"ticket-{args.ticket}" / "attachments"
    output = output.resolve()
    repository = Path(__file__).resolve().parents[2]
    if output.is_relative_to(repository):
        parser.error("attachments must be saved outside the checkout")
    config = json.loads(args.config.read_text(encoding="utf-8-sig"))
    url = config.get("url", "https://soporte.stepsapp.cl").rstrip("/")
    if not url.startswith("https://"):
        parser.error("the RPC endpoint must use HTTPS")
    uid = xmlrpc.client.ServerProxy(url + "/xmlrpc/2/common").authenticate(
        config["db"], config["username"], config["api_key"], {})
    if not uid:
        raise RuntimeError("Authentication failed")
    attachments = xmlrpc.client.ServerProxy(url + "/xmlrpc/2/object").execute_kw(
        config["db"], uid, config["api_key"], "ir.attachment", "search_read",
        [[("res_model", "=", "helpdesk.ticket"), ("res_id", "=", args.ticket)]],
        {"fields": ["id", "name", "datas"], "order": "id"})
    output.mkdir(parents=True, exist_ok=True)
    count = 0
    for attachment in attachments:
        if not attachment["datas"]:
            continue
        # IDs prevent name collisions. Strip any path components supplied remotely.
        name = Path(str(attachment["name"]).replace("\\", "/")).name
        name = "".join(c if c.isalnum() or c in " ._-" else "_" for c in name).strip(" .") or "attachment"
        target = output / f"{attachment['id']}-{name}"
        with target.open("xb") as stream:
            stream.write(base64.b64decode(attachment["datas"]))
        count += 1
    print(f"Downloaded {count} attachment(s) to {output}")


if __name__ == "__main__":
    main()
