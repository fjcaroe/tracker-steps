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


def checked_pipeline(root, repetition, diagnostic_unhashed=False):
    path = private_file(root, repetition['pipeline'])
    raw = path.read_bytes()
    if 'pipeline_sha256' not in repetition or 'pipeline_bytes' not in repetition:
        if not diagnostic_unhashed:
            raise HeaderReviewError('Pipeline hash and byte count must be recorded by the functional test')
        return path, raw, False
    if sha(raw) != repetition['pipeline_sha256'] or len(raw) != repetition['pipeline_bytes']:
        raise HeaderReviewError('Pipeline bytes differ from their functional-test receipt')
    return path, raw, True


def white_pixels(image):
    """Composite premultiplied RGB(A) on white without changing geometry."""
    if image.colorspace != pymupdf.csRGB:
        image = pymupdf.Pixmap(pymupdf.csRGB, image)
    raw = image.samples
    if image.alpha:
        raw = bytes(min(255, raw[index + channel] + 255 - raw[index + 3])
                    for index in range(0, len(raw), 4) for channel in range(3))
    return raw


def pixel_difference(expected, actual):
    if len(expected) != len(actual) or not expected:
        return None
    differences = [abs(left - right) for left, right in zip(expected, actual)]
    maximum, mean = max(differences), sum(differences) / len(differences)
    # Qt's PNG -> RGB + soft-mask split quantizes alpha by one channel level.
    # This is a bounded encoding comparison, not a perceptual similarity score.
    return {'maximum_channel_error': maximum, 'mean_channel_error': mean,
            'matches': maximum <= 1}


def header_logos(raw):
    tree = etree.fromstring(raw)
    images = []
    for source in tree.xpath('//img[@alt="Logo"]/@src'):
        if not source.startswith('data:') or ';base64,' not in source:
            raise HeaderReviewError('Company logo is not captured as original embedded bytes')
        original = base64.b64decode(source.split(';base64,', 1)[1], validate=True)
        image = pymupdf.Pixmap(original)
        pixels = white_pixels(image)
        images.append({'source_sha256': sha(original), 'white_pixel_sha256': sha(pixels),
                       'width': image.width, 'height': image.height, '_pixels': pixels})
    return images


def header_contract(raw, company_name, country_name):
    text = etree.fromstring(raw).text_content()
    return {'company_name_present': company_name in text, 'country_name_present': country_name in text,
            'logos': [{key: value for key, value in image.items() if key != '_pixels'}
                      for image in header_logos(raw)]}


def review_pages(pdf_bytes, company_name, country_name, references):
    pages = []
    with pymupdf.open(stream=pdf_bytes, filetype='pdf') as doc:
        for index, page in enumerate(doc):
            text = page.get_text()
            images = page.get_image_info(hashes=True)
            matches = []
            for item in page.get_images(full=True):
                image = pymupdf.Pixmap(doc, item[0])
                if item[1]:
                    image = pymupdf.Pixmap(image, pymupdf.Pixmap(doc, item[1]))
                placements = page.get_image_rects(item[0])
                if not any(rect.intersects(page.rect) for rect in placements):
                    continue
                for reference in references:
                    if (image.width, image.height) != (reference['width'], reference['height']):
                        continue
                    comparison = pixel_difference(reference['_pixels'], white_pixels(image))
                    if comparison and comparison['matches']:
                        matches.append({'source_sha256': reference['source_sha256'],
                                        'xref': item[0], **comparison})
            pages.append({
                'page': index + 1, 'company_name_present': company_name in text,
                'country_name_present': country_name in text,
                'expected_logo_present': bool(matches), 'logo_comparisons': matches,
                'text_sha256': sha(text.encode('utf-8')),
                'images': [{'bbox': list(image['bbox']), 'pixel_digest_md5': image['digest'].hex()}
                           for image in images],
            })
    return pages


def verify(directory, output, diagnostic_unhashed_pipeline=False):
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
               'legal_validity_certified': False, 'pipeline_provenance_verified': True}
    all_passed = True
    for index, repetition in enumerate(repetitions, 1):
        path, pdf = checked_file(directory, repetition)
        pipeline_path, pipeline_raw, provenance = checked_pipeline(
            directory, repetition, diagnostic_unhashed_pipeline)
        receipt['pipeline_provenance_verified'] &= provenance
        pipeline = json.loads(pipeline_raw)
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
        references = header_logos(header)
        pages = review_pages(pdf, proof['company_name'], proof['country_name'], references)
        if len(pages) != repetition['pages'] or not pages:
            raise HeaderReviewError('PDF page count differs from its receipt')
        passed = bool(contract['company_name_present'] and contract['country_name_present'] and references
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
                'before_conversion' if not contract['company_name_present'] or not contract['country_name_present'] or not references
                else 'pdf_conversion_or_pagination')})
    receipt['technical_headers_passed'] = all_passed and receipt['pipeline_provenance_verified']
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
    parser.add_argument('--diagnostic-unhashed-pipeline', action='store_true',
                        help='Inspect pre-hash Q2 only; can never return technical acceptance')
    args = parser.parse_args()
    result = verify(args.evidence, args.output, args.diagnostic_unhashed_pipeline)
    print(json.dumps({'technical_headers_passed': result['technical_headers_passed'],
                      'repetitions': len(result['repetitions'])}))
    return 0 if result['technical_headers_passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
