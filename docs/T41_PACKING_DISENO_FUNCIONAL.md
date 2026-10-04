# T41 — Módulo de Packing: diseño funcional (convertido de Word)

> Convertido desde `ERP Steps Odoo- Packing.docx` (adjunto del ticket 41 de
> Helpdesk, id de adjunto 3123, subido 2026-09-30). Texto íntegro, solo
> reorganizado en encabezados Markdown para navegar más fácil. Ver también
> [T41_PACKING_ANEXO1_EJEMPLOS.md](T41_PACKING_ANEXO1_EJEMPLOS.md) (el Excel
> de 17 hojas con ejemplos y formatos) y la sección "Estado de implementación"
> al final de este documento.

## Resumen del módulo

Es un módulo que consiste en registrar los procesos necesarios para
convertir la fruta a granel para proceso en una fruta embalada con calidad
y atributos para ser exportada cumpliendo las normas y exigencias de los
clientes.

**El ciclo de packing es:** la fruta recibida es almacenada en frío bajo
condiciones y normas estrictas, luego es embalada en distintos formatos o
embalajes, es inspeccionada en forma interna y también por el SAG,
embarcada de acuerdo a instrucciones de embarque. Durante todos los
procesos hay una serie de servicios que se cobran y que tienen costos de
los recursos empleados.

Se ha previsto desarrollar por etapas este módulo. Menú sugerido (ver hoja
`Menu` del anexo): en color violeta la etapa 2, en color celeste lo que ya
existe, en color café lo que se desarrolla en esta etapa 1.

## 1. Planificación

### 1.1 Orden de Proceso (OP)

Es una funcionalidad que entrega las orientaciones generales de la fruta
que se requiere por semana indicando las prioridades de los pedidos a
surtir. Están referidos a un programa de ventas y generalmente se hace
para la semana siguiente. Se pueden incluir en una misma OP varias
especies, productos-embalajes con detalle de los atributos. Posteriormente
hay una comparación entre el programa y lo embarcado en la realidad para
el packing asignado.

### 1.2 Instructivo de Embalaje

Es un documento que describe aspectos técnicos que debe cumplir la fruta
en calidad y condición y el detalle de los embalajes. Este instructivo se
adjunta como documento de la Orden de Producción.

### 1.3 Necesidades de materiales

En la orden de proceso se indican la cantidad de cajas por embalaje. Con
esta información se calculan los materiales de embalajes a utilizar
aplicando la lista de materiales. Se hace para una OP, varias o todas,
para generar necesidad consolidada. Se genera un reporte que compara stock
a la fecha versus necesidades por cada material.

### 1.4 Restricciones de fruta

Consiste en registrar dos grandes restricciones que se pueden dar en el
negocio: productores que no pueden despacharse a un mercado, y variedades
que no pueden despacharse a un mercado. Para ello se registran las
restricciones de productores y variedades por programa de ventas. El
programa contiene clientes, país y por tanto mercado. Se selecciona un
Programa de Ventas y se ingresan los productores no permitidos y
variedades no permitidas.

## 2. Recepciones

Estas tres aplicaciones (Fruta a proceso, Fruta embalada, Control de
Envases) se incluyeron en el **ticket 40** como mejoras del módulo de
Inventario. Las funcionalidades se deben ejecutar también desde Packing
por estas opciones de menú. Para efectos de referencia están en el anexo 1
en las hojas `RG`, `RE`, `CE`.

## 3. Procesos

### 3.1 Proceso de Packing (OT)

Es la transformación de la materia prima (fruta granel para proceso) en
producto terminado. El proceso se ejecuta en modernas máquinas de alta
tecnología que clasifican la fruta, la seleccionan y las vacían en salidas
programadas por calibres y calidades. En las salidas hay trabajadores
llenando cajas de distintos formatos que se etiquetan y finalmente se
paletizan.

