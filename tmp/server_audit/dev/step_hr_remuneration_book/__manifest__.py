{
    "name": "Steps - Libro de Remuneraciones",
    "version": "18.0.3.2.0",
    "category": "Human Resources/Payroll",
    "summary": "Libro consolidado por departamento en Excel y PDF, y archivo oficial DT",
    "description": """
Libro de Remuneraciones Steps
=============================

Dos productos claramente separados:

* **Libro consolidado** (Excel y PDF): informe de control interno con 24
  columnas mapeadas por código DT, agrupadas por departamento, con subtotales
  por grupo y total general.
* **Archivo oficial DT** (CSV): el archivo de carga masiva del Libro de
  Remuneraciones Electrónico, con su estructura completa y delimitador `;`.

El módulo genera el archivo para carga y control. No declara ante Mi DT ni
confirma su aceptación por la plataforma estatal.

Los valores provienen de las liquidaciones ya calculadas por el motor de
nómina instalado, mediante un perfil de mapeo configurable. El módulo no
reimplementa el cálculo previsional ni modifica el addon del proveedor.

El libro corporativo exige el grupo «Libro de Remuneraciones: exportación
completa», que implica acceso real a todas las liquidaciones de la compañía.
Para el resto del personal de Nómina existe un «Reporte parcial de
remuneraciones», rotulado como tal y sin archivo oficial DT.
""",
    "author": "Steps Consulting",
    "website": "https://stepsapp.cl",
    "license": "LGPL-3",
    "depends": ["hr_payroll"],
    "external_dependencies": {"python": ["xlsxwriter"]},
    "data": [
        "security/remuneration_book_security.xml",
        "security/ir.model.access.csv",
        "data/remuneration_book_profiles.xml",
        "report/remuneration_book_report.xml",
        "views/remuneration_book_preview_templates.xml",
        "views/remuneration_book_profile_views.xml",
        "views/hr_libro_remuneraciones_wizard_views.xml",
        "views/payroll_dashboard_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "step_hr_remuneration_book/static/src/payroll_dashboard/payroll_dashboard.js",
            "step_hr_remuneration_book/static/src/payroll_dashboard/payroll_dashboard.xml",
            "step_hr_remuneration_book/static/src/payroll_dashboard/payroll_dashboard.scss",
        ],
    },
    "post_init_hook": "post_init_hook",
    "installable": True,
    "application": True,
}
