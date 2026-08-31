"""Registro de adaptadores de motor de nómina.

El **core no conoce ningún proveedor**. Este archivo define únicamente el
contrato y un registro abierto; cada bridge (`step_hr_previred_blueminds`,
`step_hr_previred_simpledigital`) declara su dependencia real del addon del
proveedor y se registra al importarse.

Así el core puede instalarse en una base donde no existe ninguno de los dos
motores sin importar modelos, controladores ni XML IDs que podrían no estar.
"""

import logging

from odoo import _

from ..tools import previred

_logger = logging.getLogger(__name__)


class FieldSource:
    """Origen documentado de UNO de los 105 campos.

    Existe para que la correspondencia campo Previred → dato del motor sea
    **verificable**, no adivinada: cada entrada apunta a la expresión concreta
    del generador vigente de la que se tomó.
    """

    __slots__ = ("position", "kind", "source", "note")

    #: Tipos de origen admitidos.
    KINDS = (
        "rule",       # línea de la liquidación, por código de regla salarial
        "contract",   # campo del contrato
        "employee",   # campo del trabajador
        "company",    # campo de la compañía
        "indicator",  # indicador previsional del período
        "computed",   # cálculo del propio motor (tope, proporción, etc.)
        "constant",   # valor fijo de la especificación
        "period",     # derivado del período solicitado
        "unused",     # campo de uso futuro; va en cero o en blanco
    )

    def __init__(self, position, kind, source, note=""):
        assert kind in self.KINDS, "origen desconocido: %s" % kind
        self.position = position
        self.kind = kind
        self.source = source
        self.note = note

    @property
    def field_name(self):
        return previred.FIELD_NAMES[self.position - 1]

    def as_row(self):
        return (self.position, self.field_name, self.kind, self.source,
                self.note)


class EngineAdapter:
    """Contrato común de los adaptadores de motor."""

    #: Clave técnica estable; se guarda en el perfil y en la auditoría.
    key = ""
    #: Etiqueta para la interfaz.
    label = ""
    #: Addon del proveedor que este adaptador requiere.
    module = ""
    #: Generador vigente que se reutiliza, para la trazabilidad.
    generator = ""

    #: Estados de `hr.payslip` que ESTE motor considera una liquidación
    #: validada. No es una lista global: cada motor define el suyo y debe
    #: justificarlo. Nunca incluye `draft` ni `cancel`.
    eligible_states = ("done", "paid")
    #: Justificación de la lista anterior, mostrada en el perfil.
    eligible_states_note = ""

    #: ¿El motor tiene datos que justifiquen líneas anexas 01/02/03?
    supports_annexes = False
    #: Por qué sí o por qué no. Se muestra en la matriz de campos.
    annexes_note = ""

    # -- disponibilidad ------------------------------------------------------

    @classmethod
    def is_available(cls, env):
        """¿Está instalado el addon del proveedor en esta base?"""
        return bool(env["ir.module.module"].sudo().search([
            ("name", "=", cls.module), ("state", "=", "installed"),
        ], limit=1))

    # -- matriz de campos ----------------------------------------------------

    @classmethod
    def field_matrix(cls):
        """Los 105 `FieldSource` de este motor, en orden."""
        raise NotImplementedError

    @classmethod
    def check_matrix(cls):
        """Verifica que la matriz cubra las 105 posiciones exactamente una vez."""
        matrix = cls.field_matrix()
        positions = [entry.position for entry in matrix]
        problems = []
        if len(matrix) != previred.FIELD_COUNT:
            problems.append(
                "la matriz tiene %d entradas y deben ser %d"
                % (len(matrix), previred.FIELD_COUNT))
        missing = set(range(1, previred.FIELD_COUNT + 1)) - set(positions)
        if missing:
            problems.append("faltan las posiciones %s"
                            % ", ".join(str(p) for p in sorted(missing)))
        duplicated = {p for p in positions if positions.count(p) > 1}
        if duplicated:
            problems.append("se repiten las posiciones %s"
                            % ", ".join(str(p) for p in sorted(duplicated)))
        return problems

    # -- generación ----------------------------------------------------------

    @classmethod
    def generate_rows(cls, env, company, date_from, date_to, payslips):
        """Devuelve `(rows, issues)` con las filas del motor.

        `payslips` es el conjunto **ya filtrado por el core** (compañía,
        período y estados elegibles). El adaptador puede usarlo para acotar su
        consulta; si el generador del proveedor no admite ese filtro, el core
        descarta después las filas que no correspondan.

        Opcionalmente puede devolver una **tercera** posición, `row_meta`:
        una lista paralela a las líneas **principales** (código `00`) en su
        orden de aparición. Cada entrada es un `dict` con:

        * ``contract_id``: identidad técnica del contrato de esa línea, para
          que la unicidad admita tantas líneas principales como contratos
          elegibles tenga el trabajador y bloquee dos líneas del mismo
          contrato. **No** se exporta.
        * ``payslip_id`` (opcional): liquidación de origen, para trazabilidad.

        Un motor que no puede correlacionar contrato por contrato devuelve
        sólo `(rows, issues)`; el core cae entonces al criterio de unicidad
        por compañía + período + RUT.
        """
        raise NotImplementedError

    # -- utilidades compartidas ---------------------------------------------

    @staticmethod
    def split_text(text):
        """Parte el texto oficial en filas de campos.

        Se toleran CRLF y LF y se descartan las líneas vacías, que algunos
        generadores dejan al final y Previred no cuenta.
        """
        rows = []
        for line in (text or "").replace("\r\n", "\n").split("\n"):
            if not line.strip():
                continue
            rows.append(line.split(previred.SEPARATOR))
        return rows

    @staticmethod
    def missing_engine_issue(label):
        return previred.Issue(
            previred.SEVERITY_ERROR, "engine_missing",
            _("El generador Previred de «%s» no está disponible en esta "
              "base.", label))


#: Registro abierto. Cada bridge se inscribe al importarse; el core no
#: contiene ninguna entrada por sí mismo.
ADAPTERS = {}


def register(adapter):
    """Inscribe un adaptador. Idempotente: recargar el módulo no duplica."""
    if not adapter.key:
        raise ValueError("Un adaptador Previred necesita una clave.")
    ADAPTERS[adapter.key] = adapter
    _logger.info("Previred: motor «%s» registrado por %s.",
                 adapter.key, adapter.module or "?")
    return adapter


def adapter_selection():
    return [(key, adapter.label)
            for key, adapter in sorted(ADAPTERS.items())]


def get_adapter(key):
    return ADAPTERS.get(key)


def available_adapters(env):
    return [adapter for adapter in ADAPTERS.values()
            if adapter.is_available(env)]
