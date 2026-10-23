# T40 — Inventario de fruta para Packing (2026-09-29)

## Implementado

- `step_inventory_packing` amplía la recepción nativa de Inventario para fruta a proceso y fruta embalada, con peso bruto, destares, kilos netos y detalle de tarjas.
- Importación XLSX de tarjas para preparar una recepción; la importación no valida ni crea movimientos de stock por sí sola.
- Tarjas C/E/N sobre `stock.quant.package`, con kilos medidos, productor, SDP, composición simple/mixta, estado y documentos de exportación.
- Al validar la recepción se comprueba que cada tarja sea el paquete resultante de un movimiento real. Se propagan fundo, temporada, especie y variedad al paquete; se crea el detalle por productor.
- Ubicación interna reutilizable para envases en poder del productor; saldo y movimientos son los de Inventario.
- Entrega y devolución de envases por productor mediante traslados nativos, vinculables a la recepción de fruta ya validada. Inventario inicial mediante ajuste nativo, solo para administradores de Inventario.
- Perfiles de balanza configurables por empresa: BLE GATT o puerto serie Bluetooth SPP/USB, UUID o baudios, patrón de trama y factor a kg. Captura desde navegador seguro para camión o cada tarja, con última trama y fecha; se conserva el ingreso manual.
- Exportaciones actualiza documentos y estado de las tarjas al despachar, embarcar, facturar y recibir liquidación.

## Verificación

Base aislada `T40_QA_20260929T203507Z`, clonada de `LAB_TAREAS` en `odoo-new`.
Última actualización: 2026-09-30 03:52 UTC, módulo cargado, siete pruebas, cero fallos y cero errores.
La prueba completa valida un `stock.picking` entrante con `stock.move` y `stock.move.line`, crea el quant, y comprueba productor, kilos y clasificación de la tarja.

Rama: `codex/t40-inventory-packing`.
PR borrador: https://github.com/fjcaroe/tracker-steps/pull/10

## Por cerrar

- Homologar perfiles con marcas/modelos reales al conocer sus tramas y probar la captura en navegador con cada equipo. El software admite BLE GATT y Bluetooth SPP por puerto serie, no promete leer protocolos binarios cerrados sin adaptador.
- Operación de repaletizaje y conversión C→E en el flujo real de Packing.
- Piloto funcional con usuarios y datos reales antes de instalar en SyS.

No se instaló en SyS ni se cerró el ticket.

## Uso de la balanza

1. Un administrador de Inventario crea un perfil por familia/modelo en Packing Fruta → Operaciones → Perfiles de balanza. Para BLE introduce UUID de servicio y característica; para Bluetooth Classic SPP empareja el equipo con el PC y configura baudios. RFCOMM no estándar permite indicar su UUID de servicio. El patrón debe capturar solo una lectura estable y completa en su primer grupo; el multiplicador convierte la unidad recibida a kg.
2. En una recepción el operador selecciona «Balanza» y el perfil. «Leer balanza» solicita permiso al navegador y registra la lectura en el peso bruto o el destare seleccionado. El mismo control aparece en cada línea de tarja para pesaje por unidad de traslado.
3. Se requiere HTTPS y un navegador compatible. BLE usa Web Bluetooth; Bluetooth Classic SPP usa Web Serial en Chrome de escritorio. Si el equipo no está homologado, se mantiene «Manual» hasta obtener una trama de muestra y probar la lectura física.
