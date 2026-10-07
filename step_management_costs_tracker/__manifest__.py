{
    'name': 'Steps Gestión y Costos · Costos por vehículo desde Tracker',
    'summary': 'Costo real, gasto pendiente, cantidades operativas y presupuesto por vehículo y centro, con acceso desde Steps Tracker',
    'description': """
Puente entre Steps Tracker, Gastos (``step_expense_tracker``) y Gestión y Costos:

* Correspondencia explícita activo de Tracker ↔ vehículo de Odoo (por compañía, con historial).
* Servicio de costos: costo real (solo apuntes publicados, con reversas), gasto pendiente, cantidades
  operativas (km GPS, horas de sesión, horómetro) y presupuesto, sin sumar monedas ni repartir costos
  compartidos sin una regla explícita.
* Endpoint del mismo origen para el portal: ``GET /steps_tracker/costs/assets/<asset_id>``. Comprueba
  los permisos efectivos del usuario; un rol operativo sin acceso a Gastos/Costos no recibe importes.
* Asistente «Costos Tracker» desde el vehículo y desde el centro de costo de Gestión y Costos.

No escribe sobre ``step.management.historical.cost`` ni contabiliza nada.
""",
    'version': '18.0.1.1.1',
    'category': 'Operations/Planning',
    'author': 'Steps Consulting',
    'license': 'LGPL-3',
    'depends': ['step_management_costs', 'step_expense_tracker', 'step_tracker_usage', 'step_tracker_portal'],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'security/ir_rule.xml',
        'views/asset_link_views.xml',
        'views/fleet_vehicle_views.xml',
        'views/cost_center_views.xml',
        'wizard/vehicle_cost_views.xml',
    ],
    'installable': True,
    'application': False,
}
