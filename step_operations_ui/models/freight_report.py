from odoo import fields, models, tools

# Tabla creada por Studio en Desarrollo (hoja "Costeo" de Registro de fletes),
# no declarada en ningún manifiesto. Puede no existir todavía en otras bases
# (Demo, Demo-SyS, SyS, o la base de pruebas vacía que usan los tests
# automáticos): las vistas SQL de este archivo lo comprueban antes de leerla
# y se degradan a una vista vacía si no está, para no romper la instalación
# del módulo en esas bases.
STUDIO_COSTEO_LINE_TABLE = "x_orden_de_flete_line_72953"


def _table_exists(cr, table_name):
    cr.execute("SELECT to_regclass(%s) IS NOT NULL", (table_name,))
    return cr.fetchone()[0]


class StepFreightCostReport(models.Model):
    """Lectura de las líneas de costeo reales cargadas en Registro de fletes
    (Studio: x_orden_de_flete_line_72953) con la fecha y el tramo de la orden.

    Nota: depende de los nombres técnicos actuales de los campos/tablas creados
    por Studio en x_orden_de_flete. Si esos campos se renombran o se migra el
    formulario de Registro de fletes a código, esta vista SQL debe actualizarse.
    """

    _name = "step.freight.cost.report"
    _description = "Análisis de fletes (costeo real)"
    _auto = False
    _order = "order_date desc, id desc"

    order_id = fields.Many2one("x_orden_de_flete", string="Orden de flete", readonly=True)
    order_date = fields.Date(string="Fecha", readonly=True)
    route_id = fields.Many2one("x_tramo_de_flete", string="Tramo", readonly=True)
    carrier_id = fields.Many2one("res.partner", string="Transportista", readonly=True)
    product_id = fields.Many2one("product.template", string="Servicio de flete", readonly=True)
    account_id = fields.Many2one("account.account", string="Cuenta", readonly=True)
    amount = fields.Float(string="Valor del flete", readonly=True)
    company_id = fields.Many2one("res.company", string="Compañía", readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        if _table_exists(self.env.cr, STUDIO_COSTEO_LINE_TABLE):
            self.env.cr.execute("""
                CREATE OR REPLACE VIEW %s AS (
                    SELECT
                        cost.id AS id,
                        ord.id AS order_id,
                        ord.x_studio_fecha AS order_date,
                        ord.route_id AS route_id,
                        ord.x_studio_transportista AS carrier_id,
                        cost.x_studio_servicio_flete AS product_id,
                        cost.x_studio_cuenta AS account_id,
                        cost.x_studio_costo_flete AS amount,
                        ord.company_id AS company_id
                    FROM x_orden_de_flete_line_72953 cost
                    JOIN x_orden_de_flete ord ON ord.id = cost.x_orden_de_flete_id
                )
            """ % self._table)
        else:
            self.env.cr.execute("""
                CREATE OR REPLACE VIEW %s AS (
                    SELECT
                        NULL::integer AS id, NULL::integer AS order_id, NULL::date AS order_date,
                        NULL::integer AS route_id, NULL::integer AS carrier_id,
                        NULL::integer AS product_id, NULL::integer AS account_id,
                        NULL::numeric AS amount, NULL::integer AS company_id
                    WHERE false
                )
            """ % self._table)


class StepFreightPlanVsActual(models.Model):
    """Compara, por semana y servicio de flete (producto), el monto
    planificado (Planificar fletes) contra el costo real registrado
    (Registro de fletes, hoja Costeo) y calcula la diferencia.

    Igual que StepFreightCostReport, el lado "real" depende de los campos
    técnicos de Studio en x_orden_de_flete_line_72953; si esa tabla no existe
    todavía en la base, el lado "real" queda en cero (solo se compara contra
    lo planificado) en lugar de romper la instalación del módulo.
    """

    _name = "step.freight.plan.vs.actual"
    _description = "Fletes: planificado vs. real por semana"
    _auto = False
    _order = "week_start desc"

    week_start = fields.Date(string="Semana (inicio lunes)", readonly=True)
    product_id = fields.Many2one("product.template", string="Servicio de flete", readonly=True)
    planned_amount = fields.Float(string="Planificado", readonly=True)
    real_amount = fields.Float(string="Real", readonly=True)
    diff_amount = fields.Float(string="Diferencia (real - planificado)", readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        real_source = (
            """
                    SELECT
                        (date_trunc('week', ord.x_studio_fecha::timestamp))::date AS week_start,
                        cost.x_studio_servicio_flete AS product_id,
                        0.0 AS planned_amount,
                        cost.x_studio_costo_flete AS real_amount
                    FROM x_orden_de_flete_line_72953 cost
                    JOIN x_orden_de_flete ord ON ord.id = cost.x_orden_de_flete_id
                    WHERE ord.x_studio_fecha IS NOT NULL
                      AND cost.x_studio_servicio_flete IS NOT NULL
            """
            if _table_exists(self.env.cr, STUDIO_COSTEO_LINE_TABLE)
            else """
                    SELECT
                        NULL::date AS week_start, NULL::integer AS product_id,
                        NULL::numeric AS planned_amount, NULL::numeric AS real_amount
                    WHERE false
            """
        )
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW %s AS (
                SELECT
                    row_number() OVER () AS id,
                    week_start,
                    product_id,
                    SUM(planned_amount) AS planned_amount,
                    SUM(real_amount) AS real_amount,
                    SUM(real_amount) - SUM(planned_amount) AS diff_amount
                FROM (
                    SELECT
                        (date_trunc('week', plan.x_studio_fecha::timestamp))::date AS week_start,
                        line.product_id AS product_id,
                        line.amount_total AS planned_amount,
                        0.0 AS real_amount
                    FROM x_planificacion_de_flete_linea line
                    JOIN x_planificacion_de_flete plan ON plan.id = line.plan_id
                    WHERE plan.x_studio_fecha IS NOT NULL

                    UNION ALL
                    %s
                ) combined
                WHERE week_start IS NOT NULL
                GROUP BY week_start, product_id
            )
        """ % (self._table, real_source))
