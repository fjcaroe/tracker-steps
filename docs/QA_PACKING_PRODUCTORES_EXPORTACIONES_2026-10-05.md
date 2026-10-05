# Packing, Productores y Exportaciones — integración para QA

Rama de entrega: `codex/packing-productores-exportaciones-qa`. Se consolidan
`codex/t35-exterior-expenses-20261004` (79b612b) y
`codex/t41-menu-groups-20261004` (14aee04), conservando los avances T30, T38 y T40.

## Alcance de esta entrega

- **Packing 18.0.2.6.0:** materiales calculados por producto y tarja de salida;
  revisión editable con motivo obligatorio al ajustar; aprobación de un
  administrador de Inventario antes de consumir stock. Una falta de existencias
  revierte toda la operación, incluidos los movimientos de materia prima.
- Cierre con paquetes exactos, lotes y propietarios; no se permiten consumos
  duplicados ni cambios directos de estado para eludir validaciones. La fruta
  nacional queda a nombre del productor y puede devolverse mediante un traslado
  real de sus tarjas a la ubicación de cliente.
- Valoración de fruta E al precio del contrato confirmado, por variedad,
  categoría y calibre, con conversión de moneda/UdM y precio conservado al cierre.
  La valoración nativa requiere **costo promedio o FIFO**. No se cambian métodos
  de costo ni cuentas automáticamente.
- Preparación mensual de **facturas en borrador**, agrupadas por productor y
  moneda. Repetir el asistente reutiliza las facturas vinculadas. Los precios
  proceden del cierre de la OT; las cuentas se toman de las líneas del contrato.
  El responsable revisa impuestos, diario permitido y folio antes de publicar.
  En la liquidación final debe vincular estas facturas como documentos previos.
- Turno, dotación, planta, cliente, horas y detenciones; indicadores de horas
  efectivas, kg/h, kg/trabajador, kg/hora-hombre, ocio, peso medio de caja de
  cosecha, permanencia y antigüedad. El porcentaje 2J+ utiliza la clasificación
  explícita del catálogo, sin deducir equivalencias por el nombre del calibre.
- Cuadratura por resultado/calibre, PDF individual y consolidado al imprimir
  varias OT, y versiones inmutables de instructivo vinculadas a reservas reales.
- Inspecciones interna/SAG con aprobación, rechazo y reevaluación. Una OT puede
  exigir inspección; el despacho comprueba su resultado. La referencia SAG
  corresponde a un certificado emitido fuera de Odoo: esta entrega no emite
  certificados oficiales ni conecta con un servicio del organismo.
- **Inventario Packing 18.0.1.1.0:** se conserva el importador Excel y el control
  de envases. El botón «Preparar stock desde tarjas» enlaza el detalle importado
  con movimientos/paquetes nativos; la recepción se valida por separado. La
  fruta C recibida a proceso conserva al productor como propietario.
- **Productores 18.0.1.6.0:** consolidado estacional por productor, generación
  masiva, filtros, PDF y acceso a liquidaciones/documentos existentes. Confirmar
  conserva la selección; cerrar exige cerrar las liquidaciones individuales.
  No crea otra factura ni contabiliza por segunda vez.
- **Exportaciones 18.0.2.7.0:** restricciones de productor/variedad versionadas
  en el programa comercial y verificadas en Packing y despacho. Se incluyen
  los gastos exteriores por concepto y las mejoras de tarifas/contratos de las
  ramas integradas.

## Preparación de la prueba funcional

