"""El core no puede depender de ningún motor concreto.

`step_hr_previred` se instala en los tres ambientes, pero el motor previsional
no es el mismo en todos: Desarrollo y Demo llevan Blueminds y Demo-SyS lleva
SimpleDigital. Si el core importara modelos, controladores o XML IDs de uno de
ellos, se rompería en el otro.

Estas pruebas fijan esa frontera.
"""

import os
import re

from odoo.tests.common import TransactionCase, tagged

from ..models import previred_adapter as adapters

#: Addons de proveedor que el core NO puede nombrar.
VENDOR_MODULES = ("l10n_cl_hr", "l10n_cl_simpledigital_payroll")

CORE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _core_files(extensions=(".py", ".xml", ".csv")):
    """Archivos del core que se ejecutan en caliente.

    Se excluyen `migrations/`: una migración de adopción nombra por fuerza el
    XML ID antiguo, y eso no es acoplamiento en ejecución sino una conversión
    que corre una sola vez.
    """
    skip = ("__pycache__", os.sep + "tests", os.sep + "migrations")
    for folder, _dirs, files in os.walk(CORE_ROOT):
        if any(token in folder for token in skip):
            continue
        for name in files:
            if name.endswith(extensions):
                yield os.path.join(folder, name)


@tagged("post_install", "-at_install")
class TestCoreIsolation(TransactionCase):

    def test_core_never_names_a_vendor_module(self):
        """Ni un import, ni un XML ID, ni una cadena con el nombre del motor."""
        offenders = []
        for path in _core_files():
            with open(path, encoding="utf-8") as handle:
                for number, line in enumerate(handle, start=1):
                    for module in VENDOR_MODULES:
                        if module in line:
                            offenders.append(
                                "%s:%d → %s"
                                % (os.path.basename(path), number, module))
        self.assertEqual(
            offenders, [],
            "El core nombra addons de proveedor; eso pertenece a un bridge:\n"
            + "\n".join(offenders))

    def test_core_declares_only_hr_payroll_as_dependency(self):
        manifest = open(os.path.join(CORE_ROOT, "__manifest__.py"),
                        encoding="utf-8").read()
        depends = re.search(r'"depends":\s*\[([^\]]*)\]', manifest).group(1)
        self.assertEqual(
            [d.strip().strip('"\'') for d in depends.split(",") if d.strip()],
            ["hr_payroll"])

    def test_core_registry_is_open_and_may_be_empty(self):
        """Sin ningún bridge instalado el registro puede estar vacío.

        El core debe cargar igual: no puede dar por hecho que existe un motor.
        """
        self.assertIsInstance(adapters.ADAPTERS, dict)
        self.assertIsNotNone(adapters.adapter_selection())

    def test_wizard_explains_itself_when_no_engine_is_installed(self):
        """Sin motor, el asistente avisa; no revienta con un error técnico."""
        from odoo.exceptions import UserError
        saved = dict(adapters.ADAPTERS)
        adapters.ADAPTERS.clear()
        try:
            wizard = self.env["step.previred.export.wizard"].create({
                "company_id": self.env.company.id,
                "date_from": "2026-08-01",
                "date_to": "2026-08-31",
            })
            with self.assertRaises(UserError) as caught:
                wizard._validate_parameters()
            self.assertIn("perfil", str(caught.exception).lower())
        finally:
            adapters.ADAPTERS.update(saved)

    def test_no_previred_route_is_declared_by_the_core(self):
        """Las rutas HTTP del proveedor las cierra su bridge, no el core."""
        self.assertFalse(
            os.path.isdir(os.path.join(CORE_ROOT, "controllers")),
            "El core no debe publicar controladores Previred.")
