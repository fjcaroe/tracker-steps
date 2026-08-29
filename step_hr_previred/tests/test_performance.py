"""Prueba de volumen: caso 10 del encargo.

5.000 liquidaciones sintéticas, midiendo consultas, tiempo y memoria. Lo que
se vigila es que el coste sea **lineal**: el extractor debe resolver el lote en
un número de consultas constante, no una por trabajador.

Las liquidaciones son reales —se crean en la base— porque desde que el core
filtra por compañía y estado, un lote sin liquidaciones elegibles no produce
ninguna línea y la medición no valdría nada.
"""

import logging
import time
import tracemalloc

from odoo.tests.common import tagged

from ..tools import previred
from .common import PreviredCase, make_row

_logger = logging.getLogger(__name__)

#: Volumen mínimo que exige el encargo.
VOLUME = 5000

#: Techo de consultas del extractor. Es holgado a propósito: lo que se prueba
#: es que NO crezca con el número de trabajadores, no un número exacto.
MAX_QUERIES = 60


@tagged("post_install", "-at_install", "previred_performance")
class TestPerformance(PreviredCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.ruts = cls._create_volume(VOLUME)

    @classmethod
    def _create_volume(cls, count):
        """Crea `count` trabajadores con contrato y liquidación validada.

        La fixture inserta las liquidaciones con SQL en bloque, **a propósito**:
        `hr.payslip.create` dispara los cálculos de nómina (entradas de trabajo
        del contrato, días trabajados, líneas), que para 5.000 registros tardan
        más que la propia medición y no aportan nada a lo que se está midiendo.
        Lo que esta prueba mide es el **extractor**, no el motor de nómina.

        Los campos que se insertan son exactamente los que el extractor lee:
        trabajador, contrato, compañía, período y estado.
        """
        cr = cls.env.cr
        uid = cls.env.uid
        first = 10000000
        ruts = [str(first + index) for index in range(count)]

        # `resource.resource` → `hr.employee` → `hr.payslip`, en tres INSERT
        # masivos sobre `generate_series`. Toda la fixture queda dentro del
        # savepoint de la prueba y desaparece al terminar.
        cr.execute(
            """
            INSERT INTO resource_resource
                (name, resource_type, time_efficiency, tz, company_id, active,
                 create_uid, create_date, write_uid, write_date)
            SELECT 'Recurso ' || i, 'user', 100.0, 'America/Santiago', %s,
                   TRUE, %s, now(), %s, now()
            FROM generate_series(0, %s) AS i
            RETURNING id
            """, (cls.company.id, uid, uid, count - 1))
        resource_ids = [row[0] for row in cr.fetchall()]

        cr.execute(
            """
            INSERT INTO hr_employee
                (name, identification_id, company_id, department_id,
                 resource_id, employee_type, marital,
                 distance_home_work_unit, meal_distribution_mode, active,
                 create_uid, create_date, write_uid, write_date)
            SELECT 'Trabajador ' || (r.ord - 1),
                   -- `WITH ORDINALITY` empieza en 1: el desplazamiento debe
                   -- restarse o los RUT no cuadran con los de las filas.
                   (%s + r.ord - 1)::text || '-1',
                   %s,
                   CASE WHEN (r.ord - 1) %% 2 = 1 THEN %s ELSE %s END,
                   r.id, 'employee', 'single', 'kilometers', 'employee', TRUE,
                   %s, now(), %s, now()
            FROM unnest(%s::int[]) WITH ORDINALITY AS r(id, ord)
            RETURNING id
            """, (first, cls.company.id, cls.dep_agri.id, cls.dep_admin.id,
                  uid, uid, resource_ids))
        employee_ids = [row[0] for row in cr.fetchall()]

        # Sin contratos: crear 5.000 contratos dispara la generación de
        # entradas de trabajo del período, que tarda más que todo lo que esta
        # prueba mide. El departamento se resuelve entonces por el trabajador,
        # que es el último escalón de la precedencia documentada; la
        # precedencia en sí se prueba en `test_dataset`.
        cr.execute(
            """
            INSERT INTO hr_payslip
                (name, employee_id, company_id, struct_id,
                 date_from, date_to, state,
                 create_uid, create_date, write_uid, write_date)
            SELECT 'Liquidacion ' || e, e, %s, %s, %s, %s, 'done',
                   %s, now(), %s, now()
            FROM unnest(%s::int[]) AS e
            """, (cls.company.id, cls.structure.id, cls.date_from,
                  cls.date_to, uid, uid, employee_ids))
        cls.env.invalidate_all()
        return ruts

    def _synthetic_rows(self):
        """Filas sintéticas para los RUT creados. No se toca ningún dato real."""
        rows = []
        for index, rut in enumerate(self.ruts):
            rows.append(make_row(rut=rut, dv="1",
                                 last_name="APELLIDO%05d" % index,
                                 names="NOMBRE%05d" % index))
            # Uno de cada diez lleva una línea anexa con movimiento real.
            if index % 10 == 0:
                rows.append(make_row(
                    rut=rut, dv="1", line_type=previred.LINE_ADDITIONAL,
                    overrides={previred.F_MOVEMENT_CODE: "3",
                               previred.F_MOVEMENT_FROM: "01-08-2026",
                               previred.F_MOVEMENT_TO: "15-08-2026"}))
        return rows

    def test_five_thousand_records(self):
        rows = self._synthetic_rows()

        tracemalloc.start()
        started = time.time()
        query_before = self.env.cr.sql_log_count
        dataset = self.build(rows)
        queries = self.env.cr.sql_log_count - query_before
        elapsed = time.time() - started
        _current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        self.assertEqual(len(dataset.records), VOLUME)
        self.assertEqual(dataset.row_count, len(rows))
        self.assertEqual(dataset.eligible_payslip_count, VOLUME)
        self.assertEqual(dataset.dropped_count, 0)
        self.assertLess(
            queries, MAX_QUERIES,
            "El extractor hizo %d consultas para %d trabajadores: el coste "
            "debe ser constante, no una consulta por persona."
            % (queries, VOLUME))

        _logger.info(
            "Previred volumen: %d trabajadores, %d líneas, %d consultas, "
            "%.2fs, pico de memoria %.1f MB",
            VOLUME, len(rows), queries, elapsed, peak / (1024 * 1024))

    def test_rendering_five_thousand_records_is_linear(self):
        rows = self._synthetic_rows()
        dataset = self.build(rows)

        started = time.time()
        text = previred.render_records(dataset.sorted_records())
        elapsed = time.time() - started

        self.assertEqual(len(text.split(previred.LINE_ENDING)), len(rows))
        self.assertLess(elapsed, 30,
                        "Serializar %d líneas tardó %.1fs"
                        % (len(rows), elapsed))

    def test_department_split_of_five_thousand_records(self):
        """Partir el lote por departamento no debe consultar la base."""
        dataset = self.build(self._synthetic_rows())
        query_before = self.env.cr.sql_log_count
        grouped = dataset.by_department()
        total = sum(len(records) for records in grouped.values())
        self.assertEqual(self.env.cr.sql_log_count, query_before,
                         "Particionar el lote volvió a consultar la base.")
        self.assertEqual(total, VOLUME)
        self.assertEqual(len(grouped), 2)
