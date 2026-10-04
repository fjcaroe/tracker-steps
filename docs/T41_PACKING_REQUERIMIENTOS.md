# T41 — Módulo de Packing: requerimiento completo (referencia de trabajo)

> Convertido desde los adjuntos del ticket 41 (`ERP Steps Odoo- Packing.docx`,
> id 3123; `Anexo1 Módulo de Packing.xlsx`, id 3124) el 02-10-2026, a pedido
> de Fernando, para no tener que releer el docx/xlsx en cada corrida de
> soporte. Úsalo como fuente única del requerimiento; actualiza la sección
> "Estado de implementación" a medida que se avance, no el resto del
> documento (eso es la copia fiel del pedido del cliente).
>
> Rama de trabajo: `codex/t41-packing-operations` (worktree temporal
> `ticket41-packing`, se recrea con `git worktree add` sobre esa rama —
> ver Paso 2 de la SKILL de soporte). Módulo: `step_packing_operations`.

## 1. Qué es Packing (resumen funcional)

Packing es el proceso que convierte fruta a granel (recién cosechada) en
fruta embalada con calidad y atributos para exportación, cumpliendo normas
y exigencias de clientes. Ciclo: recepción en frío → embalaje en distintos
formatos → inspección interna y SAG → embarque según instrucciones. Durante
todo el proceso hay servicios que se cobran y recursos con costo.

El desarrollo está planificado **por etapas**. El Anexo 1 (hoja "Menu")
marca en el menú sugerido qué color es qué etapa:

- **Celeste** = ya existe (en Inventario/T40 o en Exportaciones).
- **Café** = se desarrolla en **esta etapa (Etapa 1)**.
- **Violeta** = Etapa 2 (costeo de procesos — explícitamente fuera de
  alcance por ahora).

La tabla de cierre del docx resume el alcance por proceso:

| Proceso | Módulo origen de la información | Etapa |
|---|---|---|
| 1. Planificación | Packing | Etapa 1 |
| 2. Recepciones fruta | Inventario (T40) | Etapa 1 (ya en Inventario, solo falta el acceso de menú desde Packing) |
| 3. Inspecciones de entrada | Packing | Etapa 1 en la tabla, pero el cuerpo del documento dice "(pendiente)" — **contradicción del propio documento, confirmar con el cliente antes de implementar** |
| 4. Proceso Embalaje de fruta | Packing | Etapa 1 |
| 5. Despachos y embarques | Packing - Exportaciones | Etapa 1 (ok en Exportaciones, falta el acceso de menú desde Packing) |
| 6. Costeo de procesos | Packing | **Etapa 2 — no implementar aún** |

## 2. Menú completo pedido (hoja "Menu" del Anexo 1)

Este es el menú objetivo completo de la app Packing. Lo que hoy existe en
`step_packing_operations` son solo las dos primeras columnas parciales
(Planificación, Procesos) — **falta todo lo demás como acceso de menú**,
aunque buena parte de la funcionalidad de fondo ya exista en otros módulos
Steps (Exportaciones, Inventario, step_packing).

| Inicio | Planificación | Recepciones | Procesos | Inspecciones | Despacho | Costos de proceso (Etapa 2) | Maestros | Configuraciones |
|---|---|---|---|---|---|---|---|---|
| Panel | Orden de Proceso | Fruta a proceso | Proceso de Packing | Inspección SAG | Instructivo Embarque | Costos directos | Productores | Fruta |
| | Instructivo Embalaje | Fruta embalada | Repaletizado | Inspección Interna | Embarque / Despacho | Asignación de costos | Productos | Especie |
| | Necesidades de materiales | Control de Envases | Informes | | Packing List | Informes | Embalajes | Grupo variedad |
| | Restricciones de fruta | | Reservas de Stock | | | | | Variedad |
| | | | | | | | | Grupo de calibre |
| | | | | | | | | Calibre de fruta |
| | | | | | | | | Categoría de fruta |
| | | | | | | | | Packing (planta) |
| | | | | | | | | Líneas de proceso |
| | | | | | | | | Tipo de proceso |
| | | | | | | | | Tipo de tarja |
| | | | | | | | | Estado de tarja |
| | | | | | | | | Causas detención líneas |

