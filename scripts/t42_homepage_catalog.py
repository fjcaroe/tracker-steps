"""Apply ticket 42's application catalog to a Steps homepage view.

The published website view can differ from the module XML because Website Builder
stores its own copy. This transformation accepts either the published 12-card
view or the newer 13-card module view and preserves everything outside the
catalog. It is deliberately idempotent.
"""

from __future__ import annotations

import argparse
from html import escape
from pathlib import Path
import re
from xml.etree import ElementTree


NEW_CARDS = [
    ("campo", "CAMPO Y PRODUCCIÓN", "QA e Inspecciones", "Controle la calidad de las tareas importantes y genere instrucciones desde el terreno.", ["Genere procesos de QA para labores críticas", "Genere OT por hallazgos desde el campo con la app móvil", "App móvil para asesores externos y generación de instrucciones"], "M3 12l6 6L21 6M3 6l6 6 12-12"),
    ("personas", "GESTIÓN DE PERSONAS", "Vacaciones", "Controle y autorice las vacaciones y ausencias de su personal de forma fácil y segura.", ["Autoregistro de vacaciones con aprobaciones", "Otorgue permisos y controle ausencias desde el portal", "Registro automático en el ciclo de sueldos"], "M8 3v4M16 3v4M4 10h16M5 5h14v16H5zM9 15l2 2 4-4"),
    ("logistica", "RECURSOS Y LOGÍSTICA", "Inventario", "Registre los movimientos de inventario integrados a cada operación y con aplicaciones móviles.", ["Movimientos diarios validados y contabilizados", "Inventario siempre actualizado", "Control por lotes y vencimientos", "Inventario de fruta siempre al día", "Consumo de materiales automático por OT"], "M4 7l8-4 8 4-8 4-8-4zM4 7v10l8 4 8-4V7M12 11v10"),
    ("finanzas", "FINANZAS Y CONTROL", "Contabilidad multimoneda", "Estados financieros oportunos y validados con indicadores de gestión.", ["Integración completa con otros módulos", "Estados financieros dinámicos y con indicadores", "Facturación electrónica nativa", "Gestión de cobranzas", "Aplicación para rendición de gastos"], "M4 3v18h16M8 16l4-5 3 2 5-7"),
    ("finanzas", "FINANZAS Y CONTROL", "Compras", "Gestione sus compras con agilidad y automatice las solicitudes.", ["Proceso de compras documentado y trazable", "Cotizaciones con envío directo por correo", "Historial de compras", "Compras programadas"], "M3 5h2l2 11h11l3-8H6M9 21h.01M18 21h.01"),
    ("exportaciones", "EXPORTACIONES", "Exportación de fruta", "El ciclo completo de exportación de fruta, desde la planificación hasta la liquidación del recibidor.", ["Programas de ventas y de embalajes", "Embarques y documentación", "Control financiero y cobranzas a clientes", "Liquidación de recibidor y cálculo IVV", "Costos por embarque", "Reclamos de clientes"], "M3 11h13v10H3zM3 11l3-3h7l3 3M18 4h3m0 0-2-2m2 2-2 2"),
    ("exportaciones", "EXPORTACIONES", "Productores", "Controle sus contratos de compra de fruta integrando estimaciones, plan financiero, embarques, preliquidación y liquidación de temporada.", ["Estimaciones de productores contratados", "Gestión de contratos de compra de fruta", "Preliquidaciones basadas en precios esperados", "Liquidaciones integradas, fáciles y oportunas", "Portal de Productores"], "M12 3c-5 0-8 3-8 8 0 5 3 9 8 10 5-1 8-5 8-10 0-5-3-8-8-8zM7 14c2-3 5-4 10-4"),
    ("exportaciones", "EXPORTACIONES", "Packing", "Control automatizado de los procesos de packing y frigorífico.", ["Control de recepciones de fruta", "Procesos de packing y medición de indicadores", "Aplicaciones móviles de paletizado y tarjas", "Cierres de proceso oportunos y validados", "Costos diarios de procesos y materiales"], "M3 7l9-4 9 4-9 4-9-4zM3 7v10l9 4 9-4V7M12 11v10"),
]