**Las etapas operativas son:**
1. Crear una OT y definir la fruta granel que se va a procesar.
2. Retirar la fruta desde las bodegas de almacenamiento en frío (frigorífico).
3. Vaciadores: ir vaciando la fruta granel a la máquina.
4. Selección: seleccionar visualmente la fruta adicional al proceso automatizado de la máquina.
5. Materiales: preparar los materiales de embalajes de las cajas que se usarán y proveer los materiales al personal de embalaje (embaladores/as).
6. Embaladores: llevar la fruta en los formatos de embalajes, pesar algunos envases, y etiquetar la caja.
7. Fruta comercial: llenar los envases con la fruta no exportable. Emitir las tarjas nacionales (N).
8. Paletizadoras: paletizar la fruta siguiendo las normas de paletizado y emitir las tarjas de exportación (E).
9. Enviar la fruta comercial y exportaciones a las bodegas de frigorífico.
10. Cerrar el proceso u Orden de Trabajo.
11. Control de calidad en la MP que ingresa, la fruta nacional resultante y la fruta de exportación.

**Una OT de packing obedece a ciertas reglas:**
- Debe ser el mismo productor para todas las tarjas C y E del proceso.
- Debe ser la misma variedad de fruta.
- Hay varios formatos resultantes de fruta (embalajes).

**Configuraciones:** Tipo de procesos — agregar campo de selección
"categoría de proceso".

**Las etapas de la funcionalidad de proceso Packing son:**
1. Crear la OT (Orden de Trabajo) de packing en base a la OP (Orden de producción) de referencia.
2. Definir la MP y recursos que se usará en la OT.
3. Registrar las tarjas (pallets).
4. Hacer la cuadratura, cierre de la OT y costear.

**Crear una OT / formulario de registro.** Estados de la OT: Creado,
Validado, Cerrado, Costeado, Contabilizado.

**Materia Prima / Lotes a procesar.** Existen dos formas de registro:
llenar el formulario del ERP (al poner el número de tarja se completan los
demás datos), y una aplicación móvil.

**Registro de las tarjas de fruta comercial.** Cada vez que se termina una
tarja de fruta comercial llenando el formulario del anexo 1 hoja "tarja
nac", esta tarja queda en estado creada pero asociada a la OT. Se puede
hacer por medio de la app móvil.

**Registro de las tarjas de fruta exportación.** Cada vez que se termina
una tarja de fruta exportación llenando el formulario del anexo 1 hoja
"tarja exp", esta tarja queda en estado creada asociada a la OT. Se puede
hacer por medio de la app móvil.

#### App móvil

Desarrollar una app móvil que cargue los datos generales de la OT y
permita escanear el código QR de la tarja y adicionarla a la sección del
formulario. La tarja puede tener un código de barra en donde esté el
número de la tarja y permitir también hacer esta lectura.

Las opciones son el registro de los tres tipos de tarjas para tres
usuarios diferentes: Tarjas de Cosecha, Tarjas Nacionales, Tarjas
Exportación.

**Características de la app:** puede estar en línea, puede trabajar en
modo offline, puede estar conectada a una impresora para imprimir las
tarjas que vaya generando y pegarlas al respectivo pallet.

#### Cierre de la OT

Una vez que se ha procesado toda la partida y se han registrado todas las
tarjas, se procede a ejecutar el cierre y cuadratura del proceso, que se
presenta en el siguiente formulario.

**Cuadratura:**
- Kilos totales a proceso: suma de kilos de las tarjas C enviadas al proceso.
- Kilos exportación: suma de kilos de las tarjas E como resultado del proceso.
- Kilos comercial: suma de kilos de las tarjas N resultado del proceso con categoría "Comercial".
- Precalibre: suma de kilos de las tarjas N resultado del proceso con categoría "Precalibre".
- Desecho: suma de kilos de las tarjas N resultado del proceso con categoría "Desecho".
- Merma: diferencia entre kilos no justificado para cuadrar el proceso.

Cuando el proceso cuadra está en estado validado y las tarjas también en
estado validado.

**Cierre del proceso** es un botón de acción que deja el proceso en estado
cerrado y genera los siguientes efectos:

- **Consumo de materiales**: se aplica para cada embalaje de exportación
  la lista de materiales que le corresponde y se produce el consumo de los
  materiales (proceso similar ejecutado en el módulo de exportaciones).
  Hay un proceso de revisión y aprobación de estos materiales consumidos y
  en esta etapa se pueden editar y finalmente aprobar y generar el consumo
  final. Este consumo de materiales genera un movimiento de salida de
  inventario (operación fabricación) de los materiales de embalajes de la
  bodega packing. En el anexo 1, hoja "Mat", se muestra la función
  estándar de Odoo.

  **Falta ajustar la aplicación en lo siguiente:**
  - Integrar módulo packing con la funcionalidad de fabricación de Inventario.
  - No se calcula el consumo de materiales asociados a pallet.
  - No se completan los datos de la hoja "Fruta"; deben cargarse con los datos del proceso.

