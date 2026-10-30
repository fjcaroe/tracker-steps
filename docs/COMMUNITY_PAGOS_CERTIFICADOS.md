# Aplicación contable, admisión HR y certificados — 30-10-2026

Base canónica `7d763a68`, posterior a
[Calidad Q4](COMMUNITY_CLAUSURA_CALIDAD.md). Rama propia
`codex/community-critical-20261030`, paquete R3 congelado en `2ebe477a`.
La pareja completa R3 pasó y se reprodujo offline contra código Git confiable.
Q4 646/441, D y H se conservan como aceptaciones históricas independientes.

## Cambios concretos

- `step_payroll_oca_api` 18.0.1.15.0 normaliza a UID real y `sudo(False)` las
  dos admisiones de estructuras/reglas originales. Autoriza campos y extremos
  de compañías, países, tipos, estructuras, reglas y ancestros de categorías,
  incluidos archivados, antes de admitir su proyección. Dos casos CE nuevos y
  la negativa aislada del país del tipo comprueban caché/sudo y denegación.
  El consumidor real `_step_materialize_original_rule_projection` demuestra
  rollback ante un fallo tardío e idempotencia posterior, conservando pares,
  maestros, timestamps, recibos, líneas y asientos cerrados. No se importan los
  120 maestros/71 reglas ni se alteran las cinco opciones upstream o el M2M/O2M.
- `step_batch_payment_grouping` y `step_batch_payment_core` 18.0.1.2.0 publican
  pagos nuevos draft y aplican sus contrapartes a facturas/bills posted abiertos
  mediante `account.payment.action_post()` y `account.move.line.reconcile()`
  reales. Usan exclusivamente los vínculos originales `payment.invoice_ids`,
  completos y guardados: una factura por pago, un pago por factura, misma empresa,
  moneda de compañía, tercero exacto y saldo completo. No infieren documentos
  por nombre o importe. Preflight completo, locks y un savepoint abarcan toda la
  operación, incluidos posting, matching, pertenencia y notas internas.
  Rechazan FX, cuotas múltiples, historia ya aplicada, caja/210233, régimen de
  caja, líneas/documentos ocultos y campos restringidos. La cuenta pendiente debe
  seguir íntegra, con residual firmado real y sin partials ni extracto bancario.
  Lote draft y miembros/IDs/fechas/importes/asientos originales se conservan.
  Formulario y botón CE usan la relación original; no crean wizard ni modelos.
  Once casos compartidos y uno de formulario CE prueban las operaciones reales.
  Ver [contrato de aplicación](../step_batch_payment_grouping/APPLICATION.md).
- `step_l10n_cl_edi_core` 18.0.1.5.0 añade política explícita de cadena PKIX y
  CRL completas a `sign_dte`/`verify_signed_dte`. Usa OpenSSL real con store vacío,
  raíz fijada, camino ordenado exacto y CRL firmadas por cada emisor. Valida
  ventanas temporales, roles/uso de clave, restricciones del camino, revocación
  de firmante/intermedios, DER, pins y límites de recursos. No consulta red,
  anclas del sistema, archivos privados ni un recibo previo. Cinco métodos Odoo
  nuevos, incluidos rechazos antes de firmar; los 18 puros DTE pasaron sin red.
  Revisión independiente sin hallazgo material; se reforzaron el límite previo
  al hash y las negativas CRL futura/vencida/al borde. El perfil y sus fuentes
  primarias se detallan en [certificados offline](COMMUNITY_CERTIFICADOS_OFFLINE.md).

Los indicadores fiscales continúan separados: la política prueba CRL
suministradas al instante de firma, no que sean las últimas disponibles online,
ni EKU/política fiscal chilena, mandato, confianza SII, folios o aceptación.
Custodia y EnvioDTE no heredan esta política automáticamente. No se usó ninguna
credencial, autoridad operativa ni emisión real; los fixtures son efímeros.

Community puede calcular `paid` al aplicar una contraparte y accountant nativo
mantener `in_payment`/`in_process`. Se conservan esos estados calculados originales:
una etiqueta no acredita conciliación bancaria ni equivalencia al ciclo del lote.
La operación nueva no cancela/revierte pagos históricos ni valida/envía el lote.

