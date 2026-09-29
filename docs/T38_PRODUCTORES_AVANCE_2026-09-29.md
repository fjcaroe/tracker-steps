# T38 — Productores (2026-09-29)

## Implementado

- `step_producers` existente en T35 conserva productores, fundos, estimaciones, tarifas y liquidaciones. Se integraron los contratos de T30 al módulo.
- Lista de precios de preliquidación por temporada, especie, variedad, vigencia y selectores comerciales; rechaza empates y variedades de otra especie.
- `step_producer_fruit_flow` calcula kilos recibidos, saldo por entregar y exceso de la estimación desde recepciones validadas de T40. Permite cerrar la entrega sin modificar kilos de una versión vigente.
- Navegación desde Productores hacia cuenta corriente, recepciones, packing, embarques y tarjas liquidadas.
- Liquidación del recibidor reparte FOB y kilos medidos de una tarja mixta entre productores. La liquidación del productor usa estados visibles Generada, Validada, Entregada y Cerrada. Se contabiliza al pasar a Entregada, según respuesta del usuario.
- Modalidad de precio por productor o pool dentro de cada liquidación del recibidor; el pool agrupa variedad, semana, transporte, tipo de pallet, calibre, categoría y tipo de fruta.
- Simulación de preliquidación por fruta pendiente, por embalar, por exportar, exportada y liquidada. Toma precio por kg de la lista de preliquidación, gasto USD/kg confirmado en esa misma línea, FOB liquidado real cuando existe, saldo contable del productor y cuotas pendientes de contratos seleccionados. La simulación no genera asientos.

## Verificación

Base aislada `T40_QA_20260929T203507Z`, clonada de `LAB_TAREAS` en `odoo-new`.
Actualización de `step_export`, `step_producers` y `step_producer_fruit_flow` el 2026-09-29 21:30:44 UTC: 27 pruebas, cero fallos y cero errores. Incluye reparto de FOB 60/40 de una tarja mixta, promedio pool, ciclo contable de liquidación y ejemplo numérico de preliquidación (100 kg exportables × USD 5,5 menos USD 2,5/kg de gasto = USD 300).

Rama: `codex/t38-producers-completion`.
PR borrador: https://github.com/fjcaroe/tracker-steps/pull/11

## Por cerrar

- Confirmar funcionalmente la fuente del gasto unitario de preliquidación. Se asumió que se configura y confirma en la lista de precios; el cálculo se bloquea cuando falta esa confirmación.
- Filtros de liquidación masiva y PDF formal.
- Validación funcional/contable con un caso real antes de instalar en SyS.

No se instaló en SyS ni se cerró el ticket.
