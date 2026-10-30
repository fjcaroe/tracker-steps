# Ventajas, impresión original, pagos y firmas — 30-10-2026

Base canónica `289e0bab`, posterior a la aceptación H de
[COMMUNITY_MULTIFRENTE.md](COMMUNITY_MULTIFRENTE.md). Rama propia
`codex/community-parallel-implementation-20261030`; productos congelados en
`56f78187`. Paquete de 30 addons propios y proveedor normal AGPL de 52 archivos:
483 archivos comunes. No sustituye la coadopción original ni la conversión integral.

## Cambios concretos

- `step_payroll_advantages_oca` 18.0.1.0.0 usa los dos modelos y el cálculo de
  `payroll_contract_advantages` LGPL real, fijado al mismo commit OCA que el motor.
  Comprueba contratos, empresas, campos, todas las filas físicas, límites,
  NULL/cero/negativos, códigos duplicados y permisos con UID normal. Calcula
  ventajas con `current_contract.advantages`, `result_qty` y `result_rate` reales,
  genera el asiento mediante el motor y protege historia cerrada. La admisión
  original de compañía conserva precedencia antes de seleccionar contratos.
  `step_payroll_benefits_native_reference` prueba el catálogo/formulario nativo;
  **no adopta** sus diez modelos, catorce tablas ni 58 maestros.
- `step_payroll_original_report` 18.0.1.0.0 permite que una acción existente con
  nombre exacto `hr_payroll.report_payslip_lang` imprima mediante el renderer
  Community de datos almacenados. Conserva su fila completa, grupos y FK de
  estructura; autoriza documentos/hijos/campos antes de la caché PDF y rechaza
  adjuntos/configuraciones no admitidas. En nativo es inerte. No crea aliases
  `hr_payroll`, reserva 462, renumera ni acredita que la acción original esté
  adoptada. El PDF funcional usa una acción privada ordinaria y datos cerrados
  con NULL, cero y negativo, sin recalcularlos.
- `step_batch_payment_grouping` y `step_batch_payment_core` 18.0.1.1.0 publican
  **pagos manuales nuevos en borrador** por `account.payment.action_post()`, con
  sus asientos reales, ID/fecha/importe/referencias/membresía conservados.
  Preflight completo, bloqueo y savepoint evitan resultados parciales. El lote
  permanece en borrador; no se atribuye equivalencia a validar/enviar/conciliar.
  Se rechaza cuenta pendiente de efectivo, proveedor externo, transferencias,
  historia publicada y compañías o registros ocultos. La nota es interna.
- `step_l10n_cl_edi_core` 18.0.1.4.0 firma/verifica DTE y EnvioDTE offline con
  XMLDSig, XSD oficiales fijados y certificado/ancla/contexto explícitos.
  Vincula emisor, receptor, tipo, folio, fecha, importe y TED/CAF. El perfil
  `sii-envelope` prepara **sólo un documento nuevo aún sin firma** con namespace
  xsi antes de firmar; el sobre final verifica sus firmas internas en contexto
  y conserva los fragmentos firmados byte por byte. Rechaza un histórico
  standalone incompatible, sin reescribirlo ni volver a firmarlo. Custodia
  18.0.1.2.0 revalida permisos y bytes originales; no añade tablas ni contadores.
  **Cadena/revocación, autoridad fiscal, transporte operativo, asignación de
  folios, emisión y aceptación SII siguen sin certificar.**

Los cuatro XSD son documentos normativos públicos, con hashes y atribuciones en
`step_l10n_cl_edi_core/xml_schemas/README.md`; no son fuentes OEEL copiadas.
El motor conserva la derivación NUMERIC de 144 archivos. El perfil ampliado
demuestra además los blobs/árboles originales de los tres addons LGPL OCA,
incluido ventajas, ligados al commit `4c71cd42e46a09a7512d92f5c63c0a9f7c26ad3e`.

## Aceptación

La pareja D pasó y su cápsula se reprodujo offline usando el verificador del
checkout Git confiable. El paquete y helpers ejecutados coinciden con Git;
ningún Python de los artefactos se ejecuta. A fue diagnóstico de 95 casos;
B ejecutó 637 y detectó una regresión de precedencia de la guarda de compañía.
C pasó 637 CE y halló un error de fixture en los 437 nativos: la creación de
valores del catálogo está restringida a Settings. Se corrigió con configurador
normal separado y prueba de denegación del rol HR, sin ampliar ACL. Ningún
resultado parcial A/B/C autoriza integrar o desplegar.

