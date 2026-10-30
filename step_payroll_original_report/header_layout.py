"""Deterministic corporate typography for this optional Community report only.

The final corporate HTML was complete, but Qt omitted its inherited typography
in repeated PDF headers. Static replays demonstrated this narrow correction;
changing spacing, delay, block/table flow or wrapper clipping did not fix it.
"""
from lxml import html


MARKER = 'step_original_report_corporate_text'
TYPOGRAPHY = ('font-family:Arial,sans-serif!important;font-size:10pt!important;'
              'line-height:1.25!important;color:#000!important;'
              'visibility:visible!important;opacity:1!important;')


def stabilize_corporate_typography(value):
    raw = value if isinstance(value, bytes) else value.encode('utf-8')
    tree = html.fromstring(raw, parser=html.HTMLParser(encoding='utf-8'))
    wrappers = tree.xpath('//*[@id="minimal_layout_report_headers"]')
    if len(wrappers) != 1:
        raise ValueError('One official corporate header wrapper is required')
    headers = wrappers[0].xpath('./div[contains(concat(" ",normalize-space(@class)," ")," header ")]')
    if not headers:
        raise ValueError('At least one corporate header is required')
    addresses = []
    # Official batch preparation concatenates one header per document. Check
    # every header independently before applying any presentation changes.
    for header in headers:
        local = header.xpath('.//*[@name="company_address"]')
        lists = header.xpath('.//*[@name="company_address_list"]')
        if len(local) != 1 or len(lists) != 1 or lists[0] not in local[0].iterdescendants():
            raise ValueError('One unambiguous corporate address is required per header')
        addresses.append(local[0])
    before = tree.text_content()
    for address in addresses:
        classes = (address.get('class') or '').split()
        if MARKER not in classes:
            classes.append(MARKER)
        address.set('class', ' '.join(classes))
        for node in [address, *address.iterdescendants()]:
            original = node.get('style') or ''
            if not original.endswith(TYPOGRAPHY):
                node.set('style', original + ';' + TYPOGRAPHY)
    if tree.text_content() != before:
        raise ValueError('Corporate text changed during typography normalization')
    return html.tostring(tree, encoding='unicode', doctype='<!DOCTYPE html>')
