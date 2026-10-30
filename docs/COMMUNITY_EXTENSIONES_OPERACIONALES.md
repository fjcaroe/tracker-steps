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

La pareja D está pendiente; esta sección no constituye aceptación hasta
registrar ambos resultados y la custodia final. A fue diagnóstico de 95 casos;
B ejecutó 637 y detectó una regresión de precedencia de la guarda de compañía.
C pasó 637 CE y halló un error de fixture en los 437 nativos: la creación de
valores del catálogo está restringida a Settings. Se corrigió con configurador
normal separado y prueba de denegación del rol HR, sin ampliar ACL. Ningún
resultado parcial A/B/C autoriza integrar o desplegar.

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