## Prueba conjunta y procedencia

R1 enfocado ejecutó **128 casos CE, cero fallos/errores**, incluidos los nuevos
de HR, DTE y aplicación contable. El postflight posterior rechazó la versión
1.2.0 porque su contrato aún fijaba 1.1.0; no es aceptación completa. Se corrigió
el checker con un perfil explícito `critical_extension` que exige la versión y
marca nuevas, sin relajar Q4/D/H. R2 sólo se materializó, sin crear base ni
ejecutar upgrade. R3 repite con bases nuevas y paquete exacto; la verificación
conjunta y la preservación están cerradas en su alcance privado.

El perfil R exige los nuevos métodos críticos individualmente, incluidos los
16 de admisión/proyección HR CE, y rechaza recibos enfocados o de generaciones
anteriores. Misma selección de 33 addons propios, proveedor normal AGPL de
52 archivos, OCA nómina LGPL (266 originales, derivación NUMERIC 144 separada)
y OCA Quality AGPL (114 originales) que Q4. No se cambian dependencias de las
apps originales para fingir una clausura Enterprise menor.

## Aceptación R3 y preservación

| Entorno privado | Pruebas | Instalados / Enterprise | Métodos críticos |
| --- | ---: | ---: | ---: |
| Community oficial y OCA reales | 665, cero fallos/errores | 120 / 0 | 206 |
| Copia fresca Cerro, referencia nativa | 457, cero fallos/errores | 397 / 140 | 163 |

Son 19 casos CE y 16 nativos adicionales respecto Q4. La postvalidación readonly
comprueba 31/27 versiones exactas y 26 módulos propios requeridos por modo;
los grafos fueron medidos independientemente antes de fijarlos en la cápsula.
El paquete común contiene 508 archivos y 33 addons propios. La segunda fila
conserva motores Enterprise originales: no es conversión integral.

Se preservan **921 tablas/proyecciones + 140 contadores = 1.061 contratos**,
**59.079 XML IDs/noupdate** originales, modelos, ACL, relaciones e históricos.
1.060 snapshots son literales. La representación `stock_package_type.base_weight`
ID 1 `15.00`→`15` se demuestra equivalente mediante SELECT readonly sobre las
cinco filas/19 columnas reconstruidas del respaldo propio R3, sin Float ni
redondeo. No se declara esa representación idéntica en bytes. Permanecen la
política H/Q4 de cinco destinos de menú, siete timestamps propios y tres ayudas
HR; no hay excepciones nuevas ni reinicios de contadores.

Las tres impresiones R3 dieron seis páginas con empresa, país y logo completos,
valores almacenados y firma intactos, sin solapamientos. Pipelines/bytes/assets
reales y seis PNG fueron revisados independientemente; la cabecera técnica se
conserva. No se certifican layout legal/productivo ni adopción original 462.

- Fuente exacta: `/opt/steps-validation/community-multifront-parallel-20261030R3`,
  `2ebe477a`; bases nuevas `COMMUNITY_PAYROLL_API_CRITICAL_20261030R3` y
  `MANAGEMENT_QA_CERRO_PAYROLL_API_CRITICAL_20261030R3`.
- Runtime oficial `4b4efe68291d6def5bb7d2e1f2b829e0cda577d4`, OCA nómina
  `4c71cd42e46a09a7512d92f5c63c0a9f7c26ad3e` y Quality
  `2d6084f553490408f7a341f05ba6ddd6e641a879`; mismos pins/procedencia que Q4.
- Evidencia fuera del checkout en `/opt/steps-validation/community-critical-20261030R`
  y `~/.codex/local-artifacts/community-critical-20261030R`.
- Cápsula `accepted-evidence-R3.tar.gz`: 1.108 miembros, 11.477.443 bytes,
  SHA256 `d8179f0f3adf4670c1562fcc689b197d67c297a3805d283b92b1296a3e95aec5`.
  Incluye fuentes vendor libres, manifiesto, logs/recibos/pipelines/assets;
  no exporta dump, filestore, credenciales ni cuerpos OEEL.
