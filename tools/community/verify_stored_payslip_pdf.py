"""Offline text/PNG proof for the two real payslip PDF fixture exports.

Uses local PyMuPDF, never changes the Odoo server or generates a substitute PDF.
All input/output artifacts must remain outside the repository.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re


REPOSITORY = Path(__file__).resolve().parents[2]
LABELS = ('Stored NEGATIVE', 'Stored ZERO', 'Stored NULL_VALUE', 'PRIVATE/PDF/1', 'Original stored payslip name')


def outside_repository(path):
    path = Path(path).resolve()
    if path.is_relative_to(REPOSITORY):
        raise ValueError('Private PDF and image artifacts must stay outside the checkout')
    return path


def numeric_values(text):
    text = text.replace('\u2212', '-').replace('\u2013', '-')
    return [float(value.replace(',', '.')) for value in re.findall(r'(?<![\w.])[-+]?\d+(?:[.,]\d+)?(?![\w.])', text)]


def row_values(document, label):
    """Fixture geometry when one label is unique; otherwise leave a clear gap."""
    matches = [(page, rect) for page in document for rect in page.search_for(label)]
    if len(matches) != 1:
        return None
    page, rect = matches[0]
    words = page.get_text('words')
    same_row = [word[4] for word in words if word[1] >= rect.y0 - 1 and word[3] <= rect.y1 + 1]
    return numeric_values(' '.join(same_row))


def verify(proof_file, output_directory):
    import fitz
    proof_file = outside_repository(proof_file)
    output_directory = outside_repository(output_directory)
    if output_directory.exists():
        raise ValueError('Use a new output directory to preserve earlier PDF proof')
    records = json.loads(proof_file.read_text(encoding='utf-8'))
    if not isinstance(records, list) or len(records) != 2:
        raise ValueError('Expected exactly two server-generated PDF proof records')
    if {(row['archived_structure'], row['basic_hidden']) for row in records} != {(False, False), (True, True)}:
        raise ValueError('Need both active/basic and archived/hidden fixture PDFs')
    output_directory.mkdir(parents=True)
    results = []
    for record in records:
        if not record['normal_employee'] or not record['stored_history_unchanged'] or record['missing_assets']:
            raise ValueError('Server actor/history/assets proof is not accepted')
        if Path(record['file']).name != record['file']:
            raise ValueError('PDF filename must be local to the server evidence directory')
        path = outside_repository(proof_file.parent / record['file'])
        data = path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        if not data.startswith(b'%PDF-') or digest != record['sha256']:
            raise ValueError('PDF bytes differ from the actual server export')
        document = fitz.open(stream=data, filetype='pdf')
        if document.page_count != record['pages'] or not document.page_count:
            raise ValueError('Actual PDF page count changed')
        text = '\n'.join(page.get_text('text') for page in document)
        normalized = re.sub(r'\s+', ' ', text)
        if not normalized.strip() or any(label not in normalized for label in LABELS):
            raise ValueError('Actual PDF is missing a stored concept or original reference/name')
        if ('Stored BASIC' in normalized) == record['basic_hidden']:
            raise ValueError('Actual PDF BASIC visibility does not match the stored presentation flag')
        numbers = numeric_values(normalized)
        if any(value not in numbers for value in (0, -25, 75)):
            raise ValueError('Actual PDF does not contain the expected zero, negative and NET fixture values')
        rows = {label: row_values(document, label) for label in ('Stored ZERO', 'Stored NEGATIVE', 'Stored NULL_VALUE')}
        if rows['Stored ZERO'] is not None and 0 not in rows['Stored ZERO']:
            raise ValueError('ZERO row is not a displayed zero')
        if rows['Stored NEGATIVE'] is not None and -25 not in rows['Stored NEGATIVE']:
            raise ValueError('NEGATIVE row lost its sign/value')
        if rows['Stored NULL_VALUE'] is not None and rows['Stored NULL_VALUE']:
            raise ValueError('NULL row acquired a numeric amount')
        text_path = output_directory / (path.stem + '.txt')
        text_path.write_text(text, encoding='utf-8')
        pages = []
        for index, page in enumerate(document):
            image_path = output_directory / ('%s-page-%02d.png' % (path.stem, index + 1))
            page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5), alpha=False).save(image_path)
            pages.append({'file': image_path.name, 'sha256': hashlib.sha256(image_path.read_bytes()).hexdigest(),
                          'width_pt': page.rect.width, 'height_pt': page.rect.height})
        results.append({'pdf': str(path), 'pdf_sha256': digest, 'pages': pages,
            'actual_pdf_labels_references_verified': True, 'basic_hidden': record['basic_hidden'],
            'zero_negative_net_values_verified': True, 'row_geometry_values': rows,
            'null_row_verified_blank': rows['Stored NULL_VALUE'] == [],
            'classification_history_certified': False, 'source_history_unchanged_as_tested': True,
            'pdf_text_sha256': hashlib.sha256(text.encode()).hexdigest(), 'visual_review_still_required': True})
        document.close()
    report = {'input_proof_sha256': hashlib.sha256(proof_file.read_bytes()).hexdigest(),
        'tool_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), 'parser': 'pymupdf',
        'pdfs': results, 'server_modified': False, 'substitute_pdf_generated': False,
        'all_pages_rendered': True, 'original_action_462_adopted': False, 'financial_payroll_certified': False}
    (output_directory / 'offline-pdf-proof.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--proof', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    result = verify(args.proof, args.output_dir)
    print('STORED_PAYSLIP_PDF_VERIFIED', len(result['pdfs']), 'actual PDFs; inspect rendered PNGs')


if __name__ == '__main__':
    main()
