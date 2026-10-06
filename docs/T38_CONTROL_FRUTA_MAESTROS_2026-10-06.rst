Productores Control de fruta y Maestros
=====================================

La revisión del 06-10-2026 incorpora los dos nuevos documentos funcionales
del ticket T38. La aprobación de Estimación recibida ese mismo día permanece
vigente. El destino de esta entrega es Desarrollo, base LAB_TAREAS.

Control de fruta
----------------

Recepción a proceso y Recepción embalada consultan los traslados originales
de Inventario por su tipo de recepción agrícola. Incluyen los pendientes,
además de los realizados, y proponen el tipo correspondiente al crear.

Procesos de packing presenta el contenido original de las tarjas resultantes,
con productor, especie, variedad, calibre, relación con la OT, lote, producto
de embalaje, número de tarja, envases, kilos, estado y kilos por exportar.
No crea un segundo proceso ni otra tabla de tarjas. Los kilos por exportar
corresponden a fruta E validada y aún sin despacho.

Embarques por productor presenta el folio y fecha del embarque original de
Exportaciones, tarja y fecha, productor, lote, variedad, producto, unidad,
embalaje/pallet, etiqueta, categoría, calibre, pallets, cajas, kilos, FOB
unitario y liquidado USD, estado y relación con la liquidación del productor.
El FOB procede de la asignación hecha por la liquidación del recibidor;
no es el precio de venta ni el retorno neto después de descuentos.

Ambos informes usan ``step.fruit.package.line``. Una tarja mixta se desglosa
por sus productores y productos originales. Sus kilos históricos no
dependen de los quants que quedan después del despacho. El FOB asignado a un
productor se distribuye por sus kilos cuando tiene varias líneas en la misma
tarja. Los pallets se presentan como participación proporcional por kilos,
para que la suma de una tarja mixta sea uno y no se duplique el total.
Las relaciones apuntan a las OT y embarques originales. Ver tarja abre el
paquete de Inventario. Las listas de consulta no permiten crear, editar ni
borrar contenido; se conservan los permisos de los documentos originales.
Los dominios de consulta y el cálculo de FOB respetan las empresas activas.

Maestros
--------

Materiales de embalajes y el selector Componente de las listas de materiales
de fruta usan la categoría existente «6 Materiales de embalaje» y sus hijas.
El número 6 identifica el nombre del maestro, no su ID de base de datos.
La búsqueda no depende de que un material ya se haya utilizado en una BOM.
No se crea ni duplica la categoría. Una coincidencia ambigua se rechaza;
sin categoría configurada, el filtro no ofrece productos ajenos.
Los componentes y categorías históricos se conservan.
El menú Lista de materiales abre primero las listas existentes. El filtro
de componentes se inicializa también en formularios nuevos. La creación de
productos se hace desde su maestro, evitando crear por accidente un producto
ajeno a la categoría desde el selector de componentes.

Paquete y verificación
----------------------

Commit del paquete: ``194ae45eea6f91f6a22084f267858f69546b5407``.
SHA256: ``6ff0ccda8dbd4bea80a10b2644d076f84aee7d16a572bed2c4133643bee3b74c``.

Versiones:

* step_producers 18.0.1.8.2, sin cambio funcional en Estimación aprobada.
* step_producer_fruit_flow 18.0.1.2.3.
* step_export 18.0.2.9.4.
* step_producers_integrations 18.0.1.0.1.

La copia nueva ``MANAGEMENT_QA_DEVELOPMENT_t38_control_1006c`` pasó 53 pruebas
sin fallos ni errores, conservación exacta de las filas de 685 tablas y
verificación de las vistas y acciones de los 20 menús. El ensayo anterior
detectó una relación inversa de embarques que ya existía; se corrigió para
reutilizarla antes de publicar. No se promovió el ensayo fallido.
La comprobación visual de la entrega intermedia detectó que el menú BOM
priorizaba el formulario y que faltaba inicializar el filtro al crear. Se
añadieron controles de regresión antes de promover el paquete final.

El ejercicio nativo de QA confirma dos tarjas de 400 kg, 800 kg producidos,
400 kg por exportar y una tarja embarcada y liquidada con FOB USD 2.170,
USD 5,425 por kg y liquidación PRUEBA/LIQ/01. Los importes, cantidades y
registros preexistentes permanecen sin cambios durante el upgrade.

La publicación usa el paquete probado, overlay privado, respaldo y bloqueo
compartido del publicador. No instala ni modifica Demo-SYS o producción.
Overlay final:
``/opt/steps-managed/releases/development/194ae45eea6f91f6a22084f267858f69546b5407``.
Respaldo final:
``/opt/steps_backups/management_development_20261006T193454Z``.
La entrega intermedia tiene respaldo independiente
``/opt/steps_backups/management_development_20261006T192718Z``.

Se verificó por navegador en Desarrollo:

* Recepción a proceso incluye el borrador anterior y la recepción realizada;
  el formulario original conserva el tipo Fruta a proceso y sus dos tarjas.
* Recepción embalada muestra el traslado original del otro productor.
* Procesos de packing muestra 160 envases, 800 kg y 400 kg por exportar;
  Ver tarja abre el paquete original.
* Embarques muestra EM-M/00002, 80 cajas, 400 kg, FOB USD 2.170 y PRUEBA/LIQ/01.
* Materiales de embalajes ofrece los 11 productos de la categoría existente.
* Lista de materiales abre las tres BOM anteriores. En un formulario nuevo,
  buscar Caja ofrece Caja Carton 5 Kg, Bolsa Caja 2.5 kg y Caja cartón 2,5 kilos,
  sin el producto de fruta ni creación rápida desde el selector.
* La prueba de formulario nuevo fue descartada y siguen las tres BOM;
  no se guardaron modificaciones sobre documentos de clientes.

La aceptación funcional de los nuevos apartados por el cliente sigue
pendiente; esta entrega no cierra T38.
