"""Preserve the published Spanish homepage and its live solution-page edits."""
import argparse
import json
from pathlib import Path
import tarfile

from lxml import etree


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('public_export', type=Path)
    parser.add_argument('source_archive', type=Path)
    parser.add_argument('module', type=Path)
    args = parser.parse_args()
    payload = json.loads(args.public_export.read_text(encoding='utf-8'))
    assert payload['source_database'] == 'karo_consultorias'
    homepage = next(v for v in payload['views']
                    if v['key'] == 'website.homepage' and v['website_id'] == 1)
    published = etree.fromstring(homepage['arch_db']['es_419'].encode())
    assert len(published.xpath('//article[@class="steps-product"]')) == 20
    document = etree.parse(str(args.module / 'views/homepage.xml'))
    record = document.xpath('//record[@id="website.homepage"]')[0]
    field = record.find('field[@name="arch"]')
    field.remove(field[0])
    field.append(published)
    for name in ('website_meta_title', 'website_meta_description', 'website_meta_og_img'):
        value = homepage[name]
        if isinstance(value, dict):
            value = value.get('es_419', value['en_US'])
        record.find('field[@name="' + name + '"]').text = value
    document.write(str(args.module / 'views/homepage.xml'), encoding='utf-8',
                   xml_declaration=True)
    with (args.module / 'views/homepage.xml').open('ab') as output:
        output.write(b'\n')
    with tarfile.open(args.source_archive) as archive:
        source = archive.extractfile('step_demo_homepage/views/solution_pages.xml')
        assert source is not None
        contents = source.read()
        etree.fromstring(contents)
        (args.module / 'views/solution_pages.xml').write_bytes(contents)
    print('PUBLIC_HOME_PRESERVED: published es_419 + solution templates')


if __name__ == '__main__':
    main()
