import json
from pathlib import Path

from lxml import etree, html


def validate_xml(path: Path) -> None:
    page = etree.parse(str(path))
    scripts = page.xpath("//script[@type='application/ld+json']")
    assert len(scripts) == 1
    json.loads(scripts[0].text)
    assert len(page.xpath("//h1")) == 1
    assert len(page.xpath("//*[@data-category]")) == 12
    assert all(anchor.get("href") for anchor in page.xpath("//a"))


def validate_render(path: Path, canonical: str = "https://stepsapp.cl/") -> None:
    page = html.fromstring(path.read_bytes())
    text = page.text_content()
    assert len(page.xpath("//h1")) == 1
    assert "ERP agrícola" in text
    assert "SOFTWARE DE GESTIÓN AGRÍCOLA SOBRE ODOO" in text
    assert len(page.xpath("//*[contains(concat(' ', normalize-space(@class), ' '), ' steps-product ')]")) == 12
    assert len(page.xpath("//*[@data-app]")) == 5
    assert page.xpath("//link[@rel='canonical' and @href=$url]", url=canonical)
    assert page.xpath("//meta[@name='description' and contains(@content, 'Software de gestión agrícola sobre Odoo')]")
    assert page.xpath("//script[@type='application/ld+json']")


if __name__ == "__main__":
    import sys

    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(
        "step_demo_homepage/views/homepage.xml"
    )
    if target.suffix == ".xml":
        validate_xml(target)
    else:
        canonical = sys.argv[2] if len(sys.argv) > 2 else "https://stepsapp.cl/"
        validate_render(target, canonical)
    print(f"HOME_SEO_OK {target}")
