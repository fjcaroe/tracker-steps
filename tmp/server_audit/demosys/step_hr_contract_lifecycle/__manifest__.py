{
    "name": "Steps - Gestión Contractual y Finiquitos",
    "version": "18.0.1.0.0",
    "category": "Human Resources/Employees",
    "summary": "Emisión de contratos, cargas DT, avisos de término y finiquitos para Nómina Steps",
    "description": """
Gestión contractual y de término laboral para Nómina Steps
============================================================

Extiende hr.contract y el módulo de Nómina (SimpleDigital / Steps) con:

* Calendario legal laboral versionado (jornada máxima 44h -> 42h -> 40h) con
  adecuación automática de contratos y alertas anticipadas.
* Plantillas laborales versionadas: contrato de temporada, a trato, a plazo
  fijo, permanente/indefinido, carta de aviso y finiquito.
* Emisión individual y masiva de contratos con snapshot histórico del PDF.
* Carga masiva de contratos a la Dirección del Trabajo (CSV).
* Cartas de aviso de término (individuales y masivas) y registro de término
  de contrato, con carga masiva a la DT.
* Cálculo auditable de finiquitos (feriado proporcional, indemnización por
  años de servicio, indemnización por meses de servicio, sustitutiva de
  aviso previo) y carga masiva de finiquitos electrónicos a la DT.

No reemplaza el Libro de Remuneraciones (step_hr_remuneration_book) ni el
motor de cálculo de SimpleDigital: se integra con ambos mediante
adaptadores/perfiles.
    """,
    "author": "Steps Consulting",
    "website": "https://stepsapp.cl",
    "license": "LGPL-3",
    "depends": [
        "hr_contract",
        "hr_holidays",
        "mail",
        "step_hr",
        "l10n_cl_hr",
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
        "views/hr_causal_termino_views.xml",
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
# NOTA DE AVANCE (quitar cuando el addon este completo):
# Incremento 1 (calendario legal) + Incremento 2 (hr.contract extendido +
# plantillas laborales versionadas + emision/impresion + snapshot de
# documentos) + Incremento 3 (CSV DT de contratos, agrupado por
# Cargo+CAE) completos.
# Pendientes (Incrementos 4+): cartas de aviso individuales/masivas +
# CSV de 19 columnas, motor de calculo de finiquitos + CSV de 48
# columnas, integracion SimpleDigital/SyS, dashboard de Inicio de
# Nomina, permisos de aprobacion de finiquitos y pruebas de navegador
# end-to-end.
