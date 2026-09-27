# -*- coding: utf-8 -*-
{
    "name": "Steps - Corrección de finiquitos",
    "summary": "Herramienta de Administrador para corregir asistencia y liquidaciones "
               "cuando un finiquito quedó con la fecha real de término mal registrada",
    "description": """Motivo: es fácil equivocar la fecha real de término al procesar un
finiquito (día festivo, error de digitación, etc.). Cuando eso pasa, Odoo sigue
generando y validando asistencia después del último día trabajado, y la liquidación
del período queda calculada sobre días de más. Corregirlo a mano requiere desbloquear
la liquidación, volver la asistencia a borrador y recién ahí eliminarla, y recalcular:
son varios pasos técnicos y sólo el perfil Administrador puede hacerlos.

Este módulo reduce todo eso a un formulario: se indica el trabajador y el último día
realmente trabajado, se revisa la vista previa de lo que se va a tocar, y un botón
aplica la corrección completa. Las liquidaciones ya pagadas nunca se tocan
automáticamente: quedan marcadas para revisión manual.

No es un fix de código: es una herramienta operativa para que el error humano de
fecha, si vuelve a pasar, se corrija en minutos y sin tocar la base de datos a mano.""",
    "version": "18.0.1.0.1",
    "category": "Human Resources/Payroll",
    "author": "Steps Consulting",
    "license": "LGPL-3",
    "depends": ["hr_work_entry_contract", "hr_payroll"],
    "data": [
        "security/hr_payroll_correction_security.xml",
        "security/ir.model.access.csv",
        "wizard/hr_termination_correction_wizard_views.xml",
    ],
    "installable": True,
    "application": False,
}
