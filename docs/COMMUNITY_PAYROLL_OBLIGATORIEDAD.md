# Obligatoriedad original y frontera OCA

Bloque preparado desde `c12c1f6e`; **pendiente de aceptación del paquete exacto**
en Community oficial, copia fresca de Cerro y upgrade privado por el coordinador.
No es adopción de los 120 maestros ni conversión integral con cero Enterprise.

## Contrato auditado

El preflight privado F compara seis campos/columnas. Los seis son obligatorios
y `NOT NULL` en origen; los seis son opcionales y nullable en la referencia CE.
No hay un caso de origen nullable que requiera inventar un valor.

| Campo | NULL en referencia F | Política de este bloque |
| --- | ---: | --- |
| `hr.payroll.structure.type.name` | 0 / 5 | `required=True`; el ORM real aplica `NOT NULL`, con admisión previa que aborta si hay NULL |
| `hr.payroll.structure.type_id` | 3 / 4 | Conserva OCA opcional; rechaza adopción original incompleta |
| `hr.salary.rule.struct_id` | 10 / 49 | Conserva OCA opcional/M2M; rechaza adopción original incompleta |
| `hr.salary.rule.category_id` | 0 / 49 | Conserva opcional, cambia eliminación del maestro a `RESTRICT` |
| `hr.salary.rule.code` | 0 / 49 | Conserva OCA opcional; rechaza adopción original incompleta |
| `hr.salary.rule.category.code` | 0 / 34 | Conserva OCA opcional; rechaza adopción original incompleta |

La fuente LGPL OCA fijada en `4c71cd42e46a09a7512d92f5c63c0a9f7c26ad3e`,
`payroll/tests/test_hr_salary_rule.py`, prueba expresamente creación y cálculo
de reglas sin código, sin categoría y categorías sin código. El parámetro real
`payroll.require_code_and_category` alimenta campos de presentación; no es una
restricción de almacenamiento que permita afirmar equivalencia obligatoria.
No se retira esa prueba ni se declara cerrada la diferencia de cinco campos.

No se encontraron pruebas `unlink()` en los tests de `payroll` fijados. La nueva
prueba propia verifica el FK real y eliminación mediante ORM: una categoría
referenciada por una regla queda protegida; una categoría que sólo conserva una
línea de borrador privada sigue la política física OCA anterior.

## Líneas históricas e instalación

La herencia clásica de `hr.payslip.line` desde reglas obliga a declarar su
`category_id` explícitamente opcional/almacenado/`SET NULL`. No se convierte al
campo relacionado no almacenado del motor nativo. No se redeclara `line.code`:
StepBase ya conserva su contrato relacionado obligatorio/`NOT NULL`, confirmado
en F. Las pruebas upstream sin código corren durante la instalación de OCA,
antes de cargar StepBase. No certifican persistencia de líneas sin código en el
paquete Simple Digital completo. La eventual equivalencia de esas líneas sigue siendo una puerta
de conversión aparte, con preservación de filas y lectura histórica.

`admit_original_nullable_storage(cr)` debe ejecutarse **antes del setup ORM**
tanto en `pre_init_hook` como en pre-migración de la nueva versión. Sólo admite
OCA real sin motor nativo ni módulos Enterprise activos o en transición; no
depende del nombre del laboratorio. Si la tabla de tipos falta, únicamente un
API en estado `to install` puede dejar su creación al ORM. En upgrade la ausencia
es error. Cuando existe, el helper toma bloqueo y rechaza nombres NULL sin
completarlos. No crea maestros, modifica nombres ni ejecuta `SET NOT NULL` por
su cuenta: lo aplica la declaración real `name=fields.Char(required=True)`.

El coordinador debe mantener respaldo, lease compartido y verificaciones de
preservación; el helper no hace commit. No hace falta un override en StepBase:
su clase de tipo únicamente redeclara `default_struct_id`.

## Admisión explícita para la futura adopción

`hr.payroll.structure._step_check_original_required_contract()` es una API
privada, de lectura normal, para la herramienta versionada de adopción original.
Debe ser una precondición de esa herramienta, antes de habilitar su cálculo o
contabilización; **no** se engancha al cálculo OCA genérico ni se activa mediante
un booleano nuevo o un marcador de contexto RPC.

Comprueba las seis obligaciones originales y referencias de tipos, estructuras,
reglas y categorías, con ACL de campo/registro y contexto de país/compañía.
Incluye reglas archivadas y jerarquías de categorías. Contrasta membresías M2M
completas con IDs SQL y selección pública OCA para detectar referencias ocultas,
primarias omitidas o fuera de la jerarquía. No lee fórmulas para mostrarlas, no
crea propietarios y no calcula liquidaciones.

Un resultado positivo certifica sólo esos requisitos y alcance de relaciones.
Siguen pendientes identidad de los 120 maestros/91 aliases, las 71 reglas y sus
fórmulas originales, relación O2M/M2M, diarios/empresas/reporte, seguridad por rol,
SyS, certificación contable/Previred/libro y conversión integral restaurable.
La diferencia escalar/traducible de entradas también mantiene su política
explícita previa; este bloque no la modifica.

## Pruebas y límites

Se entregan siete casos nuevos sobre modelos reales OCA, sin duplicar suites:
metadata/FK/NOT NULL; eliminación de categoría y frontera de línea; admisión
sin escrituras e inclusión archivada; cinco valores opcionales incompletos;
cálculo OCA legítimo con categoría opcional y proveedor real sin código (sin
persistir una línea que contradiga el contrato Base); ACL con caché y país;
preflight NULL sin backfill.
La prueba de preflight usa una tabla temporal privada, nunca maestros originales.
El coordinador debe registrar resultados reales antes de aceptar este bloque.

Producción y QA-Cerro permanecen fuera. Se conservan Calendar, Boolean bancario,
210233, pagadas, históricos, saldos, correlativos y restricciones del vencimiento.
Esta extracción parcial no resuelve el 31 de octubre.
