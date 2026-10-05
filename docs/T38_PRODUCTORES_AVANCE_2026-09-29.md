# T38 — Productores (2026-09-29)

## Actualización de integración, 05-10-2026

El consolidado de temporada, sus filtros, generación masiva y PDF ya están
implementados para QA en `step_producers` 18.0.1.6.0. Agrupan liquidaciones
completas y validadas sin duplicar documentos contables; la confirmación
conserva la selección y bloquea su reapertura individual. Ver el
[acta de integración y prueba funcional](QA_PACKING_PRODUCTORES_EXPORTACIONES_2026-10-05.md).
Los pendientes y resultados de septiembre que siguen abajo son históricos.
La aceptación con un caso real y la migración arquitectónica Fase B siguen
separadas de esta entrega.

## Implementado

- `step_producers` existente en T35 conserva productores, fundos, estimaciones, tarifas y liquidaciones. Se integraron los contratos de T30 al módulo.
- Lista de precios de preliquidación por temporada, especie, variedad, vigencia y selectores comerciales; rechaza empates y variedades de otra especie.
- `step_producer_fruit_flow` calcula kilos recibidos, saldo por entregar y exceso de la estimación desde recepciones validadas de T40. Permite cerrar la entrega sin modificar kilos de una versión vigente.
- Navegación desde Productores hacia cuenta corriente, recepciones, packing, embarques y tarjas liquidadas.
- Liquidación del recibidor reparte FOB y kilos medidos de una tarja mixta entre productores. La liquidación del productor usa estados visibles Generada, Validada, Entregada y Cerrada. Se contabiliza al pasar a Entregada, según respuesta del usuario.
- Las liquidaciones nuevas trasladan el FOB asignado al productor (100 % por defecto, ajustable entre 0 y 100 %). Las existentes conservan el cálculo histórico por tarifa al actualizar el módulo. Se bloquea la modalidad y el porcentaje una vez validada la liquidación.
- Informe PDF imprimible de liquidación del productor con identificación, tarjas, kilos, FOB, retornos, descuentos, facturación previa, ajuste documental y firmas. El informe de embarque muestra cada productor y sus kilos medidos en tarjas mixtas.
- Modalidad de precio por productor o pool dentro de cada liquidación del recibidor; el pool agrupa variedad, semana, transporte, tipo de pallet, calibre, categoría y tipo de fruta.
- Simulación de preliquidación por fruta pendiente, por embalar, por exportar, exportada y liquidada. Toma precio por kg de la lista de preliquidación, gasto USD/kg confirmado en esa misma línea, FOB liquidado real cuando existe, saldo contable del productor y cuotas pendientes de contratos seleccionados. La simulación no genera asientos.

## Verificación

Base aislada `T40_QA_20260929T203507Z`, clonada de `LAB_TAREAS` en `odoo-new`.
Actualización de `step_export`, `step_producers` y `step_producer_fruit_flow` en la base aislada: 27 pruebas, cero fallos y cero errores (última ejecución 2026-09-30 01:32:56 UTC del reloj de la VM). Incluye reparto de FOB 60/40 de una tarja mixta, promedio pool, retorno al 100 % y 80 % del FOB, ciclo contable de liquidación, render QWeb y ejemplo numérico de preliquidación (100 kg exportables × USD 5,5 menos USD 2,5/kg de gasto = USD 300). Se forzó la conversión PDF en una ejecución de QA; se generó un A4 de una página y se inspeccionó visualmente.

Rama: `codex/t38-producers-completion`.
PR borrador: https://github.com/fjcaroe/tracker-steps/pull/11

## Por cerrar

- Confirmar funcionalmente la fuente del gasto unitario de preliquidación. Se asumió que se configura y confirma en la lista de precios; el cálculo se bloquea cuando falta esa confirmación.
- El documento actual se genera por productor y liquidación de recibidor. Falta consolidar toda la temporada por productor, aplicar filtros de fecha, tipo de embarque, variedad y embarques, y generar las liquidaciones masivamente desde esa selección. El PDF actual cubre el documento individual de esa liquidación; el formato estacional final debe revisarse con un caso real.
- Validación funcional/contable con un caso real antes de instalar en SyS.

No se instaló en SyS ni se cerró el ticket.

## Incidencia de contrato en Demo-SyS, 01-10-2026

Durante la revisión del ciclo de contrato, `CTR/2026/00002` fue rechazado al intentar contabilizar porque la cuenta de cargo `410235`, tomada de la categoría del producto, no está permitida en el diario `CTOP`. La corrección de T30 permite que Contabilidad ajuste la cuenta de cargo antes del asiento y muestra las cuentas restringidas; quedó instalada y probada en Demo-SyS. Se incorporó también a esta rama de T38 para preservar el arreglo en una futura entrega de Productores. El diagnóstico, respaldo, nueve pruebas y reproducción sobre copia aislada constan en [el acta de T30](T30_REVISION_PRODUCTORES_2026-09-28.md).

El contrato real sigue sin asiento y no se modificaron sus cuentas ni las del diario. La elección de la cuenta de cargo es una decisión contable; la prueba aislada con `110331` acreditó el funcionamiento técnico, no su autorización para el caso real.
