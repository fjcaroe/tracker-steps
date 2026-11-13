# Plan de desarrollo de Viveros y Fincas

## Estado al 13 de noviembre de 2026

La demo activa está en la empresa EcoPlantas de Desarrollo. Invernadero
(`18.0.1.2.0`) y Costos compartidos (`18.0.1.1.0`) están instalados y tienen
menús activos. La demo conserva en borrador una recepción, una orden de
fabricación y un despacho. El traslado de la demo dejó evidencia del recorrido
recepción, fabricación, calidad y despacho parcial en una copia, más revisión
en navegador. EcoPlantas tiene una bodega configurada en Desarrollo.
[Recorrido de Invernadero](DEMO_ECOPLANTAS_INVERNADERO.md).

Operación de vivero (`step_nursery_operations`, `18.0.1.0.0`) está en el commit
`62f74101`. El paquete de ese commit pasó 13 pruebas automatizadas en una
copia de Desarrollo. El módulo todavía está fuera de las rutas de addons del
servicio activo. Sus pantallas, procesos y permisos con los perfiles de
EcoPlantas requieren aceptación funcional. `product_expiry`, una dependencia
del módulo, figura sin instalar. [Operación de vivero](OPERACION_VIVERO.md).

En Desarrollo también están instalados Ventas, Compras, Inventario,
Fabricación, Calidad, Contabilidad, localización chilena con guía electrónica,
Tesorería Steps y registros agrícolas BPA. Su configuración y aceptación para
EcoPlantas forman parte del plan.

## Brechas y criterios de aceptación

