# Calidad real, cabecera y referencias originales — 30-10-2026

Estado posterior: [Pagos y certificados R3](COMMUNITY_PAGOS_CERTIFICADOS.md),
665/457 casos, conserva Q4 y añade aplicación contable, admisión HR y PKIX/CRL.
Esta hoja mantiene su aceptación y evidencia originales; no es conversión integral.


Base canónica `f28f1d2c`, posterior a
[extensiones operacionales D](COMMUNITY_EXTENSIONES_OPERACIONALES.md). Rama propia
`codex/community-original-closure-20261030`; paquete Q4 congelado en `e6e856ab`.
Se conservan D y H como aceptaciones históricas independientes. Este bloque
añade operación Community de Calidad y corrige una regresión de impresión;
**no convierte todavía la identidad nativa ni la base integral**.

## Resultado probado

| Pareja exacta Q4 | Pruebas | Grafo instalado | Métodos críticos |
| --- | ---: | ---: | ---: |
| Community oficial + OCA real | 646, cero fallos/errores | 120, cero Enterprise | 173 |
| Copia fresca aislada Cerro | 441, cero fallos/errores | 397, 140 Enterprise | 147 |

Los 33 addons propios y el proveedor normal AGPL de 52 archivos suman 503
archivos comunes. La postvalidación SELECT readonly comprueba 31 versiones
exactas CE y 27 nativas, 26 propias requeridas por modo. El grafo se midió
independientemente antes de fijar los valores del colector. La segunda fila
es referencia nativa: conserva sus motores originales, no acredita conversión.

- `step_quality_contracts`, `step_quality_oca` y `step_qa_native_reference`
  18.0.1.0.0 cierran contratos neutrales, inspecciones OCA reales y consumidores
  originales en su motor correspondiente. Se prueban formulario, wizard,
  preguntas cualitativas/cuantitativas, UoM, estados, aprobación, roles normales,
  hijos completos, caché/sudo y protección de resultados cerrados. No amplían
  ACL nativas ni retargetean `quality.check`. Ver
  [COMMUNITY_CALIDAD_OCA.md](COMMUNITY_CALIDAD_OCA.md).
- Una medición SQL NULL puede existir durante preparación del wizard; no se
  convierte en cero. Confirmar/aprobar exige la medición real finita y los
  límites físicos. El caso funcional demuestra rechazo sin mutación y después
  aprobación con la medición introducida. No se relajan las guardas finales.
- `step_payroll_original_report` 18.0.1.0.1 aplica tipografía explícita sólo al
  bloque corporativo exacto de la cabecera de la ruta original admitida. Ejecuta
  primero el renderer oficial y conserva contenido, acción, grupos y FK. Soporta
  una o varias cabeceras autorizadas con preflight completo; una estructura
  ambigua aborta. No cambia márgenes, cuerpos, pies ni motor de cálculo.
- Tres impresiones reales repetidas produjeron seis páginas con empresa, país
  y logo completos. Se capturaron los HTML/argumentos reales de wkhtmltopdf y
  los bytes de sus 215 recursos. Verificación offline estricta y revisión de
  seis PNG; coordinador revisó además páginas inicial/final. Se conservaron
  NULL/cero/negativos, importes almacenados y bloque de firma sin recalcular.
  Un replay estático aislado de red mostró seis páginas completas al explicitar
  tipografía; no demuestra cuál propiedad heredada aislada causaba el defecto.
  **Cierra el defecto técnico reproducible; no certifica validez legal, layout
  productivo ni adopción numérica de la acción original 462.**

Proveedor libre real: `quality_control_oca` 18.0.1.4.0, AGPL-3,
OCA/manufacture `2d6084f553490408f7a341f05ba6ddd6e641a879`, 114 archivos
ligados a blobs/árboles Git, fingerprint
`dc412934cd1abafc4474813a08a77faebe791ab0ee83001587e46cda25bbc0a9`.
Se materializan los bytes exactos en overlay legible; no se usan symlinks que
atraviesen directorios privados inaccesibles al servicio. Nómina conserva
los 266 archivos LGPL originales OCA y la derivación NUMERIC separada de 144
archivos del pin `4c71cd42e46a09a7512d92f5c63c0a9f7c26ad3e`.

Q1 detectó una frontera de permisos del directorio del proveedor; Q2 detectó
el NULL legítimo del wizard. Q3 enfocado pasó diez casos CE; la referencia
nativa enfocada pasó cuatro. Son diagnósticos: sólo Q4 completo autoriza esta
integración. No sumar suites solapadas como pruebas únicas.

