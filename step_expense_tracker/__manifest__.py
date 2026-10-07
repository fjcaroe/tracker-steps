{
    'name': 'Steps Gastos · Traer recorridos desde Tracker',
    'summary': 'Importa el uso de vehículos de Tracker a las rendiciones de gastos y enlaza el vehículo con sus gastos',
    'description': """
Puente entre ``step_expense_report`` (rendiciones) y Steps Tracker:

* Asistente «Traer desde Tracker» en la pestaña de uso de vehículo: vista previa de sesiones
  cerradas del vehículo y período, selección explícita y creación de líneas en borrador.
* El vehículo se identifica en cada línea de uso (no en la cabecera de la rendición).
* Las líneas conservan una instantánea de lo importado y una referencia al hecho de uso
  (``step.tracker.usage``); no se sobrescriben correcciones manuales ni rendiciones aprobadas.
* Vehículo por gasto (atribución explícita) y accesos «Gastos» / «Rendiciones» desde la ficha
  del vehículo.
""",
    'version': '18.0.1.0.0',
    'category': 'Human Resources/Expenses',
    'author': 'Steps Consulting',
    'license': 'LGPL-3',
    'depends': ['step_expense_report', 'step_tracker_usage', 'fleet'],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'wizard/expense_tracker_import_views.xml',
        'views/expense_views.xml',
        'views/fleet_vehicle_views.xml',
    ],
    'installable': True,
    'application': False,
}