## 3. Detalle por área (hoja + lo que especifica)

### 3.1 Planificación — hoja "OP" (Orden de Proceso)

Formulario con cabecera (Número OP, Fecha, Fecha producción, Semana,
Programa de ventas, Packing/planta, Especie, País, Exportadora, Recibidor,
ETD, ETA) y una grilla de detalle: Especie, Variedad, Tipo Fruta, Producto,
Embalaje, Etiqueta, Calidad, Calibre, Categoría, Pallet, Cajas, Kilos, Tipo
inspección.

Del docx (sección 1):
- **1.1 Orden de Proceso**: orientaciones generales de fruta requerida por
  semana, prioridades de pedidos. Referida a un programa de ventas,
  normalmente para la semana siguiente. Una OP puede incluir varias
  especies/productos-embalajes con sus atributos. Después se compara lo
  planificado vs. lo embarcado realmente.
- **1.2 Instructivo de Embalaje**: documento técnico de calidad/condición y
  detalle de embalajes, se adjunta a la OP.
- **1.3 Necesidades de materiales**: a partir de cajas por embalaje de la
  OP, se calculan materiales aplicando la BOM. Se puede hacer para una OP,
  varias o todas (necesidad consolidada). Reporte de stock a la fecha vs.
  necesidad por material.
- **1.4 Restricciones de fruta**: dos restricciones posibles — productores
  que no pueden despacharse a un mercado, variedades que no pueden
  despacharse a un mercado. Se registran **por Programa de Ventas**
  (el programa define clientes/país/mercado): se selecciona un Programa de
  Ventas y se ingresan productores y variedades no permitidas.

### 3.2 Recepciones — hojas "RG" y "RE" (ya en Inventario/T40)

Doc: "Estas tres aplicaciones se incluyeron en el ticket 40 como mejoras
del módulo de inventario. Las funcionalidades se deben ejecutar también
desde Packing por estas opciones de menú." → **solo falta exponerlas en el
menú de Packing**, no reimplementar.

- **RG — Recepción Granel**: formulario de cabecera (Producto, UdM,
  Especie, Variedad, Unidad traslado, Cantidad UT, Embalaje, Cant.
  Embalaje, Kg recibidos) + pestaña "información adicional" (Guía
  productor, Fecha guía, Fundo, Código SGC, Fecha cosecha, Origen/clase,
  Tipo fruta orgánico/convencional, Pesaje por unidad de traslado/camión,
  Destare camión, Peso x envases, Destare envases, Neto fruta, Promedio) +
  pestaña "Fruta granel" con el detalle de **tarjas tipo C** generadas
  (N° tarja, peso bruto, destare, kg neto, cajas, promedio). Pide además
  **"crear una opción de cargar las operaciones desde un Excel"**.
- **RE — Recepción Embalado**: igual estructura de cabecera + información
  adicional, pero la pestaña de detalle genera **tarjas tipo E**
  (fruta ya embalada que llega así desde el productor/packing externo):
  N° tarja, Variedad, Producto, UdM, Embalaje, Etiqueta, Categoría,
  Calibre, Pallet, Cajas, Kilos. También pide **carga por Excel**.

### 3.3 Recepciones — hoja "CE" (Control de Envases) — **NUEVO, no implementado**

"Control de envases de cosecha con productores". Son envases que pueden
estar clasificados como activo fijo (no inventario realizable), que se
entregan a productores para transportar fruta.

- Movimientos: entrada con la fruta (se agregan líneas de registro), entrada
  por devolución, salida por emisión de guía de despacho.
- Cada productor tiene un **saldo** (cada productor = una ubicación virtual
  de inventario).
