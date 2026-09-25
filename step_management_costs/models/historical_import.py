"""Corte V2 B — cargas históricas oficiales (presupuesto y real) con
plantilla versionada.

Decisión de arquitectura (antes de tocar `historical_cost.py`, ver
`ADR_001_ARQUITECTURA_Y_CONTABILIDAD.md` §D-L y `DECISION_LOG.md`): los dos
archivos oficiales (`Anexo 1.6.2.1` presupuesto, `Anexo 1.6.10.3` real) NO se
reconstruyen como `step.management.operational.budget` — eso exigiría
aprobar 16.000+ documentos artificiales (uno por temporada/centro) que nunca
pasaron por el flujo real de aprobación. Se cargan como **hechos históricos
normalizados**: una fila del archivo = una fila de
`step.management.historical.cost` con `dataset_kind = 'budget'` o `'actual'`
(D-L). La comparación es agregada por dimensiones (temporada, centro, grupo,
etc.), no por reconstrucción de documentos.

Presupuesto y real **no** se fuerzan a la misma fila física: cada archivo
tiene su propio lote (`step.management.historical.import.batch`,
`dataset_kind` distinto) aunque comparten exactamente el mismo patrón de
staging seguro que los demás importadores del addon.

El real histórico entra con procedencia `external`, estado inicial
`entered` (Ingresado); sólo el Aprobador/Control puede aprobarlo o
bloquearlo. Una vez aprobado, los hechos quedan `locked=True` (reutiliza el
bloqueo ya existente de `historical.cost`) y sólo se corrigen con una
reversa (nuevo lote que niega los montos) o un lote nuevo — nunca editando
filas aprobadas.
"""

import base64
import hashlib
import io
import re
import unicodedata

from psycopg2 import IntegrityError

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

try:
    import openpyxl
except ImportError:  # pragma: no cover - openpyxl es dependencia de Odoo
    openpyxl = None

APPROVER_GROUP = "step_management_costs.group_management_approver"
MANAGER_GROUP = "step_management_costs.group_management_manager"

MAX_DATA_ROWS = 20000
MAX_FILE_BYTES = 15 * 1024 * 1024
AMOUNT_TOLERANCE = 0.02

DATASET_KINDS = [("budget", "Presupuesto histórico"), ("actual", "Real histórico")]

# Cabecera esperada, normalizada. Sólo la primera columna difiere de
# significado entre presupuesto ("Versión Ppto") y real ("Tipo registro");
# el resto son las mismas 17 dimensiones/medidas (Anexo 1.6.2.1 / 1.6.10.3).
COMMON_HEADERS = {
    "temporada": "season_code", "ano": "year", "mes": "month",
    "fundo": "farm", "especie": "species", "variedad": "variety",
    "tipo ccosto": "cost_type", "centro de costos": "center",
    "origen": "origin", "grupo presupuesto": "group", "actividad": "activity",
    "producto-labor": "product", "producto labor": "product", "udm": "uom",
    "cantidad": "quantity",
}
HEADERS_BY_KIND = {
    "budget": dict(COMMON_HEADERS, **{
        "version ppto": "col1",
        "valor ppto$": "amount", "valor ppto $": "amount",
        "tc ppto": "rate",
        "valor ppto us$": "amount_usd", "valor ppto us $": "amount_usd",
    }),
    "actual": dict(COMMON_HEADERS, **{
        "tipo registro": "col1",
        "valor real $": "amount", "valor real$": "amount",
        "tc real": "rate",
        "valor real us$": "amount_usd", "valor real us $": "amount_usd",
    }),
}
REQUIRED_LOGICAL_COLS = {
    "season_code", "year", "month", "center", "quantity", "amount",
    "rate", "amount_usd",
}
CENTER_TYPE_REQUIRES_SPECIES = {"crop"}


def _norm(value):
    if value is None:
        return ""
    text = str(value).strip().lower()
    text = "".join(
        ch for ch in unicodedata.normalize("NFKD", text) if not unicodedata.combining(ch)
    )
    return re.sub(r"\s+", " ", text)


def _to_float(value):
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(" ", "")
    if "," in text and "." in text:
        text = text.replace(".", "").replace(",", ".")
    elif "," in text:
        text = text.replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return None


