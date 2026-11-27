"""Read and rasterize the four private SyS invoice PDFs independently of Odoo and Ghostscript."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import re

import pymupdf


def verify(receipt, directory):
    rows = receipt["printed"]
    kinds = {"out_invoice", "out_refund"}
    actors = {row["actor"] for row in rows}
    if (receipt["original_report"] != "account.account_invoices" or receipt["authenticated_operator_count"] != 2
            or len(actors) != 2 or not all(type(actor) is int for actor in actors)
            or {(row["actor"], row["kind"]) for row in rows} != {(actor, kind) for actor in actors for kind in kinds}
            or len(rows) != 4 or not re.fullmatch("[a-f0-9]{64}", receipt["renderer_sha256"])):
        raise ValueError("Expected the four invoice and credit-note renders by the two original operators")
    result = []
    for row in rows:
        pdf = directory / ("%s-%s.pdf" % (row["actor"], row["kind"]))
        data = pdf.read_bytes()
        if sha256(data).hexdigest() != row["sha256"] or len(data) != row["bytes"] or not data.startswith(b"%PDF-"):
            raise ValueError("The off-host PDF differs from the invoicing action output")
        if row["kind"] == "out_refund" and row["references"] < 1:
            raise ValueError("The credit note must carry its original invoice reference")
        pages = []
        with pymupdf.open(stream=data, filetype="pdf") as document:
            if not document.page_count or document.page_count != row["pages"]:
                raise ValueError("The independent PDF page count differs")
            for page in document:
                pixmap = page.get_pixmap(matrix=pymupdf.Matrix(0.65, 0.65), colorspace=pymupdf.csGRAY, alpha=False)
                dark = sum(pixel < 230 for pixel in pixmap.samples)
                words = len(page.get_text("words"))
                if dark <= 500 or words < 10:
                    raise ValueError("The PDF page lacks visible invoice content")
                pages.append({"painted_pixels": dark, "words": words, "geometry": [round(page.rect.width), round(page.rect.height)]})
        result.append({"actor": row["actor"], "kind": row["kind"], "sha256": row["sha256"], "pages": pages})
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("receipt", type=Path)
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    print(json.dumps(verify(json.loads(args.receipt.read_bytes()), args.directory), sort_keys=True))
