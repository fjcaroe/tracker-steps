# Handoff — Corte V2 C (comprometido de compras y cantidad neta por comprar)

**Addon:** `step_management_costs` · **De:** `18.0.16.0.0` → **A:** `18.0.17.0.0`
**Fecha:** 2026-09-07 · **Autor:** Claude Sonnet 5 · **Estado:** implementado
y verificado en Odoo real, sin despliegue

## 1. Alcance

Tercer corte de `PROMPT_CLAUDE_SONNET5_RESPUESTAS_V2_2026-09-06.md`. Auditó
primero los modelos reales instalados en `LAB_TAREAS` (`purchase` 18.0.1.2,
`account_budget` 18.0.1.0) antes de implementar.

- **Nueva dependencia del manifiesto:** `purchase` (mismo criterio que
  `stock` — módulo estándar de Odoo, no un puente agrícola).
- `models/stock_requirement.py::_committed_quantity()`: lee
  `purchase.order.line` confirmadas (`state='purchase'`) con
  `product_qty - qty_invoiced > 0`, convertida a la UdM del producto,
  devolviendo también las líneas que componen el total (trazabilidad).
- `step.management.stock.requirement.line` gana `committed_quantity`
  (informativo, misma foto para todos los períodos del producto),
  `net_to_buy` (faltante acumulado menos lo comprometido, ambos consumidos
  una sola vez a través de los períodos — primero stock, después lo
  comprometido) y `committed_purchase_line_ids` (M2m, trazabilidad).
- **Sin doble conteo:** con `availability_metric='forecasted'`, `net_to_buy`
  no vuelve a descontar lo comprometido (`virtual_available` ya lo incluye
  como entrada prevista); con `on_hand`/`free` sí se descuenta.
- No se crean solicitudes de cotización ni OC automáticamente; lectura
  agregada de sólo consulta (`sudo()`).

## 2. Seguridad

- Sin ACL nuevas (no hay modelos nuevos): `committed_purchase_line_ids` es
  un M2m de sólo lectura a `purchase.order.line`, poblado por
  `action_compute()` con `sudo()` — el rol de Gestión y Costos no necesita
  acceso directo a Compras para ver el comprometido consolidado.
- `_check_company_auto`/reglas existentes de `stock.requirement(.line)` sin
  cambios; el comprometido se calcula siempre acotado a
  `requirement.company_id`.

## 3. Interfaz

- Lista de `stock.requirement.line`: columnas nuevas «Comprometido» y «Neto
  por comprar» (con `decoration-danger`), y la trazabilidad a líneas de
  compra como columna opcional oculta por defecto.

## 4. Migración

- Manifiesto `18.0.17.0.0`. `upgrades/18.0.17.0.0/post-migration.py`:
  preflight de sólo lectura (cuenta documentos ya calculados; los campos
  nuevos quedan en 0 hasta el próximo «Calcular», sin backfill).

## 5. Pruebas

`tests/test_v2_c_committed.py` (12 pruebas nuevas): OC borrador excluida,
confirmada incluida, cancelada excluida, parcialmente facturada (sólo el
remanente), totalmente facturada excluida, UdM convertida antes de sumar
(2 docenas → 24 unidades), dos compañías no mezcladas, trazabilidad a las
líneas de compra, `net_to_buy` consumiendo lo comprometido una sola vez a
través de dos períodos (stock cubre el primero, lo comprometido cubre parte
del segundo), métrica «forecasted» sin doble descuento, y permisos —
`group_management_user` calcula el comprometido sin necesitar acceso amplio
a Compras (`sudo()` interno).

### Verificación local

- `py_compile`, parseo de los 30 XML, `git diff --check`: OK.

### Verificación Odoo real en `odoo-new` (sólo bases desechables)

Mismo patrón que los cortes anteriores. Se encontró y corrigió **una
suposición incorrecta en un test** (no un bug de la implementación): asumí
que una factura de proveedor en borrador no contaría hacia
`purchase.order.line.qty_invoiced` (campo núcleo de Odoo, no de este
addon). La verificación en Odoo real demostró que **sí cuenta desde que la
línea de factura se crea**, sin exigir que el documento esté validado. Se
corrigió el test para reflejar el comportamiento real verificado (no se
tocó `_committed_quantity()`, que simplemente lee ese campo tal cual —
correcto, ya que reinterpretar un campo núcleo de Compras estaría fuera de
mandato de este addon).

| Escenario | Resultado |
|---|---|
| Upgrade de clon de `LAB_TAREAS` (`18.0.4.0.0` → `18.0.17.0.0`) | RC 0 · **0 failed, 0 error(s) de 246 tests** (`odoo.tests.stats`: 288 tests, 247.3s, 92012 queries) |
| Instalación limpia sin demo (`--without-demo=all`) | RC 0 · **0 failed, 0 error(s) de 246 tests** (`odoo.tests.stats`: 288 tests, 79.1s, 45075 queries) |

246 = 234 (V2 B) + 12 (V2 C) — exacto 1:1 con los métodos `test_*` nuevos.
La discrepancia `stats` (288) vs `result` (246) es la misma naturaleza
heredada, no bloqueante.

Bases (`MC_V2C_UPG`, `MC_V2C_CLEAN`), dump de `LAB_TAREAS`, directorio
temporal y scripts desechables eliminados al terminar. `LAB_TAREAS` no se
tocó.

## 6. Decisiones y supuestos

Ver `DECISION_LOG.md` §"Corte V2 C" (D-M) y `ADR_001` §D-M.

## 7. Pendientes del cliente

Sin cambios respecto a los cortes anteriores (K3, H1, K5, D20, BPA-Riego,
usuarios reales/UAT).

## 8. Confirmación de aislamiento

No se tocó `STEPS_DEMO_SYS`, ninguna otra sesión de Claude, ni bases reales.
Sin commit ni push.

## 9. Siguiente

Auditoría del backlog completo de `MATRIZ_REQUISITOS.md`, luego Corte V2 D:
maestros agrícolas y estimación desde fuentes reales (`18.0.18.0.0`).
