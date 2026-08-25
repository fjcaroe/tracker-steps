import logging

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from ..tools import dt_book
from . import remuneration_book_adapter as adapters

_logger = logging.getLogger(__name__)

SOURCE_TYPES = [
    ("rule", "Suma de líneas de liquidación"),
    ("worked_days", "Suma de días trabajados"),
    ("adapter", "Adaptador registrado"),
    ("employee_rut", "RUT del trabajador"),
    ("aggregate", "Suma de otros códigos DT"),
    ("difference", "Resta de otros códigos DT"),
    ("zero", "Sin origen (queda en cero)"),
]

SIGNS = [
    ("as_is", "Tal cual"),
    ("abs", "Valor absoluto"),
    ("invert", "Invertir signo"),
]

#: Orígenes que producen un valor por sí mismos, sin depender de otros códigos.
DIRECT_SOURCE_TYPES = ("rule", "worked_days", "adapter", "employee_rut", "zero")

#: Orígenes que se calculan a partir de otros códigos DT del mismo perfil.
DERIVED_SOURCE_TYPES = ("aggregate", "difference")


class RemunerationBookProfile(models.Model):
    """Perfil de mapeo entre códigos DT y las reglas del motor de nómina.

    Steps no reimplementa el cálculo previsional: sólo declara de qué línea ya
    calculada sale cada código DT. Cada motor de nómina (SimpleDigital, el
    localizado chileno extendido, u otro) trae su propio perfil.

    El perfil es **configuración técnica**: sólo un grupo técnico puede
    editarlo. Un Administrador de Nómina puede asignar a su empresa un perfil
    ya validado, pero no puede programar de dónde sale un importe.
    """

    _name = "step.remuneration.book.profile"
    _description = "Perfil de mapeo DT del Libro de Remuneraciones"
    _order = "sequence, name"

    name = fields.Char(required=True, string="Nombre")
    code = fields.Char(required=True, string="Código técnico")
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    state = fields.Selection(
        [
            ("draft", "Borrador"),
            ("validated", "Validado"),
            ("active", "Activo"),
        ],
        default="draft", required=True, readonly=True, copy=False,
        string="Estado",
        help="Sólo un perfil Activo puede usarse para generar el libro. Pasar "
             "a Validado exige superar la validación semántica completa.",
    )
    company_id = fields.Many2one(
        "res.company",
        string="Empresa",
        help="Vacío significa que el perfil es una plantilla global aprobada, "
             "disponible para cualquier empresa.",
    )
    note = fields.Text(string="Notas")
    detector_rule_codes = fields.Char(
        string="Reglas que lo identifican",
        help="Códigos de regla salarial separados por coma. El perfil se "
             "considera aplicable cuando TODOS esos códigos aparecen en las "
             "liquidaciones seleccionadas de esa empresa y período.",
    )
    line_ids = fields.One2many(
        "step.remuneration.book.profile.line", "profile_id", string="Mapeo",
        # Un perfil sin su mapeo no es un perfil: duplicar debe traer las
        # líneas, que es como se parte de un motor conocido para adaptarlo.
        copy=True,
    )
    validation_message = fields.Text(
        string="Resultado de la validación", readonly=True, copy=False,
    )

    _sql_constraints = [
        ("code_uniq", "unique(code)", "Ya existe un perfil con ese código técnico."),
    ]

    # -- utilidades ---------------------------------------------------------

    def detector_codes(self):
        self.ensure_one()
        return [
            code.strip()
            for code in (self.detector_rule_codes or "").split(",")
            if code.strip()
        ]

    def missing_dt_codes(self):
        """Códigos DT requeridos por el libro que el perfil no cubre."""
        self.ensure_one()
        mapped = set(self.line_ids.mapped("dt_code"))
        return [code for code in dt_book.REQUIRED_DT_CODES if code not in mapped]

    # -- validación semántica ----------------------------------------------

    def validation_errors(self):
        """Todo lo que impide usar el perfil, como lista de mensajes.

        Se comprueba antes de activar y otra vez antes de generar el libro: un
        perfil válido ayer puede dejar de serlo si se desinstala el módulo que
        aportaba un adaptador.
        """
        self.ensure_one()
        errors = []

        missing = self.missing_dt_codes()
        if missing:
            errors.append(_(
                "Faltan los códigos DT obligatorios: %s.", ", ".join(missing)))

        seen = {}
        for line in self.line_ids:
            code = (line.dt_code or "").strip()
            seen[code] = seen.get(code, 0) + 1
        duplicated = sorted(code for code, count in seen.items() if count > 1)
        if duplicated:
            errors.append(_(
                "Códigos DT definidos más de una vez: %s.",
                ", ".join(duplicated)))

        errors.extend(self._dependency_errors())
        errors.extend(self._source_errors())
        errors.extend(self._official_total_errors())
        return errors

    def _dependency_errors(self):
        """Recorre el grafo de dependencias entre códigos derivados.

        Se usa un orden topológico real y no un número fijo de pasadas: un
        perfil con una cadena larga de agregados debe resolverse igual, y un
        ciclo debe detectarse siempre, no quedarse silenciosamente en cero.
        """
        self.ensure_one()
        errors = []
        defined = {}
        for line in self.line_ids:
            defined[(line.dt_code or "").strip()] = line

        dependencies = {}
        for code, line in defined.items():
            if line.source_type not in DERIVED_SOURCE_TYPES:
                dependencies[code] = []
                continue
            operands = line.codes_list("operand_codes")
            if not operands:
                errors.append(_(
                    "El código DT %s se declara derivado pero no indica "
                    "operandos.", code))
            if code in operands:
                errors.append(_(
                    "El código DT %s se referencia a sí mismo.", code))
            unknown = [operand for operand in operands if operand not in defined]
            if unknown:
                errors.append(_(
                    "El código DT %(code)s depende de códigos que el perfil no "
                    "define: %(unknown)s.",
                    code=code, unknown=", ".join(sorted(set(unknown)))))
            dependencies[code] = [
                operand for operand in operands
                if operand in defined and operand != code
            ]

        resolved = set()
        pending = set(dependencies)
        progressed = True
        while pending and progressed:
            progressed = False
            for code in sorted(pending):
                if all(operand in resolved for operand in dependencies[code]):
                    resolved.add(code)
                    pending.discard(code)
                    progressed = True
        if pending:
            errors.append(_(
                "Hay un ciclo o una dependencia irresoluble entre los códigos "
                "DT %s. El libro no puede resolverlos y no se convertirán "
                "silenciosamente en cero.", ", ".join(sorted(pending))))
        return errors

    def _source_errors(self):
        self.ensure_one()
        errors = []
        for line in self.line_ids:
            code = (line.dt_code or "").strip()
            if line.source_type in ("rule", "worked_days"):
                if not line.codes_list("rule_codes"):
                    errors.append(_(
                        "El código DT %s no indica ningún código de regla.",
                        code))
            elif line.source_type == "adapter":
                adapter = adapters.get_adapter(line.adapter_key)
                if adapter is None:
                    errors.append(_(
                        "El código DT %(code)s usa el adaptador «%(key)s», que "
                        "no está registrado.",
                        code=code, key=line.adapter_key or "-"))
                    continue
                message = adapter.check_param(line.adapter_param)
                if message:
                    errors.append("%s (%s)" % (message, code))
                elif not adapter.is_installed(self.env):
                    errors.append(_(
                        "El código DT %(code)s necesita el modelo %(model)s, "
                        "que no está instalado en esta base.",
                        code=code, model=adapter.model))
        return errors

    def _official_total_errors(self):
        """Los cuatro totales del libro no pueden fabricarse.

        `5210`, `5201`, `5301` y `5501` tienen que salir de una fuente
        verificable —una regla del motor de nómina o la combinación de otros
        códigos que sí la tienen—, nunca de `zero` para que el perfil parezca
        completo.
        """
        self.ensure_one()
        errors = []
        by_code = {(line.dt_code or "").strip(): line for line in self.line_ids}
        for code in dt_book.OFFICIAL_TOTAL_CODES:
            line = by_code.get(code)
            if line is None:
                continue  # ya lo informa missing_dt_codes()
            if line.source_type == "zero":
                errors.append(_(
                    "El total oficial %s no puede configurarse como «Sin "
                    "origen»: debe provenir del motor de nómina.", code))
        return errors

    # -- estados ------------------------------------------------------------

    def action_validate(self):
        for profile in self:
            errors = profile.validation_errors()
            if errors:
                profile.validation_message = "\n".join(
                    "• %s" % error for error in errors)
                raise ValidationError(_(
                    "El perfil «%(name)s» no puede validarse:\n\n%(errors)s",
                    name=profile.name,
                    errors="\n".join("• %s" % error for error in errors),
                ))
            profile.validation_message = _("Validación superada.")
            profile.state = "validated"
        return True

    def action_activate(self):
        for profile in self:
            if profile.state == "draft":
                profile.action_validate()
            errors = profile.validation_errors()
            if errors:
                raise ValidationError(_(
                    "El perfil «%(name)s» dejó de ser válido:\n\n%(errors)s",
                    name=profile.name,
                    errors="\n".join("• %s" % error for error in errors),
                ))
            profile.state = "active"
        return True

    def action_back_to_draft(self):
        self.write({"state": "draft", "validation_message": False})
        return True

    def write(self, values):
        """Cualquier cambio en el mapeo devuelve el perfil a Borrador."""
        tracked = {
            "line_ids", "detector_rule_codes", "company_id", "code", "active",
        }
        result = super().write(values)
        if tracked & set(values) and "state" not in values:
            super(RemunerationBookProfile, self.filtered(
                lambda profile: profile.state != "draft"
            )).write({"state": "draft", "validation_message": False})
        return result

    # -- revalidación al terminar de cargar el registro ---------------------

    def _register_hook(self):
        """Revalida los perfiles semilla con TODO el registro ya cargado.

        No basta con hacerlo en el `post_init_hook` ni en una migración: esos
        puntos corren mientras se carga este módulo, y un adaptador puede
        depender de un modelo cuyo addon todavía no se ha cargado. El resultado
        sería un perfil marcado como borrador -y por tanto inutilizable- por un
        simple orden de carga.

        `_register_hook` se ejecuta una vez por arranque del registro, cuando
        todos los modelos existen, así que aquí la respuesta es la verdadera.
        Sólo escribe cuando el estado cambia.
        """
        result = super()._register_hook()
        try:
            from ..hooks import activate_seed_profiles
            activate_seed_profiles(self.env)
        except Exception:  # noqa: BLE001 - nunca romper el arranque por esto
            _logger.exception(
                "Libro de Remuneraciones: no se pudo revalidar los perfiles "
                "semilla al cargar el registro.")
        return result

    # -- resolución por empresa y período -----------------------------------

    @api.model
    def resolve_for(self, company, present_rule_codes):
        """Perfil aplicable a una empresa para un período concreto.

        Devuelve ``(profile, origin, issues)`` donde ``origin`` es
        ``assigned``, ``detected`` o ``unconfirmed``.

        Reglas, en este orden y sin excepciones:

        1. El perfil asignado explícitamente a la empresa, si está activo.
        2. Autodetección **usando sólo los códigos de regla que aparecen en
           las liquidaciones seleccionadas**, no todas las reglas de la base.
        3. Cero coincidencias o más de una: se bloquea y se explica. Nunca se
           toma «el primero de la lista».
        """
        assigned = company.remuneration_book_profile_id
        if assigned:
            if assigned.state != "active":
                return assigned, "unconfirmed", [dt_book.Issue(
                    "error", "profile_not_active",
                    _("El perfil «%(name)s» asignado a %(company)s está en "
                      "estado «%(state)s». Sólo puede usarse un perfil Activo.",
                      name=assigned.name, company=company.name,
                      state=dict(self._fields["state"].selection)[assigned.state]),
                )]
            if assigned.company_id and assigned.company_id != company:
                return assigned, "unconfirmed", [dt_book.Issue(
                    "error", "profile_other_company",
                    _("El perfil asignado pertenece a otra empresa."),
                )]
            return assigned, "assigned", []

        candidates = self.search([
            ("state", "=", "active"),
            "|", ("company_id", "=", company.id), ("company_id", "=", False),
        ])
        present = set(present_rule_codes or ())
        matched = []
        for profile in candidates:
            required = profile.detector_codes()
            if required and all(code in present for code in required):
                matched.append(profile)

        if len(matched) == 1:
            return matched[0], "detected", []
        if not matched:
            return self.browse(), "unconfirmed", [dt_book.Issue(
                "error", "profile_not_detected",
                _("No hay ningún perfil activo cuyas reglas identificadoras "
                  "estén presentes en las liquidaciones de %(company)s. "
                  "Perfiles activos evaluados: %(candidates)s. Asigne un "
                  "perfil aprobado en la ficha de la empresa.",
                  company=company.name,
                  candidates=", ".join(candidates.mapped("name")) or _("ninguno")),
            )]
        return self.browse(), "unconfirmed", [dt_book.Issue(
            "error", "profile_ambiguous",
            _("Más de un perfil activo coincide con las liquidaciones de "
              "%(company)s: %(names)s. Asigne explícitamente el que "
              "corresponde en la ficha de la empresa.",
              company=company.name, names=", ".join(
                  profile.name for profile in matched)),
        )]


