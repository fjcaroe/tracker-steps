{
    "name": "Steps - Gestión Contractual y Finiquitos (Núcleo)",
    "version": "18.0.2.0.1",
    "category": "Human Resources/Employees",
    "summary": "Núcleo contractual independiente de motor: contratos, cargas DT, avisos de término y finiquitos",
    "description": """
Núcleo contractual y de término laboral para Nómina Steps
============================================================

Independiente del motor de nómina instalado. Depende únicamente de
módulos estándar de Odoo (hr_contract, hr_payroll, hr_holidays, mail,
analytic). Provee:

* Calendario legal laboral versionado (jornada máxima 44h -> 42h -> 40h) con
  adecuación automática de contratos y alertas anticipadas.
* Maestro propio de causales de término (step.hr.termination.cause),
  independiente de cualquier motor.
* Plantillas laborales versionadas: contrato de temporada, a trato, a plazo
  fijo, permanente/indefinido, carta de aviso y finiquito.
* Emisión individual y masiva de contratos con snapshot histórico del PDF.
* Carga masiva de contratos a la Dirección del Trabajo (CSV).
* Cartas de aviso de término (individuales y masivas) y registro de término
  de contrato, con carga masiva a la DT.
* Cálculo auditable de finiquitos (feriado proporcional, indemnización por
  años de servicio, indemnización por meses de servicio, sustitutiva de
  aviso previo) y carga masiva de finiquitos electrónicos a la DT.

Los datos específicos de cada motor de nómina (AFP, salud, jornada,
causal legada, ubicación agrícola, etc.) NO se leen directamente desde
este módulo: se resuelven mediante los métodos
``_steps_contract_payload`` / ``_steps_pension_payload`` /
``_steps_termination_payload`` en ``hr.contract``, que sobreescriben:

* ``step_hr_contract_lifecycle_agriculture`` (Desarrollo/Demo, step_hr +
  l10n_cl_hr);
* ``step_hr_contract_lifecycle_simpledigital`` (Demo-SyS,
  l10n_cl_simpledigital_payroll).
    """,
    "author": "Steps Consulting",
    "website": "https://stepsapp.cl",
    "license": "LGPL-3",
    "depends": [
        "hr_contract",
        "hr_holidays",
        "hr_payroll",
        "hr_work_entry_contract_enterprise",
        "mail",
        "analytic",
    ],
    "data": [
        "security/hr_contract_lifecycle_groups.xml",
        "security/ir.model.access.csv",
        "security/ir_rule.xml",
        "data/hr_legal_workweek_calendar_data.xml",
        "data/hr_labor_document_sequence_data.xml",
        "data/ir_cron_data.xml",
        "report/hr_labor_document_reports.xml",
        "report/hr_labor_document_templates.xml",
        "views/hr_legal_workweek_calendar_views.xml",
        "views/hr_contract_adequacy_batch_views.xml",
        "views/step_hr_termination_cause_views.xml",
        "views/hr_labor_template_views.xml",
        "views/hr_contract_views.xml",
        "views/dt_contract_batch_views.xml",
        "views/hr_termination_notice_views.xml",
        "views/hr_severance_views.xml",
        "views/menus.xml",
        "wizard/hr_legal_calendar_simulator_views.xml",
    ],
    "installable": True,
    "application": False,
}
# NOTA DE AVANCE:
# 18.0.2.0.0 separa el nucleo de todo motor de nomina especifico (ver
# docs/CLAUDE_SEPARACION_CONTRATOS_FINQUITOS_SIMPLEDIGITAL.md y el informe
# de entrega en docs/ENTREGA_ADAPTER_CONTRATOS_SIMPLEDIGITAL.md). Requiere
# un adaptador instalado (agriculture o simpledigital) para que los datos
# previsionales, de jornada y de causal queden completos en los CSV DT.
