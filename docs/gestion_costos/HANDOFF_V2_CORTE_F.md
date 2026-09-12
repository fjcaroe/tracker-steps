# Handoff — Corte V2 F (comparativos, tablero, clasificación fuera de OP)

**Addon:** `step_management_costs` · **De:** `18.0.19.0.0` → **A:** `18.0.20.0.0`
(sin puentes nuevos — todo vive en el núcleo)
**Fecha:** 2026-09-07 · **Autor:** Claude Sonnet 5 · **Estado:** implementado
y verificado en Odoo real (instalación limpia verde salvo la misma
excepción externa ya documentada en los Cortes V2 D/E; upgrade bloqueado
por el mismo hallazgo externo, confirmado persistente por tercera vez),
sin despliegue

## 1. Alcance

Sexto corte de `PROMPT_CLAUDE_SONNET5_RESPUESTAS_V2_2026-09-06.md`. Implementa
únicamente las salidas ya confirmadas (H1 sigue bloqueando el catálogo
completo de informes/PDF, instrucción explícita del corte).

1. **Comparativo de temporada** (`wizard/season_comparison.py`):
   `step.management.season.comparison.wizard`, fuente única
   `step.management.historical.cost` (hecho normalizado del Corte V2 B) —
   nunca mezclado con la contabilidad analítica en vivo dentro de la misma
   comparación (evita el doble conteo pedido explícitamente). 8 dimensiones
   (fundo, especie, variedad, centro, origen, grupo presupuestario,
   actividad, producto-labor). Medidas en CLP y US$. Variación % **siempre**
   desde los totales ya sumados, nunca sumando/promediando porcentajes de
   fila; queda marcada "sin base" (no "0 %") cuando la temporada anterior
   no tiene monto. Excluye `origin == 'unreviewed'`.
2. **Tablero ampliado** (`models/management_dashboard.py`): se extendió
   `get_management_dashboard()` **existente** (no se creó uno paralelo).
   Bloque «real vs. presupuesto» ya existía; se le agregó `variance_percent`/
   `budget_available` con la misma protección de cero. Nuevos:
   `hectares_by_farm_species`, `hectares_by_variety` (sobre
   `step.management.cost.center`, campos ya existentes) y `stock`
   (necesidades/disponible/comprometido/neto — V2 C ya es parte del núcleo).
3. **Clasificación fuera de OP** (`wizard/out_of_op_classifier.py`):
   `step.management.out.of.op.wizard` clasifica gasto real (apuntes
   contables publicados) por **centro + temporada + grupo presupuestario**.
   La dimensión **actividad** de la clave pedida por el corte queda
   deliberadamente fuera de esta versión — bloqueada por **D20** (la única
   fuente técnica para derivarla de un apunte real es
   `product.template.actividad_id`, semántica sin confirmar). Se aísla ese
   campo y se continúa con las tres dimensiones demostrables, siguiendo el
   mismo criterio ya aplicado en el Corte V2 D. "Amparado por OP": existe
   una `step.management.production.order` autorizada/reemplazada para esa
   clave con al menos una línea del mismo grupo. Nunca excluye ni mezcla:
   ambos casos (`backed_by_op` verdadero/falso) se muestran juntos.
4. **Folio derivado, nunca fabricado**: `source_label` en el clasificador
   muestra el folio real de la OP cuando existe; si no, deriva
   «Wxx/AAAA (derivado)» de la semana ISO de los apuntes reales
   (`period.service.iso_weeks`, ya existente); sin fecha, "Sin origen
   registrado". Nunca inventa un folio.

## 2. Seguridad

ACL nuevas para los dos wizards y sus líneas (`group_management_readonly`,
CRUD completo — mismo criterio que `budget.variance.wizard`, ya existente:
"readonly" rige el acceso a los modelos de negocio, no a los wizards
transitorios que son sólo espacio de cómputo de sesión).

## 3. Interfaz

Menú **Control de costos**: «Comparativo de temporada» y «Gasto dentro /
fuera de OP», junto al ya existente «Presupuesto vs. real». El tablero
(`Centro de Gestión y Costos`, cliente OWL ya existente) recibe los datos
nuevos en el payload de `get_management_dashboard()`; su renderizado visual
(JS/QWeb) no se tocó en este corte — los bloques nuevos están disponibles
para consumo, la maquetación visual queda para una iteración de UI menor.

## 4. Migración

`step_management_costs/__manifest__.py` → `18.0.20.0.0`.
`upgrades/18.0.20.0.0/post-migration.py`: preflight informativo — todo lo
nuevo son `TransientModel` (sin tabla) y bloques calculados en vivo sobre
el tablero existente; sin cambios de esquema.

## 5. Hallazgo real corregido (núcleo, no de este corte)

