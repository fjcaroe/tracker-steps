# -*- coding: utf-8 -*-
"""Guardado del formulario Horas Máquina por la misma ruta que usa el navegador.

No hay Chrome headless en el servidor, así que en vez de simular clics se
ejercitan los endpoints reales del cliente web (`/web/dataset/call_kw` →
`get_views`, `onchange`, `web_save`) con una sesión HTTP autenticada. Es el
mismo contrato que envía la interfaz al pulsar Nuevo y Guardar.
"""

from odoo.tests.common import HttpCase, tagged

MODEL = "step.hrs.machinery"
SPECIFICATION = {
    "ot_number": {}, "date": {}, "folio": {}, "name": {}, "legacy_name": {},
    "state": {}, "company_id": {"fields": {"display_name": {}}},
}


@tagged("post_install", "-at_install")
class TestMachineryWebForm(HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.admin = cls.env.ref("base.user_admin")
        # Contraseña local de la base desechable, nunca una credencial real.
        cls.admin.write({"password": "admin_qa_maquinaria"})

    def _call_kw(self, model, method, args, kwargs=None):
        return self.make_jsonrpc_request("/web/dataset/call_kw", {
            "model": model, "method": method,
            "args": args, "kwargs": kwargs or {},
        })

    def test_form_saves_without_typing_name(self):
        self.authenticate("admin", "admin_qa_maquinaria")

        views = self._call_kw(MODEL, "get_views", [[[False, "form"]]], {"options": {}})
        self.assertIn("form", views["views"])
        arch = views["views"]["form"]["arch"]
        self.assertIn('name="ot_number"', arch)
        self.assertIn('name="name"', arch)

        # "Nuevo": el cliente pide los valores por defecto del formulario.
        defaults = self._call_kw(MODEL, "onchange", [[], {}, [], SPECIFICATION])
        self.assertFalse(defaults["value"].get("name"),
                         "El formulario nace sin Nombre; no debe pedirlo al usuario.")

        # "Guardar" con exactamente lo que escribe el usuario.
        record_id = self._call_kw(MODEL, "web_save", [
            [], {"date": "2026-08-28", "folio": "W35"}, SPECIFICATION,
        ])[0]["id"]
        self.assertTrue(record_id, "El formulario debe guardar sin escribir Nombre.")

        record = self.env[MODEL].browse(record_id)
        record.invalidate_recordset()
        self.assertTrue(record.ot_number)
        self.assertEqual(record.name, "%s 28/08/2026 OT W35" % record.ot_number)

        # Cambiar la Orden de Trabajo desde el formulario recompone el nombre.
        saved = self._call_kw(MODEL, "web_save", [
            [record_id], {"folio": "W36"}, SPECIFICATION,
        ])[0]
        self.assertEqual(saved["folio"], "W36")
        self.assertEqual(saved["name"], "%s 28/08/2026 OT W36" % saved["ot_number"])
        self.assertEqual(saved["ot_number"], record.ot_number,
                         "El correlativo no cambia al editar la labor.")

        # La prueba corre en transacción: al terminar no queda ningún registro.
        self.assertTrue(self.env[MODEL].browse(record_id).exists())

    def test_list_and_search_expose_ot_number_and_name(self):
        self.authenticate("admin", "admin_qa_maquinaria")
        views = self._call_kw(MODEL, "get_views", [[[False, "list"], [False, "search"]]], {"options": {}})
        list_arch = views["views"]["list"]["arch"]
        search_arch = views["views"]["search"]["arch"]
        for field in ("ot_number", "name", "folio", "legacy_name"):
            self.assertIn('name="%s"' % field, list_arch, "Falta %s en la lista" % field)
            self.assertIn(field, search_arch, "Falta %s en la búsqueda" % field)
