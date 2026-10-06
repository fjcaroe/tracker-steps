"""Compare public home content, links, assets and routes after the SyS rollout."""
import argparse
import hashlib
import json
from urllib.parse import urljoin
from urllib.request import urlopen

from lxml import html


def fetch(url):
    with urlopen(url, timeout=120) as response:
        assert response.status == 200, (url, response.status)
        return response.read()


def signature(document):
    home = document.xpath('//*[@data-commercial-version="2026.10"]')
    assert len(home) == 1
    root = home[0]
    return {
        'headings': [' '.join(x.text_content().split()) for x in root.xpath('.//h1|.//h2|.//h3|.//h4')],
        'text': ' '.join(' '.join(root.xpath('.//text()[not(parent::script)]')).split()),
        'links': root.xpath('.//a/@href'),
        'images': root.xpath('.//img/@src'),
        'solutions': len(root.xpath('.//article[@class="steps-product"]')),
        'packages': len(root.xpath('.//*[@data-plan]')),
        'apps': len(root.xpath('.//*[@data-app]')),
        'faqs': len(root.xpath('.//*[@id="preguntas"]//details')),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', default='https://stepsapp.cl/')
    parser.add_argument('--target', default='https://sys.stepsapp.cl/')
    args = parser.parse_args()
    source = html.fromstring(fetch(args.source))
    target = html.fromstring(fetch(args.target))
    expected, actual = signature(source), signature(target)
    for key in expected:
        assert expected[key] == actual[key], 'Published home mismatch: ' + key
    assert (actual['solutions'], actual['packages'], actual['apps'], actual['faqs']) == (20, 3, 5, 7)
    for path in set(actual['images']):
        assert path.startswith('/step_demo_homepage/'), path
        assert hashlib.sha256(fetch(urljoin(args.source, path))).digest() == \
            hashlib.sha256(fetch(urljoin(args.target, path))).digest(), path
    css = ''.join(fetch(urljoin(args.target, path)).decode() for path in
                  target.xpath('//link[@rel="stylesheet"]/@href') if path.startswith('/web/assets/'))
    assert '.steps-plan--featured' in css and '.steps-brief-card' in css
    for path in ('/contactus', '/web/login', '/soluciones/campo-y-produccion',
                 '/soluciones/personas', '/soluciones/recursos-y-logistica', '/soluciones/finanzas'):
        fetch(urljoin(args.target, path))
    print(json.dumps({'result': 'PUBLIC_HOME_MATCHES', 'target': args.target,
                      'solutions': actual['solutions'], 'packages': actual['packages'],
                      'apps': actual['apps'], 'faqs': actual['faqs'],
                      'images': 'identical', 'styles': 'loaded', 'routes': 'HTTP 200'}))


if __name__ == '__main__':
    main()