class RemunerationBookProfileLine(models.Model):
    _name = "step.remuneration.book.profile.line"
    _description = "Mapeo de un código DT"
    _order = "sequence, id"

    profile_id = fields.Many2one(
        "step.remuneration.book.profile", required=True, ondelete="cascade",
    )
    sequence = fields.Integer(default=10)
    dt_code = fields.Char(required=True, string="Código DT")
    label = fields.Char(string="Concepto")
    source_type = fields.Selection(
        SOURCE_TYPES, required=True, default="rule", string="Origen",
    )
    rule_codes = fields.Char(
        string="Códigos de regla",
        help="Códigos de regla salarial separados por coma, para 'rule', o "
             "códigos de tipo de entrada de trabajo, para 'worked_days'.",
    )
    operand_codes = fields.Char(
        string="Códigos DT operandos",
        help="Códigos DT separados por coma. En 'difference' se resta del "
             "primero todos los siguientes.",
    )
    sign = fields.Selection(SIGNS, required=True, default="as_is", string="Signo")
    adapter_key = fields.Selection(
        selection=lambda self: adapters.adapter_selection(),
        string="Adaptador",
        help="Origen externo registrado en código. No se puede indicar un "
             "modelo, un campo ni un dominio arbitrario.",
    )
    adapter_param = fields.Char(
        string="Parámetro del adaptador",
        help="Debe ser uno de los valores que el adaptador declara admitidos.",
    )

    _sql_constraints = [
        # Unicidad REAL en base de datos, además de la comprobación Python:
        # dos líneas con el mismo código DT harían que el importe mostrado
        # dependiera del orden de lectura.
        ("dt_code_uniq", "unique(profile_id, dt_code)",
         "Cada código DT puede aparecer una sola vez en un perfil."),
    ]

    @api.constrains("dt_code")
    def _check_dt_code(self):
        for line in self:
            if not (line.dt_code or "").strip().isdigit():
                raise ValidationError(_("El código DT debe ser numérico."))

    @api.constrains("source_type", "adapter_key", "adapter_param")
    def _check_adapter(self):
        """La clave de adaptador es un valor cerrado, siempre.

        Se comprueba aunque el origen todavía no sea `adapter`: el ORM acepta
        cualquier cadena en una selección calculada, y un valor inventado en el
        campo no debe poder quedar guardado ni siquiera de forma latente.
        """
        for line in self:
            if line.adapter_key and adapters.get_adapter(line.adapter_key) is None:
                raise ValidationError(_(
                    "«%(key)s» no es un adaptador registrado. Adaptadores "
                    "disponibles: %(available)s.",
                    key=line.adapter_key,
                    available=", ".join(sorted(adapters.ADAPTERS)) or "-"))
            if line.source_type != "adapter":
                continue
            adapter = adapters.get_adapter(line.adapter_key)
            if adapter is None:
                raise ValidationError(_(
                    "Debe elegir un adaptador registrado para el código DT "
                    "%s.", line.dt_code))
            message = adapter.check_param(line.adapter_param)
            if message:
                raise ValidationError(message)

    def codes_list(self, field_name):
        self.ensure_one()
        raw = self[field_name] or ""
        return [code.strip() for code in raw.split(",") if code.strip()]

    def apply_sign(self, value):
        self.ensure_one()
        if self.sign == "abs":
            return abs(value)
        if self.sign == "invert":
            return -value
        return value
