# Ticket #24 — Maquinaria / Integración con Inventario (2026-09-12)

Ejecutado como **pedido/mejora** (no como incidencia), a solicitud explícita
del usuario en el chat, sobre el documento de diseño adjunto al ticket
("2.1.3 Maquinaria integración con Inventario").

## Qué pide el ticket

Cuando una OT de Maquinaria (`step.hrs.machinery`) se costea, generar un
movimiento de Inventario por el combustible consumido: salida desde
"MQ/Stock", cantidad = litros de combustible de la línea, con referencia a
la OT y datos para distribución analítica (temporada/centro de
costos/actividad).

## Módulo nuevo: `step_machinery_inventory`

Puente nuevo (no se modificó `step_machinery`), depende de `step_machinery`
y `stock`. Sigue el patrón de puentes ya usado en el ecosistema
(`step_management_costs_machinery`, `step_management_costs_agriculture`):
un addon chico que sólo lee campos reales de otro módulo, nunca lo edita.

## Decisiones de diseño (explícitas, para revisión funcional)

1. **Botón manual, no automático.** `action_generate_inventory_move()` es un
   botón que el usuario dispara a propósito, visible cuando el estado es
   `costed`/`accounted`. No se generó automáticamente dentro de
   `action_cost()`. Motivo: es el mismo riesgo ya documentado para el
   puente BPA en `docs/gestion_costos/HANDOFF_V2_CORTE_G.md` §3.7 — más
   seguro que el usuario confirme antes de mover inventario real.
2. **Idempotencia por campo, no por búsqueda.** El campo
   `inventory_picking_id` en `step.hrs.machinery` guarda el picking ya
   creado; si ya existe, el botón sólo lo reabre — nunca duplica el
   movimiento aunque se pulse varias veces.
3. **Tipo de operación: transferencia interna dedicada, no "Orden de
   entrega".** El ticket dice literalmente "Orden de entrega", pero ese
   tipo de Odoo apunta por defecto a un cliente — este movimiento no es una
   venta. Se creó un `stock.picking.type` propio ("Consumo de Maquinaria",
   código `internal`) con origen fijo `MQ/Stock` y destino
   `MQ/Producción` (ubicaciones propias; la segunda tiene
   `usage=production`, porque Odoo 18 no expone un XML ID estable para la
   ubicación de producción por empresa). **Queda pendiente de confirmación
   funcional** si esto debe ser en cambio una Orden de entrega real
   (cliente ficticio "Consumo interno" o similar) — se optó por la opción
   más segura (no contamina el flujo de ventas) mientras se define.
4. **El picking no se valida automáticamente** (queda `confirmado`, no
   `hecho`): el equipo de bodega lo valida en Inventario como cualquier
   transferencia. Esto permite cancelarlo con las herramientas estándar de
   Odoo si el mapeo resultó incorrecto, mitigando que `x_aplicacion_foliar`
   (y aquí `step.hrs.machinery`) no siempre tengan un estado de reversa
   limpio.
5. **Distribución analítica:** no se intentó escribir
   `analytic_distribution` en el `stock.move` (Odoo no contabiliza
   analítica al mover inventario, sólo al costear/contabilizar, lo que ya
   hace `action_conta()` en `step_machinery`). En su lugar, el movimiento
   queda enlazado a `step_hrs_machinery_line_id`, desde donde se puede leer
   `cost_id` (centro de costos), `temp_id` (temporada) y `actividad_id`
   para cualquier reporte o extensión futura, sin duplicar ni inventar una
   distribución nueva.
6. **Producto de combustible:** se toma de `fleet.vehicle.step_product_id`
   (definido en `step_hr`, es un `product.template`) y se usa su
   `product_variant_id` para el movimiento. Si la maquinaria no tiene ese
   campo configurado, el botón no genera nada para esa línea y avisa con un
   `UserError` — no se inventa un producto por defecto.

## Pruebas agregadas

`tests/test_machinery_inventory_bridge.py` (4 casos, `TransactionCase`,
sigue el patrón de `step_machinery/tests/test_costing.py`):
- genera el picking con el movimiento correcto (producto, cantidad,
  ubicación, línea de origen);
- pulsar el botón dos veces no duplica el picking;
- exige estado `costed`/`accounted` antes de generar;
- exige al menos una línea con combustible y producto configurado.

Se instaló y ejecutó contra Odoo 18 Enterprise en la base temporal aislada
`TICKET24_VALID_20260912`: **4 casos, 0 fallos, 0 errores**. La validación
real detectó y permitió corregir la referencia inválida
`stock.location_production`; tras la corrección, la instalación y una
actualización posterior del módulo pasaron satisfactoriamente. También
pasaron `python -m compileall` y el parseo de los XML. No se desplegó en
`demo-sys`/`desarrollo` ni se tocaron datos compartidos.

## Pendiente / requiere confirmación funcional

- Confirmar si el tipo de operación debe ser "Orden de entrega" real (punto
  3) en vez de la transferencia interna dedicada que se construyó.
- Confirmar si el picking debe auto-validarse (marcar "Hecho") al generarse,
  o si el flujo manual de bodega (como quedó implementado) es el deseado.
- Desplegar el módulo en `desarrollo`/`demo-sys`, correr las pruebas y
  ejercer el botón con datos reales para confirmar el resultado contra lo
  que espera el cliente.
