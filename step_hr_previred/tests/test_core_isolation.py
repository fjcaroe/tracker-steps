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

    def test_core_declares_only_engine_neutral_contracts_as_dependency(self):
        manifest = open(os.path.join(CORE_ROOT, "__manifest__.py"),
                        encoding="utf-8").read()
        depends = re.search(r'"depends":\s*\[([^\]]*)\]', manifest).group(1)
        self.assertEqual(
            [d.strip().strip('"\'') for d in depends.split(",") if d.strip()],
            ["step_payroll_contracts"])

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

    def previred_user(self,login,group):
        from odoo import Command
        return self.env['res.users'].with_context(no_reset_password=True).create({
            'name':'Private Previred role','login':login,'company_id':self.env.company.id,
            'company_ids':[Command.set(self.env.company.ids)],
            'groups_id':[Command.set([self.env.ref('base.group_user').id,self.env.ref(group).id])]})

    def test_normal_summary_user_opens_real_form_but_cannot_export(self):
        from odoo.exceptions import AccessError
        user=self.previred_user('private-previred-summary','step_hr_previred.group_previred_summary')
        model=self.env['step.previred.export.wizard'].with_user(user)
        wizard=model.create({'company_id':self.env.company.id,'date_from':'2026-08-01','date_to':'2026-08-31'})
        view=self.env.ref('step_hr_previred.view_previred_export_wizard_form')
        self.assertTrue(model.get_view(view_id=view.id,view_type='form')['arch'])
        self.assertFalse(wizard.env.su)
        with self.assertRaises(AccessError):wizard._ensure_export_permission()

    def test_generate_role_uses_actual_engine_or_explains_absence(self):
        from odoo.exceptions import UserError
        from odoo.addons.step_payroll_contracts.access import payroll_role_group,has_payroll_role
        user=self.previred_user('private-previred-generate','step_hr_previred.group_previred_generate')
        wizard=self.env['step.previred.export.wizard'].with_user(user).create({
            'company_id':self.env.company.id,'date_from':'2026-08-01','date_to':'2026-08-31'})
        self.env.cr.execute('SELECT count(*) FROM res_groups');before=self.env.cr.fetchone()
        group=payroll_role_group(wizard.env,'manager')
        if self.env.get('hr.payslip') is not None:
            self.assertTrue(group)
            self.assertTrue(has_payroll_role(wizard.env,'manager'))
            wizard._ensure_export_permission()
        else:
            self.assertFalse(group)
            with self.assertRaisesRegex(UserError,'motor'):wizard._ensure_export_permission()
        self.env.cr.execute('SELECT count(*) FROM res_groups');self.assertEqual(self.env.cr.fetchone(),before)
