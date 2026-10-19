# T93 · Lotes SAG y anexos de despacho en Desarrollo

Entregado el 19-10-2026 (Chile) para revisión humana exclusivamente en Desarrollo.
Ticket 93 en etapa 4, con nota interna 9512 sin destinatarios ni notificaciones.

## Paquete publicado

- Commit probado y publicado: `bfc2430f5b593f399a5774e8251ea79c21df3997`.
- SHA-256: `3de33d89ab2dc0d2d49fdc589603e036b7983e6a4f387e2595a4ca561e388ba7`.
- Versiones: `step_packing_operations` 18.0.2.8.3,
  `step_packing_dispatch` 18.0.1.0.1 y `step_packing_sag` 18.0.2.0.0.
- Destino: <https://desarrollo.stepsapp.cl/odoo/action-2238>, base `LAB_TAREAS`.
- Ruta: Packing / Inspecciones / Inspección SAG.
- Overlay: `/opt/steps-managed/releases/development/bfc2430f5b593f399a5774e8251ea79c21df3997/`.
- Respaldo: `/opt/steps_backups/management_development_20261019T144646Z`.
- Copia fresca de prueba: `MANAGEMENT_QA_DEVELOPMENT_t93final`.
- Evidencia: `/opt/steps-validation/management_development_t93final/qa_passed.json`.

Se publicó el mismo paquete probado, con bloqueo compartido de ambientes,
verificación de versiones, ausencia de downgrade y preservación de los valores
de negocio anteriores. No se publicó en producción.

## Comportamiento

La inspección nativa admite un lote de una especie con tarjas de varias OT y
productores. El productor queda en la trazabilidad de cada tarja, fuera del
encabezado. Incluye tipo de fruta, recibidor, instructivo, variedades, catálogo
de servicios y lectura de los códigos impresos. La selección exige stock físico,
validación, empresa, especie y compatibilidad con los filtros y el historial SAG.

Genera INS, INT, REP, DET y DES conforme al servicio y al Anexo 5 suministrado;
valida longitudes, códigos oficiales y colisiones, sin truncar identificadores.
INS usa la referencia SIF. Los demás archivos y el anexo exigen la aprobación
sanitaria vigente para el país; una reevaluación pendiente bloquea su uso.

El anexo de despacho incluye folios oficiales, especies, variedades, provincia,
comuna, envases, fechas, destino, productores y total, en Excel y PDF. Conserva
encabezados y referencia de planilla al imprimir varias páginas. La referencia
funcional es el manual adjunto v04 de 10-07-2024, incluido §6.8.4.2; no certifica
requisitos actuales de un mercado. Los archivos no se envían al SAG ni ejecutan
anulaciones o movimientos. La planilla oficial se emite/regulariza en Multipuerto.

Los códigos y orígenes se completan en los maestros existentes, sin tablas
paralelas ni valores geográficos inventados. Las tarjas antiguas con stock cuyo
tipo de fruta está vacío se conservaron sin cambios. Su clasificación requiere
confirmación humana; mientras tanto no aparecen en el filtro nuevo.

## Validación

La copia del destino pasó 34 pruebas, sin fallos ni errores. Ocho casos
funcionales adicionales pasaron en la copia y nuevamente en el registro
instalado, con transacciones descartadas: varias OT/productores, lectura de
folios, filtros, cinco formatos, Excel/PDF y permisos entre empresas.

Se revisaron visualmente el Excel y el PDF real de dos tarjas, con total de 40
envases. Una segunda muestra exclusiva de maquetación repitió 80 filas en ocho
páginas: todos los encabezados y referencias se conservaron y el total apareció
en la última página. Esa muestra no representa inventario real.

En navegador se comprobaron el menú, la lista, los once servicios, el formulario,
los filtros de especie/tipo y la pestaña de archivos. El formulario de prueba se
descartó sin guardar ni registrar resultados SAG ficticios. La inspección
`SAG-2627/00001` se conservó. Las advertencias Studio y la dependencia `steps_api`
ausente ya existían antes del cambio y no impidieron los casos.

Evidencia privada en `~/.codex/local-artifacts/t93-20261019/`: `visual-review.json`
con hashes de veinte archivos, `development-qa.json`, `development-deploy.log`,
`report-review.json`, capturas de navegador y vistas previas de los reportes.
