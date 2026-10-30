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
    if len(headers) != 1:
        raise ValueError('One corporate header is required')
    addresses = headers[0].xpath('.//*[@name="company_address"]')
    lists = headers[0].xpath('.//*[@name="company_address_list"]')
    if len(addresses) != 1 or len(lists) != 1 or lists[0] not in addresses[0].iterdescendants():
        raise ValueError('One unambiguous corporate address is required')
    before = tree.text_content()
    address = addresses[0]
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