`_read_real_cost_buckets()` (clasificador fuera de OP) armaba un
diccionario `cuenta analítica → centro` con una comprensión simple. Dos
centros de costo pueden compartir intencionalmente una cuenta analítica
(escenario real, cubierto por fixtures y tests de otros cortes) — con ese
diccionario simple, el gasto real se atribuía **en silencio** al centro que
ganara la colisión de iteración, nunca reportado como ambiguo.
`operational_budget.py` ya tenía esta protección para lecturas de un
presupuesto específico (`_duplicate_analytic_centers()`); se generalizó a
`step.management.cost.center.account_to_center_map()` (nuevo método
reutilizable en el núcleo: exige 1 cuenta analítica = 1 centro, levanta
`UserError` explícito ante la ambigüedad) y el clasificador de este corte
lo usa. Encontrado por `test_expense_backed_by_op_is_classified_in_op`
contra Odoo real — en un test aislado con fixtures propias no se
reproducía; sólo apareció al correr contra el fixture compartido del
núcleo (`center_a`/`center_a2`, que comparten cuenta analítica a propósito
para otro test). Cualquier código futuro que necesite mapear cuentas
analíticas a centros de costo (no sólo maquinaria u OP) debería reutilizar
este método en vez de reimplementar el diccionario.

## 6. Pruebas

`tests/test_v2_f_dashboard.py` (19 pruebas): comparativo — temporada
anterior inexistente (sin NaN/infinito, marcado "sin base"), pesos/US$,
métrica presupuesto en cero, valores negativos/reversas, totales vs.
porcentajes (caso adversarial: promediar daría 25 %, el correcto es 0 %),
las 8 dimensiones, origen "sin clasificar" excluido, dos compañías,
permisos de consulta, temporada igual a temporada anterior rechazada;
fuera de OP — gasto sin OP clasificado correctamente (con folio derivado
Wxx/año), gasto amparado por una OP real (flujo completo presupuesto→plan→
tareas semanales→OP→autorización), filtro "sólo fuera de OP", cuenta
analítica compartida entre centros rechazada explícitamente, factura en
borrador no cuenta, sin doble conteo entre `historical_cost` y
`account.move.line`; tablero — hectáreas por fundo/especie y por variedad,
bloque de costos zero-safe (probado sobre el helper directamente, no sobre
datos ambiente — ver nota abajo).

### Verificación local

`py_compile` y `git diff --check` de todo lo tocado/nuevo: OK. XML
parseado.

### Verificación Odoo real en `odoo-new` (sólo bases desechables)

Se encontraron y corrigieron, contra Odoo real, tres defectos propios
adicionales al de §5 antes de quedar en verde: (a) `UnboundLocalError`
en `get_management_dashboard()` — el bloque `stock` se insertó antes de
que `company` estuviera definido, simple reordenamiento; (b) un test
(`test_costs_block_variance_percent_zero_safe`) asumía datos vacíos para
"la compañía principal" y fallaba contra `LAB_TAREAS` real (que sí tiene
historia) — corregido para probar el helper `_dashboard_costs_block()`
directamente, no todo `get_management_dashboard()` sin acotar; (c) el
hallazgo de §5.

| Escenario | Resultado |
|---|---|
| Instalación limpia sin demo, núcleo + 2 puentes juntos (`--without-demo=all`) | RC 1 (por la excepción externa) · **0 failed, 1 error(s) de 282 tests** — el único es `TestFase2Variance` (ajeno, ver `HANDOFF_V2_CORTE_D.md` §5); el resto —incluidas las 24 de este corte— en verde |
| Upgrade de clon de `LAB_TAREAS` (tomado hoy ~08:11, 4h después del primer hallazgo en Corte V2 D) | RC 1 (por el hallazgo externo) · **0 failed, 5 error(s) de 265 tests** — los 5 son el mismo `res_company.security_lead`/`sale_stock`, confirmado persistente por tercera vez consecutiva en el mismo día |

La vía de instalación limpia sigue siendo la verificación decisiva y
suficiente. Bases desechables (`MC_V2F_CLEAN` a `_CLEAN3`, `MC_V2F_UPG`),
dumps y directorios temporales eliminados al terminar. `LAB_TAREAS` no se
escribió.

## 7. Decisiones y supuestos

Ver `DECISION_LOG.md` §"Corte V2 F" (D-P) y `MATRIZ_REQUISITOS.md`.

## 8. Pendientes del cliente

Sin cambios respecto a los cortes anteriores (K3, H1, K5, D20, BPA-Riego,
usuarios reales/UAT). D20 bloquea específicamente la dimensión «actividad»
de la clasificación fuera de OP (punto 5 de este corte) — el resto de la
clave (centro + temporada + grupo) está implementado y verificado.

## 9. Confirmación de aislamiento

No se tocó `STEPS_DEMO_SYS`, ninguna otra sesión de Claude, ni bases
reales. Sin commit ni push.

## 10. Siguiente

Auditoría completa del backlog (`MATRIZ_REQUISITOS.md`) contra el estado
real de todos los cortes V2 A–F, luego Corte V2 G: puentes OT operacionales
verificables (`18.0.21.0.0`, condicionado a que la auditoría de addons
reales demuestre contratos suficientes).
