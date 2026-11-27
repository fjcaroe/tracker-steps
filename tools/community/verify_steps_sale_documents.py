"""Compare actual sales printouts and confirmed quotation workflows in the two private Steps copies."""
import argparse
import json
from pathlib import Path
import re


def without(data, *keys):
    return {key: value for key, value in data.items() if key not in keys}


def verify(native_pdfs, community_pdfs, native_order, community_order):
    if not __debug__:
        raise ValueError('Assertion checks must be enabled.')
    assert native_pdfs['database'] == native_order['database'] == 'MANAGEMENT_QA_STEPS_CRM_20261126U42C'
    assert community_pdfs['database'] == community_order['database'] and community_order['database'] in (
        'COMMUNITY_STEPS_CRM_QUOTE_20261127U42A', 'COMMUNITY_STEPS_CRM_PRINT_20261127U43Y',
        'COMMUNITY_STEPS_CRM_DOC_20261127U44P','COMMUNITY_STEPS_CRM_SUPPORT_20261127U44H3',
        'COMMUNITY_STEPS_CRM_INTEGRATED_20261127U46A')
    for report in (native_pdfs, community_pdfs):
        assert report['history_unchanged'] and (report['action'], report['uid']) == (444, 7)
    first, second = native_pdfs['documents'], community_pdfs['documents']
    assert len(first) == len(second) == 4
    assert sorted(r['state'] for r in first) == ['draft', 'sale', 'sale', 'sale']
    assert len({r['id'] for r in first}) == 4
    for original, restored in zip(first, second):
        assert without(original, 'bytes_sha256') == without(restored, 'bytes_sha256')
        assert original['printed_total'] and original['pdf_pages'] == len(original['page_images']) > 0
        for digest in (original['body'], original['pdf_text'], *original['page_images'],
                       original['bytes_sha256'], restored['bytes_sha256']):
            assert re.fullmatch('[0-9a-f]{64}', digest)
    assert without(native_order, 'database') == without(community_order, 'database')
    assert native_order['history_unchanged'] and native_order['rolled_back'] and native_order['saved_and_reopened']
    assert native_order['confirmation']['reopened_confirmed_order'] and native_order['confirmation']['state'] == 'sale'
    invoice = native_order['confirmation']['draft_invoice']
    assert invoice['state'] == 'draft' and invoice['wizard'] == 458 and invoice['reopened_from_sale']
    assert re.fullmatch('[0-9a-f]{64}', invoice['amounts_and_original_relations'])
    return {'historical_documents': len(first), 'matching_pages': sum(row['pdf_pages'] for row in first),
            'identical_pdf_files': sum(a['bytes_sha256'] == b['bytes_sha256'] for a,b in zip(first,second)),
            'order': native_order['confirmation']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('native-pdfs', 'community-pdfs', 'native-order', 'community-order'):
        parser.add_argument('--'+name, type=Path, required=True)
    print(json.dumps(verify(*(json.loads(path.read_bytes()) for path in vars(parser.parse_args()).values()))))
