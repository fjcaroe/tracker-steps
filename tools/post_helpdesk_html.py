"""Post formatted Helpdesk evidence through Odoo XML-RPC over HTTPS.

The local API config supplies the database, user, and key. Its stored URL is
ignored so older IP-based settings cannot send credentials over plain HTTP.
"""

import argparse
import json
import re
import xmlrpc.client
from pathlib import Path


SUPPORT_URL = "https://soporte.stepsapp.cl"
DEFAULT_CONFIG = Path.home() / ".odoo" / "helpdesk_api.json"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ticket_id", type=int)
    parser.add_argument("html_file", type=Path)
    parser.add_argument("--internal", action="store_true", help="Publish as an internal note")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--post", action="store_true", help="Actually publish; omitted for a local check")
    args = parser.parse_args()

    body = args.html_file.read_text(encoding="utf-8").strip()
    if not re.search(r"<(?:p|br|ul|ol|li|h[1-6]|div|strong|b|a)\b", body, re.I):
        parser.error("The file must contain HTML paragraphs, headings, lists, or links")
    if re.search(r"&lt;/?(?:p|br|ul|ol|li|h[1-6])\b", body, re.I):
        parser.error("The file contains escaped HTML tags; write actual HTML before posting")
    if len(re.findall(r"<br\b", body, re.I)) > 8 and len(re.findall(r"<p\b", body, re.I)) <= 1:
        parser.error("Split the long note into paragraphs, headings, and lists instead of many <br> tags")

    subtype = "mail.mt_note" if args.internal else "mail.mt_comment"
    if not args.post:
        print(f"CHECK_OK ticket={args.ticket_id} subtype={subtype} html_chars={len(body)}")
        return

    config = json.loads(args.config.read_text(encoding="utf-8"))
    common = xmlrpc.client.ServerProxy(f"{SUPPORT_URL}/xmlrpc/2/common")
    uid = common.authenticate(config["db"], config["username"], config["api_key"], {})
    if not uid:
        raise RuntimeError("Helpdesk authentication failed")
    models = xmlrpc.client.ServerProxy(f"{SUPPORT_URL}/xmlrpc/2/object")
    ticket = models.execute_kw(
        config["db"], uid, config["api_key"], "helpdesk.ticket", "read",
        [[args.ticket_id]], {"fields": ["name"]},
    )
    if len(ticket) != 1:
        raise RuntimeError(f"Ticket {args.ticket_id} does not exist or is not readable")

    message_id = models.execute_kw(
        config["db"], uid, config["api_key"], "helpdesk.ticket", "message_post",
        [[args.ticket_id]], {
            "body": body,
            "body_is_html": True,
            "message_type": "comment",
            "subtype_xmlid": subtype,
        },
    )
    message = models.execute_kw(
        config["db"], uid, config["api_key"], "mail.message", "read",
        [[message_id]], {"fields": ["body", "model", "res_id"]},
    )[0]
    stored_body = message["body"] or ""
    if message["model"] != "helpdesk.ticket" or message["res_id"] != args.ticket_id:
        raise RuntimeError(f"Message {message_id} was attached to the wrong record")
    if re.search(r"&lt;/?(?:p|br|ul|ol|li|h[1-6])\b", stored_body, re.I):
        raise RuntimeError(f"Message {message_id} contains escaped HTML; inspect it in Odoo")
    print(f"POSTED ticket={args.ticket_id} message={message_id} subtype={subtype} url={SUPPORT_URL}/helpdesk/ticket/{args.ticket_id}")


if __name__ == "__main__":
    main()