def _season_code_to_string(code):
    """«2425» → «2024/2025». Devuelve `None` si el código no es un par de
    años consecutivos de dos dígitos (mapeo determinista, auditable — no un
    maestro, D03/K1 siguen abiertas)."""
    text = str(code).strip()
    if not re.fullmatch(r"\d{4}", text):
        return None
    first, second = int(text[:2]), int(text[2:])
    if second != (first + 1) % 100:
        return None
    return "20%02d/20%02d" % (first, second)


class StepManagementHistoricalTemplateVersion(models.Model):
    _name = "step.management.historical.template.version"
    _description = "Versión de plantilla de carga histórica"
    _order = "kind, code"

    code = fields.Char(string="Código", required=True)
    kind = fields.Selection(DATASET_KINDS, string="Tipo", required=True)
    schema_version = fields.Char(string="Versión de esquema", required=True, default="1.0")
    header_signature = fields.Text(
        string="Firma de cabecera", required=True,
        help="Cabeceras normalizadas esperadas, una por línea, en orden.",
    )
    is_current = fields.Boolean(string="Vigente", default=True)
    template_file = fields.Binary(string="Plantilla descargable", attachment=True)
    template_filename = fields.Char(string="Nombre de la plantilla")
    active = fields.Boolean(default=True)
    notes = fields.Text(string="Notas de migración")

    _sql_constraints = [
        ("historical_template_version_code_unique", "unique(code)",
         "El código de la versión de plantilla debe ser único."),
    ]

    @api.constrains("kind", "is_current")
    def _check_single_current(self):
        for record in self:
            if not record.is_current:
                continue
            other = self.search([
                ("kind", "=", record.kind), ("is_current", "=", True),
                ("id", "!=", record.id), ("active", "=", True),
            ], limit=1)
            if other:
                raise ValidationError(_(
                    "Ya existe una versión vigente (%s) para «%s». Desmárquela "
                    "antes de marcar otra como vigente."
                ) % (other.code, dict(DATASET_KINDS)[record.kind]))

    def _signature_lines(self):
        self.ensure_one()
        return [line.strip() for line in (self.header_signature or "").splitlines() if line.strip()]

    @api.model
    def _find_by_headers(self, kind, normalized_headers):
        candidates = self.search([("kind", "=", kind), ("active", "=", True)])
        for candidate in candidates:
            if candidate._signature_lines() == list(normalized_headers):
                return candidate
        return self.browse()