| Contexto D | Resultado | Alcance |
| --- | --- | --- |
| Community oficial | 637 casos, cero fallos/errores; 117 instalados, cero EE | Motor OCA y proveedor AGPL reales; 164 métodos críticos comprobados individualmente. |
| Copia fresca Cerro | 437 casos, cero fallos/errores; 395 instalados, 140 EE | Referencia nativa; 143 métodos críticos. No es conversión integral. |

Son 61 casos CE y 46 nativos adicionales respecto H. No sumar como pruebas únicas
las suites que comparten contratos. Se ejecutaron además 35 verificaciones de
herramientas y 13 DTE/10 EnvioDTE puros; las comprobaciones de producto también
están dentro de las suites Odoo.

La postvalidación readonly verifica 28 versiones exactas CE y 25 nativas, con
24 módulos propios requeridos por modo. Los 266 archivos originales LGPL de
`payroll` (144), `payroll_account` (97) y ventajas (25) quedan ligados a sus
blobs/árboles del commit OCA. La derivación NUMERIC sigue separada y conserva
144 archivos, una única transformación y su prueba Git de 14 árboles.

Se preservan **921 tablas/proyecciones + 140 contadores = 1.061 contratos**,
59.079 XML IDs originales/noupdate, modelos, ACL, relaciones e históricos.
1.060 snapshots son literales. Sólo `stock_package_type.base_weight`, ID 1,
cambia representación `15.00`→`15`: el testigo SELECT readonly reconstruye sus
cinco filas/19 columnas desde el respaldo propio D y demuestra igualdad tipada,
sin Float ni redondeo; no se declara la tabla idéntica en bytes. Los cinco
destinos de menú, siete timestamps de aliases propios y tres ayudas HR mantienen
la política exacta aceptada en H; no se añaden excepciones ni se reinician
contadores. El catálogo nativo conserva sus catorce tablas tras el rollback.

Hay dos PDF almacenados de la regresión y un tercer PDF por la ruta de acción
original: UID normal, fila de acción y FK intactas, cero/negativo/NULL/NET
almacenados y ninguna reconstrucción de nómina. Se revisaron visualmente las
dos páginas del tercero y su texto. **Pendiente visual real:** C incluye
nombre/país corporativos en página 1 y D los omite; los logos y los 215 assets
coinciden y el PNG de página 2 es idéntico. No se atribuye la causa sólo al
fixture ni se acepta el layout para producción. Hace falta capturar HTML,
cabecera/pie/formato/argumentos finales de wkhtmltopdf y repetir el caso.
Los importes y el bloque legal/firma están completos; eso no certifica nómina.

Fuentes y evidencia privada:

- Snapshot Git candidato `a35f3c202997e5d849f14781714c2e82f489a2d3`
  (código de producto `56f78187`), tar SHA256
  `1050f2cde6a633158610823f47e2c364defc9cf9223537a8af4bf57b803f9723`.
- Paquete común 483 archivos, fingerprint
  `3dda89284b144c4f3725a682ccfd957383191fe8b25a4c60e8fe0ff3f68ac12b`.
- Servidor `/opt/steps-validation/community-multifront-parallel-20261030D`;
  evidencia `/opt/steps-validation/community-parallel-20261030`.
- Cápsula `accepted-evidence-D.tar.gz`: 743 miembros, 8.249.988 bytes, SHA256
  `c8b789955975fadb56f2b185c83264fda6a1ee7e7c1c5a3fc267cba8dd84f8eb`.
  No exporta dump, filestore, credenciales ni cuerpos OEEL.
- Sello final `accepted-evidence-D-sealed.tar.gz`: 745 miembros, 8.279.128 bytes,
  SHA256 `3ade6621f328368543908cb2ed505ce046d9821835c22ee97e3d7c6e169ccf5c`.
  Incluye manifiesto exhaustivo y resumen canónico SHA256
  `c589a26ac9107dd2f2d98f2b6cafd75e83c50c3306e5a7a77f219b4e618595c3`;
  recibo adyacente, permisos 0600 en servidor y replay local con código Git.
- Testigo propio D SHA256
  `5ceab150a7a8046a81c850f2b5b65643b17ead11f4e7273ec9d63c481a9f400e`.
- Recibo de cabecera `community/original-report-pdf-header-review.json`, SHA256
  `98b8c805df2b893040ec06627056c7617c22f9cb5f9d8750166863733888e3dc`.
- Copia/replay local en
  `~/.codex/local-artifacts/community-parallel-20261030/acceptance-D` y
  `summary-D.json`; ambos proceden del paquete exacto.

El inventario posterior D es idéntico al inicial, SHA256
`2cd3cfb9a85b88c5ddd65657228df3468d87dec65a50e54a89da808da64ca9ba`.
No se publicaron cambios en producción ni QA-Cerro. Los backups/restauraciones
y upgrades se serializaron con `/run/lock/steps-environments.lock`; reservas de
disco, ausencia de downgrade y de cambios activos se comprobaron por entorno.