- Los envases son productos de Inventario: agregar en la ficha agrícola del
  producto el campo booleano **"Es envases cosecha"**.
- Pide: (1) app para cargar el inventario inicial en poder de productores,
  (2) cuenta corriente de envases por productor, (3) informe de saldo por
  envase y por productor.

### 3.4 Procesos — hoja "PROC" (Proceso de Packing / OT)

El proceso de packing consiste en: 1) crear la OT en base a la OP de
referencia, 2) definir la MP y recursos, 3) registrar las tarjas, 4) hacer
la cuadratura y cierre.

**Etapas operativas físicas** (contexto, no necesariamente pantallas
separadas): crear OT y definir fruta granel a procesar → retirar fruta del
frigorífico → vaciadores vacían a la máquina → selección visual adicional →
preparar materiales de embalaje → embaladores llenan/pesan/etiquetan →
fruta comercial se emite como tarjas N → paletizadoras emiten tarjas de
exportación E → enviar fruta comercial y exportación a frigorífico → cerrar
la OT. **Reglas de la OT**: mismo productor para todas las tarjas C y E del
proceso; misma variedad de fruta; puede haber varios formatos de embalaje
resultantes.

**Formulario de la OT — campos pedidos (hoja PROC) que hoy faltan en el
modelo `step.packing.production`:**

- Referencias: Programa de embalaje, Instructivo de Embalaje, Programa de
  venta, Pedido de venta.
- Datos generales: **Tipo Proceso** (ej. "Primer proceso"), Packing/planta,
  Fecha proceso, Exportadora, Cliente, Especie, Variedad, **Tipo Fruta**
  (Convencional/Orgánico), Productor, Fundo, Lote.
- Datos de línea: Línea, **Turno**, **Dotación**, **Hora inicio/fin**,
  **Rendimiento estándar de línea (kg/hora)**, **Horas efectivas**,
  **Total horas**.
