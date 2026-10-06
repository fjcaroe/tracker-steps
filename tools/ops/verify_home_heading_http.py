"""Render a private clone and preserve the homepage outside its requested H1."""
import json
import socket
import subprocess
import time
import urllib.request
from lxml import html

TITLE = 'ERP agrícola para gestionar tu campo en Chile'


def signature(content):
    document = html.fromstring(content)
    roots = document.xpath('//*[@data-commercial-version="2026.10"]')
    assert len(roots) == 1
    root = roots[0]
    headings = root.xpath('.//h1[@id="steps-title"]')
    assert len(headings) == 1
    title = ' '.join(headings[0].text_content().split())
    headings[0].getparent().remove(headings[0])
    return title, {
        'text': ' '.join(' '.join(root.xpath('.//text()[not(parent::script)]')).split()),
        'links': root.xpath('.//a/@href'), 'images': root.xpath('.//img/@src'),
        'solutions': len(root.xpath('.//article[@class="steps-product"]')),
    }


def capture_before(url, stage):
    with urllib.request.urlopen(url + '/', timeout=40) as response:
        title, body = signature(response.read())
    (stage / 'homepage-before.json').write_text(json.dumps({'title': title, 'body': body}))


def verify_http(base, options, database, source, opts, stage):
    if database in ('LAB_TAREAS', 'karo_consultorias'):
        url = 'https://desarrollo.stepsapp.cl' if database == 'LAB_TAREAS' else 'https://stepsapp.cl'
        with urllib.request.urlopen(url + '/', timeout=60) as response:
            title, body = signature(response.read())
    else:
        with socket.socket() as listener:
            listener.bind(('127.0.0.1', 0))
            port = listener.getsockname()[1]
        command = base + [item for item in options if item not in ('--no-http',) and not item.startswith('--http-port=')]
        command += ['-d', database, '--db-filter=^' + database + '$', '--http-port=' + str(port),
                    '--addons-path=' + str(source) + ',' + opts['addons_path'],
                    '--data-dir=' + str(stage / 'data'), '--logfile=' + str(stage / 'http-clone.log')]
        process = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            for attempt in range(60):
                assert process.poll() is None, 'Private clone stopped before serving the homepage'
                try:
                    with urllib.request.urlopen('http://127.0.0.1:%s/?db=%s' % (port, database), timeout=3) as response:
                        title, body = signature(response.read())
                    break
                except (OSError, ValueError):
                    time.sleep(1)
            else:
                raise RuntimeError('Private clone did not render its homepage')
        finally:
            process.terminate()
            process.wait(timeout=30)
    assert title == TITLE, title
    before = json.loads((stage / 'homepage-before.json').read_text())
    assert body == before['body'], 'Unrequested homepage content changed'
    assert body['solutions'] == 20
    print('HOMEPAGE_HTTP_OK ' + database + ' title updated; other content/links/images preserved', flush=True)
