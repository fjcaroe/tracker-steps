"""Stable block flow for the original Community report's corporate header.

Pure HTML transformation: no ORM, document values, assets or company mutation.
The Qt PDF renderer can omit a nested Bootstrap flex/address flow. Only layout
attributes inside one unambiguous corporate header may be changed here.
"""
from lxml import html


MARKER = 'step_original_report_header_block'


def block_corporate_header(value):
    raw = value if isinstance(value, bytes) else value.encode('utf-8')
    tree = html.fromstring(raw, parser=html.HTMLParser(encoding='utf-8'))
    wrappers = tree.xpath('//*[@id="minimal_layout_report_headers"]')
    if len(wrappers) != 1:
        raise ValueError('One captured corporate header wrapper is required')
    headers = wrappers[0].xpath('./div[contains(concat(" ", normalize-space(@class), " "), " header ")]')
    if len(headers) != 1:
        raise ValueError('One corporate header is required for this report layout')
    header = headers[0]
    addresses = header.xpath('.//*[@name="company_address"]')
    lists = header.xpath('.//*[@name="company_address_list"]')
    if len(addresses) != 1 or len(lists) != 1 or not header.xpath('.//img[@alt="Logo"]'):
        raise ValueError('Corporate address and logo layout is ambiguous or unsupported')
    before = tree.text_content()
    for node in [header, *header.iterdescendants()]:
        classes = (node.get('class') or '').split()
        if node is header or 'row' in classes or 'd-flex' in classes or node is addresses[0]:
            if MARKER not in classes:
                classes.append(MARKER)
            node.set('class', ' '.join(classes))
            node.set('style', (node.get('style') or '') +
                     ';display:block!important;float:none!important;height:auto!important;overflow:visible!important;')
    if tree.text_content() != before:
        raise ValueError('Corporate header text changed during layout normalization')
    return html.tostring(tree, encoding='unicode', doctype='<!DOCTYPE html>')


def unclip_corporate_wrapper(value):
    raw = value if isinstance(value, bytes) else value.encode('utf-8')
    tree = html.fromstring(raw, parser=html.HTMLParser(encoding='utf-8'))
    wrappers = tree.xpath('//*[@id="minimal_layout_report_headers"]')
    bodies = tree.xpath('/html/body')
    if tree.tag != 'html' or len(wrappers) != 1 or len(bodies) != 1:
        raise ValueError('One official minimal corporate wrapper is required')
    before = tree.text_content()
    tree.set('style', (tree.get('style') or '') + ';height:auto!important;overflow:visible!important;')
    body = bodies[0]
    classes = [token for token in (body.get('class') or '').split() if token != 'overflow-hidden']
    classes.append('step_original_report_header_visible')
    body.set('class', ' '.join(classes))
    body.set('style', (body.get('style') or '') + ';height:auto!important;overflow:visible!important;')
    if tree.text_content() != before:
        raise ValueError('Corporate wrapper text changed during layout normalization')
    return html.tostring(tree, encoding='unicode', doctype='<!DOCTYPE html>')
