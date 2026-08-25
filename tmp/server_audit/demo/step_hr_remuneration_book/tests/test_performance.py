"""13. Rendimiento con volumen sintético.

No se impone un umbral inventado: se MIDE y se registra la línea base
(tiempo, consultas SQL y tamaño del archivo) para poder comparar entre
versiones y decidir con datos si hace falta generación asíncrona.

El volumen se controla con la variable de entorno
``STEP_BOOK_PERF_PAYSLIPS`` (por defecto 5.000 en la ejecución completa).
"""

import io
import logging
import os
import time

from odoo.tests.common import tagged

from ..tools import dt_book
from ..tools.xlsx_book import build_workbook
from .common import RemunerationBookCommon

_logger = logging.getLogger(__name__)

DEFAULT_VOLUME = int(os.environ.get("STEP_BOOK_PERF_PAYSLIPS", "5000"))


@tagged("post_install", "-at_install", "step_book_perf")
class TestPerformance(RemunerationBookCommon):
    """Prueba parametrizable de volumen. Etiquetada aparte por su duración."""

    def _bulk_payslips(self, quantity):
        """Crea liquidaciones sintéticas en bloque, sin nombres ni RUT reales.

        Los contratos se dejan en BORRADOR a propósito: un contrato en curso
        hace que Odoo genere entradas de trabajo y ejecute su comprobación de
        solapamientos, que es cuadrática y tardaría más que la medición misma.
        El Libro sólo lee `contract_id.department_id`, así que el estado del
        contrato no cambia lo que se está midiendo.
        """
        env = self.env(context=dict(
            self.env.context,
            tracking_disable=True,
            mail_create_nolog=True,
            mail_notrack=True,
        ))
        departments = [self.department_admin, self.department_field]
        employees = env["hr.employee"].create([
            {
                "name": "Sintético %05d" % index,
                # RUT sintético con dígito verificador calculado, nunca real.
                "identification_id": "%d-%s" % (
                    10000000 + index, self._verifier(10000000 + index)),
                "company_id": self.company.id,
            }
            for index in range(quantity)
        ])
        extra = {}
        if "contract_type_id" in env["hr.contract"]._fields:
            contract_type = self._contract_type()
            if contract_type:
                extra["contract_type_id"] = contract_type.id
        contracts = env["hr.contract"].create([
            dict(
                extra,
                name="Contrato %s" % employee.name,
                employee_id=employee.id,
                department_id=departments[index % 2].id,
                structure_type_id=self.structure_type.id,
                date_start="2026-01-01",
                wage=500000.0,
                state="draft",
                company_id=self.company.id,
            )
            for index, employee in enumerate(employees)
        ])
        values = self._coherent_values(
            wage=500000, deductions={dt_book.CODE_PENSION: 50000})
        payslips = env["hr.payslip"]
        batch = 500
        pairs = list(zip(employees, contracts))
        for start in range(0, len(pairs), batch):
            payslips |= env["hr.payslip"].create([
                {
                    "name": "Liquidación %s" % employee.name,
                    "employee_id": employee.id,
                    "contract_id": contract.id,
                    "struct_id": self.structure.id,
                    "date_from": "2026-06-01",
                    "date_to": "2026-06-30",
                    "company_id": self.company.id,
                    "state": "done",
                    "worked_days_line_ids": [(0, 0, {
                        "name": "Días trabajados",
                        "work_entry_type_id": self.work_entry_type.id,
                        "number_of_days": 30,
                        "number_of_hours": 240,
                    })],
                    "line_ids": [
                        (0, 0, {
                            "salary_rule_id": self.rules[dt_code].id,
                            "code": self.rules[dt_code].code,
                            "category_id": self.category.id,
                            "name": self.rules[dt_code].name,
                            "sequence": self.rules[dt_code].sequence,
                            "quantity": 1.0,
                            "rate": 100.0,
                            "amount": amount,
                            "total": amount,
                        })
                        for dt_code, amount in values.items()
                    ],
                }
                for employee, contract in pairs[start:start + batch]
            ])
        return payslips

    @staticmethod
    def _verifier(body):
        total, factor = 0, 2
        for digit in reversed(str(body)):
            total += int(digit) * factor
            factor = 2 if factor == 7 else factor + 1
        remainder = 11 - (total % 11)
        return {11: "0", 10: "K"}.get(remainder, str(remainder))

    def test_volume_baseline(self):
        quantity = DEFAULT_VOLUME
        self._bulk_payslips(quantity)
        wizard = self._wizard()

        self.env.flush_all()
        self.env.invalidate_all()
        queries_before = self.env.cr.sql_log_count
        started = time.time()
        dataset = wizard.build_dataset()
        dataset_seconds = time.time() - started
        dataset_queries = self.env.cr.sql_log_count - queries_before

        started = time.time()
        stream = io.BytesIO()
        build_workbook(stream, dataset)
        excel_seconds = time.time() - started
        payload = stream.getvalue()

        self.assertEqual(dataset.quantity, quantity)
        self.assertEqual(len(dataset.groups), 2)
        _logger.info(
            "LIBRO DE REMUNERACIONES - LÍNEA BASE DE RENDIMIENTO\n"
            "  liquidaciones      : %s\n"
            "  dataset            : %.2f s, %s consultas\n"
            "  Excel              : %.2f s, %.1f KB\n"
            "  total              : %.2f s",
            quantity, dataset_seconds, dataset_queries,
            excel_seconds, len(payload) / 1024.0,
            dataset_seconds + excel_seconds,
        )

    def test_duplicate_counting_is_linear(self):
        """El recuento de duplicados no puede ser cuadrático."""
        lines = [
            dt_book.BookLine(payslip_id=index, employee_id=index,
                             rut="%d-%s" % (10000000 + index,
                                            self._verifier(10000000 + index)),
                             department="Área", values={})
            for index in range(20000)
        ]
        dataset = dt_book.build_dataset(lines)
        started = time.time()
        counters = dt_book.build_counters(dataset)
        elapsed = time.time() - started
        self.assertEqual(counters["lines"], 20000)
        self.assertEqual(counters["unique_employees"], 20000)
        # Con `list.count()` esto tardaba minutos; O(n) baja de un segundo.
        self.assertLess(elapsed, 5.0)
        _logger.info(
            "Recuento de 20.000 líneas en %.3f s (O(n)).", elapsed)
