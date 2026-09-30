# T40 — Inventario de fruta para Packing (2026-09-29)

## Implementado

- `step_inventory_packing` amplía la recepción nativa de Inventario para fruta a proceso y fruta embalada, con peso bruto, destares, kilos netos y detalle de tarjas.
- Importación XLSX de tarjas para preparar una recepción; la importación no valida ni crea movimientos de stock por sí sola.
- Tarjas C/E/N sobre `stock.quant.package`, con kilos medidos, productor, SDP, composición simple/mixta, estado y documentos de exportación.
- Al validar la recepción se comprueba que cada tarja sea el paquete resultante de un movimiento real. Se propagan fundo, temporada, especie y variedad al paquete; se crea el detalle por productor.
- Ubicación interna reutilizable para envases en poder del productor; saldo y movimientos son los de Inventario.
- Exportaciones actualiza documentos y estado de las tarjas al despachar, embarcar, facturar y recibir liquidación.

## Verificación

Base aislada `T40_QA_20260929T203507Z`, clonada de `LAB_TAREAS` en `odoo-new`.
Última actualización: 2026-09-29 21:16:46 UTC, módulo cargado, cuatro pruebas, cero fallos y cero errores.
La prueba completa valida un `stock.picking` entrante con `stock.move` y `stock.move.line`, crea el quant, y comprueba productor, kilos y clasificación de la tarja.

Rama: `codex/t40-inventory-packing`.
PR borrador: https://github.com/fjcaroe/tracker-steps/pull/10

## Por cerrar

- Integración con balanza Bluetooth y prueba con dispositivo físico.
- Operación de repaletizaje y conversión C→E en el flujo real de Packing.
- Piloto funcional con usuarios y datos reales antes de instalar en SyS.

No se instaló en SyS ni se cerró el ticket.