class StepManagementHistoricalImportBatch(models.Model):
    _name = "step.management.historical.import.batch"
    _description = "Lote de carga histórica (presupuesto o real)"
    _inherit = ["mail.thread"]
    _order = "create_date desc, id desc"
    _check_company_auto = True

    name = fields.Char(
        string="Folio", required=True, readonly=True, copy=False,
        default=lambda s: _("Nuevo"),
    )
    company_id = fields.Many2one(
        "res.company", string="Empresa", required=True,
        default=lambda s: s.env.company, index=True,
    )
    dataset_kind = fields.Selection(
        DATASET_KINDS, string="Tipo de dato", required=True, default="actual",
    )
    template_version_id = fields.Many2one(
        "step.management.historical.template.version", string="Versión de plantilla",
        readonly=True, copy=False,
    )
    state = fields.Selection(
        [("draft", "Borrador"), ("validated", "Validado"),
         ("entered", "Ingresado"), ("approved", "Aprobado"),
         ("blocked", "Bloqueado"), ("cancelled", "Cancelado")],
        default="draft", required=True, tracking=True, index=True,
    )
    file = fields.Binary(string="Archivo Excel", required=True, attachment=True)
    filename = fields.Char(string="Nombre del archivo")
    file_hash = fields.Char(string="Hash del archivo", size=64, readonly=True, copy=False)
    batch_key_hash = fields.Char(
        string="Huella del lote", size=64, readonly=True, copy=False,
        help="Empresa + tipo + versión de plantilla + archivo — protegida "
             "por índice único parcial de Postgres (`init()`), no sólo por "
             "`search()`.",
    )
    user_id = fields.Many2one("res.users", string="Cargado por", default=lambda s: s.env.user, readonly=True)
    exclude_exact_duplicates = fields.Boolean(
        string="Excluir duplicados exactos del lote",
        help="Por omisión los duplicados exactos SE importan (reflejan el "
             "archivo tal cual); esta casilla los excluye de la importación "
             "sin borrarlos de la vista previa (auditoría).",
    )
    import_valid_only = fields.Boolean(string="Importar sólo filas válidas")
    reversal_of_id = fields.Many2one(
        "step.management.historical.import.batch", string="Reversa de",
        readonly=True, copy=False,
    )
    approved_by_id = fields.Many2one("res.users", string="Aprobado/bloqueado por", readonly=True, copy=False)
    approved_at = fields.Datetime(string="Fecha de aprobación/bloqueo", readonly=True, copy=False)
    line_ids = fields.One2many(
        "step.management.historical.import.line", "batch_id", string="Filas",
        copy=False,
    )
    cost_ids = fields.One2many(
        "step.management.historical.cost", "import_batch_id", string="Hechos creados",
        readonly=True, copy=False,
    )
    line_count = fields.Integer(compute="_compute_counts", store=True)
    error_count = fields.Integer(compute="_compute_counts", store=True)
    ok_count = fields.Integer(compute="_compute_counts", store=True)
    duplicate_count = fields.Integer(compute="_compute_counts", store=True)
    notes = fields.Text(string="Observaciones")

    @api.depends("line_ids.state", "line_ids.is_duplicate")
    def _compute_counts(self):
        for record in self:
            record.line_count = len(record.line_ids)
            record.error_count = len(record.line_ids.filtered(lambda l: l.state == "error"))
            record.ok_count = len(record.line_ids.filtered(lambda l: l.state == "ok"))
            record.duplicate_count = len(record.line_ids.filtered("is_duplicate"))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", _("Nuevo")) == _("Nuevo"):
                vals["name"] = self.env["ir.sequence"].next_by_code(
                    "step.management.historical.import.batch"
                ) or _("Nuevo")
        return super().create(vals_list)

    def init(self):
        # R5-style: índice único parcial — un lote "vigente" (no borrador,
        # no cancelado) por empresa+tipo+plantilla+archivo. Protege la
        # idempotencia frente a concurrencia, no sólo el `search()` previo.
        # Sólo estados "ya ingresados" — no 'validated': ese estado es un
        # ensayo/vista previa y calcular la huella ahí (para el `search()`
        # amistoso de `action_import`) no debe chocar todavía con el índice.
        self.env.cr.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS
                step_management_historical_import_batch_key_uniq
            ON step_management_historical_import_batch (company_id, batch_key_hash)
            WHERE state IN ('entered', 'approved', 'blocked') AND batch_key_hash IS NOT NULL
        """)

    def _ensure_approver(self):
        if not self.env.user.has_group(APPROVER_GROUP):
            raise UserError(_(
                "Necesita el perfil «Aprobador / Control» de Gestión y "
                "Costos para esta acción."
            ))

    def action_reset(self):
        for record in self:
            if record.state in ("approved", "blocked"):
                raise UserError(_("No se puede restablecer un lote aprobado o bloqueado."))
            record.cost_ids.sudo().unlink()
            record.line_ids.sudo().unlink()
            record.write({"state": "draft", "file_hash": False, "batch_key_hash": False,
                           "template_version_id": False})

    def action_cancel(self):
        self.filtered(lambda r: r.state in ("draft", "validated")).write({"state": "cancelled"})

    # ------------------------------------------------------------------
    # Validación / parsing (patrón de staging seguro ya establecido)
    # ------------------------------------------------------------------
    def _open_workbook(self):
        self.ensure_one()
        if openpyxl is None:
            raise UserError(_("La librería openpyxl no está disponible en el servidor."))
        if not self.file:
            raise UserError(_("Adjunte un archivo Excel."))
        if self.filename and not self.filename.lower().endswith(".xlsx"):
            raise UserError(_("El archivo debe ser .xlsx."))
        try:
            raw = base64.b64decode(self.file, validate=True)
        except (ValueError, TypeError) as exc:
            raise UserError(_("El archivo adjunto no contiene datos Base64 válidos.")) from exc
        if len(raw) > MAX_FILE_BYTES:
            raise UserError(_(
                "El archivo supera el máximo permitido de %(size)s MB."
            ) % {"size": MAX_FILE_BYTES // (1024 * 1024)})
        self.file_hash = hashlib.sha256(raw).hexdigest()
        try:
            values_wb = openpyxl.load_workbook(io.BytesIO(raw), data_only=True, read_only=True)
            formula_wb = openpyxl.load_workbook(io.BytesIO(raw), data_only=False, read_only=True)
        except Exception as exc:  # noqa: BLE001
            raise UserError(_("No se pudo abrir el Excel: %s") % exc)
        return values_wb, formula_wb

    def _locate_header(self, ws_values):
        headers = HEADERS_BY_KIND[self.dataset_kind]
        for r_idx, row in enumerate(ws_values.iter_rows(min_row=1, max_row=15, values_only=True), start=1):
            mapping = {}
            for c_idx, value in enumerate(row):
                logical = headers.get(_norm(value))
                if logical and logical not in mapping:
                    mapping[logical] = c_idx
            if REQUIRED_LOGICAL_COLS.issubset(set(mapping)):
                header_cells = [_norm(v) for v in row if _norm(v)]
                return r_idx + 1, mapping, header_cells
        raise UserError(_(
            "No se encontró la fila de cabecera esperada para «%s». Revise "
            "que el archivo use la plantilla oficial."
        ) % dict(DATASET_KINDS)[self.dataset_kind])

    def action_validate(self):
        self.ensure_one()
        if self.state == "approved":
            raise UserError(_("Este lote ya fue aprobado."))
        self.line_ids.sudo().unlink()
        values_wb, formula_wb = self._open_workbook()
        ws_values = values_wb.worksheets[0]
        ws_formulas = formula_wb.worksheets[0]
        start_row, cols, header_cells = self._locate_header(ws_values)

        template = self.env["step.management.historical.template.version"]._find_by_headers(
            self.dataset_kind, header_cells,
        )
        if not template:
            current = self.env["step.management.historical.template.version"].search([
                ("kind", "=", self.dataset_kind), ("is_current", "=", True), ("active", "=", True),
            ], limit=1)
            raise UserError(_(
                "La cabecera del archivo no coincide con ninguna versión de "
                "plantilla registrada. %(hint)s"
            ) % {
                "hint": (
                    _("Descargue la plantilla vigente (%s) y vuelva a exportar.") % current.code
                    if current else _("No hay una plantilla vigente registrada; contacte al administrador.")
                ),
            })
        self.template_version_id = template.id

        def cell(row, key):
            idx = cols.get(key)
            if idx is None or idx >= len(row):
                return None
            return row[idx]

        line_vals = []
        seen_hashes = {}
        empty_streak = 0
        for offset, (row_v, row_f) in enumerate(zip(
            ws_values.iter_rows(min_row=start_row, max_row=start_row + MAX_DATA_ROWS - 1, values_only=True),
            ws_formulas.iter_rows(min_row=start_row, max_row=start_row + MAX_DATA_ROWS - 1, values_only=True),
        )):
            row_number = start_row + offset
            mapped = {key: cell(row_v, key) for key in cols}
            mapped_formula = {key: cell(row_f, key) for key in cols}
            if all((v is None or str(v).strip() == "") for v in mapped.values()):
                empty_streak += 1
                if empty_streak >= 2:
                    break
                continue
            empty_streak = 0
            vals = self._parse_row(row_number, mapped, mapped_formula)
            dup_key = vals["dup_hash"]
            if dup_key in seen_hashes:
                vals["is_duplicate"] = True
                vals["duplicate_of_row"] = seen_hashes[dup_key]
            else:
                seen_hashes[dup_key] = row_number
            line_vals.append(vals)
        values_wb.close()
        formula_wb.close()

        if not line_vals:
            raise UserError(_("El archivo no contiene filas de datos."))
        self.write({"state": "validated"})
        self.env["step.management.historical.import.line"].sudo().create([
            dict(vals, batch_id=self.id) for vals in line_vals
        ])
        self.invalidate_recordset(["line_ids", "line_count", "error_count", "ok_count", "duplicate_count"])
        self.message_post(body=_(
            "Validación: %(total)s fila(s), %(err)s con error, %(dup)s "
            "duplicada(s) exacta(s)."
        ) % {"total": self.line_count, "err": self.error_count, "dup": self.duplicate_count})

    def _parse_row(self, row_number, mapped, mapped_formula):
        Center = self.env["step.management.cost.center"]
        Group = self.env["step.management.budget.group"]
        company = self.company_id
        kind = self.dataset_kind

        vals = {"row_number": row_number}
        errors = []

        # Fórmulas: sólo se permite EXACTAMENTE `= <amount>/<amount_usd>` en
        # la columna "rate" del real histórico (misma fila); todo lo demás
        # que sea fórmula se rechaza. Nunca se ejecuta una fórmula arbitraria.
        for key, formula_value in mapped_formula.items():
            if not (isinstance(formula_value, str) and formula_value.strip().startswith("=")):
                continue
            if key == "rate":
                continue  # se valida abajo con la regla exacta
            errors.append(_("La celda «%s» contiene una fórmula no permitida.") % key)

        col1 = (str(mapped.get("col1")).strip() if mapped.get("col1") else "")
        vals["raw_col1"] = col1
        if kind == "budget":
            vals["budget_version"] = col1
        else:
            vals["record_type_label"] = col1 or "Externo"

        season_code = (str(mapped.get("season_code")).strip() if mapped.get("season_code") else "")
        season_str = _season_code_to_string(season_code) if season_code else None
        if not season_code:
            errors.append(_("Falta la temporada."))
        elif not season_str:
            errors.append(_(
                "Temporada «%s» inconsistente (se espera un par de años "
                "consecutivos, p. ej. 2425)."
            ) % season_code)
        else:
            vals["season_code"] = season_code
            vals["season"] = season_str

        year = _to_float(mapped.get("year"))
        if not year or not (1900 <= int(year) <= 2100):
            errors.append(_("Año inválido."))
        else:
            vals["year"] = int(year)

        month = _to_float(mapped.get("month"))
        if not month or not 1 <= int(month) <= 12:
            errors.append(_("Mes inválido (se espera 1-12)."))
        else:
            vals["month"] = int(month)

        if vals.get("year") and vals.get("month"):
            vals["fact_date"] = "%04d-%02d-01" % (vals["year"], vals["month"])

        vals["farm"] = (str(mapped.get("farm")).strip() if mapped.get("farm") else "")
        vals["species"] = (str(mapped.get("species")).strip() if mapped.get("species") else "")
        vals["variety"] = (str(mapped.get("variety")).strip() if mapped.get("variety") else "")
        vals["cost_center_type_label"] = (
            str(mapped.get("cost_type")).strip() if mapped.get("cost_type") else ""
        )

        raw_center = (str(mapped.get("center")).strip() if mapped.get("center") else "")
        vals["center_label"] = raw_center
        if not raw_center:
            errors.append(_("Falta el centro de costos."))
        else:
            centers = Center.search([
                ("company_id", "=", company.id),
                "|", ("code", "=", raw_center), ("name", "=", raw_center),
            ], limit=2)
            if not centers:
                norm_target = _norm(raw_center)
                all_centers = Center.search([("company_id", "=", company.id)])
                centers = all_centers.filtered(
                    lambda c: _norm(c.name) == norm_target or _norm(c.code) == norm_target
                )
            if not centers:
                errors.append(_("Centro de costos «%s» no encontrado en la empresa.") % raw_center)
            elif len(centers) > 1:
                errors.append(_("Centro de costos «%s» ambiguo.") % raw_center)
            else:
                vals["center_id"] = centers.id
                if centers.cost_type in CENTER_TYPE_REQUIRES_SPECIES and not vals["species"]:
                    errors.append(_(
                        "El centro «%s» es productivo (tipo «%s») y requiere "
                        "especie informada."
                    ) % (raw_center, centers.cost_type))

        vals["origin_label"] = (str(mapped.get("origin")).strip() if mapped.get("origin") else "")

        raw_group = (str(mapped.get("group")).strip() if mapped.get("group") else "")
        vals["budget_group_label"] = raw_group
        if raw_group:
            groups = Group.search([
                ("company_id", "=", company.id),
                "|", ("code", "=", raw_group), ("name", "=", raw_group),
            ], limit=2)
            if not groups:
                norm_target = _norm(raw_group)
                all_groups = Group.search([("company_id", "=", company.id)])
                groups = all_groups.filtered(
                    lambda g: _norm(g.name) == norm_target or _norm(g.code) == norm_target
                )
            if not groups:
                errors.append(_("Grupo presupuesto «%s» no encontrado.") % raw_group)
            elif len(groups) > 1:
                errors.append(_("Grupo presupuesto «%s» ambiguo.") % raw_group)
            else:
                vals["group_id"] = groups.id

        vals["activity_label"] = (str(mapped.get("activity")).strip() if mapped.get("activity") else "")
        vals["product_label"] = (str(mapped.get("product")).strip() if mapped.get("product") else "")
        vals["uom_label"] = (str(mapped.get("uom")).strip() if mapped.get("uom") else "")

        quantity = _to_float(mapped.get("quantity"))
        if quantity is None:
            errors.append(_("Cantidad inválida."))
        else:
            vals["quantity"] = quantity

        amount = _to_float(mapped.get("amount"))
        if amount is None:
            errors.append(_("Monto inválido."))
        else:
            vals["source_amount"] = amount

        amount_usd = _to_float(mapped.get("amount_usd"))
        if amount_usd is None:
            errors.append(_("Monto US$ inválido."))
        else:
            vals["source_amount_usd"] = amount_usd

        rate_formula = mapped_formula.get("rate")
        rate = None
        if isinstance(rate_formula, str) and rate_formula.strip().startswith("="):
            if amount is not None and amount_usd:
                if self._is_safe_rate_formula(rate_formula, mapped_formula):
                    rate = amount / amount_usd
                else:
                    errors.append(_(
                        "La fórmula de TC «%s» no coincide con «Monto / "
                        "Monto US$» de la misma fila; no se ejecuta."
                    ) % rate_formula)
            else:
                errors.append(_(
                    "No se puede validar la fórmula de TC sin monto y monto US$."
                ))
        else:
            rate = _to_float(mapped.get("rate"))
        if rate is None:
            errors.append(_("TC inválido."))
        else:
            vals["source_exchange_rate"] = rate

        if amount is not None and amount_usd is not None and rate:
            expected_usd = amount / rate
            if abs(expected_usd - amount_usd) > AMOUNT_TOLERANCE:
                errors.append(_(
                    "No concilia: monto/TC = %(calc).4f vs. monto US$ = "
                    "%(usd).4f (diferencia %(diff).4f)."
                ) % {
                    "calc": expected_usd, "usd": amount_usd,
                    "diff": abs(expected_usd - amount_usd),
                })

        content = "|".join(_norm(mapped.get(k)) for k in sorted(mapped))
        vals["line_hash"] = hashlib.sha256(
            ("%s|%s|%s" % (self.file_hash or "", row_number, content)).encode("utf-8")
        ).hexdigest()
        vals["dup_hash"] = hashlib.sha256(content.encode("utf-8")).hexdigest()
        vals["is_duplicate"] = False

        vals["state"] = "error" if errors else "ok"
        vals["error"] = "\n".join(errors)
        return vals

    @staticmethod
    def _is_safe_rate_formula(formula, mapped_formula):
        """Sólo acepta `=<celda amount>/<celda amount_usd>` (con o sin `+`
        inicial), nunca otra referencia u operación."""
        text = formula.strip().lstrip("+").lstrip("=").replace(" ", "")
        return bool(re.fullmatch(r"[A-Za-z]+\d+/[A-Za-z]+\d+", text))

    # ------------------------------------------------------------------
    # Importación (todo o nada salvo "sólo válidas") — hechos normalizados
    # ------------------------------------------------------------------
    def action_import(self):
        self.ensure_one()
        if self.state != "validated":
            raise UserError(_("Primero valide el archivo."))
        if self.error_count and not self.import_valid_only:
            raise UserError(_(
                "Hay %s fila(s) con error. Corríjalas y vuelva a validar, o "
                "marque «Importar sólo filas válidas»."
            ) % self.error_count)

        # No se asigna a `self` todavía: el índice único parcial sólo cubre
        # `state in (entered, approved, blocked)`, pero escribir el campo
        # aquí forzaría un flush inmediato con el registro aún en
        # `validated` — más abajo, dentro del `savepoint()`, se asigna junto
        # con el cambio de estado real.
        key_hash = hashlib.sha256("|".join([
            str(self.company_id.id), self.dataset_kind,
            str(self.template_version_id.id), self.file_hash or "",
        ]).encode("utf-8")).hexdigest()

        duplicate = self.search([
            ("id", "!=", self.id), ("company_id", "=", self.company_id.id),
            ("batch_key_hash", "=", key_hash),
            ("state", "in", ("entered", "approved", "blocked")),
        ], limit=1)
        if duplicate:
            raise UserError(_(
                "Ya existe un lote con la misma empresa, tipo, plantilla y "
                "archivo: %s. No se vuelve a cargar."
            ) % duplicate.name)

        rows = self.line_ids.filtered(lambda l: l.state == "ok")
        if self.exclude_exact_duplicates:
            rows = rows.filtered(lambda l: not l.is_duplicate)
        if not rows:
            raise UserError(_("No hay filas válidas para importar."))

        cost_vals = []
        for row in rows:
            vals = {
                "company_id": self.company_id.id,
                "currency_id": self.company_id.currency_id.id,
                "import_batch_id": self.id,
                "dataset_kind": self.dataset_kind,
                "origin": "external",
                "name": _("%(kind)s %(season)s %(center)s") % {
                    "kind": dict(DATASET_KINDS)[self.dataset_kind],
                    "season": row.season, "center": row.center_label,
                },
                "date": row.fact_date,
                "center_id": row.center_id.id,
                "group_id": row.group_id.id if row.group_id else False,
                "indicator": row.activity_label or row.product_label,
                "quantity": row.quantity,
                "budget_version": row.budget_version,
                "record_type_label": row.record_type_label,
                "season_code": row.season_code,
                "season": row.season,
                "year": row.year,
                "month": row.month,
                "farm": row.farm,
                "species": row.species,
                "variety": row.variety,
                "cost_center_type_label": row.cost_center_type_label,
                "center_label": row.center_label,
                "origin_label": row.origin_label,
                "budget_group_label": row.budget_group_label,
                "activity_label": row.activity_label,
                "product_label": row.product_label,
                "uom_label": row.uom_label,
                "source_amount": row.source_amount,
                "source_exchange_rate": row.source_exchange_rate,
                "source_amount_usd": row.source_amount_usd,
            }
            if self.dataset_kind == "budget":
                vals["budget_amount"] = row.source_amount
            else:
                vals["actual_amount"] = row.source_amount
            cost_vals.append(vals)

        try:
            with self.env.cr.savepoint():
                created = self.env["step.management.historical.cost"].create(cost_vals)
                self.write({"state": "entered", "batch_key_hash": key_hash})
        except IntegrityError as exc:
            raise UserError(_(
                "Ya existe un lote con la misma empresa, tipo, plantilla y "
                "archivo (conflicto de concurrencia). No se vuelve a cargar."
            )) from exc

        rows.sudo().write({"imported": True})
        self.message_post(body=_(
            "Ingresados %(count)s hecho(s) histórico(s) («%(kind)s»)."
        ) % {"count": len(created), "kind": dict(DATASET_KINDS)[self.dataset_kind]})
        return {
            "type": "ir.actions.act_window",
            "res_model": "step.management.historical.import.batch",
            "res_id": self.id, "view_mode": "form", "target": "current",
        }

    def action_approve(self):
        self._ensure_approver()
        for record in self:
            if record.state != "entered":
                raise UserError(_(
                    "Sólo se puede aprobar un lote «Ingresado»."
                ))
            record.cost_ids.write({"locked": True})
            record.write({
                "state": "approved", "approved_by_id": self.env.user.id,
                "approved_at": fields.Datetime.now(),
            })
            record.message_post(body=_(
                "Lote aprobado por %s; los hechos quedan inmutables."
            ) % self.env.user.display_name)

    def action_block(self):
        self._ensure_approver()
        for record in self:
            if record.state not in ("entered", "approved"):
                raise UserError(_(
                    "Sólo se puede bloquear un lote ingresado o aprobado."
                ))
            # Reutiliza la exclusión ya existente de comparativos (ADR D-C).
            record.cost_ids.write({"origin": "unreviewed", "locked": True})
            record.write({
                "state": "blocked", "approved_by_id": self.env.user.id,
                "approved_at": fields.Datetime.now(),
            })
            record.message_post(body=_(
                "Lote bloqueado por %s; los hechos quedan excluidos de "
                "comparativos y son inmutables."
            ) % self.env.user.display_name)

    def action_create_reversal(self):
        """Corrección de un lote aprobado sin editar filas aprobadas: crea un
        nuevo lote «Ingresado» con los mismos hechos en signo contrario."""
        self.ensure_one()
        self._ensure_approver()
        if self.state != "approved":
            raise UserError(_("Sólo se puede reversar un lote aprobado."))
        reversal = self.copy({
            "name": _("Nuevo"), "state": "draft", "reversal_of_id": self.id,
            "file_hash": False, "batch_key_hash": False,
            "approved_by_id": False, "approved_at": False,
        })
        cost_vals = []
        for cost in self.cost_ids:
            vals = cost.copy_data()[0]
            vals.update({
                "import_batch_id": reversal.id,
                "locked": False,
                "quantity": -cost.quantity,
                "actual_amount": -cost.actual_amount,
                "budget_amount": -cost.budget_amount,
                "source_amount": -cost.source_amount,
                "source_amount_usd": -cost.source_amount_usd,
                "name": _("Reversa: %s") % cost.name,
            })
            cost_vals.append(vals)
        self.env["step.management.historical.cost"].create(cost_vals)
        reversal.write({"state": "entered"})
        self.message_post(body=_("Reversado por el lote %s.") % reversal.name)
        return {
            "type": "ir.actions.act_window",
            "res_model": "step.management.historical.import.batch",
            "res_id": reversal.id, "view_mode": "form", "target": "current",
        }


class StepManagementHistoricalImportLine(models.Model):
    _name = "step.management.historical.import.line"
    _description = "Fila de carga histórica"
    _order = "row_number, id"
    _check_company_auto = True

    batch_id = fields.Many2one(
        "step.management.historical.import.batch", required=True,
        ondelete="cascade", index=True,
    )
    company_id = fields.Many2one(related="batch_id.company_id", store=True, index=True)
    row_number = fields.Integer(string="Fila")
    state = fields.Selection([("ok", "OK"), ("error", "Error")], default="ok", index=True)
    error = fields.Text(string="Detalle del error")
    imported = fields.Boolean(string="Importada", default=False)
    is_duplicate = fields.Boolean(string="Duplicado exacto", default=False, index=True)
    duplicate_of_row = fields.Integer(string="Duplicado de la fila")
    line_hash = fields.Char(size=64, index=True)
    dup_hash = fields.Char(size=64, index=True)

    raw_col1 = fields.Char(string="Col. 1 (texto)")
    fact_date = fields.Date(string="Fecha")
    budget_version = fields.Char()
    record_type_label = fields.Char()
    season_code = fields.Char()
    season = fields.Char()
    year = fields.Integer()
    month = fields.Integer()
    farm = fields.Char()
    species = fields.Char()
    variety = fields.Char()
    cost_center_type_label = fields.Char()
    center_label = fields.Char()
    center_id = fields.Many2one("step.management.cost.center", check_company=True)
    origin_label = fields.Char()
    budget_group_label = fields.Char()
    group_id = fields.Many2one("step.management.budget.group", check_company=True)
    activity_label = fields.Char()
    product_label = fields.Char()
    uom_label = fields.Char()
    quantity = fields.Float(digits=(16, 4))
    source_amount = fields.Float(digits=(16, 2))
    source_exchange_rate = fields.Float(digits=(16, 6))
    source_amount_usd = fields.Float(digits=(16, 2))
