# -*- coding: utf-8 -*-
"""Restricciones fitosanitarias (carencia y reingreso) por cuartel.

Las aplicaciones fitosanitarias se registran hoy en el modelo Studio
``x_aplicacion_foliar``.  Este módulo no lo hereda en Python — un modelo manual
no está en el registro cuando se cargan las clases Python — sino que lo lee de
forma defensiva en tiempo de ejecución y materializa el resultado en un modelo
nativo, versionado, con permisos y reglas de registro propias.

El descubrimiento de las líneas de la aplicación se hace **por capacidad** y no
por nombre: los sufijos que genera Studio (``..._line_6808a``) no están
garantizados entre bases, de modo que se busca la línea que sabe de productos y
la línea que sabe de cuarteles.
"""

import logging
from datetime import datetime, time, timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

APPLICATION_MODEL = "x_aplicacion_foliar"

#: Campo del producto que sostiene cada criterio de carencia.  ``label`` es el
#: campo nativo de ``step_hr``; los otros tres son campos Studio del maestro de
#: productos y por eso se leen con guarda.
CARENCIA_FIELD_BY_CRITERION = {
    "label": "dia_carencia",
    "eu": "x_studio_das_carencia_ue",
    "usa": "x_studio_das_carencia_usa",
}


class StepPhytoRestriction(models.Model):
    _name = "step.phyto.restriction"
    _description = "Restricción fitosanitaria por cuartel"
    _order = "harvest_allowed_from desc, id desc"

    cuartel_id = fields.Many2one(
        "step.cuartel.line", string="Cuartel",
        required=True, ondelete="cascade", index=True,
    )
    centro_id = fields.Many2one(
        "account.analytic.account", string="Centro de costo",
        related="cuartel_id.centro_id", store=True, readonly=True,
    )
    fundo_id = fields.Many2one("step.fundo", string="Fundo", index=True)
    company_id = fields.Many2one(
        "res.company", string="Empresa", required=True, index=True,
        default=lambda self: self.env.company,
    )

    application_model = fields.Char(
        string="Modelo de origen", required=True, default=APPLICATION_MODEL,
        help="Modelo desde el que se derivó la restricción.",
    )
    application_id = fields.Integer(string="ID de la aplicación", required=True, index=True)
    application_ref = fields.Char(string="Folio BPA", help="Folio de la aplicación de origen.")

    date_application = fields.Datetime(string="Fecha de aplicación", required=True, index=True)

    product_ids = fields.Many2many(
        "product.template", string="Productos aplicados",
        help="Productos fitosanitarios que determinan la restricción.",
    )
    substances = fields.Char(string="Sustancias activas")

    carencia_days = fields.Integer(string="Días de carencia")
    carencia_criterion = fields.Selection(
        selection=[
            ("label", "Etiqueta (SAG)"),
            ("max", "La mayor de todas"),
            ("eu", "Unión Europea"),
            ("usa", "Estados Unidos"),
        ],
        string="Criterio aplicado",
        help="Criterio vigente al momento de calcular la restricción.",
    )
    reingreso_hours = fields.Float(string="Horas de reingreso")

    harvest_allowed_from = fields.Datetime(
        string="Cosecha permitida desde", compute="_compute_windows",
        store=True, index=True,
    )
    reentry_allowed_from = fields.Datetime(
        string="Reingreso permitido desde", compute="_compute_windows", store=True,
    )

    harvest_blocked = fields.Boolean(
        string="Carencia vigente", compute="_compute_current_state", search="_search_harvest_blocked",
    )
    reentry_blocked = fields.Boolean(
        string="Reingreso vigente", compute="_compute_current_state",
    )
    status = fields.Selection(
        selection=[
            ("carencia", "En carencia"),
            ("reingreso", "Solo reingreso"),
            ("clear", "Liberado"),
        ],
        string="Estado", compute="_compute_current_state",
    )
    days_to_harvest = fields.Integer(
        string="Días para cosechar", compute="_compute_current_state",
        help="Días que faltan para que el cuartel salga de carencia. 0 si ya está liberado.",
    )

    _sql_constraints = [
        (
            "phyto_application_cuartel_uniq",
            "unique(application_model, application_id, cuartel_id)",
            "Ya existe una restricción para esa aplicación y ese cuartel.",
        ),
    ]

    # ------------------------------------------------------------------
    # Cómputos
    # ------------------------------------------------------------------
    @api.depends("date_application", "carencia_days", "reingreso_hours")
    def _compute_windows(self):
        for record in self:
            base = record.date_application
            if not base:
                record.harvest_allowed_from = False
                record.reentry_allowed_from = False
                continue
            record.harvest_allowed_from = base + timedelta(days=record.carencia_days or 0)
            record.reentry_allowed_from = base + timedelta(hours=record.reingreso_hours or 0.0)

    @api.depends("harvest_allowed_from", "reentry_allowed_from")
    def _compute_current_state(self):
        now = fields.Datetime.now()
        for record in self:
            harvest_blocked = bool(record.harvest_allowed_from and record.harvest_allowed_from > now)
            reentry_blocked = bool(record.reentry_allowed_from and record.reentry_allowed_from > now)
            record.harvest_blocked = harvest_blocked
            record.reentry_blocked = reentry_blocked
            if harvest_blocked:
                record.status = "carencia"
                record.days_to_harvest = max(0, (record.harvest_allowed_from - now).days + 1)
            elif reentry_blocked:
                record.status = "reingreso"
                record.days_to_harvest = 0
            else:
                record.status = "clear"
                record.days_to_harvest = 0

    def _search_harvest_blocked(self, operator, value):
        if operator not in ("=", "!="):
            raise UserError(_("Filtro no soportado para 'Carencia vigente'."))
        blocked = bool(value) if operator == "=" else not value
        now = fields.Datetime.now()
        return [("harvest_allowed_from", ">" if blocked else "<=", now)]

    @api.depends("cuartel_id", "application_ref", "harvest_allowed_from")
    def _compute_display_name(self):
        for record in self:
            cuartel = record.cuartel_id.name or _("Sin cuartel")
            ref = record.application_ref or _("Aplicación %s") % record.application_id
            record.display_name = "%s · %s" % (cuartel, ref)

    # ------------------------------------------------------------------
    # Lectura defensiva del origen Studio
    # ------------------------------------------------------------------
    @api.model
    def _application_model(self):
        """Devuelve el modelo de aplicaciones, o ``None`` si Studio no está."""
        return self.env.get(APPLICATION_MODEL)

    @api.model
    def _discover_line_models(self):
        """Localiza las líneas de la aplicación por capacidad, no por nombre.

        Devuelve ``(modelo_de_productos, modelo_de_cuarteles)``; cualquiera de
        los dos puede ser ``None`` si Studio fue reconfigurado.
        """
        application = self._application_model()
        if application is None:
            return None, None
        product_model = cuartel_model = None
        for name, field in application._fields.items():
            if field.type != "one2many" or not name.startswith("x_"):
                continue
            comodel = self.env.get(field.comodel_name)
            if comodel is None:
                continue
            if product_model is None and "x_studio_producto" in comodel._fields:
                product_model = field.comodel_name
            if cuartel_model is None and "x_studio_cuartel" in comodel._fields:
                cuartel_model = field.comodel_name
        return product_model, cuartel_model

    @api.model
    def _carencia_for_product(self, product, criterion):
        """Días de carencia de un producto según el criterio de la empresa."""
        def read(field_name):
            if field_name not in product._fields:
                return 0
            return int(product[field_name] or 0)

        if criterion == "max":
            candidates = [read("dia_carencia"), read("x_studio_das_carencia_mayor")]
            candidates += [read(f) for f in CARENCIA_FIELD_BY_CRITERION.values()]
            return max(candidates or [0])
        value = read(CARENCIA_FIELD_BY_CRITERION.get(criterion, "dia_carencia"))
        # Un criterio de destino sin dato cargado no puede relajar el control:
        # se cae al valor de etiqueta, que es la exigencia legal mínima.
        return value or read("dia_carencia")

    @api.model
    def _collect_from_applications(self, applications):
        """Traduce aplicaciones Studio a valores de ``step.phyto.restriction``.

        No escribe nada; devuelve una lista de diccionarios.  Se usa tanto para
        materializar el tablero como para la verificación en vivo al aprobar
        una cosecha.
        """
        product_model, cuartel_model = self._discover_line_models()
        if not applications or not cuartel_model:
            return []

        criterion = self.env.company.step_phyto_criterion or "max"
        values = []
        for application in applications:
            header_date = application["x_studio_fecha"] if "x_studio_fecha" in application._fields else False
            company = (
                application["x_studio_empresa"]
                if "x_studio_empresa" in application._fields and application["x_studio_empresa"]
                else self.env.company
            )
            fundo = (
                application["x_studio_fundo"]
                if "x_studio_fundo" in application._fields
                else self.env["step.fundo"]
            )

            # --- productos aplicados y su restricción -------------------
            products = self.env["product.template"]
            if product_model:
                for line in self._application_lines(application, product_model):
                    product = line["x_studio_producto"]
                    if product:
                        products |= product
            carencia = max(
                [self._carencia_for_product(p, criterion) for p in products] or [0]
            )
            reingreso = max(
                [float(p.hrs_reingreso or 0.0) for p in products] or [0.0]
            )
            if not carencia and not reingreso:
                # Aplicación sin producto restringido (p. ej. solo riego).
                continue

            substances = ", ".join(
                sorted({
                    p["x_studio_sustancia_activa"].display_name
                    for p in products
                    if "x_studio_sustancia_activa" in p._fields and p["x_studio_sustancia_activa"]
                })
            )

            # --- cuarteles intervenidos --------------------------------
            for line in self._application_lines(application, cuartel_model):
                cuartel = line["x_studio_cuartel"]
                if not cuartel:
                    continue
                line_date = (
                    line["x_studio_fecha_hr_inicio"]
                    if "x_studio_fecha_hr_inicio" in line._fields
                    else False
                )
                date_application = line_date or self._as_datetime(header_date)
                if not date_application:
                    continue
                values.append({
                    "cuartel_id": cuartel.id,
                    "fundo_id": fundo.id if fundo else False,
                    "company_id": company.id,
                    "application_model": APPLICATION_MODEL,
                    "application_id": application.id,
                    "application_ref": application.display_name,
                    "date_application": date_application,
                    "product_ids": [(6, 0, products.ids)],
                    "substances": substances or False,
                    "carencia_days": carencia,
                    "carencia_criterion": criterion,
                    "reingreso_hours": reingreso,
                })
        return values

    @api.model
    def _line_inverse_field(self, line_model):
        """Nombre del many2one que apunta de la línea a la aplicación."""
        model = self.env.get(line_model)
        if model is None:
            return None
        if "x_aplicacion_foliar_id" in model._fields:
            return "x_aplicacion_foliar_id"
        return next(
            (
                name
                for name, field in model._fields.items()
                if field.type == "many2one" and field.comodel_name == APPLICATION_MODEL
            ),
            None,
        )

    @api.model
    def _application_lines(self, application, line_model):
        """Líneas de ``line_model`` que pertenecen a ``application``."""
        model = self.env.get(line_model)
        inverse = self._line_inverse_field(line_model)
        if model is None or not inverse:
            return []
        return model.sudo().search([(inverse, "=", application.id)])

    @api.model
    def _as_datetime(self, value):
        """Normaliza una fecha de cabecera a datetime (inicio del día)."""
        if not value:
            return False
        if isinstance(value, datetime):
            return value
        return datetime.combine(value, time.min)

    # ------------------------------------------------------------------
    # Materialización
    # ------------------------------------------------------------------
    @api.model
    def _store(self, values):
        """Inserta o actualiza restricciones de forma idempotente.

        La clave natural es (modelo, aplicación, cuartel), respaldada por un
        índice único, de modo que reejecutar el refresco nunca duplica.
        """
        stored = self.browse()
        for vals in values:
            existing = self.search([
                ("application_model", "=", vals["application_model"]),
                ("application_id", "=", vals["application_id"]),
                ("cuartel_id", "=", vals["cuartel_id"]),
            ], limit=1)
            if existing:
                existing.write(vals)
                stored |= existing
            else:
                stored |= self.create(vals)
        return stored

    @api.model
    def refresh(self, application_ids=None, cuartel_ids=None):
        """Recalcula restricciones desde las aplicaciones de BPA.

        Sin argumentos recorre todas las aplicaciones (uso del cron y del
        respaldo inicial).  Con ``cuartel_ids`` se limita a las aplicaciones que
        tocaron esos cuarteles, que es lo que necesita la aprobación de una
        cosecha.
        """
        application_model = self._application_model()
        if application_model is None:
            _logger.info("step_agro_traceability: %s no existe; nada que refrescar.", APPLICATION_MODEL)
            return self.browse()

        domain = []
        if application_ids:
            domain.append(("id", "in", list(application_ids)))
        applications = application_model.sudo().search(domain)

        if cuartel_ids and not application_ids:
            _product_model, cuartel_model = self._discover_line_models()
            if not cuartel_model:
                return self.browse()
            inverse = self._line_inverse_field(cuartel_model)
            if not inverse:
                return self.browse()
            lines = self.env[cuartel_model].sudo().search([
                ("x_studio_cuartel", "in", list(cuartel_ids)),
            ])
            wanted = {line[inverse].id for line in lines if line[inverse]}
            applications = applications.filtered(lambda a: a.id in wanted)

        values = self.sudo()._collect_from_applications(applications)
        if cuartel_ids:
            keep = set(cuartel_ids)
            values = [v for v in values if v["cuartel_id"] in keep]
        return self.sudo()._store(values)

    @api.model
    def cron_refresh(self):
        """Punto de entrada del cron diario."""
        restrictions = self.refresh()
        _logger.info("step_agro_traceability: %s restricciones al día.", len(restrictions))
        return True

    def action_refresh_all(self):
        """Botón «Recalcular» del tablero."""
        self.env["step.phyto.restriction"].refresh()
        return {
            "type": "ir.actions.client",
            "tag": "reload",
        }

    # ------------------------------------------------------------------
    # Consulta usada por cosecha
    # ------------------------------------------------------------------
    @api.model
    def evaluate_many(self, cuarteles, refresh=False):
        """Restricciones de varios cuarteles en una sola consulta.

        Evita el N+1 cuando la lista de cosechas pinta el estado fitosanitario
        de cientos de registros.
        """
        if not cuarteles:
            return {}
        if refresh:
            self.refresh(cuartel_ids=cuarteles.ids)
        restrictions = self.search([("cuartel_id", "in", cuarteles.ids)])
        grouped = {}
        for restriction in restrictions:
            grouped.setdefault(restriction.cuartel_id.id, self.browse())
            grouped[restriction.cuartel_id.id] |= restriction
        return grouped

    @api.model
    def evaluate_from_cache(self, cuartel, target_date, cache):
        """Evalúa contra un mapa ya cargado por :meth:`evaluate_many`."""
        empty = {
            "status": "unknown",
            "allowed_from": False,
            "restrictions": self.browse(),
            "reentry": self.browse(),
        }
        if not cuartel:
            return empty
        candidates = cache.get(cuartel.id, self.browse())
        target = self._as_datetime(target_date) or fields.Datetime.now()
        restrictions = candidates.filtered(
            lambda r: r.harvest_allowed_from and r.harvest_allowed_from > target
        )
        reentry = candidates.filtered(
            lambda r: r.reentry_allowed_from and r.reentry_allowed_from > target
        )
        return {
            "status": "carencia" if restrictions else "clear",
            "allowed_from": max(restrictions.mapped("harvest_allowed_from") or [False]),
            "restrictions": restrictions,
            "reentry": reentry,
        }

    @api.model
    def evaluate(self, cuartel, target_date, refresh=False):
        """Evalúa el estado fitosanitario de un cuartel a una fecha dada.

        Devuelve ``{'status', 'allowed_from', 'restrictions', 'reentry'}`` donde
        ``status`` es ``unknown`` (sin cuartel), ``clear`` o ``carencia``.
        """
        empty = {
            "status": "unknown",
            "allowed_from": False,
            "restrictions": self.browse(),
            "reentry": self.browse(),
        }
        if not cuartel:
            return empty
        if refresh:
            self.refresh(cuartel_ids=cuartel.ids)

        target = self._as_datetime(target_date) or fields.Datetime.now()
        restrictions = self.search([
            ("cuartel_id", "in", cuartel.ids),
            ("harvest_allowed_from", ">", target),
        ])
        reentry = self.search([
            ("cuartel_id", "in", cuartel.ids),
            ("reentry_allowed_from", ">", target),
        ])
        allowed_from = max(restrictions.mapped("harvest_allowed_from") or [False])
        return {
            "status": "carencia" if restrictions else "clear",
            "allowed_from": allowed_from,
            "restrictions": restrictions,
            "reentry": reentry,
        }
