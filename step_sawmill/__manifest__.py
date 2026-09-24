# -*- coding: utf-8 -*-
{
    "name": "Steps - Aserradero",
    "summary": "Aserrío, elaboración, secado, impregnado y certificación de madera, "
               "con órdenes de producción y trabajo y valorización por producto.",
    "description": """
Aplicación autocontenida de Aserradero (ticket 34, opción C: de Studio a código).

* Órdenes de producción (kanban por etapa) y órdenes de trabajo.
* Aserrío y Elaboración: productos obtenidos, materia prima consumida y
  valorización, con flujo Ingresada -> Autorizada -> Valorizada.
* Secado, Impregnado y Certificación de impregnado.
* Cuadrillas, catálogos de madera (grado, calidad, tipo, destino) y turnos.

Solo depende de módulos estándar de Odoo (base, mail, product, stock, mrp, hr):
no requiere ningún otro módulo Steps ni Enterprise, para poder instalarse en
otras instancias.
""",
    "version": "18.0.1.0.0",
    "category": "Manufacturing",
    "author": "Steps Consulting",
    "license": "LGPL-3",
    "depends": ["base", "mail", "product", "stock", "mrp", "hr"],
    "data": [
        "security/security.xml",
        "security/ir.model.access.csv",
        "data/sequences.xml",
        "data/stages.xml",
        "views/catalog_views.xml",
        "views/planning_views.xml",
        "views/sawing_views.xml",
        "views/elaboration_views.xml",
        "views/drying_views.xml",
        "views/impregnation_views.xml",
        "views/certification_views.xml",
        "views/menu.xml",
    ],
    "demo": ["demo/demo.xml"],
    "application": True,
    "installable": True,
}
