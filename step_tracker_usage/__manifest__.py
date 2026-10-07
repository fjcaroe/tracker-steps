{
    'name': 'Steps Tracker · Uso de vehículos',
    'summary': 'Hechos de uso de Tracker (sesiones cerradas) con vínculos explícitos a flota, empleados y cuentas analíticas',
    'description': """
Capa común para consumir Tracker desde procesos económicos (Gastos, Gestión y Costos)
sin depender de ``step_hr``:

* ``step.tracker.usage``: hecho de uso por sesión cerrada, con una indicación explícita de
  dato disponible / desconocido (distancia, horómetro, recarga de combustible).
* ``step.tracker.cost_center``: centros de costo de Tracker con correspondencia explícita
  hacia ``account.analytic.account`` (nunca por nombre).
* Sincronización por período con paginación estable y aviso de cobertura incompleta.
* Reglas de compañía para los espejos históricos ``step.tracker.*``.

Los modelos ``step.tracker.machine|driver|session|work_order`` los puede definir ``step_hr`` y/o
``step_tracker_odoo``; este módulo no los redefine, solo los referencia.
""",
    'version': '18.0.1.0.0',
    'category': 'Operations',
    'author': 'Steps Consulting',
    'license': 'LGPL-3',
    'depends': ['step_tracker_odoo', 'fleet', 'hr', 'account'],
    'data': [
        'security/ir.model.access.csv',
        'security/ir_rule.xml',
        'views/step_tracker_usage_views.xml',
        'views/step_tracker_cost_center_views.xml',
    ],
    'installable': True,
    'application': False,
}
