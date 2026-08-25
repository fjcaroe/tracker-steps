{
    "name": "Steps - Gestión Contractual y Finiquitos (Adaptador Agrícola)",
    "version": "18.0.1.0.0",
    "category": "Human Resources/Employees",
    "summary": "Adaptador de step_hr_contract_lifecycle para step_hr / l10n_cl_hr",
    "description": """
Adaptador agrícola para el núcleo contractual
================================================

Conecta ``step_hr_contract_lifecycle`` con la solución agrícola Steps:

* mapea ``step.fundo`` a la ubicación contractual neutral del núcleo
  (``hr.work.location``);
* mapea AFP, Isapre y tipo de jornada de ``l10n_cl_hr``;
* migra de forma idempotente las causales de ``hr.causal.termino`` hacia
  ``step.hr.termination.cause``, sin borrar el maestro original.

No mueve al adaptador ningún cálculo legal, flujo de aprobación,
documento ni CSV: eso vive exclusivamente en el núcleo.
    """,
    "author": "Steps Consulting",
    "website": "https://stepsapp.cl",
    "license": "LGPL-3",
    "depends": [
        "step_hr_contract_lifecycle",
        "step_hr",
        "l10n_cl_hr",
    ],
    "data": [
        "views/hr_contract_views.xml",
    ],
    "post_init_hook": "post_init_hook",
    "installable": True,
    "application": False,
}
