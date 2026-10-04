# Anexo 1 — Módulo de Packing (ejemplos y formatos)

> Convertido desde `Anexo1 Módulo de Packing.xlsx` (adjunto del ticket 41 de Helpdesk, id de adjunto 3124). Cada tabla es una hoja del Excel original, celda por celda (columna = letra de columna Excel), para conservar el layout tal como lo armó el cliente. Las celdas vacías se muestran en blanco.

## Índice de hojas

- [Menú sugerido del módulo](#menú-sugerido-del-módulo)
- [OP — Orden de Proceso (ejemplo)](#op--orden-de-proceso-ejemplo)
- [PROC — Proceso de Packing / OT (ejemplo y flujo)](#proc--proceso-de-packing--ot-ejemplo-y-flujo)
- [Mat — Consumo de materiales (notas)](#mat--consumo-de-materiales-notas)
- [Repa — Repaletizado (ejemplo)](#repa--repaletizado-ejemplo)
- [Inf Pk — Informes de Packing (placeholder, sin detalle)](#inf-pk--informes-de-packing-placeholder,-sin-detalle)
- [Res — Reservas de Stock (placeholder, sin detalle)](#res--reservas-de-stock-placeholder,-sin-detalle)
- [Tarja de Cosecha (C) — formato y estados](#tarja-de-cosecha-c--formato-y-estados)
- [Tarja de Exportación (E) — formato y estados](#tarja-de-exportación-e--formato-y-estados)
- [Tarja Nacional (N) — formato y estados](#tarja-nacional-n--formato-y-estados)
- [RG — Recepción Granel (ya en Inventario/T40)](#rg--recepción-granel-ya-en-inventariot40)
- [RE — Recepción Embalado (ya en Inventario/T40)](#re--recepción-embalado-ya-en-inventariot40)
- [CE — Control de Envases de Cosecha con Productores](#ce--control-de-envases-de-cosecha-con-productores)
- [EM — Instructivo de Embarque / Embarque-Despacho (ya en Exportaciones)](#em--instructivo-de-embarque--embarque-despacho-ya-en-exportaciones)
- [PL — Informe Packing List (ejemplo de datos)](#pl--informe-packing-list-ejemplo-de-datos)
- [PL formato — Formato de referencia Packing List](#pl-formato--formato-de-referencia-packing-list)
- [EM informe — Informe de Embarques (export legado, ejemplo de campos)](#em-informe--informe-de-embarques-export-legado,-ejemplo-de-campos)


## Menú sugerido del módulo

_Hoja original: `Menu`_

| A | B | C | D | E | F | G | H | I | J | K | L | M | N | O | P | Q |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| MODULO DE PACKING |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| Inicio | Planificación | Recepciones | Procesos | Inspecciones | Despacho | Costos de proceso | Maestros | Configuraciones |  |  |  |  |  |  |  |  |
| Panel | Orden de Proceso | Fruta a proceso | Proceso de Packing | Inspección SAG | Instructivo Embarque | Costos directos | Productores | Fruta |  |  |  |  |  |  |  |  |
|  | Instructivo Embalaje | Fruta embalada | Repaletizado | Inspección Interna | Embarque / Despacho | Asignación de costos | Productos | Especie |  |  |  |  |  |  |  |  |
|  | Necesidades de materiales | Control de Envases | Informes |  | Packing List | Informes | Embalajes | Grupo variedad |  |  |  |  |  |  |  |  |
|  | Restricciones de fruta |  | Reservas de Stock |  |  |  |  | Variedad |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  | Grupo de calibre |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  | Calibre de fruta |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  | Categoría de fruta |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  | Packing |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  | Líneas de proceso |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  | Tipo de proceso |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  | Tipo de tarja |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  | Estado de tarja |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  | Causas detención líneas |  |  |  |  |  |  |  |  |


## OP — Orden de Proceso (ejemplo)

_Hoja original: `OP`_

| A | B | C | D | E | F | G | H | I | J | K | L | M |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ORDEN DE PROCESO |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |
| Número OP |  | OP W47 001 |  | Fecha | 2026-11-05 |  |  |  |  |  |  |  |
| Fecha producción |  | 09 al 15/11/2026 |  | Semana | 46 |  |  |  |  |  |  |  |
| Programa de ventas |  | Caja 5 kg |  | Packing | San Fernando |  |  |  |  |  |  |  |
| Especie |  | Cerezas |  | País | USA |  |  |  |  |  |  |  |
| ETD |  |  |  | Exportadora | Steps |  |  |  |  |  |  |  |
| ETA |  |  |  | Recibidor | JAC |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |
| Detalle: |  |  |  |  |  |  |  |  |  |  |  |  |
| Especie | Variedad | Tipo Fruta | Producto | Embalaje | Etiqueta | Calidad | Calibre | Categoría | Pallet | Cajas | Kilos | Tipo inspección |
| Cerezas | Todas | Convencional | CE501 Cer exp | Cj gr 5 kg | Steps | C! | 2j a 4 j | Cat 1 | 80 | 14880 | 74400 | Usda |
|  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  | 80 | 14880 | 74400 |  |


## PROC — Proceso de Packing / OT (ejemplo y flujo)

_Hoja original: `PROC`_

| A | B | C | D | E | F | G | H | I | J |
|---|---|---|---|---|---|---|---|---|---|
| PROCESO DE PACKING |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |
| El proceso de packing consiste en: |  |  |  |  |  |  |  |  |  |
| 1) Crear la OT (Orden de Trabajo) de packing en base a la OP (Orden de producción) de referencia |  |  |  |  |  |  |  |  |  |
| 2) Definir la MP y recursos que se usará en la OT |  |  |  |  |  |  |  |  |  |
| 3) Registrar las tarjas (pallets) |  |  |  |  |  |  |  |  |  |
| 4) hacer la cuadratura y cierre de la OT |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |
| Crear OT |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |
| Referencias |  |  |  |  |  |  |  |  |  |
| Programa de embalaje |  |  |  | Programa de venta |  |  |  |  |  |
| Instructivo de Embalaje |  |  |  | Pedido de venta |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |
| Datos generales: |  |  |  |  |  |  |  |  |  |
| Tipo Proceso | Primer proceso |  |  | Packing | San Fernando |  |  |  |  |
| Número Proceso (OT) | 2627 W35-0001 |  |  | Fecha proceso | 2026-11-10 |  |  |  |  |
| Exportadora | Cerro El Plomo |  |  | Cliente |  |  |  |  |  |
| Especie | Cerezas |  |  | Variedad | Santina |  |  |  |  |
| Tipo Fruta | Convencional |  |  | Productor |  |  |  |  |  |
| Fundo | El Sapo | SDP |  | Lote |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |
| Datos de líneas |  |  |  |  |  |  |  |  |  |
| Línea | 1 |  |  | Dotación | 60 |  |  |  |  |
| Turno | 1 |  |  | Hr Inicio | 08:00 |  |  |  |  |
| Rendimiento St Línea | 2800 | kg x hora |  | hr Fin | 14:00 |  |  |  |  |
| Horas efectivas | 05:10 |  |  | Total horas | 06:00 |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |
| Causa detenciones | Hr Inicio | Hora fin | Total hrs | Comentario |  |  |  |  |  |
| Corte de luz |  |  | 00:15 | Falla en exterior |  |  |  |  |  |
| Problema mecánico |  |  | 00:35 |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |
| Total detenciones |  |  | 00:50 |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |
| Lotes a procesar (selección o registro de tarjas que cumplen con filtros de datos generales) |  |  |  |  |  |  |  |  |  |
| Tarjas (C ) | Fecha Recepción | Variedad | Cajas | Kilos | Calidad | Fecha Cosecha |  |  |  |
| C 2026 00015 | 2026-11-07 | Santina | 35 | 315 | A1 | 2026-11-07 |  |  |  |
| C 2026 00016 | 2026-11-07 | Santina | 35 | 315 | A1 | 2026-11-07 |  |  |  |
| C 2026 00017 | 2026-11-07 | Santina | 35 | 315 | A1 | 2026-11-07 |  |  |  |
| C 2026 00018 | 2026-11-07 | Santina | 35 | 315 | A1 | 2026-11-07 |  |  |  |
| C 2026 00019 | 2026-11-07 | Santina | 35 | 315 | A1 | 2026-11-07 |  |  |  |
|  |  |  |  |  |  |  |  |  |  |
| Otras tarjas | 2026-11-07 |  | 1400 | 12600 |  | 2026-11-07 |  |  |  |
|  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |
|  |  |  | 1575 | 14175 |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |
| Registro de Tarjas Exportación |  |  |  |  |  |  |  |  |  |
| Num Tarja (E ) | Producto | Embalaje | Pallet | Categoría | Etiqueta | Calibre | Variead Com | Cajas | Kilos |
| E 2627 0011 | CE501 Caj cereza | CJ 5 kg | Pall cer | Cat 1 | Steps | 2J | Santina | 186 | 930 |
| E 2627 0012 | CE501 Caj cereza | CJ 5 kg | Pall cer | Cat 1 | Steps | 3J | Santina | 186 | 930 |
| E 2627 0013 | CE501 Caj cereza | CJ 5 kg | Pall cer | Cat 1 | Steps | 4J | Santina | 186 | 930 |
| E 2627 0014 | CE501 Caj cereza | CJ 5 kg | Pall cer | Cat 1 | Steps | J | Santina | 186 | 930 |
|  | CE501 Caj cereza | CJ 5 kg | Pall cer | Cat 1 | Steps | XL | Santina | 186 | 930 |
| varias | CE501 Caj cereza | CJ 5 kg | Pall cer | Cat 1 | Steps | 2J | Santina | 558 | 2790 |
|  | CE501 Caj cereza | CJ 5 kg | Pall cer | Cat 1 | Steps | J | Santina | 372 | 1860 |
|  | CE501 Caj cereza | CJ 5 kg | Pall cer | Cat 1 | Steps | 3J | Santina | 372 | 1860 |
|  | CE501 Caj cereza | CJ 5 kg | Pall cer | Cat 1 | Steps | 4J | Santina | 186 | 930 |
|  |  |  |  |  |  |  |  | 2418 | 12090 |
|  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |
| Registro de tarjas Nacionales |  |  |  |  |  |  |  |  |  |
| Num Tarja (N ) | Producto | Embalaje | Pallet | Categoría | Etiqueta | Calibre | Variead Com | Cajas | Kilos |
| N 2627 0135 |  |  | Bins | Comercial |  |  | Santina | 1 | 300 |
| Varios |  |  |  | Comercial |  |  |  | 3 | 900 |
| N 2627 0137 |  |  |  | Comercial |  |  |  | 2 | 500 |
| N 2627 0138 |  |  |  | Desecho |  |  |  | 1 | 100 |
|  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  | 7 | 1800 |
|  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |
| Cierre de proceso |  |  |  |  |  |  |  |  |  |
| Cuadratura |  | kilos | Kilos |  | Cajas |  | Indicadores: |  |  |
| Kilos Totales a proceso |  | 14175 |  |  | 1575 |  | Kilos x trabajador |  | 236.2 |
|  |  |  |  |  |  |  | Kilos por hr totales |  | 2362 |
| kilos exportación |  |  | 12090 | 0.8529 | 2418 |  | kilos por hh efectivas |  | 2779 |
| Kilos Comercial |  |  | 1700 | 0.1199 | 7 |  | % Hr ocio |  | 0.1389 |
| Precalibre |  |  | 0 | 0 |  |  | % Calibres 2J up |  | 0.6923 |
| Desecho |  |  | 100 | 0.007055 |  |  | Peso prom Cj cosecha (kg) |  | 9 |
| merma |  |  | 285 | 0.02011 |  |  | Días permanencia Lotes |  | 3 |
|  |  | 14175 | 14175 | 1 |  |  | Días desde la cosecha |  | 3 |
|  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  | Calibres | kilos | % |
| Estados del proceso |  |  |  |  |  |  | XL | 930 | 0.07692 |
| Creado |  |  |  |  |  |  | J | 2790 | 0.2308 |
| Validado |  |  |  |  |  |  | 2J | 3720 | 0.3077 |
| Cerrado |  |  |  |  |  |  | 3J | 2790 | 0.2308 |
|  |  |  |  |  |  |  | 4J | 1860 | 0.1538 |
|  |  |  |  |  |  |  |  | 12090 | 1 |
| Aplicaciones móviles de packing |  |  |  |  |  |  |  |  |  |
| App para indicar tarjas de fruta a proceso |  |  |  |  |  |  |  |  |  |
| App para tarjado (paletizaje) |  |  |  |  |  |  |  |  |  |


## Mat — Consumo de materiales (notas)

_Hoja original: `Mat`_

| A | B | C | D | E | F | G | H | I | J | K | L | M |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| CONSUMO DE MATERIALES |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  | no se calcula el consumo por pallet |
|  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |
| Hoja fruta |  |  |  |  |  |  |  |  |  |  |  |  |


## Repa — Repaletizado (ejemplo)

_Hoja original: `Repa`_

| A | B | C | D | E | F | G | H | I | J | K |
|---|---|---|---|---|---|---|---|---|---|---|
| REPALETIZADO |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |
| Tipo Proceso | Repaletizaje |  |  | Packing | San Fernando |  |  |  |  |  |
| Número Proceso (OT) | 2627 W35-00011 |  |  | Fecha proceso | 2026-11-10 |  |  |  |  |  |
| Especie | Cerezas |  |  | Variedad | Santina |  |  |  |  |  |
| Tipo Fruta | Convencional |  |  | Línea | Repaletizaje |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |
| Tarjas que salen |  |  |  |  |  |  |  |  |  |  |
| Num Tarja (E ) | Productor | Producto | Embalaje | Pallet | Categoría | Etiqueta | Calibre | Variead Com | Cajas | Kilos |
| E 2627 0099 | Agr Los Cedros | CE501 Caj cereza | CJ 5 kg | Pall cer | Cat 1 | Steps | 2J | Santina | 100 | 500 |
| E 2627 0100 | Los tomates | CE501 Caj cereza | CJ 5 kg | Pall cer | Cat 1 | Steps | 3J | Santina | 86 | 430 |
|  |  |  |  |  |  |  |  |  | 186 | 930 |
|  |  |  |  |  |  |  |  |  |  |  |
| Tarja que entra |  |  |  |  |  |  |  |  |  |  |
| Num Tarja (E ) | Productor | Producto | Embalaje | Pallet | Categoría | Etiqueta | Calibre | Variead Com | Cajas | Kilos |
| E 2627 0200 | Agr Los Cedros | CE501 Caj cereza | CJ 5 kg | Pall cer | Cat 1 | Steps | 2J | Santina | 100 | 500 |
| E 2627 0200 | Los tomates | CE501 Caj cereza | CJ 5 kg | Pall cer | Cat 1 | Steps | 2J | Santina | 86 | 430 |
|  |  |  |  |  |  |  |  |  | 186 | 930 |


## Inf Pk — Informes de Packing (placeholder, sin detalle)

_Hoja original: `Inf Pk`_

| A |
|---|
| INFORMES DE PACKING |


## Res — Reservas de Stock (placeholder, sin detalle)

_Hoja original: `Res`_

_(hoja vacía / sin detalle en el anexo)_


## Tarja de Cosecha (C) — formato y estados

_Hoja original: `tarja cosecha`_

| A | B | C | D | E | F | G | H | I | J | K |
|---|---|---|---|---|---|---|---|---|---|---|
| #VALUE! | TARJA DE COSECHA |  |  |  |  |  |  |  |  |  |
|  | C 00000000 |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |
|  |  |  | Estado | Validada |  |  |  |  |  |  |
| Fecha | 2026-09-03 |  | Orden de Trabajo | 25 W36 CP01-0199 |  |  |  |  |  |  |
| Especie | Arándanos |  | Fundo | Fundo El Sapo |  |  |  |  |  |  |
| Variedad | Cruch |  | SDP | 125256 |  |  |  |  |  |  |
| Centro Costos | Arándanos Cruch 2015 |  | Ramada | 1 |  |  |  |  |  |  |
| Tipo Cosecha | Para proceso |  | Pasada | 1 |  |  |  |  |  |  |
| Contratista | Propio |  | Cuadrilla | CP01 JSoto |  |  |  |  |  |  |
| Fecha hr Inicio | 2026-09-03 09:30 |  | Fecha hr cierre | 2026-09-03 10:30 |  |  |  |  |  |  |
| Envase cosecha | Caja 4 kilos |  | Unidad traslado | Pallet |  |  |  |  |  |  |
| Cantidad bultos | 60 |  | kilos | 240 |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  | #VALUE! |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  | Estados por tipo tarja |  |  |  |  |  |
|  |  |  |  |  | Estados: |  | Cosecha (C ) | Exportación (E ) | Nacional (N) |  |
|  |  |  |  |  | Creada |  | x | x | x |  |
|  |  |  |  |  | Validada |  | x | x | x |  |
|  |  |  |  |  | Procesada |  | x |  |  |  |
|  |  |  |  |  | Repaletizada |  | x | x | x |  |
|  |  |  |  |  | Desp / Emb |  | x | x | x |  |
|  |  |  |  |  | Liquidada |  |  | x |  |  |
|  |  |  |  |  | Nula |  | x | x | x |  |


## Tarja de Exportación (E) — formato y estados

_Hoja original: `tarja exp`_

| A | B | C | D | E | F | G | H | I | J | K | L | M | N | O |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| LA TARJA DE CREA EN EL PROCESO DE RECPECIÓN DE FRUTA EMBALADA O EN EL PROCESO DE PACKING |  |  |  |  |  |  |  |  |  | REGISTRO DE UNA TARJA EN EL SISTEMA |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  | documento a emitir |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  | #VALUE! | TARJA FRUTA EXPORTACIÓN |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  | Estado | Validada |  |  |  |  |  |  |  |
|  |  | Número tarja | E 2026W35- 0001 |  |  | Fecha | 2026-10-12 |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  | Especie | Cerezas |  |  | Variedad | Santina |  |  |  |  |  |  |  |
|  |  | Tipo Fruta | Convencional |  |  | Tipo tarja | Exportación |  |  |  |  |  |  |  |
|  |  | Productor | Agr Los Cedros |  |  | Id Fundo | SDP 12456 |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  | Embalaje | Cj Granel 5 kilos |  |  | Pallet | P 1x 1,20 x 2,2 |  |  |  |  |  |  |  |
|  |  | Cantidad Cajas | 184 |  |  | Kilos | 920 |  |  |  |  |  |  |  |
|  |  | Etiqueta | Steps |  |  | Categoría | Cat 1 |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  | Certificado | 2523 |  |  | OT Proceso | 26 W10 0112 |  |  |  |  |  |  |  |
|  |  | Calidad | C1 |  |  | Packing | San Fernando |  |  |  |  |  |  |  |
|  |  | Calibre | 2J |  |  | Línea | 1 |  |  |  |  |  |  |  |
|  |  | Lote | 117 |  |  | Variedad Com. | Santina |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  | #VALUE! |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  | Estados por tipo tarja |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  | Estados: |  | Cosecha (C ) | Exportación (E ) | Nacional (N) |  |
|  |  |  |  |  |  |  |  |  | Creada |  | x | x | x |  |
|  |  |  |  |  |  |  |  |  | Validada |  | x | x | x |  |
|  |  |  |  |  |  |  |  |  | Procesada |  | x |  |  |  |
|  |  |  |  |  |  |  |  |  | Repaletizada |  | x | x | x |  |
|  |  |  |  |  |  |  |  |  | Desp / Emb |  | x | x | x |  |
|  |  |  |  |  |  |  |  |  | Liquidada |  |  | x |  |  |
|  |  |  |  |  |  |  |  |  | Nula |  | x | x | x |  |


## Tarja Nacional (N) — formato y estados

_Hoja original: `tarja nac`_

| A | B | C | D | E | F | G | H | I | J | K | L | M | N | O | P | Q |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| LA TARJA DE CREA EN EL PROCESO DE RECPECIÓN DE FRUTA EMBALADA O EN EL PROCESO DE PACKING |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  | #VALUE! | TARJA FRUTA NACIONAL |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  | N 2026W35- 0001 |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  | Estado | Validada |  |  |  |  |  |  |  |  |
|  |  |  | Especie | Cerezas |  |  | Fecha | 2026-10-12 |  |  |  |  |  |  |  |  |
|  |  |  | Tipo Fruta | Convencional |  |  | Variedad | Santina |  |  |  |  |  |  |  |  |
|  |  |  | Productor | Agr Los Cedros |  |  | Tipo tarja | Exportación |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  | Id Fundo | SDP 12456 |  |  |  |  |  |  |  |  |
|  |  |  | Embalaje | Caja Nac 10 kilos |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  | Cantidad Cajas | 50 |  |  | Kilos | 500 |  |  |  |  |  |  |  |  |
|  |  |  | Etiqueta | Steps |  |  | Categoría | Cat 1 |  |  |  |  |  |  |  |  |
|  |  |  | Lote | 117 |  |  | Pallets | 1 x 1,2 nac |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  | Certificado | 2523 |  |  | OT Proceso | 26 W10 0112 |  |  |  |  |  |  |  |  |
|  |  |  | Calidad | C1 |  |  | Packing | San Fernando |  |  |  |  |  |  |  |  |
|  |  |  | Calibre | 2J |  |  | Línea | 1 |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  | Variedad Com. | Santina |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  | #VALUE! |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  | Estados por tipo tarja |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  | Estados: |  | Cosecha (C ) | Exportación (E ) | Nacional (N) |  |
|  |  |  |  |  |  |  |  |  |  |  | Creada |  | x | x | x |  |
|  |  |  |  |  |  |  |  |  |  |  | Validada |  | x | x | x |  |
|  |  |  |  |  |  |  |  |  |  |  | Procesada |  | x |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  | Repaletizada |  | x | x | x |  |
|  |  |  |  |  |  |  |  |  |  |  | Desp / Emb |  | x | x | x |  |
|  |  |  |  |  |  |  |  |  |  |  | Liquidada |  |  | x |  |  |
|  |  |  |  |  |  |  |  |  |  |  | Nula |  | x | x | x |  |


## RG — Recepción Granel (ya en Inventario/T40)

_Hoja original: `RG`_

| A | B | C | D | E | F | G | H | I | J |
|---|---|---|---|---|---|---|---|---|---|
| RECEPCIÓN GRANEL |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |
| Cuando se marca fruta granel o fruta embalada, se presenta este formato de las Operaciones |  |  |  |  |  |  |  |  |  |
| Producto | UdM | Especie | Variedad | U Traslado | Cantidad UT | Embalaje | Cant Embalaje | Kg Recibidos |  |
| CE01 Cer… | Kg | Cerezas | Santina | Bins cereza | 48 | Cj 8 kg | 1680 | 13440 |  |
|  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  | 48 |  | 1680 | 13440 |  |
|  |  |  |  |  |  |  |  |  |  |
| En la hoja "información adicional", se agregan los siguientes campos |  |  |  |  |  |  |  |  |  |
| Guía productor |  |  |  |  | Transportista |  |  |  |  |
| Fecha guía |  |  |  |  | Chofer |  |  |  |  |
| Fundo |  |  |  |  | Rut Chofer |  |  |  |  |
| Código SGC |  |  |  |  | Patente |  |  |  |  |
| Fecha Cosecha |  |  |  |  |  |  |  |  |  |
| Orgen, clase: de la tabla de clase de fruta Steps |  |  |  |  | Pesaje: |  | kilos |  |  |
| Tipo fruta: Orgánico o convencional |  |  |  |  | Kilos Totales |  | 18160 |  |  |
| Pesaje: | Por U de Traslado, por camión |  |  |  | Destare camión |  | 4000 |  |  |
| Origen Fruta |  |  |  |  | Peso x envases |  | 15 |  |  |
| Lote |  |  |  |  | Destare envases |  | 720 |  |  |
|  |  |  |  |  | Neto fruta Kg |  | 13440 | Promedio | 8 |
|  |  |  |  |  |  |  |  |  |  |
| Fruta granel: se visualiza esta pestaña cuando se marca el casillero fruta granel |  |  |  |  |  |  |  |  |  |
| ( aquí se registra cada tarja recibida). En el ejemplo el pesaje es por camión, por eso no tiene destare cada tarja |  |  |  |  |  |  |  |  |  |
| Estas tarjas son del Tipo Cosecha (C ) |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |
| N° Tarja | Peso bruto | Destare | Kg neto | Cajas | Promedio |  |  |  |  |
| 1 |  |  | 280 | 35 | 8 |  |  |  |  |
| 2 |  |  | 280 | 35 | 8 |  |  |  |  |
| 3 |  |  | 280 | 35 | 8 |  |  |  |  |
| 4 |  |  | 280 | 35 | 8 |  |  |  |  |
| , |  |  |  |  |  |  |  |  |  |
| , |  |  |  |  |  |  |  |  |  |
| 48 |  |  | 13440 | 1680 | 8 |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |
| Crear una opción de cargar las operaciones desde un excel |  |  |  |  |  |  |  |  |  |


## RE — Recepción Embalado (ya en Inventario/T40)

_Hoja original: `RE`_

| A | B | C | D | E | F | G | H | I | J | K |
|---|---|---|---|---|---|---|---|---|---|---|
| RECEPCIÓN EMBALADO |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |
| Cuando se marca fruta granel o fruta embalada, se presenta este formato de las Operaciones |  |  |  |  |  |  |  |  |  |  |
| Producto | UdM | Especie | Variedad | U Traslado | Cantidad UT | Embalaje | Cant Embalaje | Kg Recibidos |  |  |
| CE500 Cer… | Kg | Cerezas | Santina | Pallet | 8 | CE500 5 kg | 1472 | 7360 |  |  |
| CE500 Cer… | Kg | Cerezas | Bing | Pallet | 6 | CE500 5 kg | 1104 | 5520 |  |  |
|  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  | 14 |  | 2576 | 12880 |  |  |
|  |  |  |  |  |  |  |  |  |  |  |
| En la hoja "información adicional", se agregan los siguientes campos |  |  |  |  |  |  |  |  |  |  |
| Guía productor |  |  |  |  | Transportista |  |  |  |  |  |
| Fecha guía |  |  |  |  | Chofer |  |  |  |  |  |
| Fundo |  |  |  |  | Rut Chofer |  |  |  |  |  |
| Código SGC |  |  |  |  | Patente |  |  |  |  |  |
| Fecha Cosecha |  |  |  |  |  |  |  |  |  |  |
| Orgen, clase: de la tabla de clase de fruta Steps |  |  |  |  | Packing |  |  |  |  |  |
| Tipo fruta: Orgánico o convencional |  |  |  |  |  |  |  |  |  |  |
| Pesaje: | Por U de Traslado, por camión |  |  |  |  |  |  |  |  |  |
| Origen Fruta |  |  |  |  |  |  |  |  |  |  |
| Lote |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |
| Fruta Embalada: se visualiza esta pestaña cuando se marca el casillero fruta embalada |  |  |  |  |  |  |  |  |  |  |
| ( aquí se registra cada tarja recibida). |  |  |  |  |  |  |  |  |  |  |
| las tarjas son del Tipo Exportación (E ) |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |
| N° Tarja | Variedad | Producto | UdM | Embalaje | Etiqueta | Categoría | Calibre | pallet | Cajas | Kilos |
| 1 | Santina | CE500 | Caja | CE500 5 Kg | Steps | Cat 1 | 2J | 1 | 184 | 920 |
| 2 | Santina | CE500 | Caja | CE500 5 Kg | Steps | Cat 1 | 2J | 1 | 184 | 920 |
| 3 | Santina | CE500 | Caja | CE500 5 Kg | Steps | Cat 1 | 2J | 1 | 184 | 920 |
| 4 | Santina | CE500 | Caja | CE500 5 Kg | Steps | Cat 1 | 2J | 1 | 184 | 920 |
| 5 | Santina | CE500 | Caja | CE500 5 Kg | Steps | Cat 1 | 3J | 1 | 184 | 920 |
| 6 | Santina | CE500 | Caja | CE500 5 Kg | Steps | Cat 1 | 3J | 1 | 184 | 920 |
| 7 | Santina | CE500 | Caja | CE500 5 Kg | Steps | Cat 1 | 3J | 1 | 184 | 920 |
| 8 | Santina | CE500 | Caja | CE500 5 Kg | Steps | Cat 1 | 4J | 1 | 184 | 920 |
| 9 | Bing | CE500 | Caja | CE500 5 Kg | Steps | Cat 1 | 4J | 1 | 184 | 920 |
| 10 | Bing | CE500 | Caja | CE500 5 Kg | Steps | Cat 1 | 4J | 1 | 184 | 920 |
| 11 | Bing | CE500 | Caja | CE500 5 Kg | Steps | Cat 1 | 4J | 1 | 184 | 920 |
| 12 | Bing | CE500 | Caja | CE500 5 Kg | Steps | Cat 1 | J | 1 | 184 | 920 |
| 13 | Bing | CE500 | Caja | CE500 5 Kg | Steps | Cat 1 | J | 1 | 184 | 920 |
| 14 | Bing | CE500 | Caja | CE500 5 Kg | Steps | Cat 1 | J | 1 | 184 | 920 |
|  |  |  |  |  |  |  |  | 14 | 2576 | 12880 |
|  |  |  |  |  |  |  |  |  |  |  |
| Crear una función para cargar las operaciones por una carga excel |  |  |  |  |  |  |  |  |  |  |


## CE — Control de Envases de Cosecha con Productores

_Hoja original: `CE`_

| A |
|---|
| CONTROL DE ENVASES DE COSECHA CON PRODUCTORES |
|  |
| Es un control de ciertos envases (que pueden estar claasificados como activo fijo, no como inventario realizable) que se entregan |
| a Productores para transportar la fruta. Los movimientos posibles son: |
| Movimiento de entrada con la fruta donde se agregan las líneas de registro |
| Movimiento de entrada por un movimeinto de devolución |
| Tiene movimiento de salida en la emisión de una guía de despacho |
| Cada productor tendrá un saldo producto de los movimientos de entrada y salida de productos |
| (cada productor es una ubicación virtual de inventario) |
|  |
| Los envases son productos del módulo de inventario y se reconcen por |
| Agregar en la hija agrícola en campo " Es envases cosecha" que debe estar marcado como verdadero |
|  |
|  |
|  |
|  |
|  |
|  |
|  |
|  |
|  |
|  |
|  |
|  |
|  |
|  |
|  |
|  |
|  |
|  |
|  |
| Esta funcionalidad consiste en:Generar reportes sobre |
| 1) Crear App para cargar el inventario inicial en poder de productores |
| 2) Generar una cuenta corriente de envases por productor |
| 3) Generar un informe de saldo por envases y por productor |


## EM — Instructivo de Embarque / Embarque-Despacho (ya en Exportaciones)

_Hoja original: `EM`_

| A | B | C | D | E | F | G | H | I | J | K | L |
|---|---|---|---|---|---|---|---|---|---|---|---|
| INSTRUCTIVO DE EMBARQUE |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |
| Formulario de registro |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |
| Programa de venta | Cer 5kg |  |  |  |  |  |  |  |  |  |  |
| Tipo embarque | Maritimo |  |  | Fecha |  | 2026-10-15 |  | Incoterm | FOB |  |  |
| Num Embarque | M1001 |  |  | Cliente |  | JAC |  | Modalidad | A FIRME |  |  |
| Especie | Cerezas |  |  | Tipo fruta |  | Convencional |  |  |  |  |  |
| Nave | Nokita |  |  | País destino |  | USA |  |  |  |  |  |
| Agencia Aduana | Agencia Carle |  |  | Recibidor |  | JAC |  |  |  |  |  |
| POL - AOL | Valparaíso |  |  | Fecha zarpe |  | 2026-10-16 |  |  |  |  |  |
| POD - AOD | Philadelphia |  |  | fecha llegada |  | 2026-11-05 |  |  |  |  |  |
| Consegnee | NKA Fruit |  |  | Notify |  | Hua Lung |  |  |  |  |  |
| FFWW | Pacific Logistic |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |
| Transporte Internacional: |  |  |  |  |  |  |  |  |  |  |  |
| Cía Naviera-Aerea | Maesrk |  | Contenedor |  |  | VGM |  |  | Kg brutos |  |  |
| Día carga |  |  | Hora carga solicitada |  |  | Sello |  |  | Temperatura |  |  |
| Booking |  |  | N° Courier |  |  |  |  |  | Termógrafo |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |
| pallets | cajas | kilos netos | precio kg | Precio Cj | FOB factura | Flete | Otros | Total US$ |  |  |  |
| 20 | 3680 | 18400 | 3 | 15 | 55200 | 5500 |  | 60700 |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |
| Especie | Variedad | Producto | UdM | Embalaje | Etiqueta | Categoría | Calibre | pallet | Cajas | Kilos |  |
| Cerezas | Santina | CZ Export 5 kg | Caja | CE500 5 Kg | Steps | Cat 1 | 2J | 6 | 1104 | 5520 |  |
| Cerezas | Santina | CZ Export 5 kg | Caja | CE500 5 Kg | Steps | Cat 1 | 3J | 8 | 1472 | 7360 |  |
| Cerezas | Santina | CZ Export 5 kg | Caja | CE500 5 Kg | Steps | Cat 1 | 4J | 6 | 1104 | 5520 |  |
|  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  | 20 | 3680 | 18400 |  |
| Observaciones |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |
| EMBARQUE / DESPACHO |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |
| Formulario de registro |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |
| Programa de venta | Cer 5kg |  |  |  |  |  |  |  |  |  |  |
| Tipo embarque | Maritimo |  |  | Fecha |  | 2026-10-15 |  | Guía SII | 133 |  |  |
| Num Embarque | M1001 |  |  | Cliente |  | JAC |  | Incoterm | FOB |  |  |
| Especie | Cerezas |  |  | Tipo fruta |  | Convencional |  | Modalidad | A FIRME |  |  |
| Nave | Nokita |  |  | País destino |  | USA |  |  |  |  |  |
| Agencia Aduana | Agencia Carle |  |  | Recibidor |  | JAC |  | DUS | 12586524-8 |  |  |
| POL - AOL | Valparaíso |  |  | Fecha zarpe |  | 2026-10-16 |  | BL - AWB | COSU005866455 |  |  |
| POD - AOD | Philadelphia |  |  | fecha llegada |  | 2026-11-05 |  | Factura Exp |  |  |  |
| Consegnee | NKA Fruit |  |  | Notify |  | Hua Lung |  |  |  |  |  |
| FFWW | Pacific Logistic |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |
| Transporte Internacional: |  |  |  |  |  |  |  |  |  |  |  |
| Cía Naviera-Aerea | Maesrk |  | Contenedor | ZG-46545852221 |  | VGM | 4300 |  | Kg brutos | 21000 |  |
| Día carga |  |  | Hora carga solicitada |  |  | Sello | 33344444 |  | Temperatura | C° -0,5 |  |
| Booking |  |  | N° Courier |  |  |  |  |  | Termógrafo | 66778888 |  |
|  |  |  |  |  |  |  |  |  |  |  |  |
| Transporte local: |  |  |  |  |  |  |  |  |  |  |  |
| Empr. Transporte | Transportes Quinchao |  |  |  |  |  | Certificado SAG |  | 56666 |  |  |
| Chofer | Juanito |  | RUT | 55555-8 | Patente | GTE-201 | Patente carro |  | RRT-012 |  |  |
| Planta | San Fernando |  |  |  | Tipo Camión | Frigorífico | Fecha hr salida |  | 2026-10-16 08:16 |  |  |
|  |  |  |  | Enc Despacho | Juanin |  |  | Contraparte | Pepito |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |
| pallets | cajas | kilos netos | precio kg | Precio Cj | FOB factura | Flete | Otros | Total US$ |  |  |  |
| 20 | 3680 | 18400 | 3 | 15 | 55200 | 5500 |  | 60700 |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |
| Detalle: |  |  |  |  |  |  |  |  |  |  |  |
| Pallet / tarja | Variedad | Productor | Producto | UdM | Embalaje | Etiqueta | Categoría | Calibre | pallet | Cajas | Kilos |
| 2026W35- 0001 | Santina | Agr Los Cedros | CZ Export 5 kg | Caja | CE500 5 Kg | Steps | Cat 1 | 2J | 1 | 184 | 920 |
| 2026W35- 0002 | Santina | Agr Los Cedros | CZ Export 5 kg | Caja | CE500 5 Kg | Steps | Cat 1 | 2J | 1 | 184 | 920 |
| 2026W35- 0003 | Santina | Agr Los Cedros | CZ Export 5 kg | Caja | CE500 5 Kg | Steps | Cat 1 | 2J | 1 | 184 | 920 |
| 2026W35- 0004 | Santina | Agr Los Cedros | CZ Export 5 kg | Caja | CE500 5 Kg | Steps | Cat 1 | 2J | 1 | 184 | 920 |
| 2026W35- 0005 | Santina | Agr Los Cedros | CZ Export 5 kg | Caja | CE500 5 Kg | Steps | Cat 1 | 2J | 1 | 184 | 920 |
| 2026W35- 0006 | Santina | Agr Los Cedros | CZ Export 5 kg | Caja | CE500 5 Kg | Steps | Cat 1 | 2J | 1 | 184 | 920 |
| 2026W35- 0007 | Santina | Agr Los Cedros | CZ Export 5 kg | Caja | CE500 5 Kg | Steps | Cat 1 | 3J | 1 | 184 | 920 |
| 2026W35- 0008 | Santina | Agr Los Cedros | CZ Export 5 kg | Caja | CE500 5 Kg | Steps | Cat 1 | 3J | 1 | 184 | 920 |
| 2026W35- 0009 | Santina | Agr Los Cedros | CZ Export 5 kg | Caja | CE500 5 Kg | Steps | Cat 1 | 3J | 1 | 184 | 920 |
| 2026W35- 0010 | Santina | Agr Los Cedros | CZ Export 5 kg | Caja | CE500 5 Kg | Steps | Cat 1 | 3J | 1 | 184 | 920 |
| 2026W35- 0011 | Santina | Agr Los Cedros | CZ Export 5 kg | Caja | CE500 5 Kg | Steps | Cat 1 | 3J | 1 | 184 | 920 |
| 2026W35- 0012 | Santina | Agr Los Cedros | CZ Export 5 kg | Caja | CE500 5 Kg | Steps | Cat 1 | 3J | 1 | 184 | 920 |
| 2026W35- 0013 | Santina | Agr Los Cedros | CZ Export 5 kg | Caja | CE500 5 Kg | Steps | Cat 1 | 3J | 1 | 184 | 920 |
| 2026W35- 0014 | Santina | Agr Los Cedros | CZ Export 5 kg | Caja | CE500 5 Kg | Steps | Cat 1 | 3J | 1 | 184 | 920 |
| 2026W35- 0015 | Santina | Agr Los Cedros | CZ Export 5 kg | Caja | CE500 5 Kg | Steps | Cat 1 | 4J | 1 | 184 | 920 |
| 2026W35- 0016 | Santina | Agr Los Cedros | CZ Export 5 kg | Caja | CE500 5 Kg | Steps | Cat 1 | 4J | 1 | 184 | 920 |
| 2026W35- 0017 | Santina | Agr Los Cedros | CZ Export 5 kg | Caja | CE500 5 Kg | Steps | Cat 1 | 4J | 1 | 184 | 920 |
| 2026W35- 0018 | Santina | Agr Los Cedros | CZ Export 5 kg | Caja | CE500 5 Kg | Steps | Cat 1 | 4J | 1 | 184 | 920 |
| 2026W35- 0019 | Santina | Los tomates | CZ Export 5 kg | Caja | CE500 5 Kg | Steps | Cat 1 | 4J | 1 | 184 | 920 |
| 2026W35- 0020 | Santina | Los tomates | CZ Export 5 kg | Caja | CE500 5 Kg | Steps | Cat 1 | 4J | 1 | 184 | 920 |
|  |  |  |  |  |  |  |  |  | 20 | 3680 | 18400 |


## PL — Informe Packing List (ejemplo de datos)

_Hoja original: `PL`_

| A | B | C | D | E | F | G | H | I | J | K | L | M | N | O | P | Q | R | S | T | U | V | W | X | Y | Z | AA | AB |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| INFORME PACKING LIST |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| SHIPMENT | VESSEL | ETD | LOADING PORT | ETA | DISCHARGE PORT | CONSIGNEE | FRUIT | VARIETY | PACKAGE | LOTE NUMBER | FOLIO CALIDAD | LABEL | QUALITY | TYPE OF FRUIT | PALLET | NBR.HATCH/CONTAINER | BL/NBR | SIZE | BOX | TEMP CHECK | GROWER NUMBER | GROWER NAME | PACK CODE | PACKING | ORIGIN VARIETY | ORIGIN FACILITY | PACK DATE |
| M1001 | Nokita | 2026-10-16 | Valparaíso | 2026-11-05 | Philadelphia | JAC | Cerezas | Santina | CE500 5 kg | 320 |  | Steps | CAT 1 | Convencional | 2026W35- 0001 | ZG-46545852221 |  | 2J | 184 |  | SDP 12456 | Agr Los Cedros | CE500 | CJ 5 kg | Santina | San Fernando | 2026-10-12 |
| M1001 | Nokita | 2026-10-16 | Valparaíso | 2026-11-05 | Philadelphia | JAC | Cerezas | Santina | CE500 5 kg | 322 |  | Steps | CAT 1 | Convencional | 2026W35- 0002 | ZG-46545852221 |  | 2J | 184 |  | SDP 12456 | Agr Los Cedros | CE500 | CJ 5 kg | Santina | San Fernando | 2026-10-12 |
| M1001 | Nokita | 2026-10-16 | Valparaíso | 2026-11-05 | Philadelphia | JAC | Cerezas | Santina | CE500 5 kg | 322 |  | Steps | CAT 1 | Convencional | 2026W35- 0003 | ZG-46545852221 |  | 2J | 184 |  | SDP 12456 | Agr Los Cedros | CE500 | CJ 5 kg | Santina | San Fernando | 2026-10-12 |
| M1001 | Nokita | 2026-10-16 | Valparaíso | 2026-11-05 | Philadelphia | JAC | Cerezas | Santina | CE500 5 kg | 322 |  | Steps | CAT 1 | Convencional | 2026W35- 0004 | ZG-46545852221 |  | 2J | 184 |  | SDP 12456 | Agr Los Cedros | CE500 | CJ 5 kg | Santina | San Fernando | 2026-10-12 |
| M1001 | Nokita | 2026-10-16 | Valparaíso | 2026-11-05 | Philadelphia | JAC | Cerezas | Santina | CE500 5 kg | 323 |  | Steps | CAT 1 | Convencional | 2026W35- 0005 | ZG-46545852221 |  | 2J | 184 |  | SDP 12456 | Agr Los Cedros | CE500 | CJ 5 kg | Santina | San Fernando | 2026-10-12 |
| M1001 | Nokita | 2026-10-16 | Valparaíso | 2026-11-05 | Philadelphia | JAC | Cerezas | Santina | CE500 5 kg | 323 |  | Steps | CAT 1 | Convencional | 2026W35- 0006 | ZG-46545852221 |  | 2J | 184 |  | SDP 12456 | Agr Los Cedros | CE500 | CJ 5 kg | Santina | San Fernando | 2026-10-12 |
| M1001 | Nokita | 2026-10-16 | Valparaíso | 2026-11-05 | Philadelphia | JAC | Cerezas | Santina | CE500 5 kg | 323 |  | Steps | CAT 1 | Convencional | 2026W35- 0007 | ZG-46545852221 |  | 3J | 184 |  | SDP 12456 | Agr Los Cedros | CE500 | CJ 5 kg | Santina | San Fernando | 2026-10-12 |
| M1001 | Nokita | 2026-10-16 | Valparaíso | 2026-11-05 | Philadelphia | JAC | Cerezas | Santina | CE500 5 kg | 322 |  | Steps | CAT 1 | Convencional | 2026W35- 0008 | ZG-46545852221 |  | 3J | 184 |  | SDP 12456 | Agr Los Cedros | CE500 | CJ 5 kg | Santina | San Fernando | 2026-10-12 |
| M1001 | Nokita | 2026-10-16 | Valparaíso | 2026-11-05 | Philadelphia | JAC | Cerezas | Santina | CE500 5 kg | 322 |  | Steps | CAT 1 | Convencional | 2026W35- 0009 | ZG-46545852221 |  | 3J | 184 |  | SDP 12456 | Agr Los Cedros | CE500 | CJ 5 kg | Santina | San Fernando | 2026-10-12 |
| M1001 | Nokita | 2026-10-16 | Valparaíso | 2026-11-05 | Philadelphia | JAC | Cerezas | Santina | CE500 5 kg | 320 |  | Steps | CAT 1 | Convencional | 2026W35- 0010 | ZG-46545852221 |  | 3J | 184 |  | SDP 12456 | Agr Los Cedros | CE500 | CJ 5 kg | Santina | San Fernando | 2026-10-12 |
| M1001 | Nokita | 2026-10-16 | Valparaíso | 2026-11-05 | Philadelphia | JAC | Cerezas | Santina | CE500 5 kg | 320 |  | Steps | CAT 1 | Convencional | 2026W35- 0011 | ZG-46545852221 |  | 3J | 184 |  | SDP 12456 | Agr Los Cedros | CE500 | CJ 5 kg | Santina | San Fernando | 2026-10-12 |
| M1001 | Nokita | 2026-10-16 | Valparaíso | 2026-11-05 | Philadelphia | JAC | Cerezas | Santina | CE500 5 kg | 322 |  | Steps | CAT 1 | Convencional | 2026W35- 0012 | ZG-46545852221 |  | 3J | 184 |  | SDP 12456 | Agr Los Cedros | CE500 | CJ 5 kg | Santina | San Fernando | 2026-10-12 |
| M1001 | Nokita | 2026-10-16 | Valparaíso | 2026-11-05 | Philadelphia | JAC | Cerezas | Santina | CE500 5 kg | 322 |  | Steps | CAT 1 | Convencional | 2026W35- 0013 | ZG-46545852221 |  | 3J | 184 | CC104257 | SDP 12456 | Agr Los Cedros | CE500 | CJ 5 kg | Santina | San Fernando | 2026-10-12 |
| M1001 | Nokita | 2026-10-16 | Valparaíso | 2026-11-05 | Philadelphia | JAC | Cerezas | Santina | CE500 5 kg | 322 |  | Steps | CAT 1 | Convencional | 2026W35- 0014 | ZG-46545852221 |  | 3J | 184 |  | SDP 12456 | Agr Los Cedros | CE500 | CJ 5 kg | Santina | San Fernando | 2026-10-12 |
| M1001 | Nokita | 2026-10-16 | Valparaíso | 2026-11-05 | Philadelphia | JAC | Cerezas | Santina | CE500 5 kg | 322 |  | Steps | CAT 1 | Convencional | 2026W35- 0015 | ZG-46545852221 |  | 4J | 184 |  | SDP 12456 | Agr Los Cedros | CE500 | CJ 5 kg | Santina | San Fernando | 2026-10-12 |
| M1001 | Nokita | 2026-10-16 | Valparaíso | 2026-11-05 | Philadelphia | JAC | Cerezas | Santina | CE500 5 kg | 322 |  | Steps | CAT 1 | Convencional | 2026W35- 0016 | ZG-46545852221 |  | 4J | 184 |  | SDP 12456 | Agr Los Cedros | CE500 | CJ 5 kg | Santina | San Fernando | 2026-10-12 |
| M1001 | Nokita | 2026-10-16 | Valparaíso | 2026-11-05 | Philadelphia | JAC | Cerezas | Santina | CE500 5 kg | 322 |  | Steps | CAT 1 | Convencional | 2026W35- 0017 | ZG-46545852221 |  | 4J | 184 |  | SDP 12456 | Agr Los Cedros | CE500 | CJ 5 kg | Santina | San Fernando | 2026-10-12 |
| M1001 | Nokita | 2026-10-16 | Valparaíso | 2026-11-05 | Philadelphia | JAC | Cerezas | Santina | CE500 5 kg | 322 |  | Steps | CAT 1 | Convencional | 2026W35- 0018 | ZG-46545852221 |  | 4J | 184 |  | SDP 12456 | Agr Los Cedros | CE500 | CJ 5 kg | Santina | San Fernando | 2026-10-12 |
| M1001 | Nokita | 2026-10-16 | Valparaíso | 2026-11-05 | Philadelphia | JAC | Cerezas | Santina | CE500 5 kg | 322 |  | Steps | CAT 1 | Convencional | 2026W35- 0019 | ZG-46545852221 |  | 4J | 184 |  | SDP 12456 | Los Tomates | CE500 | CJ 5 kg | Santina | San Fernando | 2026-10-12 |
| M1001 | Nokita | 2026-10-16 | Valparaíso | 2026-11-05 | Philadelphia | JAC | Cerezas | Santina | CE500 5 kg | 322 |  | Steps | CAT 1 | Convencional | 2026W35- 0020 | ZG-46545852221 |  | 4J | 184 |  | SDP 12456 | Los Tomates | CE500 | CJ 5 kg | Santina | San Fernando | 2026-10-12 |


## PL formato — Formato de referencia Packing List

_Hoja original: `PL formato`_

| A | B | C | D | E | F | G | H | I | J | K | L | M | N | O | P | Q |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| >>>>> Formato de referencia, adecuar formato para Odoo |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  | PACKING LIST |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  | PRODUCT |  |  |  |  | EXPORTER |  |  |  |  |  |  |  |  |  |  |
|  | CNTR |  |  |  |  | IMPORTER |  |  |  |  |  |  |  |  |  |  |
|  | INVOICE |  |  |  |  | POD |  |  |  |  |  |  |  |  |  |  |
|  | VESSEL |  |  |  |  | POL |  |  |  |  |  |  |  |  |  |  |
|  | ETD |  |  |  |  | TOTAL BOXES |  |  |  |  |  |  |  |  |  |  |
|  | ETA |  |  |  |  | NET WEIGHT |  |  |  |  |  |  |  |  |  |  |
|  | BK |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| CSP | FOLIO PALLET | VARIETY | DATE PACKING | CSG | BOXES | NET WEIGHT | GROSS WEIGHT | THERMOS | CALIBRE |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  | 7800 | 11700 | 13260 |  |  |  |  |  |  |  |  |  |


## EM informe — Informe de Embarques (export legado, ejemplo de campos)

_Hoja original: `EM informe`_

| A | B | C | D | E | F | G | H | I | J | K | L | M | N | O | P | Q | R | S | T | U | V | W | X | Y | Z | AA | AB | AC | AD | AE | AF | AG | AH | AI | AJ | AK | AL | AM | AN | AO | AP | AQ | AR | AS | AT | AU | AV | AW | AX | AY | AZ | BA | BB | BC | BD | BE | BF | BG | BH | BI | BJ | BK | BL | BM | BN | BO | BP | BQ | BR | BS | BT |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| INFORME DE EMBARQUES |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| TARJA |  | TERMOGRAFO | COD.PROD. | PRODUCTOR | LOTE | COD.ESPECIE | ESPECIE | COD.VARIEDAD | VARIEDAD | VARI.ORIG | VARIEDAD ORIGEN | TFRUTA | STATUS1 | CERTIF | COD.ENVASE | ENVASE | KGS ENV. | COD.ETIQ. | ETIQUETA | COD.CATEG | CATEGORIA | CALIBRE | CAJAS | KgN * Cajas | EMBARQ | NAVE | TRANSPORTE | ZARPE | SEMANA(ZARPE) | BODEGA | EMBARCADOR | CONTENEDOR | TIPO CONTEN. | BL | COD.MERCADO | MERCADO | PTO.ORIGEN | PTO.DESTINO | ARRIBO | PAIS | CLIENTE | RECIBIDOR | BROKER | EXPORTADOR | COD.EMBALAJE | EMBALAJE | FECH.EMBALAJE | CCOSTO | PACKING | G.DESP. | FACTURA | O.COMP. | COLOR | N.CREDITO | N.DEBITO | LIQ.EXTERIOR | DUS | CIA.MARITIMA | COD. | PRODUCTOR ORIGINAL | AG.ADUANA | TIPO CAMION | EMP.TRANSP. | GUIA PROD. | NO.PROC.PACKING | MES ZARPE | CENTRAL.DESP.PACK | NOMBRE DESP.PACK | COD.CSP | FECHA EMBARQUE | TIPO VENTA |
| 3090101216 |  | CC103981 | 155491 | VILLA ESTELA | 117 | 1 | ARANDANOS | 146 | RIDLEY 1403 | 146 | RIDLEY 1403 | CONVENCIONAL | 0 |  | AR0150 | AR 1.50 KG 12X125 | 1.5 | 8 | ZG ZG | CAT 1 | CAT 1 | 14 | 34 | 51 | 1 | QANTAS | AEREO | 2023-11-20 | 47 |  |  | 81-56412790 |  |  | 5 | LEJANO ORIENTE | A.C.A.M.B | INCHEON | 2023-11-24 | COREA DEL SUR | SP FRESH | SP FRESH CORPORATION | SIN BROKER | ZURGROUP S.A. | AR1061 | 12X125 CSH SPF MT+M | 2023-11-17 |  | CENTRAL FRUTICOLA SA | 8773 |  |  |  |  |  |  |  |  | 155491 | VILLA ESTELA |  | REFRIGERADO | EXTERNO | 1951 | 0 | NOVIEMBRE | 25 | C. F. SAN ESTEBAN | 110942 | 2023-11-22 | EXPORT TRADICIONAL |
| 3090101216 |  | CC103981 | 155491 | VILLA ESTELA | 117 | 1 | ARANDANOS | 146 | RIDLEY 1403 | 146 | RIDLEY 1403 | CONVENCIONAL |  |  | AR0150 | AR 1.50 KG 12X125 | 1.5 | 8 | ZG ZG | CAT 1 | CAT 1 | 14 | 92 | 138 | 1 | QANTAS | AEREO | 2023-11-20 | 47 |  |  | 81-56412790 |  |  | 5 | LEJANO ORIENTE | A.C.A.M.B | INCHEON | 2023-11-24 | COREA DEL SUR | SP FRESH | SP FRESH CORPORATION | SIN BROKER | ZURGROUP S.A. | AR1061 | 12X125 CSH SPF MT+M | 2023-11-17 |  | CENTRAL FRUTICOLA SA | 8773 |  |  |  |  |  |  |  |  | 155491 | VILLA ESTELA |  | REFRIGERADO | EXTERNO | 0 | 1 | NOVIEMBRE | 25 | C. F. SAN ESTEBAN | 110942 | 2023-11-22 | EXPORT TRADICIONAL |
| '3090101216 |  | CC103981 | 155491 | VILLA ESTELA | 117 | 1 | ARANDANOS | 146 | RIDLEY 1403 | 146 | RIDLEY 1403 | CONVENCIONAL |  |  | AR0150 | AR 1.50 KG 12X125 | 1.5 | 8 | ZG ZG | CAT 1 | CAT 1 | 14 | 21 | 31.5 | 1 | QANTAS | AEREO | 2023-11-20 | 47 |  |  | 81-56412790 |  |  | 5 | LEJANO ORIENTE | A.C.A.M.B | INCHEON | 2023-11-24 | COREA DEL SUR | SP FRESH | SP FRESH CORPORATION | SIN BROKER | ZURGROUP S.A. | AR1061 | 12X125 CSH SPF MT+M | 2023-11-17 |  | CENTRAL FRUTICOLA SA | 8773 |  |  |  |  |  |  |  |  | 170042 | PARCELA MAITENES 6 |  | REFRIGERADO | EXTERNO | 0 | 2 | NOVIEMBRE | 25 | C. F. SAN ESTEBAN | 110942 | 2023-11-22 | EXPORT TRADICIONAL |
| '3090101216 |  | CC103981 | 155491 | VILLA ESTELA | 117 | 1 | ARANDANOS | 146 | RIDLEY 1403 | 146 | RIDLEY 1403 | CONVENCIONAL |  |  | AR0150 | AR 1.50 KG 12X125 | 1.5 | 8 | ZG ZG | CAT 1 | CAT 1 | 14 | 32 | 48 | 1 | QANTAS | AEREO | 2023-11-20 | 47 |  |  | 81-56412790 |  |  | 5 | LEJANO ORIENTE | A.C.A.M.B | INCHEON | 2023-11-24 | COREA DEL SUR | SP FRESH | SP FRESH CORPORATION | SIN BROKER | ZURGROUP S.A. | AR1061 | 12X125 CSH SPF MT+M | 2023-11-17 |  | CENTRAL FRUTICOLA SA | 8773 |  |  |  |  |  |  |  |  | 170042 | PARCELA MAITENES 6 |  | REFRIGERADO | EXTERNO | 0 | 2 | NOVIEMBRE | 25 | C. F. SAN ESTEBAN | 110942 | 2023-11-22 | EXPORT TRADICIONAL |
| '3090101216 |  | CC103981 | 155491 | VILLA ESTELA | 117 | 1 | ARANDANOS | 146 | RIDLEY 1403 | 146 | RIDLEY 1403 | CONVENCIONAL |  |  | AR0150 | AR 1.50 KG 12X125 | 1.5 | 8 | ZG ZG | CAT 1 | CAT 1 | 18 | 1 | 1.5 | 1 | QANTAS | AEREO | 2023-11-20 | 47 |  |  | 81-56412790 |  |  | 5 | LEJANO ORIENTE | A.C.A.M.B | INCHEON | 2023-11-24 | COREA DEL SUR | SP FRESH | SP FRESH CORPORATION | SIN BROKER | ZURGROUP S.A. | AR1061 | 12X125 CSH SPF MT+M | 2023-11-17 |  | CENTRAL FRUTICOLA SA | 8773 |  |  |  |  |  |  |  |  | 170042 | PARCELA MAITENES 6 |  | REFRIGERADO | EXTERNO | 0 | 2 | NOVIEMBRE | 25 | C. F. SAN ESTEBAN | 110942 | 2023-11-22 | EXPORT TRADICIONAL |
| '3090101216 |  | CC103981 | 155491 | VILLA ESTELA | 117 | 1 | ARANDANOS | 146 | RIDLEY 1403 | 146 | RIDLEY 1403 | CONVENCIONAL |  |  | AR0150 | AR 1.50 KG 12X125 | 1.5 | 8 | ZG ZG | CAT 1 | CAT 1 | 14 | 43 | 64.5 | 1 | QANTAS | AEREO | 2023-11-20 | 47 |  |  | 81-56412790 |  |  | 5 | LEJANO ORIENTE | A.C.A.M.B | INCHEON | 2023-11-24 | COREA DEL SUR | SP FRESH | SP FRESH CORPORATION | SIN BROKER | ZURGROUP S.A. | AR1061 | 12X125 CSH SPF MT+M | 2023-11-17 |  | CENTRAL FRUTICOLA SA | 8773 |  |  |  |  |  |  |  |  | 155491 | VILLA ESTELA |  | REFRIGERADO | EXTERNO | 0 | 3 | NOVIEMBRE | 25 | C. F. SAN ESTEBAN | 110942 | 2023-11-22 | EXPORT TRADICIONAL |
| '3090101216 |  | CC103981 | 155491 | VILLA ESTELA | 117 | 1 | ARANDANOS | 146 | RIDLEY 1403 | 146 | RIDLEY 1403 | CONVENCIONAL |  |  | AR0150 | AR 1.50 KG 12X125 | 1.5 | 8 | ZG ZG | CAT 1 | CAT 1 | 18 | 17 | 25.5 | 1 | QANTAS | AEREO | 2023-11-20 | 47 |  |  | 81-56412790 |  |  | 5 | LEJANO ORIENTE | A.C.A.M.B | INCHEON | 2023-11-24 | COREA DEL SUR | SP FRESH | SP FRESH CORPORATION | SIN BROKER | ZURGROUP S.A. | AR1061 | 12X125 CSH SPF MT+M | 2023-11-17 |  | CENTRAL FRUTICOLA SA | 8773 |  |  |  |  |  |  |  |  | 155491 | VILLA ESTELA |  | REFRIGERADO | EXTERNO | 0 | 3 | NOVIEMBRE | 25 | C. F. SAN ESTEBAN | 110942 | 2023-11-22 | EXPORT TRADICIONAL |
| '3090101215 |  | CC103972 | 155491 | VILLA ESTELA | 117 | 1 | ARANDANOS | 146 | RIDLEY 1403 | 146 | RIDLEY 1403 | CONVENCIONAL |  |  | AR0150 | AR 1.50 KG 12X125 | 1.5 | 8 | ZG ZG | CAT 1 | CAT 1 | 18 | 165 | 247.5 | 1 | QANTAS | AEREO | 2023-11-20 | 47 |  |  | 81-56412790 |  |  | 5 | LEJANO ORIENTE | A.C.A.M.B | INCHEON | 2023-11-24 | COREA DEL SUR | SP FRESH | SP FRESH CORPORATION | SIN BROKER | ZURGROUP S.A. | AR1061 | 12X125 CSH SPF MT+M | 2023-11-17 |  | CENTRAL FRUTICOLA SA | 8773 |  |  |  |  |  |  |  |  | 155491 | VILLA ESTELA |  | REFRIGERADO | EXTERNO | 0 | 1 | NOVIEMBRE | 25 | C. F. SAN ESTEBAN | 110942 | 2023-11-22 | EXPORT TRADICIONAL |
| '3090101215 |  | CC103972 | 155491 | VILLA ESTELA | 117 | 1 | ARANDANOS | 146 | RIDLEY 1403 | 146 | RIDLEY 1403 | CONVENCIONAL |  |  | AR0150 | AR 1.50 KG 12X125 | 1.5 | 8 | ZG ZG | CAT 1 | CAT 1 | 18 | 75 | 112.5 | 1 | QANTAS | AEREO | 2023-11-20 | 47 |  |  | 81-56412790 |  |  | 5 | LEJANO ORIENTE | A.C.A.M.B | INCHEON | 2023-11-24 | COREA DEL SUR | SP FRESH | SP FRESH CORPORATION | SIN BROKER | ZURGROUP S.A. | AR1061 | 12X125 CSH SPF MT+M | 2023-11-17 |  | CENTRAL FRUTICOLA SA | 8773 |  |  |  |  |  |  |  |  | 155491 | VILLA ESTELA |  | REFRIGERADO | EXTERNO | 0 | 3 | NOVIEMBRE | 25 | C. F. SAN ESTEBAN | 110942 | 2023-11-22 | EXPORT TRADICIONAL |
| '3090101220 |  |  | 155491 | VILLA ESTELA | 121 | 1 | ARANDANOS | 146 | RIDLEY 1403 | 145 | SIERRA | CONVENCIONAL |  |  | AR0150 | AR 1.50 KG 12X125 | 1.5 | 8 | ZG ZG | CAT 1 | CAT 1 | 14 | 22 | 33 | 2 | UNITED | AEREO | 2023-11-22 | 47 |  |  | 016-42829032 |  |  | 5 | LEJANO ORIENTE | A.C.A.M.B | INCHEON | 2023-11-27 | COREA DEL SUR | SP FRESH | SP FRESH CORPORATION | SIN BROKER | ZURGROUP S.A. | AR1061 | 12X125 CSH SPF MT+M | 2023-11-21 |  | CENTRAL FRUTICOLA SA | 8775 |  |  |  |  |  |  |  |  | 155491 | VILLA ESTELA |  | CONTENEDOR | EXTERNO | 0 | 7 | NOVIEMBRE | 25 | C. F. SAN ESTEBAN | 110942 | 2023-11-24 | EXPORT TRADICIONAL |
| '3090101220 |  |  | 155491 | VILLA ESTELA | 121 | 1 | ARANDANOS | 146 | RIDLEY 1403 | 144 | RIDLEY 1105 | CONVENCIONAL |  |  | AR0150 | AR 1.50 KG 12X125 | 1.5 | 8 | ZG ZG | CAT 1 | CAT 1 | 14 | 52 | 78 | 2 | UNITED | AEREO | 2023-11-22 | 47 |  |  | 016-42829032 |  |  | 5 | LEJANO ORIENTE | A.C.A.M.B | INCHEON | 2023-11-27 | COREA DEL SUR | SP FRESH | SP FRESH CORPORATION | SIN BROKER | ZURGROUP S.A. | AR1061 | 12X125 CSH SPF MT+M | 2023-11-21 |  | CENTRAL FRUTICOLA SA | 8775 |  |  |  |  |  |  |  |  | 155491 | VILLA ESTELA |  | CONTENEDOR | EXTERNO | 0 | 5 | NOVIEMBRE | 25 | C. F. SAN ESTEBAN | 110942 | 2023-11-24 | EXPORT TRADICIONAL |