1. Entrar a [Desarrollo](https://desarrollo.stepsapp.cl/web) o
   [Demo](https://demo.stepsapp.cl/web) con permisos de Inventario. La aprobación
   de materiales, instructivos e inspecciones requiere administrador de Inventario;
   los consolidados y facturas requieren Contabilidad. Para operar ambas partes,
   el usuario necesita ambos permisos.
2. Revisar **Exportaciones → Configuración → Parámetros contables**. Seleccionar
   el diario «Compra fruta exportación» y, si corresponde, activar «Exigir contrato
   para fruta de exportación». Esta opción queda desactivada por defecto para
   conservar las OT históricas que no tenían contrato.
3. Confirmar un contrato del productor con precios, cuotas, cuentas y moneda.
   Revisar los productos de fruta exportable y su método de costo. Si se usan
   precios por categoría/calibre, vincular los catálogos de Inventario con sus
   equivalentes de contratos; **sus IDs no son intercambiables**.
4. Recibir fruta C: elegir fundo/especie, registrar pesaje, importar tarjas o
   cargarlas manualmente; preparar movimientos y validar la recepción. Para
   productos rastreados, indicar el lote en el detalle antes de preparar stock.
5. Crear/validar OP y OT; seleccionar contrato, tarjas C/E/N, tiempos y requisito
   de inspección. Preparar materiales, justificar ajustes y aprobar. Cerrar la
   OT y comprobar quants, tres traslados y valoración de fruta E. Si se reservan
   tarjas, crear y aprobar primero una versión del instructivo de la OP; acceder
   a **Packing → Planificación → Reservas por instructivo** y seleccionarla.
6. Registrar la inspección exigida y comprobar que el despacho se bloquea si
   falta aprobación o si la última revisión de cualquier tipo fue rechazada.
   Devolver las tarjas N al productor desde la OT cerrada cuando corresponda.
7. Preparar compra mensual; revisar el borrador. Al liquidar definitivamente,
   revisar las facturas previas y el documento de ajuste con su folio real.
8. En **Productores → Generar consolidados**, elegir temporada/filtros. Se
   incluyen **liquidaciones completas y validadas**. Una liquidación que mezcla
   embarques o variedades fuera del filtro se excluye completa: no se distribuyen
   arbitrariamente sus descuentos. Imprimir varios consolidados para emisión masiva.

## Límites y fases que siguen separadas

- El costeo completo de procesos y la asignación de costos son **Etapa 2** según
  T41. Los estados «Costeada/Contabilizada» del modelo histórico no tienen nuevos
  botones en esta entrega; el cierre operativo sí mueve y valora inventario.
- Productores sigue dependiendo de Exportaciones. La **Fase B de T38** (trasladar
  modelos/XML IDs e invertir dependencias conservando tablas y datos) no forma
  parte de esta consolidación funcional; requiere una migración específica y
  pruebas de instalación independiente. No presentar esta versión como una app
  ya instalable sin Exportaciones.
- Balanzas e impresoras deben homologarse con los equipos reales. Los perfiles
  y captura existentes se conservan; no se presume compatibilidad física.
- El piloto contable con folios y políticas reales del cliente sigue siendo una
  validación funcional de QA antes de pasar a producción.

## Pruebas y despliegue

Las pruebas se ejecutan en `AGRO_INTEGRATION_QA_20261005_DEVELOPMENT` y
`AGRO_INTEGRATION_QA_20261005_DEMO`, copias aisladas con correo y tareas programadas
deshabilitados, sin HTTP y con registros sintéticos que se revierten. En los
clones se detectó un aviso preexistente de `steps_api` sin código disponible;
no depende de los cinco módulos agrícolas ni impidió sus pruebas.

Herramientas versionadas: `tools/agro_qa/`. El paquete se construye fuera del
checkout, verifica sintaxis Python/XML y no incluye credenciales ni datos.
El despliegue exige el SHA256 y commit exactos, un respaldo de base/configuración,
un directorio de addons por ambiente y una lista cerrada de destinos.

**Desarrollo comparte su directorio original de código con Steps productivo.**
Por eso esta entrega usa `/opt/steps-agro-qa/releases/<ambiente>/<commit>` como
primer directorio de addons y restringe cada servicio QA a su propia base.
No se copian estos cambios al código compartido ni se reinician servicios
productivos. Solo se actualizan `LAB_TAREAS` y `STEPS_DEMO`.

Los respaldos privados quedan bajo `/opt/backups/agro-qa-<ambiente>-<UTC>/`.
Contienen `database.dump`, configuración anterior, metadatos de la entrega y
registro de actualización. Ante una falla, conservar el respaldo y diagnosticar
la base exacta antes de recuperar; el script no elimina ni restaura bases de
usuarios automáticamente.

## Evidencia de la entrega, 05-10-2026

Commit de aplicación desplegado en ambos QA:
`3c104abafa1d001d05af0fea714949acf8a58fca`.
Paquete de 198 archivos, SHA256:
`beee8473257cf5c0967fef6ad6fb7f673806e4f041073a773d604e87fd7ae368`.
Se verificó el contenido contra el commit, normalizando únicamente finales
de línea de Windows/Linux. Los commits posteriores de documentación/herramientas
no cambian el código agrícola desplegado.

| Ambiente | Pruebas en copia aislada | Servicio actualizado | Verificación final |
|---|---|---|---|
| Desarrollo / `LAB_TAREAS` | 53, 0 fallos, 0 errores; 17:47:55 UTC | `odoo18-dev.service` | Cinco versiones correctas, código del commit, ocho formularios compilados, menú de reservas y acceso HTTPS 200 |
| Demo / `STEPS_DEMO` | 53, 0 fallos, 0 errores; 17:47:59 UTC | `odoo18-demo.service` | Cinco versiones correctas, código del commit, ocho formularios compilados, menú de reservas y acceso HTTPS 200 |

Registros finales de prueba:

- `/opt/steps-agro-qa/development/tests-20261005T174635Z.log`
- `/opt/steps-agro-qa/demo/tests-20261005T174646Z.log`

Respaldos inmediatamente anteriores a la versión final:

- `/opt/backups/agro-qa-development-20261005T174832Z/`
- `/opt/backups/agro-qa-demo-20261005T174943Z/`

Los servicios productivos `odoo18.service` y `odoo18-sys.service` permanecieron
activos, con inicio previo a estos despliegues. No se actualizó ninguna base
productiva. Los diarios, cuentas, folios y contratos reales quedan para la
prueba funcional del responsable contable, sin publicar facturas de prueba.
