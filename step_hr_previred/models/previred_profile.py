"""Perfil de formato Previred.

Un perfil declara **qué especificación** se está emitiendo: nombre, versión,
fuente, vigencia y motor de nómina que la produce. No mapea campos: los 105
campos los construye el generador del motor. El perfil existe para que un
archivo generado quede atado a una versión concreta del formato oficial, y
para que cuando Previred publique una versión nueva se pueda añadir sin
reescribir el histórico.

Editar perfiles es configuración técnica y exige su propio grupo: un
Administrador de Nómina puede generar el archivo, pero no redefinir contra qué
especificación se genera.
"""

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from ..tools import previred
from . import previred_adapter as adapters


class PreviredProfile(models.Model):
    _name = "step.previred.profile"
    _description = "Perfil de formato Previred"
    _order = "sequence, id"

    name = fields.Char(required=True, string="Nombre")
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    engine = fields.Selection(
        selection=lambda self: adapters.adapter_selection(),
        required=True, string="Motor de nómina",
        help="Generador vigente cuyas líneas reutiliza este perfil. El módulo "
             "no reimplementa los 105 campos.",
    )
    layout = fields.Selection(
        [("variable", "Largo variable, por separador"),
         ("fixed", "Largo fijo, por posición")],
        default="variable", required=True, string="Tipo de formato",
        help="Los dos motores instalados emiten largo variable. El largo fijo "
             "se declara para poder añadirlo sin cambiar el histórico.",
    )
    spec_version = fields.Char(
        required=True, default=previred.SPEC_VERSION, string="Versión",
    )
    spec_date = fields.Char(
        required=True, default=previred.SPEC_DATE,
        string="Fecha de la especificación",
    )
    effective_from = fields.Char(
        required=True, default=previred.SPEC_EFFECTIVE_FROM,
        string="Rige desde", help="Período de remuneración AAAA-MM desde el "
                                  "cual rige esta versión.",
    )
    effective_to = fields.Char(
        string="Rige hasta",
        help="Último período de remuneración AAAA-MM cubierto. Vacío = sin "
             "fecha de término.",
    )
    source_url = fields.Char(
        required=True, default=previred.SPEC_URL, string="Fuente",
        help="Documento oficial del que se tomó la especificación.",
    )
    field_count = fields.Integer(
        default=previred.FIELD_COUNT, readonly=True,
        string="Campos por registro",
    )
    separator = fields.Char(
        default=previred.SEPARATOR, readonly=True, string="Separador",
    )
    encoding = fields.Char(
        default=previred.ENCODING, readonly=True, string="Codificación",
    )
    line_ending = fields.Char(
        default="CRLF", readonly=True, string="Fin de línea",
    )
    eligible_states = fields.Char(
        required=True, default="done,paid", string="Estados exportables",
        help="Estados de la liquidación que ESTE motor considera validados, "
             "separados por coma. Nunca puede incluir «draft» ni «cancel».",
    )
    eligible_states_note = fields.Text(
        readonly=True, string="Justificación de los estados",
        help="Por qué el motor considera validados esos estados. Lo escribe "
             "el bridge del proveedor, no la configuración.",
    )
    supports_annexes = fields.Boolean(
        readonly=True, string="Emite líneas anexas",
        help="Si el motor tiene datos que justifiquen líneas 01/02/03. "
             "El módulo no inventa anexas que el motor no respalde.",
    )
    annexes_note = fields.Text(readonly=True, string="Nota sobre anexas")
    company_ids = fields.Many2many(
        "res.company", string="Compañías",
        help="Compañías que usan este perfil. Vacío = disponible para todas.",
    )
    note = fields.Text(string="Notas")
    matrix_html = fields.Html(
        compute="_compute_matrix_html", string="Matriz de campos",
        help="Los 105 campos oficiales y de qué dato del motor sale cada uno.",
    )

    @api.depends("engine")
    def _compute_matrix_html(self):
        """Matriz campo Previred → origen en el motor.

        Es la evidencia de que ninguna correspondencia se adivinó: cada fila
        apunta a la expresión concreta del generador vigente.
        """
        for profile in self:
            adapter = adapters.get_adapter(profile.engine)
            if adapter is None:
                profile.matrix_html = (
                    "<p class='text-muted'>%s</p>"
                    % _("El motor de este perfil no está registrado en esta "
                        "base; instale su módulo puente para ver la matriz."))
                continue
            rows = ["<table class='table table-sm table-striped'>",
                    "<thead><tr><th>#</th><th>Campo oficial</th>"
                    "<th>Origen</th><th>Dato del motor</th><th>Nota</th>"
                    "</tr></thead><tbody>"]
            for entry in adapter.field_matrix():
                position, name, kind, source, note = entry.as_row()
                rows.append(
                    "<tr><td>%s</td><td>%s</td><td><code>%s</code></td>"
                    "<td><code>%s</code></td><td>%s</td></tr>"
                    % (position, name, kind,
                       (source or "").replace("<", "&lt;"),
                       (note or "").replace("<", "&lt;")))
            rows.append("</tbody></table>")
            profile.matrix_html = "".join(rows)

    _sql_constraints = [
        ("unique_engine_version",
         "unique(engine, spec_version, layout)",
         "Ya existe un perfil para ese motor, versión y tipo de formato."),
    ]

    @api.constrains("engine")
    def _check_engine(self):
        for profile in self:
            if adapters.get_adapter(profile.engine) is None:
                raise ValidationError(_(
                    "El motor «%(engine)s» no está registrado. Motores "
                    "disponibles: %(available)s.",
                    engine=profile.engine or "-",
                    available=", ".join(sorted(adapters.ADAPTERS)) or "-"))

    @api.constrains("effective_from", "effective_to", "spec_date")
    def _check_periods(self):
        import re
        for profile in self:
            for value, label in ((profile.effective_from, _("Rige desde")),
                                 (profile.effective_to, _("Rige hasta")),
                                 (profile.spec_date,
                                  _("Fecha de la especificación"))):
                if value and not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", value):
                    raise ValidationError(_(
                        "«%(label)s» debe tener el formato AAAA-MM y vale "
                        "«%(value)s».", label=label, value=value))
            if (profile.effective_to and profile.effective_from
                    and profile.effective_to < profile.effective_from):
                raise ValidationError(_(
                    "«Rige hasta» no puede ser anterior a «Rige desde»."))

    @api.constrains("eligible_states")
    def _check_eligible_states(self):
        """Los estados prohibidos lo son para todos los motores."""
        from .previred_extractor import FORBIDDEN_STATES
        valid = dict(self.env["hr.payslip"]._fields["state"].selection or [])
        for profile in self:
            states = profile.state_list()
            if not states:
                raise ValidationError(_(
                    "El perfil «%s» debe declarar al menos un estado "
                    "exportable.", profile.name))
            forbidden = [s for s in states if s in FORBIDDEN_STATES]
            if forbidden:
                raise ValidationError(_(
                    "Un archivo Previred no puede incluir liquidaciones en "
                    "estado %(states)s: no están validadas.",
                    states=", ".join(forbidden)))
            unknown = [s for s in states if valid and s not in valid]
            if unknown:
                raise ValidationError(_(
                    "Estado desconocido en el perfil «%(profile)s»: "
                    "%(states)s. Estados válidos: %(valid)s.",
                    profile=profile.name, states=", ".join(unknown),
                    valid=", ".join(sorted(valid))))

    def state_list(self):
        """Los estados exportables como tupla limpia."""
        self.ensure_one()
        return tuple(
            part.strip() for part in (self.eligible_states or "").split(",")
            if part.strip())

    def sync_from_adapter(self):
        """Copia al perfil lo que el bridge declara sobre su motor.

        Es idempotente y sólo escribe los campos informativos: la lista de
        estados es configurable y no se pisa si ya fue ajustada.
        """
        for profile in self:
            adapter = adapters.get_adapter(profile.engine)
            if adapter is None:
                continue
            values = {
                "eligible_states_note": adapter.eligible_states_note,
                "supports_annexes": adapter.supports_annexes,
                "annexes_note": adapter.annexes_note,
            }
            if not profile.eligible_states:
                values["eligible_states"] = ",".join(adapter.eligible_states)
            profile.write(values)

    def adapter(self):
        """Adaptador del motor de este perfil."""
        self.ensure_one()
        adapter = adapters.get_adapter(self.engine)
        if adapter is None:
            raise ValidationError(_(
                "El perfil «%s» apunta a un motor que no está registrado.",
                self.name))
        return adapter

    def availability_error(self):
        """Mensaje si el perfil no puede usarse en ESTA base, o `None`."""
        self.ensure_one()
        adapter = adapters.get_adapter(self.engine)
        if adapter is None:
            return _("El motor «%s» no está registrado en el código.",
                     self.engine or "-")
        if not adapter.is_available(self.env):
            return _("El módulo «%(module)s» que implementa «%(label)s» no "
                     "está instalado en esta base.",
                     module=adapter.module, label=adapter.label)
        if self.layout != "variable":
            return _("Sólo está implementado el formato de largo variable por "
                     "separador; el perfil «%s» declara largo fijo.", self.name)
        return None

    @api.model
    def applies_to(self, period):
        self.ensure_one()
        value = period.strftime("%Y-%m") if hasattr(period, "strftime") \
            else str(period or "")[:7]
        return bool(value and self.effective_from <= value
                    and (not self.effective_to or value <= self.effective_to))

    @api.model
    def default_for(self, company, period=None, strict=True):
        """Perfil aplicable a `company` en esta base.

        Se prefiere un perfil asignado explícitamente a la compañía; si no hay,
        uno general cuyo motor esté instalado. Si el motor no puede deducirse
        sin ambigüedad, no se adivina.
        """
        period_value = period.strftime("%Y-%m") if hasattr(period, "strftime") \
            else str(period or "")[:7]
        domain = [
            "|", ("company_ids", "=", False), ("company_ids", "in", company.id),
        ]
        if period_value:
            domain += [
                ("effective_from", "<=", period_value),
                "|", ("effective_to", "=", False),
                ("effective_to", ">=", period_value),
            ]
        candidates = self.search(domain)
        assigned = candidates.filtered(lambda p: company in p.company_ids)
        for group in (assigned, candidates):
            usable = group.filtered(lambda p: not p.availability_error())
            if len(usable) == 1:
                return usable
            if len(usable) > 1:
                if strict:
                    raise UserError(_(
                        "Hay más de un perfil Previred aplicable a «%(company)s» "
                        "para %(period)s: %(profiles)s. Asigne uno de forma "
                        "exclusiva a la compañía o corrija sus vigencias.",
                        company=company.display_name,
                        period=period_value or _("el período solicitado"),
                        profiles=", ".join(usable.mapped("display_name"))))
                return self.browse()
        return self.browse()
