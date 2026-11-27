"""Compare the four original SyS invoices in RGB at 96 and 144 DPI and verify the unchanged physical baseline."""
import argparse
import hashlib
import json
from pathlib import Path

import pymupdf

from verify_sys_invoice_pdfs import compare_native, compare_printed_pages, verify


SWATCHES = {("111827", "212529"), ("5f636f", "6c757d")}


def load(path):
    return json.loads(path.read_bytes())


def pixels(page, dpi):
    bitmap = page.get_pixmap(dpi=dpi, colorspace=pymupdf.csRGB, alpha=False)
    return [bitmap.width, bitmap.height, hashlib.sha256(bitmap.samples).hexdigest()]


def compare(native, old, candidate):
    for receipt, directory in (native, old, candidate):
        verify(receipt, directory)
    for receipt, _ in (old, candidate):
        compare_native(native[0], receipt)
        if any(receipt[key] != native[0][key] for key in ("renderer_sha256", "text_extractor_sha256")):
            raise ValueError("Original renderer/extractor binary differs")
    baseline = compare_printed_pages(native[0], native[1], old[1])
    observed_colors = {tuple(pair) for page in baseline for pair in page["different_text_colors"]}
    if observed_colors != SWATCHES or any(not page["different_pixels"] for page in baseline):
        raise ValueError("The original control no longer demonstrates the two different print colors")
    verified = compare_printed_pages(native[0], native[1], candidate[1])
    if any(page["different_pixels"] or page["different_text_colors"] for page in verified):
        raise ValueError("The corrected printout differs in text colors or the original raster")
    for page in verified:
        name = "%s-%s.pdf" % (page["actor"], page["kind"])
        with pymupdf.open(native[1]/name) as original, pymupdf.open(old[1]/name) as previous, pymupdf.open(candidate[1]/name) as current:
            i = page["page"] - 1
            rgb = {}
            for dpi in (96, 144):
                original_rgb = pixels(original[i], dpi)
                if original_rgb != pixels(current[i], dpi) or original_rgb == pixels(previous[i], dpi):
                    raise ValueError("RGB pixels did not validate both controls at %d dpi" % dpi)
                rgb[str(dpi)] = original_rgb
            page["rgb"] = rgb
    return {"original_action": native[0]["original_report"], "renderer_sha256": native[0]["renderer_sha256"],
            "text_extractor_sha256": native[0]["text_extractor_sha256"], "previous": baseline, "corrected": verified}


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    for source in ("native", "previous", "candidate"):
        p.add_argument("--" + source, type=Path, required=True)
        p.add_argument("--" + source + "-directory", type=Path, required=True)
    args = p.parse_args()
    print(json.dumps(compare((load(args.native), args.native_directory), (load(args.previous), args.previous_directory),
                             (load(args.candidate), args.candidate_directory)), sort_keys=True))