## Preservación y custodia

Q4 conserva **921 tablas/proyecciones + 140 contadores = 1.061 contratos** y
**59.079 XML IDs originales/noupdate**. Son 1.060 snapshots literales y el
testigo tipado de `stock_package_type`: cinco filas/19 columnas del respaldo
propio Q4, `base_weight` ID 1 `15.00`→`15`, igual valor sin Float ni redondeo.
No se declara esa representación idéntica en bytes. La política de cinco
destinos de menú, siete timestamps propios y tres ayudas HR permanece idéntica
a H/D. No hay excepciones nuevas ni reinicios de contadores. Se conservan
maestros, modelos, ACL, relaciones e históricos, incluido el catálogo de Calidad.

Fuentes/ejecución privada:

- `/opt/steps-validation/community-multifront-parallel-20261030Q4`, bases nuevas
  `COMMUNITY_PAYROLL_API_QUALITY_20261030Q4` y
  `MANAGEMENT_QA_CERRO_PAYROLL_API_QUALITY_20261030Q4`.
- Community oficial `4b4efe68291d6def5bb7d2e1f2b829e0cda577d4` y pins OCA
  anteriores; proveedores, paquete y helpers ejecutados reproducidos desde Git.
- Evidencia en `/opt/steps-validation/community-original-closure-20261030` y
  `~/.codex/local-artifacts/community-original-closure-20261030`.
- Cápsula `accepted-evidence-Q4.tar.gz`: 1.106 miembros, 11.470.669 bytes,
  SHA256 `c4cb592e561a476d4159919105c133a54ecd138073ce8dffa9720720d5f1f164`.
  Incluye capturas/recursos reales y manifiesto exhaustivo; no exporta dump,
  filestore, credenciales ni cuerpos OEEL. El verificador confiable Git pasó
  offline, sin ejecutar Python del artefacto ni acceder a bases.
- Sello `accepted-evidence-Q4-sealed.tar.gz`: 1.108 miembros, 11.531.043 bytes,
  SHA256 `3438862fee5b8250ba20345b2e3dd1eb9e520dba072f134744bde294123cc554`.
  Resumen canónico SHA256
  `96815469afe9274f208a740f59a10bbec93c3fc3e03989c01b2b4d7d9c6f0863`;
  recibo adyacente y permisos privados 0600. Replay independiente del sello
  compara todos sus miembros y el resumen byte por byte con el verificador Git.
- Testigo de representación Q4 SHA256
  `130901c50859881ca4fa6a4ea57709ea3be3d4c9e27c82a354ede33a15ebb2ad`.
- Revisión visual final SHA256
  `6fd5592aa0a9cce36f1d631e694b493ca90c9cc770c8c0e5da40dcc90945a285`.

El inventario completo Cerro/Steps/SyS anterior y posterior es idéntico,
SHA256 `2cd3cfb9a85b88c5ddd65657228df3468d87dec65a50e54a89da808da64ca9ba`.
Se comprobaron fuentes propias privadas activas y productos fuera de Cerro.
Restauraciones, respaldo y upgrades usan `/run/lock/steps-environments.lock`,
overlays nuevos y reservas de disco. No hubo publicación en producción ni
refresh QA-Cerro, emisión SII o modificación de vencimientos.

## Configuración original: avance real y bloqueo conservado

Se implementó y ejecutó auditoría física de referencias originales sobre H CE,
D CE y D nativo: registry real `_table`/`_inherits`, relaciones FK/M2M,
Reference/Many2oneReference, JSON tipado y familia de acciones. Introspección
de clases/campos sin leer registros ni copiar cuerpos OEEL; SELECT readonly
con dos snapshots completos iguales, incluidas todas las secuencias. Odoo
sobrescribe PGOPTIONS: el arranque probado fija readonly antes del primer pool
y comprueba cursor/servidor reales. No usa el runner de upgrade ni su finalizador
de traducciones, ni reintenta en lectura/escritura.

| Referencia auditada | Modelos registry | Snapshots tablas/secuencias | Caminos físicos | Bloqueos registrados |
| --- | ---: | ---: | ---: | ---: |
| H CE | 564 | 1.097 | 336 | 116 |
| D CE | 566 | 1.101 | 336 | 116 |
| D nativo | 1.223 | 2.621 | 402 | 27 |

