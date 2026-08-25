"""7. XSS en la previsualización y 10. contenido de la síntesis de control."""

from odoo.tests.common import tagged

from ..tools import dt_book
from .common import RemunerationBookCommon

#: Cargas útiles clásicas más comillas, `&` y Unicode.
PAYLOADS = (
    "<script>alert('xss')</script>",
    "<img src=x onerror=alert(1)>",
    "\" onmouseover=\"alert(2)",
    "Ñandú & Cía <b>negrita</b>",
    "'; DROP TABLE--",
)


@tagged("post_install", "-at_install")
class TestPreviewIsEscaped(RemunerationBookCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        employee = cls._create_employee("Vista Sintética", "12.345.678-5")
        cls._create_payslip(
            employee, cls._create_contract(employee, cls.department_admin),
            cls._coherent_values(wage=500000))

    def test_company_and_profile_names_are_escaped(self):
        """El marcado se muestra como TEXTO: ni etiquetas ni atributos vivos.

        Lo que importa no es que la subcadena `onerror` no aparezca -aparece,
        escapada, dentro del texto visible- sino que no quede como una etiqueta
        ni como un atributo que el navegador pueda ejecutar.
        """
        for payload in PAYLOADS:
            self.company.name = "Empresa %s" % payload
            self.profile.name = "Perfil %s" % payload
            wizard = self._wizard()
            wizard.action_refresh_preview()
            html = str(wizard.preview_html or "")
            self.assertNotIn("<script", html)
            self.assertNotIn("<img", html)
            self.assertNotIn("</script>", html)
            # Ningún atributo de evento fuera de una entidad escapada.
            for handler in ("onerror=", "onmouseover=", "onload="):
                position = html.find(handler)
                while position != -1:
                    # Debe venir precedido de texto escapado, no de una etiqueta
                    # abierta sin cerrar.
                    fragment = html[:position]
                    self.assertGreater(
                        fragment.rfind(">"), fragment.rfind("<"),
                        "%s quedó dentro de una etiqueta viva" % handler)
                    position = html.find(handler, position + 1)

    def test_escaped_payload_is_visible_as_text(self):
        self.profile.name = "Perfil <script>alert(1)</script>"
        wizard = self._wizard()
        wizard.action_refresh_preview()
        html = str(wizard.preview_html or "")
        self.assertIn("&lt;script&gt;", html)

    def test_blocking_message_is_escaped(self):
        self.company.name = "Empresa <script>alert('x')</script>"
        wizard = self._wizard(month="1", year=2026)  # período sin liquidaciones
        wizard.action_refresh_preview()
        html = str(wizard.preview_html or "")
        self.assertTrue(wizard.preview_blocked)
        self.assertNotIn("<script>", html)
        self.assertIn("&lt;script&gt;", html)

    def test_preview_shows_scope_profile_origin_and_availability(self):
        wizard = self._wizard()
        wizard.action_refresh_preview()
        html = str(wizard.preview_html or "")
        self.assertIn("Alcance: empresa completa", html)
        self.assertIn("Asignado", html)
        self.assertIn("Disponibilidad de las salidas", html)
        self.assertIn("Archivo oficial DT", html)

    def test_preview_counts_lines_workers_and_quality_issues(self):
        no_rut = self._create_employee("Sin RUT Sintético", False)
        self._create_payslip(
            no_rut, self._create_contract(no_rut), self._coherent_values())
        wizard = self._wizard()
        wizard.action_refresh_preview()
        html = str(wizard.preview_html or "")
        for label in (
            "Liquidaciones consideradas", "Líneas del informe",
            "Trabajadores únicos", "Líneas sin RUT",
            "Líneas con RUT inválido", "Líneas sin departamento",
            "Diferencias de conciliación",
        ):
            self.assertIn(label, html)

    def test_preview_never_shows_names_ruts_or_amounts(self):
        wizard = self._wizard()
        wizard.action_refresh_preview()
        html = str(wizard.preview_html or "")
        self.assertNotIn("Vista Sintética", html)
        self.assertNotIn("12.345.678", html)
        self.assertNotIn("500000", html)

    def test_partial_mode_says_the_official_csv_is_not_available(self):
        wizard = self._wizard(mode="partial")
        wizard.action_refresh_preview()
        html = str(wizard.preview_html or "")
        self.assertIn("Alcance parcial", html)
        self.assertIn("no disponible", html)

    def test_blocking_errors_are_separated_from_warnings(self):
        self.company.remuneration_book_profile_id = False
        self.profile.detector_rule_codes = "NADA_QUE_COINCIDA"
        wizard = self._wizard()
        wizard.action_refresh_preview()
        html = str(wizard.preview_html or "")
        self.assertIn("Errores que impiden generar el informe", html)
        self.assertTrue(wizard.preview_blocked)

    def test_dataset_scope_labels(self):
        self.assertEqual(dt_book.SCOPE_LABELS[dt_book.SCOPE_FULL],
                         "Alcance: empresa completa")
        self.assertEqual(dt_book.SCOPE_LABELS[dt_book.SCOPE_PARTIAL],
                         "Alcance parcial")
