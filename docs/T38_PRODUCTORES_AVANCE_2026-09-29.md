# T38 — Productores (2026-09-29)

## Implementado

- `step_producers` existente en T35 conserva productores, fundos, estimaciones, tarifas y liquidaciones. Se integraron los contratos de T30 al módulo.
- Lista de precios de preliquidación por temporada, especie, variedad, vigencia y selectores comerciales; rechaza empates y variedades de otra especie.
- `step_producer_fruit_flow` calcula kilos recibidos, saldo por entregar y exceso de la estimación desde recepciones validadas de T40. Permite cerrar la entrega sin modificar kilos de una versión vigente.
- Navegación desde Productores hacia cuenta corriente, recepciones, packing, embarques y tarjas liquidadas.
- Liquidación del recibidor reparte FOB y kilos medidos de una tarja mixta entre productores. La liquidación del productor usa estados visibles Generada, Validada, Entregada y Cerrada. Se contabiliza al pasar a Entregada, según respuesta del usuario.

## Verificación

Base aislada `T40_QA_20260929T203507Z`, clonada de `LAB_TAREAS` en `odoo-new`.
Actualización de `step_export`, `step_producers` y `step_producer_fruit_flow` el 2026-09-29 21:13:39 UTC: 26 pruebas, cero fallos y cero errores. Incluye reparto de FOB 60/40 de una tarja mixta y ciclo contable de liquidación.

Rama: `codex/t38-producers-completion`.
PR borrador: https://github.com/fjcaroe/tracker-steps/pull/11

## Por cerrar

- Simulación de preliquidación completa con gastos unitarios, anticipos y cinco etapas de fruta.
- Modalidad de precio pool, filtros de liquidación masiva y PDF formal.
- Validación funcional/contable con un caso real antes de instalar en SyS.

No se instaló en SyS ni se cerró el ticket.
