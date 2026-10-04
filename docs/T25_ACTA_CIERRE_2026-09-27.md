# T25: cierre del módulo de guías de despacho (versión sin CAF)

**Fecha:** 27 de septiembre de 2026
**Ticket:** [T25](https://soporte.stepsapp.cl/helpdesk/ticket/25)
**Entornos:** Desarrollo (`LAB_TAREAS`, `https://desarrollo.stepsapp.cl`) y Demo-SyS (`STEPS_DEMO_SYS`, `https://demo-sys.stepsapp.cl`)
**Código:** rama `ticket/25-dispatch-guide-completo`, [PR #7](https://github.com/fjcaroe/tracker-steps/pull/7) en borrador

## 1. Alcance contrastado

| Documento del ticket | Qué pide |
|---|---|
| *2.10 Módulo Guías de despacho* (12-09) | Crear guía con encabezado, detalle, transporte y observaciones (Anexo 1); facturar guías; libro de guías (Anexo 2, SII); maestros de transportistas, choferes y contactos; configuración de razón del traslado y tipo de despacho; relación con Inventario, Cosecha, Ventas y Fletes. |
| *Respuestas* (12-09) | Todos los tipos de guía, **primero el traslado de fruta campo → packing**. Inventario se descuenta cuando Bodega confirma la salida. Facturación 1:1, varias guías por factura o sin facturar. Transporte obligatorio: transportista y RUT, chofer y RUT, patente de camión y remolque, origen, destino y motivo. |
| *Versión sin CAF* (24-09) y formato Citripal | El módulo es el mismo para proveedor DTE **Odoo** o **Tercero**. Con Tercero, el número de guía se registra a mano y el documento es interno. Los datos de transporte van al pie del formato. |

La entrega del 25-09 (18.0.1.0.0) cubría el folio externo, los datos básicos,
el PDF, y la creación desde entregas y Fletes. Al compararla con el Anexo 1 faltaban:

- razón del traslado y tipo de despacho como tablas, con la regla de flete;
- fecha y hora de salida y llegada;
- chofer y transportista tomados de Contactos, y patentes desde Flota;
- empaque, lote, impuestos y analítica en las líneas;
- subtotal, exento, IVA y total;
- paga flete → OT de flete;
- facturación de guías y libro de guías;
- creación desde traslados internos y desde **Cosecha**, que era la prioridad del cliente.

## 2. Qué se entregó (`step_dispatch_guide` 18.0.2.0.1 y `step_dispatch_guide_cosecha` 18.0.1.0.0)

**Formulario de la guía (Anexo 1)**

- **Cliente/destinatario:** RUT, dirección, comuna y región se toman del contacto. También se registran contacto, giro, referencia, forma de pago y vencimiento.
- **Configuración de despacho:**
  - razón del traslado con los códigos SII 1 a 9;
  - tipo de despacho (la misma tabla de Fletes);
  - fecha y hora de salida y de llegada;
  - origen y destino;
  - camión y remolque desde Flota, que completan la patente; también se puede escribir a mano;
  - chofer: contactos con «¿Chofer?»;
  - transportista: contactos con «Transporte de carga?».
- **Detalle:** producto, descripción, empaque, cantidad de empaque (bins), UdM, cantidad, kilos, precio neto, impuestos, lote/serie y distribución analítica.
- **Totales:** total de bins y kilos, subtotal afecto, exento, IVA y total.
- **Fruta:** bins vacíos en devolución, GLOBALG.A.P./GGN y CSG.

**Reglas**

- *Tipo de despacho → paga flete.* Con «No», no se permite marcar Paga flete: aparece el mensaje «Este tipo de despacho no paga flete». Con «Sí», es obligatorio.
- *Paga flete → OT de flete.* Al confirmar se crea la orden de flete con transportista, camión, tramo y fecha, y queda enlazada a la guía.
- *Confirmación* exige razón del traslado, chofer y, si paga flete, tramo. En modo **Odoo** (DTE 52 con CAF) la confirmación sigue bloqueada.
- *Anulación* registra el indicador del libro SII: 1 si el folio se anula en borrador, 2 si la guía ya estaba confirmada. La recepción parcial (3) se marca a mano. No se puede anular una guía facturada.

**Facturación de guías**

- Las guías confirmadas con razón **1. Operación constituye venta** aparecen en *Guías de despacho → Guías → Facturar guías* y en *Contabilidad → Clientes → Facturar guías*.
- Se factura desde el botón **Facturar** de la guía o seleccionando varias guías del mismo cliente (*Acciones → Facturar guías*). Se crea una factura borrador con las líneas y analítica de cada guía y la referencia **tipo 52** con el folio de cada guía, tal como exige el SII para facturas de guías.
- La guía queda *Facturada* con su factura. Si la factura se anula o se borra, la guía vuelve a *Por facturar*.

**Informes**

- *Estado de guías:* tabla dinámica y gráfico por razón, estado y mes.
- *Libro de guías:* lista y PDF con las columnas del detalle del instructivo SII LGD (folio, anulado/modificado, tipo de operación, fecha, RUT y razón social, neto, tasa, IVA, total, total modificado y documento de referencia). Incluye el resumen del período: folios y guías anuladas, guías de venta con su monto, y guías no venta por código de traslado.

**Dónde se crea la guía**

- Desde el propio módulo: *Guías → Crear guía de despacho*.
- Desde **entregas** de Inventario: razón 1 si vienen de una venta. Se copian líneas, lote y precio de venta.
- Desde **traslados internos** de Inventario: razón 5.
- Desde **Fletes**: marca Paga flete y copia tramo, camión y transportista.
- Desde la **recepción de Cosecha**: razón 5, origen fundo/cuartel y destino packing. Cada línea de la recepción pasa a la guía con su producto, envase, cajas y kilos, y la tarja queda en la descripción.

**Menú:** Inicio · Guías (Crear, Guías de despacho, Facturar guías) · Informes (Estado de guías, Libro de guías) · Maestros (Transportistas, Choferes, Contactos) · Configuración (Razón del traslado, Tipo de despacho, Ajustes).

## 3. Por qué se implementó así

- **Contactos y Flota en vez de maestros propios.** El Anexo 1 pide tomar chofer y transportista de Contactos (notas 1 y 2) y la patente de un maestro (nota 3). Las marcas `step_chofer` y `step_carga` ya existían en Movilización y Agrícola. El maestro de choferes de la 18.0.1 se conservó como «maestro anterior» para no perder historial, y su único chofer pasó a contacto.
- **Tipo de despacho compartido con Fletes.** Esa tabla ya existía, con la columna «¿Paga flete?» exigida por el diseño, así que no se duplicó.
- **Encabezado propio en el PDF.** El formato Citripal trae los datos de la empresa en el cuerpo. Además, el diseño de documentos de la empresa en Desarrollo tiene una personalización Studio ajena a este ticket (ver sección 8).
- **Cosecha en un módulo puente.** Demo-SyS no tiene Cosecha. El puente se instala solo donde están ambos módulos.
- **Sin inventario desde la guía.** El cliente eligió que el stock baje cuando Bodega confirma la salida. La guía se enlaza a la operación de Inventario, pero no mueve stock por sí misma.

## 4. Pruebas y resultados

- **Copias aisladas** `T25_GUIAS_DEV_TEST` y `T25_GUIAS_DEMOSYS_TEST`, ya eliminadas.
  - Desarrollo: **17 pruebas, 0 fallas y 0 errores** (15 de guías y 2 de Cosecha). Demo-SyS: **15 pruebas, 0 fallas**.
  - Cubren los totales del diseño, la confirmación en modo Tercero, los datos obligatorios, el folio único por empresa y el bloqueo del modo Odoo. También la regla de flete por tipo de despacho, la OT de flete y la patente desde Flota.
  - En facturación: varias guías en una factura con referencias 52, rechazo de clientes mezclados y de razones no facturables, bloqueo de anulación si hay factura, y liberación de la guía al borrar la factura.
  - Además: indicadores de anulación, resumen del libro, creación desde traslado interno, creación desde recepción de Cosecha y render de ambos PDF.
- Las **12 pruebas de Exportaciones** (`step_export`, T35), que usan guías, pasaron con el módulo nuevo.
- **Recorrido de menús** con administrador, bodega (Inventario: usuario) y contabilidad (Facturación), en Desarrollo y Demo-SyS: todas las vistas cargan sin errores. Bodega y contabilidad ven solo lo que les corresponde. Los botones aparecen en entregas, órdenes de flete, facturas y recepciones de Cosecha.
- **Flujo real después del despliegue**, en `LAB_TAREAS` y `STEPS_DEMO_SYS`, con reversión:
  - Bodega creó y confirmó una guía de venta con flete: se generó la OT de flete; IVA 19 % = 19.000 y total = 119.000.
  - Contabilidad la facturó: factura de 119.000 con la referencia (52, folio).
  - Se generaron el PDF de la guía y el del libro.
  - No quedaron residuos.
- **PDF de muestra:** una hoja carta con el formato Citripal, que se adjunta al ticket.
- **Servicios:** `odoo18-dev` y `odoo18-demo-sys` activos, con HTTP 200 en `/web/login` de ambos dominios y sin errores en los logs de actualización.

## 5. Parámetros que el administrador puede cambiar

| Parámetro | Dónde | Valor actual | Cuándo cambiarlo |
|---|---|---|---|
| Proveedor DTE | *Inventario → Configuración → Ajustes → Guías de despacho* | **Tercero** en todas las empresas de ambos entornos | Solo cuando la empresa tenga CAF tipo 52 y se habilite la emisión desde Odoo, que es un desarrollo aparte. |
| Razón del traslado | *Guías de despacho → Configuración → Razón del traslado* ([Desarrollo](https://desarrollo.stepsapp.cl/odoo/action-2058) · [Demo-SyS](https://demo-sys.stepsapp.cl/odoo/action-1908)) | Códigos SII 1 a 9; solo el 1 está marcado *Facturable* | Para ajustar el texto o marcar otra razón como facturable. El **código** debe seguir la tabla SII porque va al libro. |
| Tipo de despacho y regla de flete | *Guías de despacho → Configuración → Tipo de despacho* ([Desarrollo](https://desarrollo.stepsapp.cl/odoo/action-1948) · [Demo-SyS](https://demo-sys.stepsapp.cl/odoo/action-1784)) | Retira cliente: No · Despacho a cliente: Opcional · Despacho a tercero: Opcional (igual que la tabla del diseño, en ambos entornos) | Si se agrega otro tipo de despacho o cambia su regla de flete. |
| Transportistas / choferes | *Guías de despacho → Maestros* | Marcas «Transporte de carga?» y «¿Chofer?» del contacto | Al incorporar un transportista o chofer. |
| Quién puede crear choferes desde la guía | *Ajustes → Usuarios →* usuario *→ Permisos adicionales → Creación de contacto* | Sin cambios (norma de Odoo 18) | Dárselo a quienes emiten guías y deben registrar choferes nuevos al vuelo. Sin ese permiso eligen contactos existentes. |
| Quién factura guías | Ficha del usuario → *Facturación* | Requiere *Facturación* o superior | Para el personal que factura. |
| Tramos de flete | *Fletes → Maestros → Tramos* | Tramos existentes | Al agregar rutas nuevas con flete pagado. |

Enlaces directos:

- Desarrollo: [Inicio](https://desarrollo.stepsapp.cl/odoo/action-2050), [Crear guía](https://desarrollo.stepsapp.cl/odoo/action-2051), [Facturar guías](https://desarrollo.stepsapp.cl/odoo/action-2052), [Libro de guías](https://desarrollo.stepsapp.cl/odoo/action-2054).
- Demo-SyS: [Inicio](https://demo-sys.stepsapp.cl/odoo/action-1900), [Crear guía](https://demo-sys.stepsapp.cl/odoo/action-1901), [Facturar guías](https://demo-sys.stepsapp.cl/odoo/action-1902), [Libro de guías](https://demo-sys.stepsapp.cl/odoo/action-1904).

## 6. Respaldo y despliegue

- Respaldos en `odoo-new`, con dump de la base, código anterior, `SHA256SUMS`, estado del servicio, módulos antes y después y log de actualización:
  - `/opt/steps_backups/ticket25_guias_completo_20260927T202828Z/{dev,demosys}/`: antes de 18.0.2.0.0.
  - `/opt/steps_backups/ticket25_guias_2_0_1_20260927T203631Z/{dev,demosys}/`: antes de 18.0.2.0.1, más el resultado del flujo verificado.
- Datos migrados en Desarrollo:
  - las 2 guías existentes (folios 12 y 152) quedaron con el chofer «Juanin» como contacto chofer;
  - su transportista quedó marcado como transporte de carga;
  - sus razones de traslado quedaron vacías, porque antes eran texto libre: se completan al editarlas.
- Demo-SyS no tenía guías.
- Los árboles de addons son `/opt/dev_odoo18/odoo_agriculture` y `/opt/demosys_odoo18/odoo_agriculture`. Ninguna base productiva que lea el árbol de Desarrollo tiene `step_dispatch_guide` instalado.
- **Sin cambios:** SyS, Demo (`STEPS_DEMO`) y Cerro El Plomo. Estos dos últimos tienen la 18.0.1 como dependencia de Exportaciones (T35) y se actualizan cuando se decida.
- Commits: `81f0344`, `9e45dc7`, `fc1bd32`, `f0341ed`, `7c626f1`.

## 7. Límites

- **Emisión DTE 52 desde Odoo (con CAF)** sigue fuera: requiere folios autorizados, certificado y validación ante el SII. El modo Tercero, pedido en el complemento, es el que queda operativo.
- **Envío del Libro de Guías en XML al SII** no se implementó: según el instructivo, solo se envía cuando el SII lo solicita y, en modo Tercero, lo emite el sistema que timbra las guías. El libro de Odoo es de control interno.
- Crear la guía **desde un pedido de venta antes de entregar** se cubre desde la entrega del pedido o desde el módulo. Un botón en el pedido mismo sería una mejora.
- Las pruebas con datos se revirtieron. Las OT de flete de prueba consumieron los correlativos `FLE202600004` y `FLE202600005` en Desarrollo, porque las secuencias no retroceden.

## 8. Hallazgo fuera de alcance

En Desarrollo (`LAB_TAREAS`) la vista `web_studio.report_editor_customization_diff.view._web.external_layout_standard` (Studio, febrero 2026) reemplaza el diseño estándar de documentos de la empresa por un formato «ENTREGA DE EPP» que usa `doc.x_name`. Con eso, en esa base falla cualquier PDF que use el diseño estándar, incluidas las facturas. La misma personalización está en Demo (`STEPS_DEMO`); no existe en Demo-SyS ni en Cerro El Plomo. No se modificó: queda informado para revisarlo aparte.
