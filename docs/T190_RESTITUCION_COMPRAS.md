# T190 — recuperar Compras y conservar las proformas

## Problema y corrección

Las vistas primarias de proforma mensual, anticipo y compra nativa tenían la
misma prioridad. Odoo ordena por `priority,name,id`: la vista
`purchase.order.advance.proforma.form` se elegía antes de
`purchase.order.form` cuando una acción no indicaba formulario explícito.
Así, Compras abría el formulario de anticipo, sin el ciclo nativo habitual.
Los pedidos y las acciones originales seguían presentes.

Las vistas específicas de fruta y anticipos ahora tienen prioridades 90 y 95.
La compra conserva su formulario nativo y sus botones de confirmación,
recepción y facturación. Las acciones de solicitudes, pedidos confirmados y
compras del proveedor excluyen las proformas sin cambiar sus contextos ni el
filtro de estado de los pedidos confirmados.

Compras incorpora el menú **Proformas de fruta**, con los accesos existentes a
**Preparar compra mensual** y **Proformas de compra**. Reutiliza las acciones,
registros y permisos existentes; los anticipos conservan su acceso en Productores.

## Paquete

- Commit del paquete: `7d7c0225c78eaba555dd2ead02b96824e0da0097`.
- SHA-256: `9d4c006fbc7ad686cebf837ddc84e15beb6136cf139f42ab2c9f0037826f3b5c`.
- `step_packing_fruit_proforma`: `18.0.1.2.1`.
- `step_producer_advances`: `18.0.1.1.1`.
- Los commits posteriores del ticket incorporan herramientas y evidencia de
  verificación; no cambian los bytes de estos módulos.

## Validación

Las copias independientes de Desarrollo (`t190d1`), Cerro (`t190c1`) y
QA-Cerro (`t190q1`) pasaron 66 pruebas cada una, sin fallos ni errores.
La prueba nueva utiliza `Form` sin indicar una vista, con un usuario comprador:
crea una solicitud, confirma, recibe tres unidades y genera la factura de
proveedor en borrador conservando el vínculo con la línea de compra.

También se verificaron los ciclos de proforma mensual y anticipos, documentos
33/46, retenciones, reintentos sin duplicación, fechas de pago y anexos de mil
filas. Se revisaron los PDF sintéticos de resumen y anexo. Las pruebas no
validan compras ni facturas comerciales de los ambientes publicados.

La publicación utiliza el mismo paquete, respaldos completos, bloqueo
compartido y overlays privados; compara los registros comerciales antes y
después. QA-Cerro conserva su base y aislamiento, sin reemplazarla por otra copia.

La comprobación de navegador abre solicitudes y pedidos, pulsa Nuevo sin
guardar, verifica el formulario y sus líneas, abre proformas y anticipos y
navega por el nuevo menú desde Compras. La revisión mantiene desactivada la
suscripción IoT ajena a este flujo y bloquea métodos de escritura de documentos.
Las sesiones temporales se eliminan al terminar.

## Publicación comprobada el 10 de noviembre de 2026

| Ambiente | Copia: 66 pruebas | Versión y formulario efectivo | Menús y navegador |
| --- | --- | --- | --- |
| Desarrollo | Sin fallos | Verificado | Verificado |
| Cerro El Plomo | Sin fallos | Verificado | Verificado |
| QA-Cerro El Plomo | Sin fallos | Verificado | Verificado |

`verify_cerro_release_pair.py` confirmó versiones y fuentes idénticas en Cerro
y QA-Cerro. Los tres servicios quedaron activos. Las comprobaciones de
navegador finalizaron sin errores ni documentos guardados, y las tres sesiones
temporales fueron eliminadas. Las evidencias, PDF y respaldos permanecen fuera
del repositorio público.
