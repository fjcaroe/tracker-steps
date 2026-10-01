# T30 · Revisión de contratos de compra en Productores

## Solicitud recibida

El cliente adjuntó al ticket 30 el archivo **“2.5 Módulo Compras, anticipo contrato, modificación .docx”** (adjunto 3105, 28-09-2026). Pidió separar productos y cuotas, mostrar cuatro hojas —Productos, Calendario de pago, Notas y Contabilización— y trasladar el flujo desde Gestión y Costos al módulo Productores.

La especificación original del mismo ticket (adjunto 2962) indica productos, cantidades ordenadas, distribución analítica, cuotas, versiones y provisión contable. La revisión conserva esos datos y cambia su organización.

## Implementación

- Nuevo menú **Productores → Contratos de compra** y formulario con las cuatro pestañas solicitadas. El menú anterior de Gestión y Costos se desactiva durante la actualización.
- Productos contratados con cantidad, cantidad ordenada tomada de órdenes de compra confirmadas, unidad, precio, neto, cuenta de cargo y distribución analítica. La orden de compra puede vincularse al contrato y a cada producto.
- Calendario de cuotas con vencimiento, cantidad, neto, criterio de validación y estados Creado, Aprobado y Contabilizado. La confirmación exige que las cantidades y netos programados coincidan con los productos.
- Revisiones numeradas: conservan las cuotas ya contabilizadas y trasladan sólo las pendientes a una nueva versión. Los contratos previos del módulo antiguo se copian, preservando folio, productor, versión y cuotas; la migración puede repetirse sin duplicar registros.
- Contabilización explícita por un usuario contable: cargo por producto y abono a provisión, con productor, distribución analítica, moneda y tipo de cambio de Odoo. No se publica asiento al confirmar el contrato. El contador vincula los asientos de pago y reversa de cada cuota; para publicar la provisión de una revisión de un contrato ya contabilizado debe vincular primero una reversa publicada de la parte pendiente.
- Los campos contables y las transiciones de estado quedan protegidos por permisos y acciones del flujo.

## Validación

Se restauró una copia aislada de `STEPS_DEMO_SYS` en `T30_REVIEW_20260929`, con archivos del módulo separados. Se creó en esa copia un contrato del flujo anterior para verificar la migración; migró una vez, sin duplicación. También se probaron en la copia la confirmación de cantidades y netos, revisión de cuotas, asiento equilibrado por un usuario contable, vínculo con compras confirmadas y vistas. La suite del módulo terminó con **8 pruebas, 0 fallas y 0 errores** (`/tmp/t30_review_tests5.log`). Los asientos y cuentas sintéticas sólo existen en la copia aislada.

En Demo-SyS se respaldó la base y el módulo en `/opt/demosys_odoo18/backups/t30_demo_backup_20260929`, se actualizó `step_producers` a `18.0.1.1.0` y se verificó: servicio activo, HTTP 200 local y público, menú nuevo activo (acción 1918), menú antiguo inactivo, cuatro pestañas presentes y **0 contratos** existentes. Acceso: [Contratos de compra en Demo-SyS](https://demo-sys.stepsapp.cl/odoo/action-1918).

## Configuración y validación del cliente

En cada contrato, el responsable define productor, productos, cantidades, precio y vencimientos. Antes de contabilizar, Contabilidad revisa la cuenta de cargo por producto, el diario de contrato, la cuenta de provisión y, si corresponde, la distribución analítica. No se asignaron cuentas ni diario por defecto en Demo-SyS porque esa empresa aún no tiene los códigos del ejemplo del documento (110331 y 210331); forzarlos implicaría contabilizar en cuentas no validadas.

La versión original menciona el concepto 22 del flujo de caja. Tesorería ya recoge órdenes de compra confirmadas mediante su hoja de Órdenes de compra, pero Demo-SyS no tiene ese concepto configurado; esta entrega no crea un concepto 22 ni asigna automáticamente cuotas de contrato a Tesorería. Contabilidad debe indicar qué concepto y tratamiento de pagos/reversas corresponde antes de automatizar ese tramo.

**Pendiente:** el cliente valida el flujo en Demo-SyS y confirma el diario, cuentas y criterio de reversa y concepto de Tesorería para su empresa. La instancia SyS no se modificó, de acuerdo con el acuerdo del ticket de revisar primero en Demo-SyS.

## Corrección del rechazo contable del 01-10-2026

El cliente intentó contabilizar `CTR/2026/00002` en Demo-SyS y Odoo rechazó la cuenta `410235` (Costo de Mercaderías Vendidas). La inspección de solo lectura mostró que esa cuenta fue heredada por la línea desde la categoría del producto «Cereza Expor». El diario `CTOP` (Contrato Productor) tiene `110331` (Contrato productores) como cuenta predeterminada y `210299` (Contrato fruta x pagar) como cuenta de provisión; su lista de cuentas permitidas contiene solo `210299`. Por ello el intento no produjo asiento. El contrato anterior `CTR/2026/00001` tampoco tiene asiento.

La corrección `3cfcd1a` permite a un usuario de Contabilidad modificar la cuenta de cargo de un contrato confirmado **antes** de contabilizarlo; conserva inmutables producto, cantidad, precio y cuenta después de publicar el asiento. En la pestaña Contabilización se muestran las cuentas por producto. Una validación anticipada enumera las cuentas que el diario restringe y dirige al ajuste de cuentas permitidas, sin cambiarlas automáticamente.

En la copia aislada `T30_CONTRACT_ACCOUNT_QA_20261001`, clonada de `STEPS_DEMO_SYS`, la actualización pasó 9 pruebas del módulo, 0 fallos y 0 errores. Se reprodujo el rechazo real del contrato `CTR/2026/00002`; solo en esa copia se simuló cambiar el cargo a `110331` y permitir esa cuenta en `CTOP`: se publicó un asiento equilibrado de dos líneas y se descartó con `rollback` al terminar. La simulación demuestra viabilidad técnica, **no aprueba la cuenta contable**.

En Demo-SyS se respaldaron base y módulo en `/opt/demosys_odoo18/backups/t30_contract_account_fix_20261001T145855Z`, se actualizó `step_producers` a `18.0.1.1.1` y el servicio quedó activo. La URL del formulario responde HTTP 200. Los contratos `CTR/2026/00001` y `CTR/2026/00002` siguen sin asiento y sus cuentas no se modificaron. Falta que Contabilidad confirme la cuenta de cargo del contrato y autorice incluirla en las cuentas permitidas del diario antes de contabilizar la versión vigente.
