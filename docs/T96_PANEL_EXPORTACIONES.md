# T96 Panel de Exportaciones

Solicitud: ticket 96, adjunto 3373 y respuestas 9539/9540 del 20-10-2026.
Destinos solicitados: Desarrollo y Cerro El Plomo. Desarrollo es el único QA.
El adjunto original y sus tres imágenes se conservan fuera del repositorio.

## Alcance

`step_export_dashboard` amplía la portada existente sin modelos ni tablas nuevas.
El contenedor usa la altura del área de acción, permite desplazamiento vertical
y reduce el espacio de portada, indicadores, trazabilidad y accesos rápidos.
Conserva todas las acciones de navegación originales.

Agrega dos tablas: especie y programa de venta, cada una con kilos, monto USD
y precio por kilo planificados y reales. Los filtros de temporada, mes y semana
se combinan. Mes y semana incluyen año para no mezclar temporadas de años distintos.
Las tablas tienen desplazamiento horizontal en pantallas estrechas.

Planificado: líneas semanales de versiones vigentes de programas. Los programas
reemplazados no se suman otra vez. Los embarques de versiones antiguas conservan
su vínculo histórico y se agrupan por serie y empresa con la versión vigente.
Los kilos reales usan carga de embarques embarcados, facturados o liquidados.

Decisión humana 9539/9540: monto real neto = factura + nota de débito − nota de
crédito, solo documentos contabilizados. Odoo representa los débitos como
facturas positivas y los créditos como `out_refund`. Se usa `amount_untaxed`,
conversión contable a USD a la fecha de cada documento y sin sumar impuestos.
También se reconocen notas vinculadas al documento original aunque no copien
el vínculo directo al embarque. No se incluyen borradores, documentos anulados,
compras ni asientos generales.

El período del comparativo corresponde al embarque (`date`), igual que el
criterio del forecast existente. Los programas se filtran por inicio de semana.
Los embarques sin fecha se incluyen solo sin filtros de mes/semana y se informa
su existencia. El promedio total es monto total dividido por kilos totales;
una base de cero se muestra sin precio.

Se consultan modelos existentes mediante ORM, reglas y empresas activas, sin
`sudo`. Si el perfil no puede leer facturas, los importes reales quedan sin valor
y se informa la restricción. No se reemplazan datos faltantes por importes ficticios.
No hay modelos Studio, tablas paralelas ni cambios a documentos históricos.

## Paquete

Commit: `14d582077044f6230baab458f5eb9afe2a623513`.
SHA-256: `4fc09f91101550ebaa859ced17adb46f84aa5b0394fc4e2eb26eb72d2b4b6769`.
Módulo: `step_export_dashboard` 18.0.1.0.0, nueve archivos.
Tipo de operación: `--kind export-dashboard` en las herramientas canónicas.

Las pruebas cubren promedios ponderados, filtros combinados, versiones,
borradores, fechas ausentes, límites por empresa y facturas/débitos/créditos
con conversión EUR/USD. El probe verifica el menú real y compila los assets
JS, XML y SCSS en una copia privada. Los documentos sintéticos son transitorios,
sin emisión de DTE, correos ni despachos; todas las transacciones se descartan.

La herramienta local de navegador falla antes de inicializar, tanto en CUA
como en la alternativa Windows (`failed to write kernel assets`, ruta inexistente).
No confundir compilación de assets con comprobación visual del desplazamiento.
La revisión a zoom normal continúa pendiente hasta poder abrir el navegador.

Evidencia privada: `~/.codex/local-artifacts/t95-t96-20261020/`.


## Validación y entrega en Desarrollo

Copia fresca: `MANAGEMENT_QA_DEVELOPMENT_t96c`. Cuatro pruebas sin fallos ni
errores; cuatro casos funcionales adicionales con rollback. Compilación nativa
de JS/XML/SCSS correcta (`T96_ASSET_COMPILATION_OK`). Pruebas anteriores de
diagnóstico permitieron corregir la fixture contable; no acreditan el paquete.
Se compararon todas las columnas preexistentes de las tablas de negocio.

Mismo archivo publicado en Desarrollo con respaldo
`/opt/steps_backups/management_development_20261020T192426Z`, bloqueo compartido
y overlay `releases/development/14d582077044f6230baab458f5eb9afe2a623513`.
Comprobación posterior: versión, fuente cargada, menú, assets y cuatro casos
correctos. La comprobación del panel renderizado a zoom normal continúa pendiente.
La publicación posterior en Cerro se detalla a continuación.
T96 permanece abierto; el fallo local del navegador no acredita una falla de Odoo.

Registro interno: nota 9541; etapa 6 En Espera, sin notificaciones.


## Publicación en Cerro El Plomo

El mismo paquete pasó cuatro pruebas y cuatro casos en la copia fresca
`MANAGEMENT_QA_CERRO_t96c`, con compilación nativa de assets y preservación de
las columnas anteriores. Se publicó por la autorización expresa del ticket
para ambos destinos, sin añadir una solicitud de aprobación a ese alcance.
Respaldo: `/opt/steps_backups/management_cerro_20261020T193228Z`.
Overlay: `releases/cerro/14d582077044f6230baab458f5eb9afe2a623513`.
Bloqueo compartido, sin downgrade ni modificación de raíces compartidas.
Comprobación posterior correcta: versión, fuente, menú, assets y cuatro casos
funcionales con rollback. No se afirma una revisión del panel en navegador;
T96 continúa abierto por esa comprobación visual concreta.