El nativo conserva hashes de los 120 maestros/71 reglas y 89 PK de aliases
originales, incluido reporte. Los clones CE no los han adoptado: cuatro aliases
de contrato nominalmente iguales no prueban identidad física. El número 462
está ocupado; no se reserva, renumera ni importa a ciegas. Se cotejaron los
59.079 XML IDs con el dump original mediante parser COPY inerte; nunca se
ejecuta SQL del dump. Permanecen discriminadores calculados/related, historial
en vista, JSON/serializados sin tipo, endpoints y restricciones sin cerrar.
Las observaciones de caminos se solapan: no son referencias únicas.

Evidencia `external-reference-closure-f801083d/evidence/summary.json`, SHA256
`27e108b14a0aa705f860f8a4ee4ea8416273ce0629efb476bf788c6405f17182`;
archivo de 33 miembros SHA256
`ca2da8a1f629b10c7636eff4912738acdb45a3d78d5564b50a702d30d19f200b`.
El coordinador reprodujo offline tres evaluaciones/summaries contra código
confiable y hashes originales; el dump permanece privado en servidor.
**No se importaron maestros, reglas ni aliases.** Este contrato evita una
adopción destructiva; no autoriza afirmar bootstrap cerrado.

## Qué falta y valoración del 31

La matriz vigente cuenta 133 módulos propios en repo y 37 fuera del inventario
instalado de Cerro, incluidos adaptadores/referencias. Continúan **54 apps
propias instaladas con caminos Enterprise y 140 Enterprise en producción**.
Añadir adaptadores probados no reduce por sí solo esos consumidores.

1. Coadoptar los 120 maestros/71 reglas y permisos/FK/M2M/JSON/aliases originales
   con identidad física cerrada. Beneficios nativos: diez modelos/catorce tablas/
   58 maestros pendientes. Certificar configuración chilena, días, cantidades,
   redondeos/YTD, asientos, Previred y libro contra SyS real, preservando su
   discrepancia de configuración sin copiar fórmulas a ciegas ni recalcular pagadas.
2. Completar DTE/CAF/folios/firma, cadena/revocación, respuestas y transporte SII,
   y consumidores de documentos/guías/exportación. Firma offline no es emisión.
3. Cerrar conciliación y ciclo completo de lotes, pagos y consumidores restantes.
4. Convertir Calidad nativa: doce modelos, diecisiete tablas y 19 maestros;
   `quality.check` y `qc.inspection` son identidades distintas. Studio,
   Documentos/Firma, interfaz y restantes productos siguen pendientes.
5. Ensayar copia integral restaurable con cero Enterprise, comparar datos y
   flujos por rol y aceptar en Desarrollo. Corte productivo fuera de la tarea.

**El 31 sigue en riesgo alto; no hay evidencia para prometer terminar todo en
ese plazo ni porcentaje global defendible.** Paralelizar implementaciones y
agrupar una aceptación exacta aprovecha las tres plazas adicionales disponibles;
saltarse identidad, permisos o pruebas sólo trasladaría el riesgo a los datos.
La programación sigue activa hasta cumplir las puertas de COMMUNITY_AUTONOMIA.

## Siguiente prompt

Continúa desde la canónica actualizada en worktree propio. Lee AGENTS.md,
~/.odoo/environments.json, operación, workflow, COMMUNITY_CONTINUACION.md,
COMMUNITY_CLAUSURA_CALIDAD.md, COMMUNITY_AUTONOMIA.md y sus referencias.
Conserva Q4 646/441 y D/H, relee documentos cambiados y audita inventario completo
readonly/fuentes privadas antes de implementar. Prioriza el cierre físico de
referencias Simple Digital original: discriminadores calculados/related,
JSON/serializados sin tipo, endpoints y restricciones, 120 maestros/71 reglas,
89 aliases con reporte 462 ocupado, beneficios/metadata/ACL. No importar,
reservar ni renumerar antes de cerrar todos los caminos y la concurrencia.
Mantén la cabecera técnica Q4 y su soporte de impresión múltiple, sin atribuir
layout productivo/legal o adopción original. Usa hasta las plazas autorizadas
para frentes independientes reales: Calidad nativa/consumidores, DTE completo
y Tesorería, con upgrades siempre serializados. Prueba paquete exacto en
Community oficial y copia fresca Cerro; conserva IDs, maestros, ACL, relaciones,
históricos, saldos y contadores. Respeta Calendar, Boolean bancario y 210233.
No recalcules cerradas ni toques producción, vencimientos, QA-Cerro, SII real
o fuentes OEEL. Guarda evidencia privada, commits/push, integra sólo lo validado
y ejecuta python tools/git/verify_handoff.py --require-pushed. Informa avances,
bloqueos y riesgo real; ninguna extracción parcial resuelve el vencimiento.