- **Consumo de Materia Prima** con salida a fabricación por las tarjas
  tipo C. Sin valor, porque la fruta para proceso ingresada se compra solo
  la fruta para exportación que resulta embalada.

- **Entrada de inventario de fruta resultante del proceso:**
  - Fruta exportación: valorizada al precio del contrato del productor. El productor emitirá una factura mensual por la fruta de exportación. Se debe configurar un diario de "compra fruta exportación".
  - Comercial: sin valor porque esta fruta se devuelve al productor porque es de su propiedad.
  - Precalibre: sin valor, misma razón.
  - Desecho: sin valor, misma razón.

- **Costos del proceso:** se aborda en la etapa 2.

### 3.2 Repaletizado

Es un proceso de la tabla de tipos de procesos que pertenece al grupo de
corrección. Consiste en la modificación de tarjas en estado vigente
principalmente que están con llenado parcial, de tal forma que en este
proceso se generan nuevas tarjas a partir de otras tarjas: tarjas que
salen (a repaletizado) y tarjas que entran (de repaletizado).

**Las reglas de este proceso son:**
- La cantidad de cajas que salen son las mismas que entran en otras tarjas.
- Las tarjas que entran heredan la trazabilidad de las que salen.
- Las tarjas que entran pueden ser mixtas, es decir, se pueden juntar dos o más productores en una tarja que entra.
- La variedad de las tarjas que salen es la misma de la variedad de las tarjas que entran. No puede cambiar ningún otro atributo: calidad, categoría, calibre, embalaje.
- Se pueden repaletizar cualquier tipo de tarjas: C, E o N, pero nunca se juntan en un mismo proceso.

Formulario de registro. Las tarjas que salen quedan con estado
"Repaletizada". Las tarjas que entran quedan en estado Validadas. La línea
de proceso identifica la tarja física.

### 3.3 Informes de packing

- Informe de procesos: resumen y detalle.
- Informe de proceso al productor (formato en PDF — pendiente).

### 3.4 Reservas de Stock

Es una función que permite reservar stock para procesos especiales, de tal
forma de evitar que la fruta sea utilizada en otro proceso.

**Para hacer la reserva los pasos son:**
1. Debe existir primero la creación de un Instructivo de Embalaje.
2. Ingresar a la opción de reserva identificando la fruta que se asocia al instructivo.
3. Cuando se ingrese a un proceso de packing se debe ingresar en la sección de referencia el número del instructivo de embalaje.
4. Existirá un informe de la fruta reservada.

## 4. Inspecciones

*(pendiente)*

## 5. Despacho

Estas funciones indicadas en el menú sugerido están desarrolladas en el
módulo de Exportaciones y se deben ejecutar también desde este menú de
Packing.

## 7. Maestros

Estos maestros indicados en el menú sugerido están desarrollados en el
módulo de Exportaciones y se deben ejecutar también desde este menú de
Packing.

## Configuraciones

Estas configuraciones indicadas en el menú sugerido están desarrolladas en
el módulo de Exportaciones y se deben ejecutar también desde este menú de
Packing.

## Tabla de etapas de desarrollo

| Proceso | Módulo origen información | Etapas de desarrollo |
|---|---|---|
| 1. Planificación | Packing | Etapa 1 |
| 2. Recepciones fruta | Inventario | Etapa 1 (en inventario) |
| 3. Inspecciones de entrada | Packing | Etapa 1 *(nota: el cuerpo del documento dice "pendiente" para Inspecciones — hay una contradicción entre la tabla y el texto; confirmar con el cliente antes de implementar)* |
| 4. Proceso Embalaje de fruta | Packing | Etapa 1 |
| 5. Despachos y embarques | Packing - Exportaciones | Etapa 1 (ok en exportaciones) |
| 6. Costeo de procesos | Packing | Etapa 2 |

---

## Estado de implementación (actualizado 2026-10-02)

Worktree: `C:\Users\tito4\.codex\worktrees\ticket41-packing\Odoo`, rama
`codex/t41-packing-operations`, módulo `step_packing_operations`.

