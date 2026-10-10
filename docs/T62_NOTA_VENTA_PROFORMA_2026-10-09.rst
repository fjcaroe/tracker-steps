T62 - Nota de venta y Proforma de Cerro El Plomo
==============================================

Alcance y resultado
------------------

Se atendió la descripción del ticket y el comentario humano del 09-10-2026:
implementar Nota de venta y Proforma según el PDF adjunto. El nuevo módulo
step_sale_export_report 18.0.1.0.0 trabaja sobre sale.order; no crea documentos,
maestros ni reportes Studio paralelos. La activación automática del formato
estándar se limita a Cerro El Plomo SpA, empresa del adjunto. Las otras empresas
conservan su formato estándar. En Desarrollo se activa en su empresa principal
para permitir la revisión funcional, sin copiar registros de Cerro.

El documento incluye logo/domicilio/RUT de la empresa del pedido, cliente,
fecha, Incoterm nativo, embarque relacionado, número de pedido, kilos y cajas
por línea, precios, descuentos, observaciones e instrucciones de transferencia.
Mantiene la numeración nativa: no inventa una secuencia comercial separada.
La dirección se obtiene del ERP; no reemplaza el domicilio vigente por el
que aparece en el ejemplo adjunto.

Flete y Seguro son tipos de línea del pedido, no cargos sumados fuera de Odoo.
El desglose concilia con amount_untaxed, amount_tax y amount_total. La cantidad
comercial y unidad también se muestran para explicar el precio unitario.
Kilos y cajas son cantidades explícitas del documento; no se supone que cada
unidad sea una caja ni se reparte el peso de un embarque entre productos.

Cuenta, titular y SWIFT se leen del maestro bancario de la empresa. ABA se
configura en el banco nativo. Se rechaza seleccionar la cuenta de otro titular
o de otra empresa. El adjunto deja los identificadores bancarios vacíos y
menciona AVOS AMERICA INC sin aclarar su rol. No se seleccionó una cuenta real:
queda pendiente confirmar la instrucción de pago y configurar la cuenta.
El reporte informa esa ausencia; no imprime los datos sintéticos del ensayo.
La firma solo aparece cuando existe una firma real del pedido; no se copia
el sello/firma del ejemplo como si autorizara todos los documentos.

Uso
---

1. Seleccionar Cerro El Plomo SpA.
2. Exportaciones / Embarque / Notas de venta y proformas, o el pedido de Ventas.
3. Completar Kilos, Cajas y Detalle en Proforma por línea. Usar los productos
   habituales y registrar Flete/Seguro como líneas comerciales.
4. Imprimir Nota de venta - formato exportación o Proforma - formato exportación.
   Proforma respeta el grupo nativo de impresión de proformas.
5. En Ajustes / Empresas / Nota de venta / Proforma, seleccionar la cuenta
   aprobada. BIC/SWIFT y ABA se mantienen en su banco relacionado.

Pruebas y publicación
---------------------

Paquete inmutable del commit ade6e0a2ec064a55643727b20913bc737d470444,
SHA256 c6f8634c2c076e9991ddcab1867daec304343101c8d0fb979d462d34cb111155.
Las correcciones posteriores del publicador y exportador de evidencias no
modifican los nueve archivos del módulo de ese paquete.

MANAGEMENT_QA_DEVELOPMENT_t62a y MANAGEMENT_QA_CERRO_t62a son copias privadas
frescas de sus respectivos destinos, con correo y cron deshabilitados.
Ambas pasaron cinco pruebas sin fallos/errores, comparación de registros
originales y el flujo de vendedor: formulario efectivo, menú de Exportaciones,
acciones de impresión, Proforma, confirmación de venta y PDF de Nota de venta.
Se verificó un pedido con descuento, flete y seguro por total de 215 USD.
El pedido largo genera dos páginas con encabezado de tabla repetido y cierre
completo. Se inspeccionaron visualmente los PNG de ambos PDF y la continuación.
Los registros de prueba se revierten al final de cada verificador.

Publicado el mismo paquete primero en Desarrollo y después en Cerro, con
/run/lock/steps-environments.lock, ausencia de upgrades concurrentes, control
de versiones/configuración/fuentes, dump, filestore y configuración recuperables.
Se usaron overlays privados, sin sustituir addons compartidos.

Desarrollo:

- Respaldo /opt/steps_backups/management_development_20261010T001709Z.
- Overlay /opt/steps-managed/releases/development/ade6e0a2ec064a55643727b20913bc737d470444.
- MANAGEMENT_DEPLOY_OK y MANAGEMENT_VERIFY_OK development.

Cerro:

- Respaldo /opt/steps_backups/management_cerro_20261010T002012Z.
- Overlay /opt/steps-managed/releases/cerro/ade6e0a2ec064a55643727b20913bc737d470444.
- MANAGEMENT_DEPLOY_OK y MANAGEMENT_VERIFY_OK cerro.
- Servicio activo y HTTPS correcto en https://cerroelplomo.stepsapp.cl.

Revisión adicional en Chrome después de publicar: empresa Cerro El Plomo SpA,
menú Exportaciones / Embarque / Notas de venta y proformas y formulario Nuevo
con las tres columnas añadidas. No se guardó ese formulario comercial.

Los resultados, PDF del cliente y muestras privadas quedan fuera del checkout,
en ~/.codex/local-artifacts/ticket-62. Código y herramientas se integran en
codex/ambientes-canonicos-reparacion y quedan también en codex/t62-proforma-cerro.

El formato está publicado y probado. La configuración de instrucciones
bancarias queda pendiente de confirmación; el ticket permanece en seguimiento
por ese punto y no se presenta como una cuenta de cobro ya configurada.
La nota interna 9295 registra el resultado y el pendiente. T62 quedó en
In Progress; la nota tiene cero notificaciones y no se envió correo al cliente.
