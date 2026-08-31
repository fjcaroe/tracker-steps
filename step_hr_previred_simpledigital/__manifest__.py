{
    "name": "Steps - Previred: motor SimpleDigital",
    "version": "18.0.2.1.0",
    "category": "Human Resources/Payroll",
    "summary": "Conecta el Previred por departamento de Steps con SimpleDigital",
    "description": """
Previred Steps — puente con el motor SimpleDigital
===================================================

Único punto del sistema que conoce `l10n_cl_simpledigital_payroll`. Aporta:

* el adaptador que reutiliza el generador `/hr_payroll/previred/txt` ya en
  producción, incluidas sus líneas anexas por movimiento de personal;
* la **matriz campo Previred → dato del motor**, generada desde el código del
  generador, no deducida;
* el perfil de formato del motor, con sus estados exportables justificados;
* la redirección del menú `Nómina / Reportes / Previred TXT Remuneraciones`
  hacia el asistente nuevo, para que exista un solo flujo Previred visible;
* el **cierre de la ruta insegura del proveedor**: `/hr_payroll/previred/txt`
  y `/hr_payroll/previred/csv` aceptaban la compañía desde la URL y
  consultaban con `sudo()`. Se corrige heredando el controlador, sin modificar
  el addon del proveedor.
""",
    "author": "Steps Consulting",
    "website": "https://stepsapp.cl",
    "license": "LGPL-3",
    "depends": ["step_hr_previred", "l10n_cl_simpledigital_payroll"],
    "data": [
        "data/previred_profile.xml",
        "views/menu_views.xml",
    ],
    "post_init_hook": "post_init_hook",
    "installable": True,
    "auto_install": True,
    "application": False,
}
