{
    "name": "Steps - Previred por departamento",
    "version": "18.0.3.8.1",
    "category": "Human Resources/Payroll",
    "summary": "TXT Previred consolidado o por departamento, más Excel de revisión",
    "description": """
Previred por departamento
=========================

Amplía y valida el archivo Previred que genera el motor de nómina instalado,
sin modificar el addon del proveedor.

* **TXT consolidado**: conserva los importes conciliados del motor y normaliza
  los campos que la especificación oficial vigente exige.
* **TXT por departamento**: un archivo por departamento, entregados en un ZIP
  con manifiesto de control (archivo, departamento, conteos y SHA-256).
* **Excel de revisión**: consolidado con hoja Resumen y hoja por departamento,
  o un XLSX por departamento. Refleja el mismo dataset que el TXT y no
  recalcula ningún valor.

Las líneas anexas de un trabajador (tipos 01, 02 y 03) viajan siempre
inmediatamente después de su línea principal, también al partir el archivo por
departamento: es lo que exige la especificación para que Previred las
contabilice.

Formato oficial
---------------

Formato estándar largo variable, por separador. Se mantienen perfiles
históricos (v84 hasta julio de 2026) y el perfil v98 vigente desde agosto de
2026; cada lote queda atado a la versión correspondiente a su período.

Previred recibe archivos **TXT, CSV o ZIP**. El XLSX es una salida de control
para personas y está rotulado como tal: no es un archivo cargable en Previred.

Este módulo genera archivos para carga y control. **No** los envía a Previred
ni confirma su aceptación por la plataforma.
""",
    "author": "Steps Consulting",
    "website": "https://stepsapp.cl",
    "license": "LGPL-3",
    "depends": ["hr_payroll"],
    "external_dependencies": {"python": ["xlsxwriter"]},
    "data": [
        "security/previred_security.xml",
        "security/ir.model.access.csv",
        "views/previred_wizard_views.xml",
        "views/previred_profile_views.xml",
        "views/previred_batch_views.xml",
        "views/resource_calendar_views.xml",
    ],
    "post_init_hook": "post_init_hook",
    "installable": True,
    "application": False,
}
