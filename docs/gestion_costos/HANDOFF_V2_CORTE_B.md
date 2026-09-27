# Handoff — Corte V2 B (cargas históricas oficiales y plantillas versionadas)

**Addon:** `step_management_costs` · **De:** `18.0.15.0.0` → **A:** `18.0.16.0.0`
**Fecha:** 2026-09-07 · **Autor:** Claude Sonnet 5 · **Estado:** implementado
y verificado en Odoo real, sin despliegue

## 1. Alcance

Segundo corte de `PROMPT_CLAUDE_SONNET5_RESPUESTAS_V2_2026-09-06.md`. Carga
los dos archivos oficiales del cliente (`Anexo 1.6.2.1` presupuesto —
16.045 filas/241 duplicados exactos—, `Anexo 1.6.10.3` real —18.638 filas/
116 duplicados—, tres temporadas 2324/2425/2526 cada uno) sin usarlos como
fixture del repositorio ni cargarlos íntegros en ninguna base durante la
construcción.

**Decisión de arquitectura previa (obligatoria antes de tocar
`historical_cost.py`, ver `ADR_001` §D-L y `DECISION_LOG.md` §"Corte V2 B"):**
ambos archivos se cargan como **hechos históricos normalizados**
(`step.management.historical.cost` con `dataset_kind = 'budget'|'actual'`,
una fila = un registro fuente), **no** como
`step.management.operational.budget` — reconstruir presupuestos operacionales
desde datos masivos exigiría aprobar miles de documentos artificiales.
Presupuesto y real nunca comparten fila física (lotes separados,
`dataset_kind` distinto).

- `models/historical_import.py` (nuevo): `step.management.historical
  .template.version` (plantilla versionada, sólo Administrador),
  `.import.batch` (el "lote": staging seguro, mismo patrón que los demás
  importadores del addon), `.import.line` (staging).
- `models/historical_cost.py`: campos nuevos, todos opcionales
  (`dataset_kind`, snapshots de las 18 columnas — texto tal cual el archivo
  para las dimensiones, `source_amount`/`source_exchange_rate`/
  `source_amount_usd` tal cual el archivo para las medidas). Los registros
  manuales previos a este corte (comparación pareada) siguen funcionando sin
  cambios (`dataset_kind` vacío).
- Especie/variedad: obligatoria sólo si el centro resuelto es productivo
  (`cost_type = 'crop'`), nunca por regla global — verificado contra la
  distribución real de ambos archivos (Frutales siempre las trae;
  Operacional/Administrativo no).
- Fórmula de TC: nunca se ejecuta una fórmula arbitraria de Excel; sólo se
  acepta `=<Monto>/<Monto US$>` de la misma fila en la columna TC del real
  histórico (validado por regex sobre las referencias de celda, calculado en
  servidor).
- Duplicados exactos: siempre visibles; por omisión se importan (reflejan el
  archivo); casilla explícita para excluirlos sin borrar la evidencia.
- El real histórico entra `origin='external'`, estado inicial `entered`
  (Ingresado); sólo Aprobador/Control aprueba (`locked=True`) o bloquea
  (`origin='unreviewed'`, reutilizando la exclusión de comparativos ya
  existente). Corrección posterior = reversa (`action_create_reversal`,
  nuevo lote con signo contrario) o lote nuevo — nunca editar filas
  aprobadas.

## 2. Seguridad

- ACL nuevas: `historical.template.version` (sólo lectura/manager),
  `historical.import.batch(.line)` con fila `_approver` explícita (aprobar/
  bloquear es un gate de rol en Python, la ACL de `user` no permite
  `unlink`).
- Reglas globales por empresa para `import.batch(.line)`;
  `template.version` es un maestro global (sin `company_id`, un solo
  formato para todas las empresas, mantenido sólo por el Administrador).
- Índice único parcial de Postgres para la idempotencia del lote (empresa +
  tipo + plantilla + archivo), con la misma corrección de alcance que ya
  documenta este handoff en «Verificación» — sólo cubre estados realmente
  ingresados, no el borrador/validado.

## 3. Interfaz

- Menú **Gestión y Costos > Control de costos > Cargas históricas
  oficiales**; **Maestros > Plantillas de carga histórica** (Administrador).
- Formulario de `historical.cost`: nueva sección «Hecho histórico
  normalizado (V2 B)», sólo visible cuando `dataset_kind` está informado.

## 4. Migración

- Manifiesto `18.0.16.0.0`; sin dependencias nuevas.
- `data/historical_template_versions.xml`: siembra las dos versiones
  vigentes (`PPTO_HIST_V1`, `REAL_HIST_V1`) con la cabecera exacta de los
  anexos oficiales.
