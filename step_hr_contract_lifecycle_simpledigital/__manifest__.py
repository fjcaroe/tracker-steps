{
    "name": "Steps - Gestión Contractual y Finiquitos (Adaptador SimpleDigital)",
    "version": "18.0.1.0.0",
    "category": "Human Resources/Employees",
    "summary": "Adaptador de step_hr_contract_lifecycle para l10n_cl_simpledigital_payroll",
    "description": """
Adaptador SimpleDigital para el núcleo contractual
=====================================================

Conecta ``step_hr_contract_lifecycle`` con
``l10n_cl_simpledigital_payroll`` (motor usado en Demo-SyS):

* mapea AFP (``hr.contract.afp_option``), salud
  (``hr.contract.health_institution``) y jornada
  (``hr.contract.work_schedule_id``);
* mapea la comuna real vía ``hr.employee.hr_commune``
  (``res.country.commune``);
* migra de forma idempotente las causales de ``hr.causal.contract.end``
  (vinculadas hoy a ``hr.employee.causal_contract_end_id``) hacia
  ``step.hr.termination.cause``, sin borrar el maestro original;
* NO modifica el cálculo de liquidaciones de SimpleDigital ni hereda el
  reporte de liquidación por el XPath ``worked_days_table`` que causó la
  incompatibilidad original;
* NO instala ``step_hr`` ni ``l10n_cl_hr``.

SimpleDigital no tiene un modelo de finiquito propio (el término
mid-month se resuelve dentro del cálculo de la liquidación): el modelo
canónico de finiquito sigue siendo ``hr.severance`` del núcleo.
    """,
    "author": "Steps Consulting",
    "website": "https://stepsapp.cl",
    "license": "LGPL-3",
    "depends": [
        "step_hr_contract_lifecycle",
        "l10n_cl_simpledigital_payroll",
    ],
    "data": [],
    "post_init_hook": "post_init_hook",
    "installable": True,
    "application": False,
}
