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

## Validaciones de campo separadas en T45

- [T45](https://soporte.stepsapp.cl/helpdesk/ticket/45) conserva la homologación de perfiles con marcas/modelos reales al conocer sus tramas y probar la captura en navegador con cada equipo. El software admite BLE GATT y Bluetooth SPP por puerto serie, no promete leer protocolos binarios cerrados sin adaptador.
- T45 también conserva el piloto de recepción con usuarios y datos representativos antes de declarar operativa la captura física. Desarrollo es el ambiente solicitado para esas pruebas; SyS no forma parte de esta entrega.

No se instaló en SyS. El 01-10-2026 el cliente propuso cerrar el desarrollo de T40 y abrir un ticket separado para la prueba de balanzas; se creó T45 para conservar esa validación.

## Revisión del 01-10-2026 de los puntos indicados por el cliente

El comentario del cliente del 01-10 señala que no encuentra todos los avances en QA y aclara que repaletizaje y conversión C→E ya están desarrollados en Packing. Revisamos el código instalado en Desarrollo y las pruebas de ambos módulos. El servicio `odoo18-dev` está activo; `https://desarrollo.stepsapp.cl/web/login` responde HTTP 200. En `LAB_TAREAS` están instalados `step_inventory_packing` y `step_packing_operations`, ambos versión `18.0.1.0.0`. Las pruebas de Packing del servidor contienen los tres casos citados abajo.

| Flujo | Evidencia de QA aislada | En Desarrollo | Paso para revisión funcional |
| --- | --- | --- | --- |
| Recepción de fruta embalada y tarja E | `test_reception_validates_stock_and_tag_detail`: valida el picking nativo y comprueba stock, productor, temporada, especie y 50 kg en la tarja | Packing Fruta → Recepciones → Fruta embalada | Validar una recepción de prueba y consultar el paquete resultante. |
| Tarjas y composición por productor | `test_package_state_and_producer_detail`: valida estado, kilos y SDP; `test_excel_import_creates_tags_without_validating_stock`: comprueba que la importación no valida movimientos por sí sola | Packing Fruta → Tarjas de fruta | Abrir una tarja y comprobar productor, kilos, especie y estado. |
| Envases de cosecha | `test_container_issue_and_return_use_stock_moves`: entrega tres unidades y devuelve dos con saldos de Inventario; `test_opening_balance_creates_inventory_adjustment`: comprueba inventario inicial | Packing Fruta → Operaciones → Entregas y devoluciones de envases; Inventario inicial de envases | Registrar entrega y devolución de prueba con un productor. |
| Perfil de balanza | `test_scale_profile_requires_valid_transport_and_pattern`: comprueba protocolo, patrón y rechazos de configuración inválida | Packing Fruta → Operaciones → Perfiles de balanza | Probar la captura con marca, modelo y trama reales; la prueba automatizada no homologa el equipo físico. |
| Conversión C→E en fabricación | `step_packing_operations` / `test_manufacturing_close_checks_real_packages`: consume una tarja C de 100 kg en una OT nativa, produce una tarja E de 80 kg y confirma el movimiento del producto terminado al paquete E | Packing Fruta → Planificación → Órdenes de proceso → Orden de trabajo | Repetir con productos, lista de materiales y tarjas del cliente. La merma del ejemplo es 20 kg. |
| Repaletizaje simple y mixto | `test_repack_moves_quant_between_packages`: traslada existencias entre paquetes y cambia sus estados; `test_repack_mixed_target_keeps_producer_detail`: conserva 15 cajas y los dos productores en la tarja mixta | Packing Fruta → Operaciones → Repaletizado | Probar un caso de cada tipo con paquetes de prueba. |

Las siete pruebas de `step_inventory_packing` y las ocho pruebas de `step_packing_operations` pasaron en las copias aisladas documentadas en los registros de T40 y [T41](T41_PACKING_OPERACIONES_2026-09.md). No se ejecutaron pruebas nuevas en producción ni se generaron registros sintéticos allí. Los dos flujos de Packing dejan de figurar como trabajo técnico pendiente para T40. La homologación física de balanza y la validación del flujo con datos y usuarios del cliente se siguen en T45. SyS no se modificó.

## Uso de la balanza

1. Un administrador de Inventario crea un perfil por familia/modelo en Packing Fruta → Operaciones → Perfiles de balanza. Para BLE introduce UUID de servicio y característica; para Bluetooth Classic SPP empareja el equipo con el PC y configura baudios. RFCOMM no estándar permite indicar su UUID de servicio. El patrón debe capturar solo una lectura estable y completa en su primer grupo; el multiplicador convierte la unidad recibida a kg.
2. En una recepción el operador selecciona «Balanza» y el perfil. «Leer balanza» solicita permiso al navegador y registra la lectura en el peso bruto o el destare seleccionado. El mismo control aparece en cada línea de tarja para pesaje por unidad de traslado.
3. Se requiere HTTPS y un navegador compatible. BLE usa Web Bluetooth; Bluetooth Classic SPP usa Web Serial en Chrome de escritorio. Si el equipo no está homologado, se mantiene «Manual» hasta obtener una trama de muestra y probar la lectura física.