CATEGORY_ORDER = ("campo", "personas", "logistica", "finanzas", "exportaciones")
ARTICLE_RE = re.compile(r'<article class="steps-product" data-category="([^"]+)">.*?</article>', re.S)


def new_article(card: tuple[str, str, str, str, list[str], str]) -> str:
    category, label, title, description, bullets, icon_path = card
    items = "".join(f"<li>{escape(item)}</li>" for item in bullets)
    return (
        f'<article class="steps-product" data-category="{category}">\n'
        f'        <div class="steps-product__top"><span class="steps-product__icon"><svg class="st-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="{icon_path}"/></svg></span><span>{label}</span><small>00</small></div>\n'
        f'        <h3>{escape(title)}</h3><p>{escape(description)}</p>\n'
        f'        <details><summary>Ver capacidades <span aria-hidden="true">+</span></summary><ul>{items}</ul></details>\n'
        '    </article>'
    )


def transform(source: str) -> str:
    start_marker = '<div class="steps-catalog">'
    end_marker = '<div class="steps-catalog-note">'
    if source.count(start_marker) != 1 or source.count(end_marker) != 1:
        raise ValueError("Expected exactly one Steps catalog")
    before, rest = source.split(start_marker, 1)
    catalog, after = rest.split(end_marker, 1)
    found = ARTICLE_RE.findall(catalog)
    if len(found) not in (12, 13, 20):
        raise ValueError(f"Unexpected existing catalog size: {len(found)}")
    articles = {category: [] for category in CATEGORY_ORDER}
    for match in ARTICLE_RE.finditer(catalog):
        category = match.group(1)
        article = match.group(0)
        title = re.search(r"<h3>(.*?)</h3>", article, re.S)
        if category not in articles or not title:
            raise ValueError("Unknown category or missing title")
        if title.group(1) in {card[2] for card in NEW_CARDS}:
            continue
        # The unpublished module has one generic Exportaciones card. The
        # workbook replaces it with three specific export offerings.
        if title.group(1) == "Exportaciones":
            continue
        articles[category].append(article)
    if sum(map(len, articles.values())) != 12:
        raise ValueError("Expected the 12 original offerings")
    for card in NEW_CARDS:
        articles[card[0]].append(new_article(card))
    all_articles = [article for group in CATEGORY_ORDER for article in articles[group]]
    if len(all_articles) != 20:
        raise ValueError("Expected 20 offerings after transformation")
    all_articles = [re.sub(r"<small>\d{2}</small>", f"<small>{number:02d}</small>", article, count=1)
                    for number, article in enumerate(all_articles, 1)]
    replacement = start_marker + "".join(all_articles) + "</div>\n    " + end_marker
    result = before + replacement + after
    filter_pattern = re.compile(r'<div class="steps-filters".*?</div>', re.S)
    filters = (
        '<div class="steps-filters" role="group" aria-label="Filtrar soluciones por área" hidden="hidden">'
        '<button type="button" data-filter="all" aria-pressed="true">Todas las soluciones <span>20</span></button>'
        '<button type="button" data-filter="campo" aria-pressed="false">Campo y producción</button>'
        '<button type="button" data-filter="personas" aria-pressed="false">Personas</button>'
        '<button type="button" data-filter="logistica" aria-pressed="false">Recursos y logística</button>'
        '<button type="button" data-filter="finanzas" aria-pressed="false">Finanzas</button>'
        '<button type="button" data-filter="exportaciones" aria-pressed="false">Exportaciones</button>'
        '</div>'
    )
    result, replacements = filter_pattern.subn(filters, result)
    if replacements != 1:
        raise ValueError("Expected exactly one filters group")
    ElementTree.fromstring(result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    source = args.input.read_text(encoding="utf-8")
    result = transform(source)
    args.output.write_text(result, encoding="utf-8")
    print(f"Wrote {args.output}: 20 cards, 5 categories")


if __name__ == "__main__":
    main()
