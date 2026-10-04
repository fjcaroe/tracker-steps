import sys
import zipfile

from lxml import etree

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
with zipfile.ZipFile(sys.argv[1]) as archive:
    root = etree.fromstring(archive.read("word/document.xml"))

page = 1
for paragraph in root.iter(W + "p"):
    text = "".join(paragraph.itertext()).strip()
    if text:
        print(page, text)
    for element in paragraph.iter():
        if element.tag == W + "lastRenderedPageBreak":
            page += 1
        elif element.tag == W + "br" and element.get(W + "type") == "page":
            page += 1
