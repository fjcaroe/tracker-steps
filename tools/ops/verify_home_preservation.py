"""Compare the live homepage to a tested clone, allowing only the heading change."""
import argparse
import json
import re

from lxml import etree
from manage_management import query


def views(database):
    assert re.fullmatch(r'[A-Za-z0-9_]+', database)
    return json.loads(query(database, "SELECT COALESCE(json_object_agg(id,arch_db),'{}') "
        "FROM ir_ui_view WHERE active AND inherit_id IS NULL AND key='website.homepage'"))


def without_heading(arch):
    tree = etree.fromstring(arch.encode())
    for heading in tree.xpath('//h1[@id="steps-title"]'):
        for child in list(heading): heading.remove(child)
        heading.text = 'TITLE'
    return etree.tostring(tree, method='c14n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('before_database')
    parser.add_argument('after_database')
    args = parser.parse_args()
    before, after = views(args.before_database), views(args.after_database)
    assert before and before.keys() == after.keys(), 'Published homepage variants changed'
    translations = 0
    for identity, variants in before.items():
        for language, arch in variants.items():
            assert language in after[identity]
            assert without_heading(arch) == without_heading(after[identity][language]), (identity, language)
            translations += 1
    print('HOME_CONTENT_PRESERVED_OK views=%s translations=%s' % (len(before), translations))


if __name__ == '__main__': main()
