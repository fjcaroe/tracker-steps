# Ticket #23 — BPA / Integración con Inventario (2026-09-12)

Ejecutado como **pedido/mejora** (no como incidencia), a solicitud explícita
del usuario en el chat, sobre el documento de diseño adjunto al ticket
("1.2.1 BPA integración con Inventario").

## Qué pide el ticket

Cuando una OT-BPA de Aplicación foliar (`x_aplicacion_foliar`) se costea,
generar un movimiento de Inventario: salida desde "Bodega BPA" con los
productos y cantidades de la hoja "Consumo productos", referenciando la
OT-BPA.

## Relación con trabajo previo ya documentado

Este ticket toca el mismo modelo (`x_aplicacion_foliar`) que
`docs/gestion_costos/HANDOFF_V2_CORTE_G.md` §3.7 identificó como "el único
candidato viable" para un puente distinto (Orden de Producción → OT-BPA,
de planificación a ejecución) — **no es el mismo puente**: aquel bridgea
*planificación → ejecución*; este ticket pide *ejecución → Inventario*.
Pero comparten el mismo riesgo de fondo, ya señalado en ese documento:
`x_aplicacion_foliar` **no tiene estado de anulación** (`status1` →
`status2` → `status3` → `Contabilizado`, sin `cancel`). Ese documento dejaba
pendientes, sin resolver unilateralmente, exactamente las dos decisiones
que este ticket también necesita:

1. **¿Automático o manual?** → Igual que ahí: se implementó como **botón
   manual** (`action_generate_inventory_move`), nunca automático al
   costear.
2. **¿Dependencia dura o lectura defensiva de `step_bpa_irrigation`?** → Se
   optó por **dependencia dura** (`depends: ["step_bpa_irrigation", ...]`,
   `_inherit = "x_aplicacion_foliar"` sin guardas), siguiendo el precedente
   más reciente citado en ese mismo documento
   (`step_bpa_irrigation/models/machinery_integration.py`, del mismo autor,
   que ya usa dependencia dura en vez de lectura defensiva).

Estas dos decisiones estaban explícitamente marcadas como "no me corresponde
tomar unilateralmente" en el corte de auditoría anterior; se tomaron ahora
porque el usuario pidió ejecutar este ticket directamente en el chat.

## Módulo nuevo: `step_bpa_inventory`

Puente nuevo (no se modificó `step_bpa_irrigation`), depende de
`step_bpa_irrigation` y `stock`.

- **Modelo nuevo `step.bpa.inventory.consumption.line`**: la "hoja Consumo
  productos" que pide el ticket no existe hoy en `x_aplicacion_foliar`
  (sólo hay un campo agregado `x_studio_costo_de_productos`, sin detalle por
  producto) — se agregó como línea editable (producto, cantidad, UdM) en
  vez de inventar un reparto automático desde el monto agregado.
- **Campo `inventory_picking_id`** en `x_aplicacion_foliar`: idempotencia —
  si ya existe, el botón reabre el mismo movimiento en vez de duplicarlo.
- **Botón `action_generate_inventory_move`**: visible en `status3`
  ("Costeado") y `Contabilizado`; exige al menos una línea de consumo;
  crea una transferencia interna desde "BPA/Stock" hacia
  "BPA/Producción" (ubicación virtual propia con `usage=production`), con
  `origin` = número de OT-BPA. Se usa una ubicación propia porque Odoo 18
  crea sus ubicaciones de producción por empresa sin un XML ID estable.
- El picking **no se auto-valida** (queda confirmado, no "Hecho"): el
  equipo de bodega lo valida como cualquier transferencia normal, lo que
  permite cancelarlo con las herramientas estándar de Inventario si el
  mapeo resultó incorrecto — mitiga la falta de estado de anulación en el
  origen.
- **Tipo de operación:** igual que en el Ticket #24 (Maquinaria), se creó
  un `stock.picking.type` propio ("Consumo BPA") en vez de reutilizar
  "Orden de entrega" (que en Odoo apunta a un cliente) — **pendiente de
  confirmación funcional**.

## Pruebas agregadas

`tests/test_bpa_inventory_bridge.py` (4 casos, sigue el patrón de
`step_bpa_irrigation/tests/test_machinery_naming.py`):
- genera el picking con las líneas correctas (producto, cantidad,
  ubicación) y enlaza cada línea de consumo con su `stock.move`;
- pulsar el botón dos veces no duplica el picking;
- exige estado `status3`/`Contabilizado` antes de generar;
- exige al menos una línea de consumo de productos.

Se instaló y ejecutó contra Odoo 18 Enterprise en la base temporal aislada
`TICKET23_VALID_20260912`: **4 casos, 0 fallos, 0 errores**. La primera
instalación detectó que `stock.location_production` no existe como XML ID en
Odoo 18; se corrigió creando la ubicación virtual propia descrita arriba y
se repitió la instalación completa con resultado satisfactorio. También
pasaron `python -m compileall` y el parseo de los XML. No se desplegó en
`demo-sys`/`desarrollo` ni se tocaron datos compartidos.

## Pendiente / requiere confirmación funcional

- Confirmar si el tipo de operación debe ser "Orden de entrega" real en vez
  de la transferencia interna dedicada.
- Confirmar si el picking debe auto-validarse al generarse.
- Evaluar si conviene, más adelante, prellenar `consumption_line_ids` desde
  algún registro de aplicación de productos existente en vez de que el
  usuario los tipee a mano (hoy no hay ese detalle en ningún lado del
  ecosistema auditado — ver Corte V2 G).
- Desplegar el módulo en `desarrollo`/`demo-sys`, correr las pruebas y
  ejercer el botón con datos reales para confirmar el resultado contra lo
  que espera el cliente.