| # | Requisito | Estado |
|---|---|---|
| 1.1 | Orden de Proceso (OP) | ✅ Hecho — `step.packing.order`, standalone, con líneas, instructivo, validación |
| 1.2 | Instructivo de Embalaje | ✅ Hecho — campo `instruction` (Html) en la OP |
| 1.3 | Necesidades de materiales | ✅ Hecho — `action_refresh_materials`, usa BOM como referencia (patrón Exportaciones) |
| 1.4 | Restricciones de fruta (productor/variedad) | ✅ Hecho — `forbidden_producer_ids`/`forbidden_variety_ids` en la OP |
| 2 | Recepciones (RG/RE/CE) — acceso también desde Packing | ❌ **Falta** — ya existen en Inventario (T40) pero el menú de Packing no tiene entradas que apunten a esas acciones |
| 3.1 | Crear OT en base a OP | ✅ Hecho — `action_create_production` desde la línea de la OP |
| 3.1 | OT como modelo propio (no Fabricación) | ✅ Hecho (02-10-2026) — antes heredaba `mrp.production`, se corrigió a `step.packing.production` standalone |
| 3.1 | Registro de tarjas C/E/N vía formulario y app móvil | ✅ Hecho — formulario (m2m en la OT) + `/packing/mobile` con escaneo QR/código de barra |
| 3.1 | Reglas de OT (mismo productor, misma variedad) | ✅ Hecho — `_check_packing_tags` |
| 3.1 | Cuadratura (kilos input/export/comercial/precalibre/desecho/merma) | ✅ Hecho — `_compute_packing_balance` |
| 3.1 | Cierre: consumo de materiales de embalaje (BOM como referencia) | ✅ Hecho (02-10-2026) — `_consume_packaging_materials`, solo tarjas de exportación |
| 3.1 | Cierre: no completa datos de hoja "Fruta" / diario "compra fruta exportación" / valorización al precio de contrato del productor | ❌ **Falta** — no implementado; requiere definir con el cliente el diario contable y cómo se obtiene el precio de contrato |
| 3.1 | Hoja "Fruta" (anexo `Mat`, fila 32) | ❌ **Falta** — no identificado qué modelo/reporte es exactamente; aclarar con el cliente |
| 3.2 | Repaletizado (C/E/N, mixto, hereda trazabilidad) | ✅ Hecho — `step.packing.repack` |
| 3.3 | Informe de procesos: resumen y detalle | ⚠️ **Parcial** — hay un reporte PDF por OT individual (`report_packing_process`); falta un informe consolidado tipo "resumen" de varias OT |
| 3.3 | Informe de proceso al productor (PDF) | ⏸️ El propio documento dice "pendiente" |
| 3.4 | Reservas de Stock ligadas a instructivo de embalaje | ✅ Hecho — extiende `step.export.stock.reservation` con `step_packing_order_id` |
| 4 | Inspecciones (SAG, interna) | ⏸️ El propio documento dice "pendiente" (pero la tabla dice Etapa 1 — aclarar) |
| 5 | Despacho/Embarque — acceso también desde Packing | ❌ **Falta** — funcionalidad existe en `step_export`, pero el menú de Packing no tiene entradas hacia Embarque/Despacho/Packing List |
| 6 | Costeo de procesos | Etapa 2, no corresponde ahora |
| 7 | Maestros — acceso también desde Packing | ❌ **Falta** — igual que Despacho, existen en Exportaciones pero no están enlazados desde el menú de Packing |
| — | Configuraciones — acceso también desde Packing | ❌ **Falta** — igual, existen en Exportaciones pero no enlazadas desde Packing |
| — | Ícono y portada propia de la app | ✅ Hecho (02-10-2026) — ícono + dashboard OWL con KPIs de OP/OT |

**Lectura del cliente ("llevamos un 10%, falta el 90%"):** gran parte de lo
que falta es **enlazar desde el menú de Packing** funcionalidad que YA
EXISTE en otros módulos (Recepciones en Inventario, Despacho/Maestros/
Configuraciones en Exportaciones) — el propio documento lo dice
explícitamente para los puntos 2, 5, 7 y Configuraciones. Eso es rápido de
resolver (agregar `<menuitem>` que apunten a las acciones ya existentes).
Lo genuinamente nuevo que falta es: valorización/diario contable del
cierre de OT (3.1), la hoja "Fruta" sin identificar, y el informe
consolidado de procesos (3.3).
