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


def compare_native(original, candidate):
    fields = ("company", "document", "kind", "pages", "references", "reference_permissions",
              "article_text_sha256", "pdf_text_sha256")
    def documents(receipt):
        return {(row["actor"], row["kind"]): {key: row[key] for key in fields} for row in receipt["printed"]}

    native = documents(original)
    if len(native) != 4 or native != documents(candidate):
        raise ValueError("The invoice identity, permissions, or complete printed contents differ from the native application")


def compare_printed_pages(receipt, original_directory, migrated_directory):
    def text_runs(page):
        return [span for block in page.get_text("dict")["blocks"] if "lines" in block
                for line in block["lines"] for span in line["spans"] if span["text"].strip()]

    def geometry(page):
        return [{k: v for k, v in path.items() if k not in ("color", "fill")} for path in page.get_drawings()]

    result = []
    for row in receipt["printed"]:
        name = "%s-%s.pdf" % (row["actor"], row["kind"])
        with pymupdf.open(original_directory / name) as original, pymupdf.open(migrated_directory / name) as migrated:
            if original.page_count != migrated.page_count:
                raise ValueError("The original and migrated invoice page counts differ")
            for number, (source, target) in enumerate(zip(original, migrated), start=1):
                a = source.get_pixmap(colorspace=pymupdf.csGRAY, alpha=False)
                b = target.get_pixmap(colorspace=pymupdf.csGRAY, alpha=False)
                if (a.width, a.height) != (b.width, b.height):
                    raise ValueError("The physical dimensions of the printed page differ")
                before, after = text_runs(source), text_runs(target)
                for field in ("text", "font", "size", "origin", "bbox", "flags"):
                    if [span[field] for span in before] != [span[field] for span in after]:
                        raise ValueError("The text geometry or typography differs from the original page")
                shapes = geometry(source)
                if shapes != geometry(target):
                    raise ValueError("The drawing geometry differs from the original page")
                colors = sorted({(format(old["color"], "06x"), format(new["color"], "06x"))
                                 for old, new in zip(before, after) if old["color"] != new["color"]})
                pixels = sum(x != y for x, y in zip(a.samples, b.samples))
                result.append({"actor": row["actor"], "kind": row["kind"], "page": number,
                               "pixels": a.width * a.height, "different_pixels": pixels, "text_runs": len(before),
                               "drawing_paths": len(shapes), "different_text_colors": colors})
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("receipt", type=Path)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--native-receipt", type=Path)
    parser.add_argument("--native-directory", type=Path)
    args = parser.parse_args()
    receipt = json.loads(args.receipt.read_bytes())
    result = verify(receipt, args.directory)
    if args.native_receipt:
        native = json.loads(args.native_receipt.read_bytes())
        compare_native(native, receipt)
        if args.native_directory:
            verify(native, args.native_directory)
            result = {"rasterization": result, "native_pages": compare_printed_pages(receipt, args.native_directory, args.directory)}
    elif args.native_directory:
        parser.error("--native-directory requires a native receipt")
    print(json.dumps(result, sort_keys=True))
