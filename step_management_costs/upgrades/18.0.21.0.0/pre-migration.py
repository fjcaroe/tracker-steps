"""T51 — el centro de costo de Gestión y Costos pasa a ser la cuenta analítica.

Se eliminó el modelo propio `step.management.cost.center`. Antes de que el ORM
cambie los `Many2one`/`Many2many` hacia `account.analytic.account`, esta
pre-migración (sólo SQL, reejecutable):

1. agrega a `account_analytic_account` las columnas de gestión (tipo,
   hectáreas, plantas, fundo, cuartel, especie, variedad);
2. asocia cada centro antiguo con su cuenta analítica: la que ya tenía
   (`analytic_account_id`) o, si no tenía, una cuenta nueva con su mismo
   código, nombre y empresa. Nunca se adivina por coincidencia de texto;
3. reescribe todas las columnas que apuntaban al centro antiguo (también las
   de módulos puente fuera de este addon) para que apunten a la cuenta, y
   quita esas claves foráneas antiguas;
4. deja el centro antiguo sin referencias; Odoo elimina su tabla al
   retirar el modelo.

Si el modelo antiguo ya no existe, no hace nada.
"""

import json
import logging

_logger = logging.getLogger(__name__)

OLD_TABLE = "step_management_cost_center"
MANAGEMENT_COLUMNS = (
    ("cost_type", "varchar"), ("hectares", "numeric"), ("plants", "numeric"),
    ("farm", "varchar"), ("plot", "varchar"), ("species", "varchar"),
    ("variety", "varchar"),
)


def migrate(cr, version):
    if not version:
        return
    cr.execute("SELECT to_regclass(%s)", (OLD_TABLE,))
    if not cr.fetchone()[0]:
        return

    for column, sql_type in MANAGEMENT_COLUMNS:
        cr.execute(
            "ALTER TABLE account_analytic_account ADD COLUMN IF NOT EXISTS %s %s"
            % (column, sql_type)
        )

    cr.execute("""
        SELECT id, code, name, company_id, active, cost_type, hectares, plants,
               farm, plot, species, variety, analytic_account_id
          FROM step_management_cost_center ORDER BY id
    """)
    centers = cr.fetchall()

    cr.execute("CREATE TEMP TABLE IF NOT EXISTS t51_center_map (old_id integer PRIMARY KEY, new_id integer NOT NULL) ON COMMIT DROP")
    plan_id = None
    created = reused = 0
    seen_accounts = {}
    for (center_id, code, name, company_id, active, cost_type, hectares, plants,
         farm, plot, species, variety, account_id) in centers:
        values = {
            "cost_type": cost_type, "hectares": hectares, "plants": plants,
            "farm": farm, "plot": plot, "species": species, "variety": variety,
        }
        if account_id:
            reused += 1
            if account_id in seen_accounts:
                raise RuntimeError("T51: varios centros comparten una cuenta analítica; revisar sus valores y relaciones antes de fusionarlos.")
            else:
                seen_accounts[account_id] = center_id
                # No se pisa un dato de gestión que la cuenta ya tuviera.
                sets = ", ".join(
                    "%(c)s = COALESCE(NULLIF(%(c)s, ''), %%(%(c)s)s)" % {"c": c}
                    if c in ("farm", "plot", "species", "variety", "cost_type")
                    else "%(c)s = CASE WHEN COALESCE(%(c)s, 0) = 0 THEN %%(%(c)s)s ELSE %(c)s END" % {"c": c}
                    for c in values
                )
                cr.execute(
                    "UPDATE account_analytic_account SET %s WHERE id = %%(id)s" % sets,
                    dict(values, id=account_id),
                )
        else:
            if plan_id is None:
                cr.execute(
                    "SELECT id FROM account_analytic_plan WHERE parent_id IS NULL ORDER BY id LIMIT 1"
                )
                row = cr.fetchone()
                if not row:
                    raise RuntimeError(
                        "T51: no existe ningún plan analítico para crear la cuenta del centro %s." % code
                    )
                plan_id = row[0]
            cr.execute(
                """
                INSERT INTO account_analytic_account
                       (name, code, company_id, active, plan_id, root_plan_id,
                        cost_type, hectares, plants, farm, plot, species, variety,
                        create_uid, write_uid, create_date, write_date)
                VALUES (%(name)s::jsonb, %(code)s, %(company_id)s, %(active)s, %(plan_id)s, %(plan_id)s,
                        %(cost_type)s, %(hectares)s, %(plants)s, %(farm)s, %(plot)s,
                        %(species)s, %(variety)s, 1, 1, now(), now())
                RETURNING id
                """,
                dict(values, name=json.dumps({"en_US": name}), code=code,
                     company_id=company_id, active=active, plan_id=plan_id),
            )
            account_id = cr.fetchone()[0]
            created += 1
        cr.execute("INSERT INTO t51_center_map VALUES (%s, %s) ON CONFLICT (old_id) DO UPDATE SET new_id=EXCLUDED.new_id", (center_id, account_id))
        cr.execute("UPDATE step_management_cost_center SET analytic_account_id=%s WHERE id=%s", (account_id, center_id))

    cr.execute("""
        SELECT c.conname, c.conrelid::regclass::text, a.attname
          FROM pg_constraint c
          JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = c.conkey[1]
         WHERE c.contype = 'f' AND c.confrelid = %s::regclass
    """, (OLD_TABLE,))
    for conname, table, column in cr.fetchall():
        cr.execute('ALTER TABLE %s DROP CONSTRAINT "%s"' % (table, conname))
        cr.execute(
            'UPDATE %(t)s SET "%(c)s" = m.new_id FROM t51_center_map m WHERE %(t)s."%(c)s" = m.old_id'
            % {"t": table, "c": column}
        )
        _logger.info("T51: %s.%s reapuntada del centro antiguo a la cuenta analítica.", table, column)

    # Update inherited view metadata before the core form changes its model;
    # installed bridges must not temporarily validate against a removed model.
    cr.execute("UPDATE ir_ui_view SET model='account.analytic.account' WHERE model='step.management.cost.center'")
    cr.execute("UPDATE ir_act_window SET res_model='account.analytic.account' WHERE res_model='step.management.cost.center'")
    cr.execute("""
        UPDATE ir_model_data d SET model='account.analytic.account',res_id=m.new_id
          FROM t51_center_map m WHERE d.model='step.management.cost.center' AND d.res_id=m.old_id
    """)

    _logger.info(
        "T51: %s centro(s) migrados a cuentas analíticas (%s existentes, %s creadas).",
        len(centers), reused, created,
    )
