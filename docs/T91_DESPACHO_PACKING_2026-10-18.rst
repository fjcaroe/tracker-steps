T91 Instructivo de despacho y despacho
=====================================

Solicitud 91, respuesta humana 9499, adjuntos 3363 y 3364. Destinos: Desarrollo
para QA y revisión, Cerro El Plomo como producción del solicitante. Se conserva
el módulo de despacho y los modelos y registros existentes. No se usa Studio.

Implementación
--------------

step_packing_dispatch amplía step.export.dispatch.order como instructivo de
despacho, manteniendo su tabla e identificadores anteriores. El número se
ingresa en el documento. El embarque es una relación al instructivo nativo de
Exportaciones; temporada, especie, nave, recibidor, transporte y puerto de
salida se consultan desde ese embarque. La carga solicitada agrega líneas
operacionales, no nuevos maestros de productos o fruta. Traer carga del embarque
copia explícitamente sus cantidades y filtros sin alterar las líneas originales
ni reemplazar una carga ya ingresada.

La tabla contempla producto, embalaje, productor, variedad, marca, calibre,
calidad, pallets, cajas por pallet y kilos por caja. Cajas = pallets por cajas;
kilos = cajas por kilos por caja. Camiones redondea hacia arriba pallets dividido
por capacidad: 100 pallets a 20 por camión son cinco camiones; 101 son seis.
Los filtros opcionales vacíos aceptan cualquier valor, los numéricos y producto
se comprueban contra la composición real de la tarja. Los identificadores de
productor y embalaje se relacionan con los maestros ya existentes.

Packing / Despacho contiene cuatro entradas: Instructivo de despacho, Despacho,
Packing List y Traslado lotes. Esta última conserva la acción original del módulo
step_packing_batch; no se sustituye por una pantalla de transferencias distinta.
Las inspecciones del mismo modelo step.packing.inspection se consultan en
Packing / Inspecciones / Inspecciones SAG o Inspecciones internas. Las entradas
antiguas se desactivan, preservando los documentos y acciones históricas.

La guía nativa step.dispatch.guide incorpora Número instructivo despacho debajo
de Embarque y la pestaña Folio Pallet. Admite lectura o escritura exacta del
folio, varios folios separados por comas, y selección desde una lista filtrada.
Repetir la lectura del mismo folio no lo duplica. La guía usa la relación de
embarques original; sus tarjas se agregan a la carga existente sin eliminar
otras asociaciones del embarque.

Solo se ofrecen tarjas E validadas de la misma empresa, temporada y especie,
con stock interno sin reservas y coincidencia con la carga solicitada. También
se aplican restricciones de productor y variedad del programa de ventas.
Se rechaza asignar una tarja a otra guía vigente. Los bloqueos de filas del
instructivo y los paquetes serializan asignaciones concurrentes. Se respetan
la capacidad del camión y la cantidad por cada combinación de filtros,
incluidas líneas con filtros que se solapan. No se sobreescriben los filtros
de un instructivo con guías vigentes, ni la carga de una guía confirmada o
que ya tenga un packing list.

Traer detalle de pallets prepara las líneas de producto de la guía solo cuando
el detalle está vacío; no reemplaza precios o líneas existentes. La confirmación
usa la función de despacho original y comprueba las inspecciones exigidas.
No se emite un nuevo DTE ni se inventa un movimiento de stock. El folio tributario
y la operación de inventario siguen el procedimiento nativo de la guía.

El packing list conserva su modelo, secuencia, reporte y relación a guía.
Al seleccionar una guía con instructivo toma exactamente sus tarjas, por
onchange y también por creación/escritura de backend. Se rechazan discrepancias
manuales. El botón de la guía abre su packing list existente o crea uno, evitando
duplicarlo. Los packing lists anteriores sin este instructivo no se reescriben.

Validación y publicación
-----------------------

Paquete final: f5bd63d1b01babf08758acc91f5f243bfcf46197, versión
18.0.1.0.0. SHA256 a70fa903b1f6d3e52c27683cd077d61d73da253757de1ff3dd87d005065c1614.
La suite cubre cálculos/preservación del embarque, lector/lista/confirmación y
packing list, filtros/capacidad/duplicados y reglas por empresa/menús.
Las cuatro pruebas pasaron en la copia fresca de Desarrollo y en la copia de
compatibilidad de Cerro. El certificado de cada destino vincula el mismo commit
y SHA256. Después de publicar se comprobó versión, ruta efectiva, vistas y menús
y se repitieron los cuatro casos con rollback en cada ambiente.

Se publicó primero en Desarrollo y luego en Cerro, bajo la exclusión compartida
/run/lock/steps-environments.lock, con overlays privados y sin actualizar sus
raíces compartidas. Cada destino conserva las versiones instaladas de Packing,
Inventario y Exportaciones: no se publicaron versiones diferentes de esos módulos.

Respaldos recuperables anteriores a la publicación:

* /opt/steps_backups/management_development_20261018T204710Z
* /opt/steps_backups/management_cerro_20261018T205011Z

La comparación de tablas e importes antes/después pasó en ambas copias y ambos
destinos. Se excluyeron únicamente las columnas nuevas del instructivo y la guía;
se preservó íntegramente cada campo previamente existente y sus relaciones.
Las vistas antiguas Studio que generan advertencias al cargar Desarrollo no se
modificaron. La única ausencia de módulo admitida allí sigue siendo steps_api,
ya identificada por la herramienta operacional antes de esta entrega.

Revisión en navegador: cuatro entradas de Despacho; menú separado Inspecciones;
formulario del instructivo con datos del embarque real consultados sin guardar;
campo Número instructivo despacho debajo de Embarque; pestaña Folio Pallet con
entrada de lector y tabla de tarjas; formulario nativo del packing list. Las
vistas previas se descartaron, sin crear documentos comerciales de clientes.
Las capturas y los certificados se guardan fuera del checkout en
~/.codex/local-artifacts/tickets-20261018/; visual-review.json registra sus hashes.
El comprobador de cierre exige esa evidencia y rechaza comentarios humanos
posteriores a 9499 que aún no se hayan incorporado.

T91 quedó resuelto, con nota interna 9500. La nota no genera notificaciones ni
correo externo. No se generaron guías, DTE ni despachos reales de clientes
durante las pruebas; los casos transaccionales se revirtieron íntegramente.
