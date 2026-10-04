import json
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from lxml import html
from pathlib import Path

urls=[
    'https://desarrollo.stepsapp.cl/cosecha/',
    'https://desarrollo.stepsapp.cl/task/',
    'https://stepsapp.cl/web_tracker/',
    'https://stepsapp.cl/truck/',
    'https://colaciones.stepsapp.cl/',
    'https://desarrollo.stepsapp.cl/colaciones/app/',
    'https://stepsapp.cl/harvest/',
]
results=[]
for url in urls:
    try:
        with urlopen(Request(url,headers={'User-Agent':'Steps Homepage Validation'}),timeout=20) as response:
            tree=html.fromstring(response.read())
            result={'url':url,'status':response.status,'title':tree.xpath('string(//title)'), 'final_url':response.url,'manifest':tree.xpath('//link[@rel="manifest"]/@href')}
    except (HTTPError,URLError,TimeoutError) as error:
        result={'url':url,'error':str(error)}
    results.append(result)
    print(json.dumps(result,ensure_ascii=False))
# Results go to stdout; redirect to an artifact directory outside the checkout.
