# © 2025 (Jamie Escalante <jamie.escalante7@gmail.com>)
# -*- coding: utf-8 -*-

import logging
import unicodedata

from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)

#: Catálogo canónico de conceptos de costo de maquinaria: (código, nombre).
#: El orden es el del informe funcional y coincide con `_cost_components()`
#: de `step.hrs.machinery.line`.
CANONICAL_SERVICES = (
    ("01", "Combustible"),
    ("02", "Aceites y lubricantes"),
    ("03", "Repuestos"),
    ("04", "Mantención correctiva"),
    ("05", "Mano de Obra"),
    ("06", "Arriendo"),
    ("07", "Mantención preventiva"),
    ("08", "Depreciación mensual"),
)

#: Cuentas contables canónicas: (código, nombre, tipo de cuenta Odoo 18).
CANONICAL_CARGO_ACCOUNT = ("410161", "Costo estándar maquinarias", "expense")
CANONICAL_ABONO_ACCOUNT = ("210233", "Provisión costo maquinarias", "liability_current")

#: Prefijo de los códigos temporales usados para reordenar sin chocar con la
#: restricción `unique(cod, company_id)`.
TEMP_CODE_PREFIX = "__MIGR__"


def normalize_label(text):
    """Normaliza un nombre para poder compararlo: sin tildes, sin mayúsculas."""
    if not text:
        return ""
    decomposed = unicodedata.normalize("NFKD", str(text))
    stripped = "".join(char for char in decomposed if not unicodedata.combining(char))
    return " ".join(stripped.lower().split())


