# Operación de vivero en Odoo 18

La aplicación `step_nursery_operations` complementa la portada de
Invernadero. Usa los pedidos, recetas, órdenes, lotes, paquetes,
ubicaciones, recepciones, traslados y facturas nativos. Usa también los
maestros agrícolas y el reparto semanal ya instalado. No carga datos de
una empresa real ni cambia la configuración al instalar.

- **Operación de vivero**: planes, ocupación, custodia y bitácora. El
  operador necesita también acceso nativo a los pedidos, bodegas y
  empresas que atiende. **Administración de vivero** mantiene ciclos.
- **Contabilidad**: revisar repartos y costo de lote. Solo usuarios con
  facturación pueden preparar cobros. Los cobros quedan en borrador. La
  tarea de preparación de vencidos se instala desactivada.
- **Inventario**: la ubicación interna de custodia de bandejas o semillas
  debe quedar fuera de la ubicación de stock disponible para producción y
  ventas normales. El propietario y el lote de semilla se conservan en
  movimientos nativos. Los empaques nativos se usan para identificar
  bandejas, incluso antes de la prueba con una impresora del cliente.

## Configuración y aceptación

| Requisitos | Configuración y caso de aceptación |
| --- | --- |
| PRD-01 a PRD-04 | Crear bandejas por cavidad, unidad/millar y ciclos con los maestros vigentes. Con un pedido de 1.000 plantas, 35 días, +10% y 128 cavidades, verificar 9 bandejas y 1.152 unidades a sembrar sin modificar las 1.000 vendidas. Superponer dos etapas en un mesón y comprobar el aviso en las fechas afectadas. |
| PRD-05 a PRD-09 | Configurar operaciones nativas Siembra, Germinación, Crecimiento y Rustificación y despacho por lote. Correr todo el lote con Calidad durante crecimiento y antes de despacho; registrar germinación y labores; contar, descartar, comprobar saldo y replanificar pendientes. La receta y criterios de calidad se toman del cliente. |
| INV-01 a INV-06 | Crear ubicaciones internas por estado; registrar salida de 10 bandejas y devolución de 3; verificar saldo 7. Cargar una muestra de semilla con peso y germinación y convertir el peso neto de una recepción en unidades desde sus operaciones detalladas; configurar vencimiento, recetas y consumo real; recibir semilla de cliente sin capitalizarla; provocar una necesidad con mínimo de stock. |
| VTA-01 a VTA-04 | Crear cuatro cuotas de 25.000 en un pedido de 100.000. Confirmar y verificar cuatro despachos nativos. Validar anticipo y deducción con entregas parciales. Validar plantines y bandejas y abrir el comprobante combinado. La guía tributaria nativa y el tratamiento de préstamo deben probarse con certificación SII; el comprobante combinado no reemplaza el DTE. Preparar un cargo por préstamo vencido y repetir la acción sin duplicarlo. |
| COM-01 a COM-03 | Configurar rutas y reglas de reabastecimiento; verificar demanda de insumos y solicitud de cotización. Probar autorización por monto, recepción parcial y cotejo con factura. Configurar método de valorización compatible y verificar distribución de flete, seguro y aduana en recepción. |
| FIN-01 y FIN-02 | Terminar un lote, registrar merma normal y anormal, asignar indirectos del reparto semanal confirmado por centro y verificar costo de las unidades útiles y de las entregas netas. El reporte es de gestión: no genera un asiento, cambia el costo estándar ni reescribe la valoración de movimientos cerrados. |
| FIN-03 a FIN-05 | Definir RUT, plan, diarios, monedas, UF, formato de cartola y dimensiones de análisis. Probar DTE de emisión, recepción y acuse en certificación por tipo de documento y conciliación en el banco real. Validar separación de empresas y conciliación del margen analítico con Contabilidad. |
| MAQ-01 a MAQ-06 | Recibir la misma variedad de dos propietarios; reservar y consumir solo el lote del dueño vinculado a la orden. Consultar recibido, consumido, devuelto y saldo; registrar germinación; probar etiqueta y lectura por bandeja. Preparar cobro por bandeja o por planta entregada y validar devolución de sobrantes con guía cuando corresponda. |
| TEC-01 | En un dispositivo autorizado descargar órdenes, cortar conectividad, recargar, registrar riego y germinación, reconectar y validar un solo registro de cada evento. El piloto cubre bitácora, no las transacciones completas del ERP. Guardar y sincronizar con el mismo usuario; no usar un perfil de navegador compartido. |
| TEC-03 | Verificar el acceso API con un usuario técnico de mínimos permisos. Lectores y sensores requieren definir dispositivo, protocolo y escenarios. |

El ciclo usa días corridos desde la fecha pactada. Las bandejas de siembra
se redondean hacia arriba. El registro de una cuota crea su propia agrupación
logística en rutas que propagan el grupo. Antes de usar fabricación contra
pedido, verificar la regla de abastecimiento para que no genere una segunda
orden además de la siembra programada.

## Prueba en Desarrollo

`tools/ops/test_nursery_development.py <identificador>` se ejecuta en el host
canónico desde el paquete exacto. Toma una copia fresca, neutraliza correo y
cron, escucha solo en loopback durante las pruebas y elimina la copia al
terminar. No cambia el servicio ni la base activa. El comprobador de navegador
`tools/ops/check_nursery_offline_ui.cjs` usa Chromium y Playwright para ensayar
caché, cola local, pérdida de conectividad y sincronización, sin datos reales.

Verificar las vistas efectivas con los perfiles del cliente y los
casos completos antes de habilitar el módulo para revisión. Si se publica,
usar el mismo paquete certificado, respaldo, bloqueo compartido y overlay
privado conforme a `docs/OPERACION_ODOO_CANONICA.md`.