Las correcciones conservan las guardas: cuenta efectiva configurada antes de
crear el pago privado; cantidades Python mediante `result_qty`; transporte PDF
oficial `debug=False` admitido sin aceptar payload financiero; carácter monetario
de presentación U+FEFF tratado sólo en la aserción; contexto DTE tipado separado
de la variable que inspecciona el traductor Odoo; compañía original admitida
antes de seleccionar ventajas.

## Pendientes acumulados y fecha

El inventario inicial readonly cubrió Cerro, Steps y SyS, sus fuentes privadas
y módulos propios fuera de Cerro. Permanecen 54 apps propias instaladas con
caminos Enterprise; producción Cerro conserva 140 EE. Extraer o probar una
biblioteca no reduce ese inventario sin cerrar sus consumidores y la conversión.

Prioridad inmediata: [bootstrap original](COMMUNITY_PROXIMO_BOOTSTRAP.md), sus
120 maestros/71 reglas/88 aliases originales, cuatro tipos compartidos, reporte
462, referencias contables JSON, metadata/ACL y diferencias físicas. No forzar
NOT NULL global, inventar maestros ni aplanar relaciones. Después certificar
reglas, entradas/días/YTD/redondeo/asientos/Previred/libro con la referencia real
SyS y resolver sus diferencias explícitas de configuración.

Siguen abiertos DTE/CAF/folios/firma/respuestas/transporte SII completos;
conciliación y ciclo de lotes/consumidores; Calidad, Studio/Documentos/Firma;
productos propios fuera de Cerro; y una copia integral restaurable que opere
con **cero Enterprise**, más aceptación en Desarrollo. El corte productivo
está fuera de la automatización. El 31 sigue en riesgo alto: los bloques
funcionales nuevos no acreditan llegar con toda la migración terminada.

Calidad quedó preparada y publicada **sin integrar** en `52c1c2f7`, rama
`codex/community-quality-20261030`: contratos neutrales, inspecciones OCA reales
y referencia nativa, nueve casos CE/cuatro nativos propuestos. Cuatro pruebas
puras y comprobaciones estáticas no sustituyen su pareja funcional pendiente.
Conserva `quality.check` y los consumidores originales sin retarget; OCA
manufacture fijado en `2d6084f553490408f7a341f05ba6ddd6e641a879`.

La autorización de hasta cinco agentes sigue vigente; la capacidad observada
es coordinador más tres agentes. Se reutilizaron las tres plazas en ventajas,
pagos/reporte y firmas/sobre/evidencia, y luego Calidad. Las restauraciones y
upgrades continúan serializados por el bloqueo compartido.

## Siguiente prompt

Continúa desde la canónica actualizada, en worktree propio. Lee AGENTS.md,
~/.odoo/environments.json, operación, workflow, COMMUNITY_CONTINUACION.md,
COMMUNITY_EXTENSIONES_OPERACIONALES.md, COMMUNITY_AUTONOMIA.md y sus referencias.
Conserva la pareja aceptada y relee sólo documentos cambiados. Revisa antes el
inventario completo readonly de Cerro/Steps/SyS y fuentes privadas/externas.
Prioriza coadopción real de la configuración original Simple Digital–OCA:
120 maestros, 71 reglas, IDs/88 aliases, cuatro tipos compartidos, reporte 462,
FK/M2M/JSON, metadata y permisos; usa el renderer original Community ya real,
sin reservar/renumerar una colisión ni inventar maestros. Cierra todas las
referencias antes de escribir y aborta ante concurrencia o alcance sin clasificar.
Conserva el límite de cabecera corporativa del PDF: captura fragmentos/argumentos
finales, repite impresión y verifica empresa/país por página antes de dar layout
productivo por aceptado; no basta comprobar assets ni importes.
Si se bloquea, conserva el bloqueo y prueba el candidato Calidad 52c1c2f7 en
pareja privada exacta antes de integrarlo. Mantén visibles la certificación SyS,
DTE/SII completo, consumidores restantes y conversión integral cero EE.
Usa hasta las plazas autorizadas, sin solapar upgrades. Preserva IDs, maestros,
ACL, relaciones, históricos, saldos y correlativos. No recalcules pagadas ni
escribas en producción, cambies vencimientos, eludas licencia, refresques QA,
emitas SII o copies OEEL. Respeta Calendar, Boolean bancario y 210233.
Guarda evidencia privada, commits/push, integra sólo lo validado y ejecuta
python tools/git/verify_handoff.py --require-pushed. Informa avances verificables
y valoración honesta del 31; ninguna extracción parcial resuelve el vencimiento.