- **Causas de detención de línea** (sub-tabla): causa, hora inicio, hora
  fin, total horas, comentario — con catálogo propio ("Causas detención
  líneas" en Configuraciones, ej. "Corte de luz", "Problema mecánico").
- **Indicadores calculados** al cerrar: kilos por trabajador, kilos por
  hora totales, kilos por hora-hombre efectiva, % hora ociosa, % calibres
  2J y superiores, peso promedio caja de cosecha, días de permanencia de
  los lotes, días desde la cosecha.
- **Desglose de kilos por calibre** (XL, J, 2J, 3J, 4J…) con % sobre el
  total de exportación.
- Config: agregar a Tipo de Proceso el campo selección **"categoría de
  proceso"** (ya implementado: `step_category` Embalaje/Corrección).
- Estados de la OT: Creado, Validado, Cerrado — (el documento complementario
  agrega Costeado y Contabilizado, ya reflejados en el modelo actual).
- **Dos apps móviles** (hoy hay una sola pantalla que cubre ambos casos,
  confirmar si el cliente quiere pantallas separadas):
  1. App para indicar/seleccionar tarjas de fruta a procesar (entrada C).
  2. App para tarjado/paletizaje (creación de tarjas E/N de salida).

### 3.5 Procesos — hoja "Mat" (Consumo de materiales)

Prácticamente vacía salvo dos notas explícitas del cliente:
- **"No se calcula el consumo por pallet"** — el consumo de materiales debe
  calcularse **por cada pallet/tarja de salida**, no solo como total
  agregado de la OT. La implementación actual (`_consume_packaging_materials`)
  calcula un consumo agregado por total de cajas de exportación de la OT,
  **no desglosado por pallet** — es un gap confirmado por el propio Excel.
- **"Hoja fruta"**: referencia a que los datos de la hoja "Fruta" (maestro)
  deben completarse con los datos reales del proceso, no quedar vacíos.

Del cuerpo del docx (sección "Cierre del proceso → Consumo de materiales"):
- Se aplica, para cada embalaje de exportación, la lista de materiales que
  corresponde (**proceso similar al que ya usa el módulo de Exportaciones**
  — o sea: BOM como dato de referencia, nunca una `mrp.production`; así se
  implementó en la reescritura de T41).
- El consumo genera una salida de inventario (concepto "operación
  fabricación", pero por traslado directo, no por una Orden de Fabricación
  real) de los materiales de embalaje desde la bodega de Packing.
- Hay un **proceso de revisión y aprobación** de los materiales consumidos:
  se pueden editar antes de aprobar y generar el consumo final. **No
  implementado** — hoy el consumo se genera y valida de una sola vez al
  cerrar, sin paso de revisión/edición previo.
- Consumo de materia prima (tarjas C): sin valor, porque la fruta para
  proceso se compra solo cuando resulta en fruta de exportación embalada.
- Entrada de inventario de fruta resultante:
  - **Exportación**: valorizada al precio del contrato del productor. El
    productor emite una factura mensual por la fruta de exportación. Hay
    que **configurar un diario "Compra fruta exportación"**. No
    implementado (valorización/facturación).
  - **Comercial, precalibre, desecho**: sin valor, se devuelven al
    productor (son de su propiedad). Confirmar que el movimiento de salida
    hacia el productor está modelado (hoy solo se registra el ingreso a
    bodega propia, no la devolución).
- Costos del proceso: **Etapa 2**, no implementar ahora.

### 3.6 Procesos — hoja "Repa" (Repaletizado)

Ya implementado como `step.packing.repack` y coincide bien con la hoja:
tarjas que salen / tarjas que entran, con Productor, Producto, Embalaje,
Pallet, Categoría, Etiqueta, Calibre, Variedad comercial, Cajas, Kilos. El
docx añade reglas ya cubiertas por el modelo actual: cantidad de cajas que
salen = las que entran, trazabilidad heredada, tarjas de entrada pueden ser
mixtas (varios productores), la variedad no cambia, no se mezclan tipos
C/E/N en un mismo proceso, tarjas salientes quedan "Repaletizada" y
entrantes "Validadas".

### 3.7 Procesos — hoja "Inf Pk" (Informes de Packing)

Hoja vacía en el Excel (sin maqueta). Del docx (3.3):
- **Informe de procesos**: resumen y detalle. Hoy solo existe el reporte
  PDF por OT individual (`report_packing_process`) — **falta un informe
  consolidado/resumen de varias OT** (por OP, por rango de fechas, etc.).
- **Informe de proceso al productor** (PDF): el propio docx dice
  "pendiente" — no es un gap, está marcado como diferido por el cliente.

### 3.8 Procesos — hoja "Res" (Reservas de Stock)

Hoja vacía. Del docx (3.4): reservar stock para procesos especiales, para
evitar que la fruta se use en otro proceso. Flujo: debe existir primero un
Instructivo de Embalaje → se reserva identificando la fruta asociada a ese
instructivo → al entrar a un proceso de Packing, se referencia el número
del instructivo en la reserva → existe un informe de fruta reservada.

Implementado como extensión de `step.export.stock.reservation`
(`step_packing_order_id`, `step_package_ids`, reservar/liberar). **Falta**:
vincular la reserva al **Instructivo de Embalaje** específico (hoy se
referencia a la Orden de Proceso completa, no a un instructivo puntual) y
el informe de fruta reservada. Falta también exponerla en el menú propio de
Packing (hoy solo se edita desde la vista heredada de Exportaciones).

### 3.9 Tarjas — hojas "tarja cosecha", "tarja exp", "tarja nac"

Las tres comparten la misma matriz de estados por tipo de tarja (clave para
validar que las transiciones de estado del sistema sean correctas):

| Estado | Cosecha (C) | Exportación (E) | Nacional (N) |
|---|---|---|---|
| Creada | x | x | x |
| Validada | x | x | x |
| Procesada | x | | |
| Repaletizada | x | x | x |
| Desp / Emb (despachada/embarcada) | x | x | x |
| Liquidada | | x | |
| Nula | x | x | x |

Confirmar contra el modelo real de tarjas (`stock.quant.package` extendido
por `step_inventory_fruit_tag`/`step_packing`) que **todas** estas
transiciones existen para el tipo de tarja correcto — en particular
"Desp/Emb" para C (hoy el flujo de T41 solo marca C como "processed", no
hay un estado de despacho para tarjas C) y "Liquidada"/"Nula" en general.

Campos de cabecera de cada tarja (para los formularios/reportes):
- **Tarja cosecha (C)**: N° tarja, Estado, Fecha, Orden de Trabajo, Especie,
  Fundo, Variedad, SDP, Centro de Costos, Ramada, Tipo Cosecha
  (Propio/Contratista), Pasada, Contratista, Cuadrilla, Fecha/hora
  inicio-cierre, Envase cosecha, Unidad traslado, Cantidad bultos, Kilos.
- **Tarja exportación (E)**: N° tarja, Estado, Fecha, Especie, Variedad,
  Tipo Fruta, Tipo tarja, Productor, Id Fundo, Embalaje, Pallet, Cantidad
  cajas, Kilos, Etiqueta, Categoría, Certificado, OT Proceso, Calidad,
  Packing, Calibre, Línea, Lote, Variedad comercial.
- **Tarja nacional (N)**: mismos campos que exportación (mismo formato de
  formulario).

### 3.10 Despacho — hojas "EM" (Instructivo de Embarque / Embarque-Despacho) y "PL" / "PL formato" (Packing List)

Del docx (sección 5): "Estas funciones indicadas en el menú sugerido están
desarrolladas en el módulo de Exportaciones y se deben ejecutar también
desde este menú de Packing" → **no reimplementar, solo exponer en el menú
de Packing** los accesos que ya existen en `step_export`.

- **EM — Instructivo de Embarque**: programa de venta, tipo embarque
  (marítimo/aéreo), número embarque, especie, nave, agencia aduana,
  POL-AOL/POD-AOD, consignee, notify, FFWW, datos de transporte
  internacional (naviera, contenedor, VGM, sello, booking, kg brutos,
  temperatura, termógrafo), totales (pallets, cajas, kilos netos, precio
  kg, precio caja, FOB factura, flete, otros, total US$) y detalle por
  pallet/tarja.
- **EM — Embarque/Despacho**: superset del instructivo, agrega Guía SII,
  DUS, BL-AWB, factura exportación, transporte local (empresa, chofer,
  RUT, patente, tipo camión, certificado SAG, fecha/hora salida, encargado
  despacho, contraparte) y el mismo detalle por pallet con factura real.
- **PL — Packing List**: reporte plano por pallet para el cliente/naviera,
  en inglés: Shipment, Vessel, ETD/ETA, Loading/Discharge port, Consignee,
  Fruit, Variety, Package, Lote, Folio calidad, Label, Quality, Type of
  fruit, Pallet, Contenedor, BL, Size/calibre, Box, Temp check, Grower
  number/name, Pack code, Packing, Origin variety/facility, Pack date.
- **PL formato**: layout de referencia visual del Packing List tradicional
  (cabecera Product/Exporter/Importer/POD/POL/Total boxes/Net weight +
  tabla CSP/Folio pallet/Variety/Date packing/CSG/Boxes/Net-Gross
  weight/Thermos/Calibre) — "adecuar formato para Odoo", es decir, el
  reporte final en Odoo no tiene que copiar el Excel pixel a pixel, solo
  contener esos datos.
- **EM informe** (hoja de referencia, data histórica de otro sistema,
  72 columnas): ejemplo de un informe de embarques muy granular usado
  antes por el proveedor. Columnas relevantes para diseñar a futuro el
  "Informe de embarques" (no es un requisito de UI, es solo catálogo de
  campos posibles): tarja, termógrafo, productor, lote, especie, variedad,
  tipo fruta, envase, etiqueta, categoría, calibre, cajas, kg, embarque,
  nave, transporte, zarpe, semana zarpe, bodega, contenedor, BL, mercado,
  puerto origen/destino, arribo, país, cliente, recibidor, broker,
  exportador, embalaje, fecha embalaje, centro costo, packing, guía
  despacho, factura, orden compra, DUS, naviera, agencia aduana, tipo
  camión, empresa transporte, guía productor, N° proceso packing, mes
  zarpe, central/nombre despacho packing, fecha embarque, tipo venta.

### 3.11 Maestros y Configuraciones

Doc: "desarrollados en el módulo de Exportaciones, deben ejecutarse
también desde este menú de Packing" → **menú pasante únicamente**.
Confirmar que cada uno de estos modelos ya existe antes de crear accesos
(la mayoría vive en `step_export`, `step_inventory_packing` o `step_packing`):

- Maestros: Productores, Productos, Embalajes.
- Configuraciones: Fruta, Especie, Grupo variedad, Variedad, Grupo de
  calibre, Calibre de fruta, Categoría de fruta, Packing (planta), Líneas
  de proceso, Tipo de proceso, Tipo de tarja, Estado de tarja, Causas
  detención líneas (esta última es nueva — no confirmado que exista ya un
  catálogo editable, ver 3.4).

## 4. Estado de implementación (actualizar aquí, no arriba)

_Última actualización: 02-10-2026, tras la reescritura arquitectónica de
T41 (eliminar dependencia de `mrp.production` y de las vistas de Studio) y
el agregado de portada/ícono propio. Pendiente: todo lo demás listado abajo._

### 4.1 Hecho

- [x] OP (`step.packing.order` + `step.packing.order.line`): cabecera,
  detalle, instructivo (como campo Html), restricciones de productor/
  variedad **a nivel de OP** (no de Programa de Ventas como pide el doc —
  revisar si corresponde mover), necesidad de materiales
  (`action_refresh_materials`, usa BOM como referencia).
- [x] OT (`step.packing.production`): modelo propio (ya no
  `_inherit mrp.production`), tarjas C de entrada / E-N de salida,
  cuadratura (kg input/export/comercial/precalibre/desecho/merma),
  validar/cerrar. Cierre mueve stock real con 3 traslados directos
  (consumo MP, consumo material de embalaje agregado por BOM, salida de
  producto terminado) — sin crear `mrp.production`.
- [x] Repaletizado (`step.packing.repack`): completo, coincide con la hoja.
- [x] Reservas de stock: extensión de `step.export.stock.reservation`
  (reservar/liberar), vinculada a la Orden de Proceso.
- [x] Reporte PDF por OT individual (`report_packing_process`).
- [x] App móvil única para registrar tarjas C/E/N por escaneo (cubre en una
  sola pantalla lo que el doc describe como dos apps).
- [x] Portada ejecutiva (dashboard OWL) + ícono propio + menú como app
  independiente (ya no cuelga de "Packing Fruta"/Studio).
- [x] Permisos propios (`stock.group_stock_user`, ya no requiere acceso a
  Fabricación).

### 4.2 Falta — accesos de menú a funcionalidad que YA EXISTE en otros módulos (bajo esfuerzo, alto impacto en la percepción de "módulo incompleto")

- [ ] Recepciones → Fruta a proceso / Fruta embalada (pasar a RG/RE de
  Inventario-T40).
- [ ] Procesos → Informes (falta el consolidado, ver 4.3) y exponer
  Reservas de Stock con su propio menú (hoy solo vía Exportaciones).
- [ ] Despacho → Instructivo Embarque / Embarque-Despacho / Packing List
  (pasar a las pantallas ya existentes en `step_export`).
- [ ] Maestros → Productores / Productos / Embalajes (pasar a los ya
  existentes).
- [ ] Configuraciones → Fruta / Especie / Grupo variedad / Variedad /
  Grupo de calibre / Calibre de fruta / Categoría de fruta / Packing /
  Líneas de proceso / Tipo de proceso / Tipo de tarja / Estado de tarja
  (pasar a los catálogos existentes; confirmar ubicación exacta de cada
  uno antes de enlazar).

### 4.3 Falta — funcionalidad nueva real (esfuerzo medio/alto)

- [ ] **Control de Envases con productores** (hoja CE): modelo nuevo
  completo — movimientos entrada/salida, cuenta corriente por productor
  (ubicación virtual), informe de saldo, campo "Es envases cosecha" en
  producto, app de carga de inventario inicial.
- [ ] **Campos de la OT que faltan** (hoja PROC): Tipo Proceso, Tipo Fruta,
  Fundo/SDP, Exportadora, Cliente, Lote, Turno, Dotación, Hora
  inicio/fin, Rendimiento estándar de línea, Horas efectivas, Total horas.
- [ ] **Causas de detención de línea**: catálogo + sub-tabla en la OT
  (causa, hora inicio, hora fin, total, comentario).
- [ ] **Indicadores calculados de la OT**: kg/trabajador, kg/hora,
  kg/hora-hombre efectiva, % hora ociosa, % calibres 2J+, peso promedio
  caja cosecha, días de permanencia del lote, días desde cosecha.
- [ ] **Desglose de kilos por calibre** en la cuadratura de la OT.
- [ ] **Consumo de materiales por pallet** (hoy es agregado por toda la
  OT — el Excel pide desglose por cada tarja/pallet de salida).
- [ ] **Paso de revisión/aprobación del consumo de materiales** antes de
  generar el consumo final (hoy se genera y valida de una sola vez).
- [ ] **Valorización de la fruta de exportación** al precio de contrato
  del productor + diario "Compra fruta exportación" + facturación mensual
  del productor.
- [ ] **Devolución al productor** de fruta comercial/precalibre/desecho
  (modelar la salida hacia el productor, no solo el ingreso a bodega
  propia).
- [ ] **Carga de recepciones (RG/RE) desde Excel** (pedido explícito en
  ambas hojas) — aunque RG/RE sean de Inventario/T40, el pedido de carga
  masiva por Excel es nuevo.
- [ ] **Informe consolidado de procesos** (resumen + detalle de varias OT,
  no solo el PDF individual por OT).
- [ ] **Vincular la reserva de stock al Instructivo de Embalaje** puntual
  (hoy se referencia la OP completa) + informe de fruta reservada.
- [ ] Revisar la **matriz de estados por tipo de tarja** (sección 3.9)
  contra el modelo real: falta confirmar "Desp/Emb" para tarjas C y el
  ciclo completo de "Liquidada"/"Nula" para los tres tipos.
- [ ] **Inspecciones** (SAG, Interna): el propio documento dice
  "pendiente" pero la tabla de etapas lo marca Etapa 1 — **confirmar con
  el cliente** antes de invertir esfuerzo aquí.

### 4.4 Explícitamente fuera de alcance por ahora

- Costeo de procesos (Etapa 2 completa): costos directos, asignación de
  costos, informes de costeo.
- Informe de proceso al productor en PDF (el propio docx lo marca
  "pendiente").

## 5. Archivos originales

- Docx: `ERP Steps Odoo- Packing.docx` — adjunto id 3123 del ticket 41.
- Excel: `Anexo1 Módulo de Packing.xlsx` — adjunto id 3124 del ticket 41,
  17 hojas: Menu, OP, PROC, Mat, Repa, Inf Pk, Res, tarja cosecha, tarja
  exp, tarja nac, RG, RE, CE, EM, PL, PL formato, EM informe.

Si el cliente adjunta una versión nueva de estos archivos en el ticket,
hay que repetir la conversión (no asumir que este documento sigue vigente
sin comparar fechas de adjunto).
