"""Make the Studio-created freight line models portable (ticket T27, puntos 3 y 4).

Igual que migrations/18.0.2.0.1/pre-migrate.py hizo para los seis modelos
principales de Fletes, estos tres modelos de línea (hojas "Tarifas",
"Detalles" y "Costeo" de los formularios Studio) ya existen en la base como
modelos manuales (ir_model.state = 'manual', creados por Studio) pero su
único ir_model_data conocido pertenece al módulo studio_customization, con
nombres aleatorios (p. ej. "tarifa_de_fletes_lin_8dda065d-...").
ir.model.access.csv de este módulo referencia esos modelos por el id externo
corto "model_<nombre_tecnico>" (implícitamente bajo step_operations_ui), que
no existe todavía. Sin este paso, la actualización del módulo falla al
cargar la CSV de permisos con "No se encontraron registros que coincidan
con id externo".
"""


def migrate(cr, version):
    model_names = (
        "x_tarifa_de_fletes_line_57b07",
        "x_orden_de_flete_line_709f3",
        "x_orden_de_flete_line_72953",
    )
    for model_name in model_names:
        cr.execute(
            """
            INSERT INTO ir_model_data (module, name, model, res_id, noupdate)
            SELECT %s, %s, 'ir.model', id, TRUE
              FROM ir_model
             WHERE model = %s
               AND NOT EXISTS (
                   SELECT 1
                     FROM ir_model_data
                    WHERE module = %s AND name = %s
               )
            """,
            (
                "step_operations_ui",
                f"model_{model_name}",
                model_name,
                "step_operations_ui",
                f"model_{model_name}",
            ),
        )