- Sello `accepted-evidence-R3-sealed.tar.gz`: 1.110 miembros, 11.536.353 bytes,
  SHA256 `bb7447176221219403ba0b57db52fcee8f65b01793cb5806e671f6f586de4635`.
  Resumen canónico SHA256
  `9bc8c6032e73bea410b7367340968f502c18bdf4c43c6cc65913da185244e461`;
  recibo adyacente y permisos privados 0600. Replay independiente de todos los
  miembros y resumen byte por byte contra el verificador Git confiable.
- Testigo tipado R3 SHA256
  `1617a861aea2ec37ec4ddd256c29231ad4571781f3223a9259271a70a53ad286`.
- Revisión de cabecera SHA256
  `3f6983006f742162029d02c6cbf3295ba51fee025e155014043860dfd40af02c`.
- Verificación offline completa con el código Git confiable, sin ejecutar
  Python del artefacto ni acceder a bases. Inventario anterior/posterior idéntico,
  SHA256 `2cd3cfb9a85b88c5ddd65657228df3468d87dec65a50e54a89da808da64ca9ba`.

Se usaron respaldo, overlays y bases nuevos, reservas de disco y
`/run/lock/steps-environments.lock`, sin solapar upgrades. No hubo cambios en
producción, refresh QA-Cerro, emisión SII, vencimientos ni runtime compartido.
El backend criptográfico postflight queda registrado como metadata privada;
no certifica autoridades fiscales ni que las CRL sean las últimas online.

## Tres discriminadores originales demostrados

`original_external_references_related.py` admite únicamente la cadena física
de dos pasos hacia `ir.model.model` de `calendar.event`, `mail.activity` y
`rating.rating`: M2O almacenado, tabla real, FK validada, namespace único,
discriminador char almacenado y contraste SELECT con el extremo real. No
ejecuta computes ni generaliza a discriminadores arbitrarios o multihop.

| Referencia readonly | Guardas antes/después | Consultas por snapshot completo |
| --- | ---: | ---: |
| H CE | 116 → 113 | 505 |
| D CE | 116 → 113 | 505 |
| D nativo | 27 → 24 | 614 |

Cada referencia tiene dos capturas completas iguales. CE observa diez vínculos
Calendar y 27 Activity sin discrepancias; Rating está vacío. En nativa los tres
están vacíos: es cierre de contrato/ausencia, **no prueba de un flujo nativo con
referencias activas**. Se conservan todas las rutas/observaciones anteriores,
catálogos, extremos, aliases y hashes originales de 120 maestros/71 reglas y
59.079 XML IDs. El runtime readonly previo f801 se reutiliza íntegro; esta
extracción no afirma un nuevo arranque de registry ni snapshot global de negocio.

Los 113 bloqueos CE incluyen 89 aliases aún no adoptados, siete contratos con
destinos faltantes, acción 462 ocupada, cinco M2O sin FK física, una vista de
historial, una inversa, un JSON y ocho contratos serializados. Son contratos,
no filas ni un porcentaje de avance. Los 24 nativos conservan siete M2O sin FK,
cuatro discriminadores arbitrarios, una vista, cuatro JSON y ocho serializados.
Importación, reserva/renumeración y escritor siguen bloqueados.

Evidencia privada del cierre:

- `/opt/steps-validation/community-critical-20261030R/related-discriminators/final-ac0c7833`.
- Cápsula de 18 miembros `related-discriminators-ac0c7833.tar.gz`, SHA256
  `0306945caca1dec157e5e8da870968971d02b6e4a38731684515877c159ce850`.
- Resumen remoto SHA256
  `6a185d92cca76ca1a1a66852448ac21e748f31dd5e0f7cc5a1e612a19e08aa34`.
- Replay del coordinador en
  `~/.codex/local-artifacts/community-critical-20261030R/related-discriminators-ac0c7833/root-independent-replay.json`:
  17 hashes, seis fuentes Git exactas y tres evaluaciones/consultas/contrastes/
  summaries idénticos. No se ejecuta Python del artefacto ni se accede a bases.