- `upgrades/18.0.16.0.0/post-migration.py`: preflight de sólo lectura
  (cuenta registros manuales sin `dataset_kind`, sin tocar nada). Modelos
  nuevos sin backfill.

## 5. Pruebas

`tests/test_v2_b_historical_import.py` (17 pruebas nuevas), usando muestras
representativas pequeñas construidas en memoria (nunca los archivos reales
del cliente ni datos personales): 18 columnas extremo a extremo; versión de
plantilla desconocida (columna extra) rechazada; fórmula de TC segura
calculada en servidor; fórmula no seguro y fórmula en otra columna
rechazadas; especie obligatoria en centro productivo y opcional en
operacional; centro inexistente y ambiguo (por normalización); duplicado
exacto mostrado e incluido por omisión, y excluible explícitamente sin
perder la fila del detalle; mismo archivo concurrente bloqueado; dos
compañías aisladas; conciliación monetaria con tolerancia; aprobación
bloquea ediciones (con RPC de un rol sin permiso); reversa sin editar el
lote aprobado; bloqueo excluye de comparativos.

### Verificación local

- `py_compile`, parseo de los 30 XML, `git diff --check`: OK.

### Verificación Odoo real en `odoo-new` (sólo bases desechables)

Mismo patrón que los cortes anteriores. Se encontraron y corrigieron **dos
bugs reales** durante la verificación (ninguno visible a `py_compile`/parseo
XML, ambos exigían Odoo real para aparecer):

1. **Alcance del índice único parcial demasiado amplio.** El índice cubría
   `state NOT IN ('draft','cancelled')`, incluyendo `'validated'`. Calcular
   la huella del lote (`batch_key_hash`) para el `search()` amistoso de
   duplicados, con el registro todavía en `validated`, disparaba un flush
   inmediato de la ORM que chocaba con el índice **antes** de que el
   `search()` alcanzara a dar el error legible — `psycopg2.errors.
   UniqueViolation` crudo en `test_same_file_concurrent_blocked`. Corregido
   acotando el índice a `state IN ('entered','approved','blocked')` y
   moviendo la asignación de `batch_key_hash` a dentro del mismo
   `savepoint()` que la escritura real de estado.
2. **Orden de `<menuitem>` en `menu_views.xml`.** El nuevo ítem de menú de
   plantillas referenciaba `parent="menu_management_masters"` antes de que
   ese menú se definiera en el mismo archivo. Invisible en upgrade (el XML
   ID ya existía en la base de una instalación anterior) pero rompía la
   **instalación limpia** (`ParseError: External ID not found`). Corregido
   reordenando las líneas.

| Escenario | Resultado |
|---|---|
| Upgrade de clon de `LAB_TAREAS` (`18.0.4.0.0` → `18.0.16.0.0`), addon final | RC 0 · **0 failed, 0 error(s) de 234 tests** (`odoo.tests.stats`: 274 tests, 211.9s, 86236 queries) |
| Instalación limpia sin demo (`--without-demo=all`) | RC 0 · **0 failed, 0 error(s) de 234 tests** (`odoo.tests.stats`: 274 tests, 47.2s, 40415 queries) |

234 = 217 (V2 A) + 17 (V2 B) — exacto 1:1 con la suma de métodos `test_*`
nuevos de este corte. La discrepancia `stats` (274) vs `result` (234) es la
misma naturaleza heredada de cortes anteriores, no bloqueante.

Bases (`MC_V2B_UPG`, `MC_V2B_UPG2`, `MC_V2B_CLEAN`), dump de `LAB_TAREAS`,
directorio temporal y scripts desechables eliminados al terminar.
`LAB_TAREAS` no se tocó (sólo `pg_dump`).

## 6. Decisiones y supuestos

Ver `DECISION_LOG.md` §"Corte V2 B" (D-L) y `ADR_001` §D-L. Ningún dato
personal ni archivo completo del cliente quedó en el repositorio.

## 7. Pendientes del cliente

- K3, H1, K5, D20, BPA-Riego, usuarios reales/UAT: sin cambios, siguen
  bloqueados según lo ya documentado.

## 8. Confirmación de aislamiento

No se tocó `STEPS_DEMO_SYS`, ninguna otra sesión de Claude, ni bases reales
(`LAB_TAREAS` sólo se leyó vía `pg_dump`). Sin commit ni push. Los archivos
`.xlsx` del cliente permanecen en `Downloads/`, fuera del repositorio.

## 9. Siguiente

Corte V2 C: comprometido de compras y cantidad neta por comprar
(`18.0.17.0.0`).