class TypeServiceMachinery(models.Model):
    _name = 'type.service.machinery'
    _inherit = ['mail.thread']

    name = fields.Char(string='Nombre', index=True, required=True)
    cod = fields.Char(string='Código Servicio')
    cargo_account_id = fields.Many2one('account.account', string='Cuenta Cargo')
    abono_account_id = fields.Many2one('account.account', string='Cuenta Abono')
    categ = fields.Selection(string='Categoría',
                                  selection=[('service', 'Servicio'),
                                             ('contract', 'Contrato')])
    comment = fields.Html(string='Comentario')
    company_id = fields.Many2one(
        'res.company', string='Empresa', default=lambda self: self.env.company,
        index=True, help='Vacío para compartir el concepto entre empresas.',
    )

    _sql_constraints = [
        ('service_code_company_unique', 'unique(cod, company_id)',
         'El código del concepto debe ser único por empresa.'),
    ]

    # ------------------------------------------------------------------
    # Homologación del catálogo y de la configuración contable
    # ------------------------------------------------------------------
    @api.model
    def _ensure_canonical_account(self, company, definition, report):
        """Devuelve la cuenta canónica de la empresa, creándola si falta.

        Se apoya sólo en el ORM: nada de IDs fijos ni de escritura directa en
        `code_store`, que en Odoo 18 es un campo dependiente de la empresa.
        """
        code, name, account_type = definition
        Account = self.env["account.account"].sudo().with_company(company)
        account = Account.search([("code", "=", code)], limit=1)
        if account:
            report["cuentas_reutilizadas"].append("%s %s" % (code, account.display_name))
            if company not in account.company_ids:
                account.write({"company_ids": [(4, company.id)]})
                report["cuentas_compartidas"].append("%s -> %s" % (code, company.name))
            return account
        account = Account.create({
            "code": code,
            "name": name,
            "account_type": account_type,
            "reconcile": False,
        })
        # El nombre es traducible: se deja también en el idioma de trabajo para
        # que Desarrollo y Demo muestren exactamente lo mismo.
        for lang in self.env["res.lang"].sudo().search([("active", "=", True)]).mapped("code"):
            account.with_context(lang=lang).name = name
        report["cuentas_creadas"].append("%s %s (%s)" % (code, name, account_type))
        return account

    @api.model
    def _ensure_journal_accepts(self, company, accounts, report):
        """Permite las cuentas canónicas en el diario de maquinaria.

        Si el diario no restringe cuentas (lista vacía) se deja como está: ya
        acepta cualquier cuenta. Si restringe, se agregan las canónicas sin
        quitar las que ya estaban autorizadas.
        """
        journal = company.sudo().step_journal_machinery
        if not journal:
            journal = self.env["account.journal"].sudo().search(
                [("code", "=", "CDMaq"), ("company_id", "=", company.id)], limit=1)
        if not journal:
            report["diario"] = "sin diario de maquinaria configurado en %s" % company.name
            return False
        if not journal.account_control_ids:
            report["diario"] = "%s: sin restricción de cuentas (acepta todas)" % journal.code
            return journal
        missing = accounts - journal.account_control_ids
        if not missing:
            report["diario"] = "%s: %s" % (
                journal.code,
                ", ".join(sorted(journal.account_control_ids.mapped("code"))),
            )
            return journal
        # Odoo prohíbe restringir un diario que ya tiene apuntes con otras
        # cuentas, así que las cuentas ya usadas se conservan en la lista.
        used = self._accounts_used_in_journal(journal)
        target = journal.account_control_ids | accounts | used
        try:
            journal.write({"account_control_ids": [(6, 0, target.ids)]})
        except Exception as error:  # noqa: BLE001 - se informa y no se aborta
            report["diario"] = "%s: no fue posible ampliar las cuentas permitidas (%s)" % (
                journal.code, error)
            _logger.warning(
                "Maquinaria: no se pudo ampliar account_control_ids del diario %s: %s",
                journal.code, error)
            return journal
        report["diario_cuentas_agregadas"].extend(sorted(missing.mapped("code")))
        report["diario"] = "%s: %s" % (
            journal.code,
            ", ".join(sorted(journal.account_control_ids.mapped("code"))),
        )
        return journal

    @api.model
    def _accounts_used_in_journal(self, journal):
        """Cuentas que ya aparecen en apuntes del diario."""
        self.env["account.move.line"].flush_model(["account_id", "journal_id"])
        self.env.cr.execute(
            "SELECT DISTINCT account_id FROM account_move_line "
            "WHERE journal_id = %s AND account_id IS NOT NULL",
            (journal.id,),
        )
        ids = [row[0] for row in self.env.cr.fetchall()]
        accounts = self.env["account.account"].sudo().browse(ids).exists()
        if journal.default_account_id:
            accounts |= journal.default_account_id
        if journal.suspense_account_id:
            accounts |= journal.suspense_account_id
        return accounts

    @api.model
    def _canonical_companies(self):
        """Empresas sobre las que hay que homologar el catálogo."""
        companies = self.sudo().search([("company_id", "!=", False)]).mapped("company_id")
        return companies or self.env["res.company"].sudo().search([], order="id", limit=1)

    @api.model
    def _ensure_canonical_catalog(self, companies=None):
        """Deja el catálogo canónico de 8 conceptos con sus cuentas.

        Idempotente: puede ejecutarse tantas veces como haga falta sin
        duplicar conceptos, sin depender de IDs de base de datos y sin romper
        las relaciones existentes (líneas de consumo y de ratio siguen
        apuntando al mismo registro, sólo se corrige su código).
        """
        report = {
            "empresas": [],
            "conceptos_encontrados": [],
            "conceptos_normalizados": [],
            "conceptos_creados": [],
            "cuentas_creadas": [],
            "cuentas_reutilizadas": [],
            "cuentas_compartidas": [],
            "relaciones_asignadas": [],
            "diario_cuentas_agregadas": [],
            "diario": "",
        }
        Service = self.sudo()
        companies = companies or self._canonical_companies()
        for company in companies:
            report["empresas"].append(company.name)
            cargo = self._ensure_canonical_account(company, CANONICAL_CARGO_ACCOUNT, report)
            abono = self._ensure_canonical_account(company, CANONICAL_ABONO_ACCOUNT, report)
            self._ensure_journal_accepts(company, cargo | abono, report)

            existing = Service.search([("company_id", "in", (company.id, False))])
            by_label = {}
            for record in existing:
                by_label.setdefault(normalize_label(record.name), record)
            by_code = {}
            for record in existing:
                by_code.setdefault((record.cod or "").strip(), record)

            # 1) Emparejar cada concepto canónico con el registro que ya
            #    representa ese significado; el nombre manda sobre el código,
            #    porque en Demo los códigos están intercambiados.
            matched = {}
            claimed = self.browse()
            for code, label in CANONICAL_SERVICES:
                record = by_label.get(normalize_label(label))
                if record and record not in claimed:
                    matched[code] = record
                    claimed |= record
            for code, label in CANONICAL_SERVICES:
                if code in matched:
                    continue
                record = by_code.get(code)
                if record and record not in claimed:
                    matched[code] = record
                    claimed |= record
            for code, _label in CANONICAL_SERVICES:
                if code in matched:
                    report["conceptos_encontrados"].append(
                        "%s -> %s (cod actual %s)" % (code, matched[code].name, matched[code].cod))

            # 2) Liberar los códigos que deben moverse usando códigos
            #    temporales, para no chocar con unique(cod, company_id).
            to_renumber = {
                code: record for code, record in matched.items()
                if (record.cod or "").strip() != code
            }
            for code, record in to_renumber.items():
                record.write({"cod": "%s%s" % (TEMP_CODE_PREFIX, record.id)})
            # Los códigos temporales tienen que llegar a base ANTES de escribir
            # los definitivos: si no, unique(cod, company_id) salta al aplicar
            # los UPDATE uno por uno.
            self.env.flush_all()
            for code, record in to_renumber.items():
                previous = next(
                    (c for c, r in by_code.items() if r == record and c), "")
                record.write({"cod": code})
                report["conceptos_normalizados"].append(
                    "%s: '%s' %s -> %s" % (company.name, record.name, previous or "(sin código)", code))
            self.env.flush_all()

            # 3) Crear los conceptos que faltan.
            for code, label in CANONICAL_SERVICES:
                if code in matched:
                    continue
                record = Service.create({
                    "name": label, "cod": code, "company_id": company.id,
                    "categ": "service",
                })
                matched[code] = record
                self.env.flush_all()
                report["conceptos_creados"].append("%s: %s %s" % (company.name, code, label))

            # 4) Asignar las cuentas canónicas donde falten o difieran.
            for code, _label in CANONICAL_SERVICES:
                record = matched[code]
                values = {}
                if record.cargo_account_id != cargo:
                    values["cargo_account_id"] = cargo.id
                if record.abono_account_id != abono:
                    values["abono_account_id"] = abono.id
                if values:
                    record.write(values)
                    report["relaciones_asignadas"].append(
                        "%s: %s %s -> cargo %s / abono %s"
                        % (company.name, code, record.name, cargo.code, abono.code))

        _logger.info(
            "Maquinaria catálogo canónico | empresas=%s | encontrados=%s | normalizados=%s | "
            "creados=%s | cuentas creadas=%s | cuentas reutilizadas=%s | relaciones=%s | "
            "diario=%s | cuentas agregadas al diario=%s",
            report["empresas"], len(report["conceptos_encontrados"]),
            report["conceptos_normalizados"], report["conceptos_creados"],
            report["cuentas_creadas"], report["cuentas_reutilizadas"],
            len(report["relaciones_asignadas"]), report["diario"],
            report["diario_cuentas_agregadas"],
        )
        return report