| Bloque | Cobertura actual | Trabajo pendiente y criterio de aceptación |
| --- | --- | --- |
| Encargos y planificación de producción | La rama calcula siembra, sobresiembra y bandejas desde una línea de pedido y genera una orden nativa. Hoy admite un plan y una orden por línea. El ciclo se parametriza por especie y temporada. | Agregar previsiones sin pedido, comparar demanda y capacidad, asignar previsiones a encargos y programar varias partidas por línea cuando corresponda. Confirmar, dividir, reprogramar y cancelar un encargo con conservación de la cantidad vendida y sin órdenes duplicadas. |
| Siembra, cámara de germinación y extendido | Fabricación y Calidad están instalados. La rama incluye bitácora de germinación y riego, muestreo por lote y ocupación por etapa y ubicación. | Implementar partes de siembra con cantidades reales, entradas y salidas de cámara y partes de extendido. Validar capacidad, tiempos, conteos, mermas y traspasos parciales. Aceptación con trazabilidad continua de semilla a plantín y saldo por ubicación. |
| Invernadero, revisión, tratamientos y visitas | La portada muestra el recorrido de la demo. La rama añade ocupación, observaciones y dosis en bitácora. Steps tiene inspecciones, aplicaciones y monitoreo BPA. | Mostrar ocupación planificada y real. Completar revisión y liberación de partidas, bloqueos de calidad, tratamientos vinculados a lote e inventario, partes de visita y de procesos varios. Validar que una partida retenida se excluya de la preparación de cargas hasta su liberación autorizada. |
| Recomendación de variedades | Hay maestros de especie y variedad y muestreo de semillas. | Acordar criterios y datos de entrada con Producción. Empezar con un catálogo de recomendaciones aprobadas por cultivo, temporada y destino. Registrar criterio y responsable al aplicar una recomendación. |
| Partidas de injerto | Fabricación, lotes y maestros agrícolas proveen la base. El flujo específico está pendiente. | Desarrollar parte, asignación y ejecución. Reservar lotes de portainjerto y variedad, registrar consumo, prendimiento, rechazo, reinjerto y saldo. Rastrear la partida resultante hasta ambos lotes de origen y hasta cada despacho. Probar ejecución parcial y reversa. |
| Control de almacén | Odoo dispone de almacenes, ubicaciones, lotes, recuentos, ajustes, traslados y reposición. La rama añade custodia de semillas y préstamo de bandejas. | Configurar recuentos y trasvases por lote y ubicación, cuarentena y segregación por propietario. Probar recuento con diferencia, transferencia parcial y devolución de bandejas, con saldos verificables y conservación de la semilla del cliente. [Inventario Odoo](https://www.odoo.com/documentation/18.0/applications/inventory_and_mrp/inventory/warehouses_storage.html). |
| Multiempresa, multialmacén y multiejercicio | Odoo tiene compañías, almacenes y fechas contables. Steps dispone de maestro de temporadas. La rama incluye reglas por compañía. | Probar dos empresas, dos almacenes y dos temporadas con roles acotados. Definir traslado interno y circuito interempresa según propiedad. Conservar lote y temporada de origen en una venta o devolución posterior y contabilizar en la fecha y el ejercicio habilitados. |
| Ventas, distribución y transporte | Pedidos, entregas, devoluciones y facturas son nativos. La rama programa entregas parciales, genera comprobante de plantas y bandejas y prepara cobro de maquila. | Implementar pedido de transporte, previsión, preparación y parte de carga con transportista, capacidad, paradas, lotes y cantidades. Validar carga parcial, reprogramación, albarán o guía, devolución, saldo por entregar y factura por lo acordado. Usar los movimientos realizados como origen del comprobante. |
| Compras y reposición | Están instaladas Compras, recepciones y valoración con costos en destino. Odoo dispone de reglas de reposición. | Parametrizar mínimos, proveedores, plazos, rutas y aprobación de compras. Probar demanda de insumos que genere reposición, pedido a proveedor, recepción parcial, devolución, factura de compra y factura de gasto con analítica. [Reposición Odoo](https://www.odoo.com/documentation/18.0/applications/inventory_and_mrp/inventory/warehouses_storage/replenishment.html). |
| Costos de producción y transporte | Costos compartidos reparte por driver y semana. El código de vivero calcula materiales valorizados, operaciones, indirectos, mermas y costo de entrega neta. El reporte actual exige una sola orden cerrada por lote y no genera asientos. | Imputar mano de obra y fletes a partida o despacho, conciliar analítica y valoración, y definir el costeo de lotes con varias operaciones u orígenes. Validar que un costo de transporte se impute una sola vez y que el margen se pueda conciliar con documentos de origen. |
| Tesorería y enlace a Contabilidad | Están instalados Contabilidad, Tesorería Steps, pagos por factura y módulos de DTE. La rama prepara algunos cargos en borrador. | Configurar diarios, impuestos, vencimientos y analítica por empresa. Probar factura de venta, cobro parcial, nota de crédito, factura de proveedor y gastos, pago y conciliación. Certificar DTE y guías en el ambiente de prueba que corresponda. Si se exige enlace a un sistema contable externo, acordar destino y formato antes de diseñar el conector. [Localización chilena Odoo](https://www.odoo.com/documentation/18.0/es_419/applications/finance/fiscal_localizations/chile.html). |
| Fincas y cultivos | Steps tiene fundos, sectores, temporadas, variedades, aplicaciones BPA, monitoreo de plagas y registros de labores y costos. | Completar gestión por fundo y cuartel, vigencias de arriendos, obligaciones, ingresos y gastos por fundo, cultivo y temporada, y trazabilidad de costos por trabajador o cuadrilla. Validar arriendo y factura de gasto, tratamiento, monitoreo, consumo, labor y margen con sus documentos de origen. |
| Pildoración | Los lotes, la custodia y Fabricación son reutilizables. El flujo específico está pendiente. | Implementar parte de entrada a germinación, parte de pildoración y parte de carga. Registrar lotes de entrada y salida, propietario, unidades o peso, insumos, rendimiento, rechazos y saldos. Probar un lote propio y uno de cliente con entrega, devolución o cobro del servicio según contrato. |

## Secuencia de entregas

1. **Habilitar el módulo existente y probar el vivero base.** Reproducir el
   paquete `62f74101` en una copia fresca de Desarrollo, comprobar sus
   dependencias y configurar un caso EcoPlantas con datos de prueba. Validar
   menús y formularios con Operación, Inventario, Ventas y Contabilidad.
   Ejecutar encargo, plan, lote, calidad, dos entregas, devolución y costo.
   Revisar custodia, maquila y bandejas donde corresponda. Dejar el módulo
   habilitado para revisión en Desarrollo después de certificar el paquete y
   sus permisos.
2. **Completar producción e injertos.** Incorporar previsiones, partes de
   siembra, cámara, extendido, revisión, tratamientos, visitas, procesos
   varios y recomendaciones. Implementar injertos sobre la misma
   trazabilidad. Cerrar con una partida de injerto producida, clasificada
   y preparada para despacho.
3. **Cerrar abastecimiento, ventas y distribución.** Completar reposición,
   compras, recuentos, trasvases, pedidos de transporte, preparación y partes
   de carga. Probar el ciclo con dos bodegas y una devolución parcial.
4. **Cerrar costos, tesorería y contabilidad.** Conciliar materiales, mano de
   obra, indirectos y transporte con inventario, analítica y facturación.
   Validar cobros, pagos y conciliación. Contabilidad define los criterios
   de costeo y DTE desde la primera entrega para aplicarlos a los casos
   logísticos y de maquila.
5. **Completar Fincas y Pildoración.** Integrar los registros agrícolas y la
   operación de fincas con los módulos existentes. Implementar pildoración
   sobre la trazabilidad de lotes y el circuito de maquila cuando aplique.
   Ambos desarrollos pueden avanzar cuando se estabilicen los maestros, la
   custodia y los movimientos de la primera entrega.
6. **Aceptar el producto completo.** Repetir los casos en una segunda
   configuración de vivero, con una empresa ajena que compruebe los permisos,
   dos almacenes y cambio de temporada y ejercicio. Demostrar historial de
   partidas, saldos, márgenes y documentos. Cerrar cada bloque con evidencia
   y aceptación del responsable funcional.

## Primera tarea para retomar

Preparar en copia de Desarrollo un pedido de 1.000 plantas, ciclo de 35 días,
sobresiembra del 10 % y bandejas de 128 cavidades. Verificar 9 bandejas y
1.152 unidades a sembrar. Recibir la semilla, confirmar una sola orden,
registrar germinación y revisión de calidad, producir por lote y comprobar
la merma. Hacer dos entregas de 600 y 400, devolver 20 y comprobar 980 unidades
entregadas netas, el saldo del lote y el documento comercial correspondiente.
Revisar también un reintento de generación de orden y el acceso desde una
empresa ajena. Registrar por paso el usuario, el resultado y el enlace a la
evidencia.

Usar el commit de Operación de vivero como fuente del módulo. Antes de
integrar cambios funcionales, comparar sus dependencias y scripts con la
rama canónica `origin/codex/ambientes-canonicos-reparacion` y con las versiones
efectivas de Desarrollo. Probar cualquier migración con el paquete exacto en
una copia aislada. La publicación para revisión requiere respaldo, bloqueo
compartido, overlay privado y verificación posterior del menú, formulario y
flujo. [Operación canónica de Odoo](https://github.com/fjcaroe/tracker-steps/blob/codex/ambientes-canonicos-reparacion/docs/OPERACION_ODOO_CANONICA.md).

Durante el piloto recoger ejemplos de los partes, las reglas de injerto,
pildoración y recomendación varietal, el criterio de reparto de fletes y el
tratamiento comercial de semillas y bandejas de terceros. Estos insumos
permiten estimar cada entrega y convertir la matriz en tickets con responsable
funcional y prueba de aceptación.