- 21 pruebas de las cuatro suites de referencias verdes; sus conteos no se
  suman a los de producto como casos de negocio únicos.

## Pendientes y siguiente bloque

Continúan 54 apps propias instaladas con caminos Enterprise y 140 módulos EE
en producción Cerro. La matriz de 133 módulos propios/37 fuera del inventario
instalado no cambia por estas versiones. La copia nativa conserva Enterprise;
el paquete Community de ensayo no sustituye todavía las 381 apps instaladas.

Prioridad: cerrar los caminos semánticos originales restantes y preparar una
migración versionada de identidad real, distinguiendo deltas planeados de
aliases/maestros de guardas de seguridad aún sin demostrar. Resolver beneficios,
metadata/ACL, reglas chilenas, días/entradas, YTD/redondeos, asientos, Previred y
libro contra la referencia real SyS sin copiar fórmulas ni recalcular pagadas.
Completar autoridad/configuración de certificados, CAF/folios y flujo DTE/SII;
conciliación y ciclo de lotes; Calidad nativa, Studio/Documentos/Firma y demás
productos. Finalmente probar copia integral restaurable con cero Enterprise
y aceptación en Desarrollo. El corte productivo está fuera de la automatización.

La aserción adicional de agregados del lote `59620fbf`, publicada en la rama
financiera, queda preservada para un siguiente paquete; no cambia producto ni
demostró un defecto que justificara reiniciar R3. No se incorpora a su fuente
congelada ni se presenta como ejecutada en esta aceptación.

El 31 sigue en riesgo alto: estos tramos funcionales no permiten prometer
terminar toda la migración ni dar un porcentaje global defendible. Mantener
activa la programación y todas las restricciones de COMMUNITY_AUTONOMIA.md.

## Siguiente prompt

Continúa desde la canónica actualizada en worktree propio. Lee AGENTS.md,
~/.odoo/environments.json, operación, workflow, COMMUNITY_CONTINUACION.md,
COMMUNITY_PAGOS_CERTIFICADOS.md, COMMUNITY_CERTIFICADOS_OFFLINE.md,
COMMUNITY_AUTONOMIA.md y sus referencias. Conserva las parejas aceptadas,
relee documentos cambiados y revisa inventario completo readonly de Cerro,
Steps, SyS, fuentes privadas activas y productos fuera de Cerro.
Prioriza la coadopción Simple Digital–OCA real: cierra referencias semánticas,
FK/inversas, vistas de historial y JSON/serializados restantes. Conserva la
clausura física de Calendar/Activity/Rating y sus límites de datos observados.
Distingue los deltas planeados de los 89 aliases/120 maestros/71 reglas de las
guardas de seguridad todavía sin demostrar; no habilites un escritor ni reserves,
renumeres o importes mientras falten contratos/identidad/permisos/concurrencia.
Completa beneficios y certificación chilena con SyS real sin copiar fórmulas
ni recalcular pagadas. En paralelo avanza consumidores reales de la política
DTE de cadena/CRL, autoridad/configuración/folios/respuestas SII, Tesorería,
Calidad nativa y Documentos/Firma. Incorpora las aserciones financieras 59620fbf
con la próxima aceptación exacta, sin atribuirles una ejecución previa.
Usa las plazas autorizadas y una sola cola de upgrades; prueba paquete exacto
en Community oficial y copia fresca Cerro. Preserva IDs, maestros, ACL,
relaciones, históricos, saldos y correlativos. Respeta Calendar, Boolean
bancario y 210233. No toques producción, vencimientos ni QA-Cerro; no recalcules
cerradas, emitas al SII real, envíes mensajes externos o copies fuentes OEEL.
Guarda evidencia privada y commits/push, integra sólo lo validado y ejecuta
python tools/git/verify_handoff.py --require-pushed. Mantén visibles las puertas
de conversión integral restaurable cero EE y aceptación en Desarrollo; ninguna
extracción parcial resuelve el 31.
