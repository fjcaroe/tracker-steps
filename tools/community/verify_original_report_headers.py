"""Offline review of real captured payroll PDF headers; no Odoo/database access.

This checks technical presentation of a private fixture, never legal validity.
PyMuPDF is needed only on the offline review workstation.
"""
import argparse
import base64
import hashlib
import json
from pathlib import Path

from lxml import html as etree
import pymupdf


class HeaderReviewError(ValueError):
    pass


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def private_file(root, name):
    if not isinstance(name, str) or Path(name).is_absolute():
        raise HeaderReviewError('Evidence path must be a private relative filename')
    path = (root / name).resolve()
    if not path.is_relative_to(root.resolve()):
        raise HeaderReviewError('Evidence path escapes its private directory')
    if not path.is_file():
        raise HeaderReviewError('Evidence file is absent: ' + name)
    return path


def checked_file(root, entry):
    path = private_file(root, entry['file'])
    raw = path.read_bytes()
    if sha(raw) != entry['sha256'] or len(raw) != entry['bytes']:
        raise HeaderReviewError('Evidence file does not match its recorded bytes: ' + entry['file'])
    return path, raw


def header_contract(raw, company_name, country_name):
    tree = etree.fromstring(raw)
    text = tree.text_content()
    images = []
    for source in tree.xpath('//img[@alt="Logo"]/@src'):
        if not source.startswith('data:') or ';base64,' not in source:
            raise HeaderReviewError('Company logo is not captured as original embedded bytes')
        original = base64.b64decode(source.split(';base64,', 1)[1], validate=True)
        image = pymupdf.Pixmap(original)
        if image.alpha:
            image = pymupdf.Pixmap(image, 0)
        images.append({'source_sha256': sha(original), 'pixel_digest_md5': image.digest.hex()})
    return {'company_name_present': company_name in text, 'country_name_present': country_name in text,
            'logos': images}


def review_pages(pdf_bytes, company_name, country_name, expected_logo_digests):
    pages = []
    with pymupdf.open(stream=pdf_bytes, filetype='pdf') as doc:
        for index, page in enumerate(doc):
            text = page.get_text()
            images = page.get_image_info(hashes=True)
            found = {image['digest'].hex() for image in images}
            pages.append({
                'page': index + 1, 'company_name_present': company_name in text,
                'country_name_present': country_name in text,
                'expected_logo_present': bool(expected_logo_digests & found),
                'text_sha256': sha(text.encode('utf-8')),
                'images': [{'bbox': list(image['bbox']), 'pixel_digest_md5': image['digest'].hex()}
                           for image in images],
            })
    return pages


def verify(directory, output):
    directory, output = Path(directory), Path(output)
    proof_path = private_file(directory, 'proof.json')
    proof = json.loads(proof_path.read_text(encoding='utf-8'))
    for key in ('normal_actor', 'stored_history_unchanged', 'original_action_unchanged',
                'existing_structure_fk_unchanged'):
        if proof.get(key) is not True:
            raise HeaderReviewError('Missing functional preservation evidence: ' + key)
    if proof.get('original_action_numeric_adoption') is not False or proof.get('missing_assets') != []:
        raise HeaderReviewError('Adoption or asset evidence does not match this limited review')
    repetitions = proof.get('repetitions', [])
    if len(repetitions) != 3 or type(proof.get('actor_id')) is not int or proof['actor_id'] <= 0:
        raise HeaderReviewError('Three real repetitions and a normal fixture actor are required')
    output.mkdir(mode=0o700, parents=True, exist_ok=True)
    output.chmod(0o700)
    receipt = {'schema': 'original-report-header-review-v1', 'proof_sha256': sha(proof_path.read_bytes()),
               'reviewer_sha256': sha(Path(__file__).read_bytes()), 'repetitions': [],
               'technical_headers_passed': False, 'productive_layout_accepted': False,
               'legal_validity_certified': False}
    all_passed = True
    for index, repetition in enumerate(repetitions, 1):
        path, pdf = checked_file(directory, repetition)
        pipeline_path = private_file(directory, repetition['pipeline'])
        pipeline = json.loads(pipeline_path.read_text(encoding='utf-8'))
        if any(len(pipeline.get(key, [])) != 1 for key in ('prepare_calls', 'run_calls', 'argument_calls')):
            raise HeaderReviewError('Actual prepare, conversion and argument calls must each occur once')
        prepared, run, arguments = (pipeline[key][0] for key in ('prepare_calls', 'run_calls', 'argument_calls'))
        for call in (run, arguments):
            if call['environment']['uid'] != proof['actor_id'] or call['environment']['sudo'] is not False:
                raise HeaderReviewError('Conversion did not preserve the normal actor')
        if arguments.get('session_arguments_captured') is not False:
            raise HeaderReviewError('Session/cookie data must not be captured')
        for call in (prepared, run):
            for part in [call['header'], call['footer'], *call['bodies']]:
                checked_file(pipeline_path.parent, part)
        checked_file(pipeline_path.parent, prepared['html'])
        if prepared['header']['sha256'] != run['header']['sha256']:
            raise HeaderReviewError('Prepared header differs from actual converter input')
        if prepared['footer']['sha256'] != run['footer']['sha256']:
            raise HeaderReviewError('Prepared footer differs from actual converter input')
        _, header = checked_file(pipeline_path.parent, run['header'])
        contract = header_contract(header, proof['company_name'], proof['country_name'])
        digests = {image['pixel_digest_md5'] for image in contract['logos']}
        pages = review_pages(pdf, proof['company_name'], proof['country_name'], digests)
        if len(pages) != repetition['pages'] or not pages:
            raise HeaderReviewError('PDF page count differs from its receipt')
        passed = bool(contract['company_name_present'] and contract['country_name_present'] and digests
                      and all(page['company_name_present'] and page['country_name_present']
                              and page['expected_logo_present'] for page in pages))
        all_passed &= passed
        with pymupdf.open(stream=pdf, filetype='pdf') as doc:
            for item, page in zip(pages, doc):
                raw = page.get_pixmap(matrix=pymupdf.Matrix(1.5, 1.5), alpha=False).tobytes('png')
                name = 'repetition-%s-page-%s.png' % (index, item['page'])
                target = output / name
                with target.open('xb') as handle:
                    handle.write(raw)
                target.chmod(0o600)
                item['png'] = {'file': name, 'sha256': sha(raw), 'bytes': len(raw)}
        receipt['repetitions'].append({'pdf': path.name, 'pdf_sha256': sha(pdf),
            'pipeline_sha256': sha(pipeline_path.read_bytes()), 'header': contract, 'pages': pages,
            'paperformat': arguments['paperformat'], 'converter_arguments': arguments['arguments'],
            'passed': passed, 'loss_boundary': None if passed else (
                'before_conversion' if not contract['company_name_present'] or not contract['country_name_present'] or not digests
                else 'pdf_conversion_or_pagination')})
    receipt['technical_headers_passed'] = all_passed
    raw = json.dumps(receipt, indent=2, sort_keys=True).encode('utf-8') + b'\n'
    target = output / 'review.json'
    with target.open('xb') as handle:
        handle.write(raw)
    target.chmod(0o600)
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    result = verify(args.evidence, args.output)
    print(json.dumps({'technical_headers_passed': result['technical_headers_passed'],
                      'repetitions': len(result['repetitions'])}))
    return 0 if result['technical_headers_passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
