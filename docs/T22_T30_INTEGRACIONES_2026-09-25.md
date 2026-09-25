# T22 y T30 Integraciones verificadas en copia de Desarrollo

## Estado de la entrega

Código en `codex/t22-t30-integraciones`, worktree `Odoo-t22-t30`. La base de esta rama reúne, sin rediseñarlos, los módulos existentes de las ramas T25, T22 y T30. El commit de implementación siguiente contiene esta entrega.

Se ejecutaron 20 casos funcionales de Odoo 18 en `CODEX_T22_T30_20260925`, copia aislada de LAB_TAREAS con crons y servidores de correo desactivados. Resultado final: 0 fallos y 0 errores. No se actualizaron LAB_TAREAS, demo-sys ni SyS. La preparación del despliegue a Desarrollo fue rechazada por la revisión automática de aprobación con «blocked by policy», sin motivo más específico. No se intentó eludir el bloqueo.

## T25 aprobado

Fernando confirmó en esta conversación que T25 está aprobado. Se considera aceptada la entrega de Guías sin CAF, con proveedor DTE tercero. No se interpreta como aprobación de los nuevos cambios de T22/T30 ni como un despliegue ya realizado. El estado de Helpdesk no fue modificado ni se enviaron mensajes al cliente.

## T22

- `step_inventory_fruit_tag` 18.0.1.1.0 corrige kilos: las unidades de peso se convierten a kg; cajas/unidades se convierten primero a la unidad base del producto y luego se multiplican por su peso. Incluye migración para recalcular los kilos almacenados de los paquetes existentes.
- `step_inventory_dispatch` añade selección de una OP autorizada de la misma empresa, conserva su folio y lleva empresa, dirección de origen, referencias OP/OT y kilos a la guía.
- En salidas terminadas usa cantidad efectivamente entregada, no la demanda inicial. Rechaza operaciones canceladas o sin cantidades despachables.
- `step_inventory_harvest` propaga la OP seleccionada y la OT de Cosecha a la recepción de Inventario. Conserva el proceso existente de revisión y validación de Bodega.
- Se conservaron las referencias OP/OT de texto por compatibilidad con movimientos históricos.

Pendientes del alcance completo de T22: variantes de producto (el documento original las marca pendientes), panel de entrada, y completar/revalidar los puentes de consumo de BPA/Maquinaria. Estos dos puentes existen en otras ramas y Desarrollo; no fueron modificados ni se da por completada su integración mediante esta entrega. El puente de Cosecha cubre el flujo contratista que ya admite el módulo existente; no añade recepción de cosecha propia.

## T30

- `step_purchase_contract_account` añade diario, fecha contable y distribución analítica al contrato. El Debe usa la cuenta de gastos del producto o su categoría; el Haber usa la nueva cuenta de provisión del diario. No se fijan cuentas numéricas ni se crean cuentas reales.
- Botón Contabilizar contrato para usuarios de Contabilidad. Exige contrato confirmado vigente, cuotas aprobadas, moneda compatible y configuración completa. Crea un asiento por cuota con proveedor, vencimiento, moneda y distribución analítica. El bloqueo de fila del contrato evita contabilizaciones concurrentes duplicadas.
- Las cuotas contabilizadas conservan su comprobante; cantidades, producto, precio, unidad y vencimiento quedan protegidos. Un contrato con pagos pendientes no se cierra desde la acción Cerrar.
- Al revisar condiciones, las cuotas sin pagos procesados se reversan y pasan a una nueva versión. Las cuotas con pagos, incluso parciales, permanecen en la versión original con su saldo pendiente; no se alteran sus pagos ni se genera una segunda obligación por ellas.
- Los pagos de proveedor pueden vincularse a una cuota. Se valida empresa, proveedor, moneda, sentido del pago y exceso de importe. Pagos en proceso o pagados reducen la previsión pendiente; borradores, cancelados y rechazados no la reducen.
- Compras permite referenciar un contrato; valida proveedor/moneda y exige contrato confirmado vigente al confirmar la compra. La recepción muestra el contrato de la compra.
- `step_purchase_contract_treasury` agrega cuotas aprobadas/contabilizadas con saldo al concepto 22 de egresos, conservando fecha y moneda. Requiere que ese concepto esté configurado en la compañía. Usa el mecanismo existente de actualización de flujo para mantener identidad y trazabilidad.

No se automatizan pagos bancarios, compensación de anticipos contra facturas/órdenes de compra ni reversas parciales por cada pago. La reversa parcial al pagar sigue a cargo del contador, como indica el documento funcional. Las cuotas parcialmente pagadas se conservan en el contrato original; no se ofrece cambiar automáticamente su saldo dentro de una revisión. Las cuotas históricamente marcadas como contabilizadas sin comprobante requieren revisión/vinculación antes de revisar condiciones.

## Validación

Casos: asientos balanceados e idempotencia, configuración faltante, bloqueo de edición, reversas y nueva versión, proveedor incorrecto, moneda extranjera, estados contables sin comprobante, cierre con deuda, pago parcial y exceso de pago, concepto 22 y retiro de cuotas reversadas, tarjas existentes, toneladas/kg, cajas/peso, despacho parcial real y recepción de Cosecha con OT.

Log final local: `C:/Users/tito4/Documents/Odoo/output/t22-t30-final-tests.log`. Log remoto: `/tmp/codex_t22_t30_finaltest.log`. Hay un aviso previo de `steps_api` no cargado en la base original; no impidió cargar los módulos ni ejecutar los 20 casos. La migración de kilos está incluida, pero su ejecución desde la versión anterior debe comprobarse en la actualización de Desarrollo: la última prueba aislada ya partía de la versión nueva.

Los servicios `odoo18-dev` y `odoo18-demo-sys` continuaban activos al finalizar la verificación. La copia de pruebas y los módulos bajo `/tmp/codex_t22_t30_20260925` quedan disponibles para continuar; no tienen un servicio persistente iniciado.
