{
    "name": "Steps - Previred: motor Blueminds",
    "version": "18.0.2.0.0",
    "category": "Human Resources/Payroll",
    "summary": "Conecta el Previred por departamento de Steps con l10n_cl_hr",
    "description": """
Previred Steps — puente con el motor Blueminds
==============================================

Único punto del sistema que conoce `l10n_cl_hr`. Aporta:

* el adaptador que reutiliza el asistente `wizard.export.csv.previred` ya en
  producción, de modo que los importes de los 105 campos son los que la
  empresa concilia hoy;
* la **matriz campo Previred → dato del motor**, generada desde el código del
  generador, no deducida;
* el perfil de formato del motor;
* la redirección del menú Previred que este motor ya publicaba, para que exista
  un solo flujo Previred visible dentro de Nómina.

Correcciones deliberadas respecto del generador anterior, todas cubiertas por
pruebas: se filtra por compañía y por estado validado, que el asistente del
proveedor no hacía.
""",
    "author": "Steps Consulting",
    "website": "https://stepsapp.cl",
    "license": "LGPL-3",
    "depends": ["step_hr_previred", "l10n_cl_hr"],
    "data": [
        "data/previred_profile.xml",
        "views/menu_views.xml",
    ],
    "post_init_hook": "post_init_hook",
    "installable": True,
    "auto_install": True,
    "application": False,
}
