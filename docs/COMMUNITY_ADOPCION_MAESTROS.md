## Pausa solicitada por el usuario — 30-10-2026

La migración y la automatización `migraci-n-odoo-community` están **PAUSADAS**
por petición del usuario; continuará el jueves. No reactivar ni iniciar nuevas
pruebas hasta que el usuario retome el trabajo. El vencimiento del 31 no está
resuelto y no se modificó. Producción y QA-Cerro no se tocaron.

La última pareja aceptada sigue siendo **T2: 671 CE / 462 nativos** en la
canónica `c33e4b20`. El candidato **U3** pasó **684 pruebas CE**, cero fallos y
errores, y su testigo completo readonly cerró cuatro contratos de almacenamiento.
La referencia nativa se interrumpió por esta pausa; **467 es su objetivo, no un
resultado aprobado**. No hay pareja U aceptada ni evidencia sellada. No integrar
el candidato a la canónica ni reutilizar la copia interrumpida como aceptación.

Punto recuperable:

- `origin/codex/community-adoption-validated-20261030`, código `4312b0f7`:
  29 archivos seleccionados, API 1.17.0, 33 propios/467 archivos + 52 AGPL.
  Pasaron 62 pruebas puras; el código sigue pendiente de aceptación funcional doble.
- `origin/codex/community-storage-20261030`, `9ac5284e`: implementación completa,
  herramientas ancladas y ensayos conservados. Candidato normal en
  `/opt/steps-validation/community-multifront-parallel-20261030U3` y recibos locales
  en `~/.codex/local-artifacts/community-storage-20261030U`.
- Ensayo anclado U2: instalación real terminada, 59.113 XML IDs sin pérdidas ni
  retargets, 950 contratos/949 literales, 146 contadores exactos, cero diferencias
  de constraints originales. Quedan 32 columnas con obligatoriedad distinta y
  32 FK nuevas. La revisión agregada de históricos no es exacta y su clasificación
  quedó cancelada: no afirmar preservación integral. Review SHA256
  `047ed159127fc6c05f9bdef35c397652665e0dcf63297d537d1209b547fb6efe`.
- El observador nativo U2 rechazó correctamente su constante antigua 381 ante
  el origen actual 382. El agente preservó `2802bcde` en
  `origin/codex/community-storage-custody-U-20261030`: perfil opt-in ligado al
  inventario 9358 y a la lista completa de módulos, con 14 pruebas puras y replay
  offline real. No está integrado ni probado funcionalmente; recuperar y revisar.

Al retomar: fetch y revisar concurrencia; recuperar los commits indicados;
repetir la pareja exacta completa en una raíz y bases privadas nuevas, con el
bloqueo compartido. Completar postflight, preservación, custodia y sello antes de
integrar U. Retomar clasificación anclada y el Sourceproof explícito de 382 antes
de repetir la proyección original. Conservar F/G de S7 como evidencia separada.
La duplicación de liquidaciones/líneas y reembolsos sigue sin certificar: U0
reveló que el camino copy puede omitir el código requerido; no corregirlo tomando
valores actuales del maestro sobre históricos. Siguen pendientes certificación
de las 71 reglas, Previred/libro, DTE/CAF/SII y conversión integral restaurable
cero Enterprise. El inventario permanece en 55 apps con caminos EE y producción
conserva 140 EE. Respetar todas las restricciones anteriores.

---

# Maestros originales, permisos y referencia SyS — 30-10-2026

La pareja normal vigente es **T2**, congelada en `10278323`: **671 casos
Community y 462 nativos, cero fallos y errores**. Foundation **1.16.0** corrige
la FK de seguridad detectada después de S7 mediante la API original de Odoo.
El paquete exacto y el postflight físico pasaron en ambos entornos. S7 queda
conservado como evidencia histórica, con su regresión diagnosticada.

La copia original S7 completó además la proyección real de sus 71 reglas bajo
UID7: **71 relaciones creadas y cero en la segunda ejecución**, con commit.
Los 120 maestros originales, sus datos, IDs, ACL, reporte 462/modelo 600 y
contadores permanecen. Esto cierra la proyección de relaciones; no certifica
sus importes ni la adopción completa de metadatos, interfaz legada e históricos.
G validó por separado cinco formularios y cuatro menús de configuración contra
el testigo nativo real, conservando la categoría oculta y los otros tres visibles.
Ninguna de estas puertas convierte integralmente Cerro ni resuelve el 31.
Este bloque no publicó cambios en producción ni en QA-Cerro.

## Pareja T2 y proyección original aceptada por alcance

T2 conserva **33 addons propios / 461 archivos propios + 52 AGPL = 513**,
API **18.0.1.16.0** y Foundation **18.0.1.16.0**. El archivo Git seleccionado
coincide con el paquete probado y su evidencia fue reproducida offline desde
el worktree de integración. Pasaron 212/168 métodos críticos y 31/27 versiones
exactas. Grafos medidos independientemente: **120/0 EE Community y 398/140 EE
en referencia nativa**. La referencia sigue usando Enterprise.

Se preservaron **925 tablas/proyecciones, 147 contadores y 59.113 XML IDs**
del respaldo fresco posterior a T139/T140. Son 1.072 contratos: 1.071 literales
y el único cambio tipado `base_weight` ID1 `15.00`→`15`, sin Float ni redondeo.
El testigo T2 se reconstruyó desde su propio dump; SHA256
`0632c34720d3b9edb32ddc82826085f027c8d8eca0a876bd636afb205e175314`.
Los históricos, vencimientos e identidades originales se compararon antes y
después; no se reutilizan los snapshots anteriores para afirmar esta conservación.

Las pruebas de borrado reales verificaron RESTRICT con actor Settings normal
en ambos motores. El postflight T exige además la FK validada, no diferida,
sus columnas/extremos, modelos y campos originales. En nativa contrastó antes
del upgrade, después del upgrade, tras las pruebas y desde otra lectura final;
en CE frío no se inventó un baseline nativo. El OID queda informativo. T1 pasó
671 pruebas CE pero falló al leer OID como JSON; nativa T1 detuvo antes del
upgrade. Se conservan esos intentos y se repitió T2 con `oid::bigint`, sin
relajar la política de borrado ni fabricar un recibo T1 de aceptación.

Evidencia privada T2: `/opt/steps-validation/community-multifront-parallel-20261030T2`
y `~/.codex/local-artifacts/community-adoption-20261030S/accepted-normal-T2`.
Archivo 1.106 miembros: `11c01c60ba0263a1f87becaca404140af08350ff8b8be15f656883da139d5b57`.
Sello offline 1.108 miembros, 11.512.292 bytes:
`aafb9c8b073fe04ef90822b50bdabe41c0e217d7fd999a7b6eb1218481dbe55d`.
Resumen: `8bdd1318b54c00c4d5d9f54b73a89e43444743775a987c6630bc36e9aa74bb81`.

El intento anclado **F** usó sólo los contratos de datos/seguridad y la API
real de proyección. No saltó una excepción de menú: el alcance `projection-only`
es explícito y el alcance `full` permanece estricto. El Source nativo real es
obligatorio, con actor/contexto y partición 118 permitidos/dos denegados exactos.
Se observaron las 71 inserciones y la segunda llamada idempotente, con todas las
columnas originales, auditoría de maestros, políticas y contadores intactos.
Se conservaron 88 aliases de origen; los tres de referencia no se adoptaron.
Sólo los dos modelos OCA nuevos, vacíos y ausentes en origen recibieron lectura
del gerente existente. No se agregaron grants sobre los modelos originales.

F: `/opt/steps-validation/community-original-handover-20261030S7/anchor/probe-source-projection-F`.
Probe: `a21e327512a1ba4bc349793a64f8770d6288b9c412c1e751b405bcbca4ecd480`.
Recibo después del commit: `f926c064d3494dd7a97cc507f4bdd37f7e9aa98da8d6a11add952a59dc0d9b73`.
Mantiene `ui_admission=False`, metadatos/refs opacas no admitidos, certificación
financiera e integral falsas. El runtime anclado S7 permanece congelado en 1.15;
la corrección 1.16 probada en T2 debe adoptarse en un overlay nuevo, sin pisarlo.

El observador nativo readonly de menús confirmó, bajo el mismo UID7, tres menús
visibles y categorías ocultas con `debug=False`. No se infiere permiso desde
el nombre ni se añade el grupo técnico. Kernel y todas las conexiones PG fueron
readonly, sin ejecutar acciones ni leer nómina histórica. Source de menús:
`c5a81c31ba8242207920d301e5ee1baeb07813285f9d93157168c8485497e289`.
**G terminó con commit y los tres flags verdaderos**:
`source_menu_witness_validated`, `source_menu_visibility_parity`,
`core_ui_admitted`. Validó cinco formularios por la API real y los cuatro menús,
sus lecturas/ACL, acciones/modelos y visibilidad normal contra aquel Source.
El renderer original conservó su ruta/configuración bajo el actor normal;
no se imprimió una liquidación histórica ni se certificó su validez legal.
G observó **cero/cero inserciones** sobre las 71 membresías ya creadas por F.
Maestros, alias, auditoría, política original y contadores permanecieron exactos.
No hay excepción por país o grupo técnico: la categoría se conserva oculta
porque esa denegación fue observada realmente en ambos motores.

G: `/opt/steps-validation/community-original-handover-20261030S7/anchor/probe-source-full-G`.
Probe `511e52c07e1bb368fe51d7cb39e85014290748e27cc54accab8fbf44164701d4`;
recibo después del commit `1c101c590ecc180abf23d8b3c72ef03f00731e849be030cec42d1b7728a46c3d`.
Las copias locales se verificaron por hash y como datos inertes. `full` designa
el alcance del probe de configuración, **no la conversión completa**:
`all_legacy_flows_certified`, `original_metadata_semantics_admitted`,
`financial_certified` e `integral_conversion` siguen falsos.

Inventario vigente después de T139/T140: Cerro **382/140 EE/101 propias**;
Steps **310/123/19** y SyS **332/142/17**. Repo **134 propias / 37 fuera de Cerro**,
**55 apps instaladas con caminos EE**. La nueva app multiempresa explica el
aumento de alcance; no se atribuye a una regresión o retiro Enterprise de esta
migración. Ver la matriz y su fuente readonly `9358e34e…7240e`.

## Histórico S7: código y aceptación funcional

- Foundation `step_payroll_contracts` **18.0.1.15.0** conserva la familia nativa
  de beneficios como datos, sin fingir su API. Sus observadores contrastan
  14 tablas/58 filas y relaciones originales en el ensayo anclado. Dos aliases
  OCA reutilizan los grupos originales; no crean grupos ni membresías.
- El adaptador de `res.groups` resuelve esos dos pares mediante las interfaces
  públicas `get_id`/`parse` de las definiciones reales de Odoo. Odoo sólo registra
  un nombre externo por grupo: `env.ref` por sí solo no prueba `has_group` ni
  expresiones de campos/vistas. Se conservan IDs, evaluador, implicaciones y
  restricciones. Un alias en conflicto falla también al negarlo; el nombre
  nativo válido mantiene su comportamiento. Ocho casos nativos enfocados pasaron
  antes de repetir la pareja completa.
- API **18.0.1.16.0** añade formulario, lista, acción y menú Community reales de
  tipos de entrada. Tres casos comprueban actor normal, país oculto, campos y
  caché caliente. Los indicadores sin semántica certificada permanecen de sólo
  lectura en el formulario; no se introducen maestros.
- Paquete exacto: **33 addons propios / 461 archivos propios + 52 del proveedor
  AGPL = 513**. El archivo Git reproducido en el worktree de integración coincide
  byte a byte con los 461 archivos propios probados. Se verificaron 212/168
  métodos críticos y 31/27 versiones por modo, incluidos 26 módulos requeridos.
- Grafos medidos: Community **120 instalados / 0 EE**; copia nativa de Cerro
  **397 / 140 EE**. La segunda conserva Enterprise y es una referencia.
- Preservación normal: **921 tablas/proyecciones + 140 contadores**, 59.079
  aliases originales y sus noupdate, modelos, relaciones, ACL, históricos y
  saldos. El único cambio de representación permitido sigue siendo
  `stock_package_type.base_weight` ID 1 `15.00`→`15`; un testigo nuevo, desde el
  respaldo S7, prueba equivalencia sin Float ni redondeo. R3 permanece separado.

Evidencia privada: `/opt/steps-validation/community-multifront-parallel-20261030S7`
y `~/.codex/local-artifacts/community-adoption-20261030S`. Cápsula normal:
`8efe41690d0f7b5451455b0a9d7b9f0dc610d9674b832fd4759f29de642b9939`.
Reproducción offline con código Git confiable y sello de 1.104 miembros,
11.501.675 bytes: **`ad84c0302d4f46f39411f4f5c5fc49c468cf2cb37a394d5793f4e900c924aae0`**.
Resumen: `d9925da02991a4e55638be96151097ef651feb373b6694547202362737491e2a`.
El sello y su recibo se conservaron también en el servidor con modo 0600;
los bytes se releyeron allí y sus hashes coinciden con los verificados localmente.
El replay independiente desde el worktree de integración y 38 pruebas puras
de aliases, captura, custodia y verificador pasaron. Estas pruebas puras no
sustituyen los 1.133 casos funcionales de la pareja S7.

## Ensayo original anclado: avance y bloqueos

Las herramientas experimentales quedan preservadas en
`origin/codex/community-original-adoption-20261030`; no se presentan como una
conversión aceptada. S1 detuvo antes de ORM por Git; S3 detectó que el motor no
se había cargado. S2/S4 originales sólo se materializaron. S5/S7 cargaron OCA
real en copia fresca: **modelo 600, reporte 462, 144 instalados/0 EE** en S7,
con los demás productos explícitamente fuera de operación.

El perfil privado conserva los 120 registros y omite semillas y políticas
aditivas. Mantiene sus datos, maestros y permisos originales; dos modelos OCA
nuevos vacíos sólo admiten lectura del gerente existente. Usa cuatro columnas
nuevas nulas sin inferir propietario/padre y derivaciones LGPL mínimas para
preservar propiedades JSONB desde el primer arranque. La instalación oficial
por estados evita que `-i` propague init y recargue datos noupdate del proveedor.
La limpieza LGPL se delega completa, reteniendo sólo dos aliases originales
comprobados; 23 guardas SQL preceden ORM y sus tres negativas se ejecutaron.

El observador nativo readonly real confirmó **118 maestros permitidos y dos
tipos denegados** al UID7, sin ser superusuario ni cambiar sus cuatro compañías.
Los tipos 3/4 de Bélgica no son usados por las cuatro estructuras. Las reglas
de país originales deben conservar su denegación; no se concede acceso para
hacer pasar el ensayo. Todas las estructuras y las 71 reglas sí son visibles.
Sourceproof S7B: `6577c8c2d004778ce825e6427e3f4081080ccf15db8391febb18538082b42773`.
La primera comprobación Target S7 con ese Sourceproof pasó la política, actor,
contexto y partición de los 120 maestros. Se detuvo en el primer formulario
por el observador que prohíbe SQL fuera de la proyección. No alcanzó a escribir
las 71 membresías; el intento y su rechazo quedan conservados, sin ampliar
permisos ni aceptar una escritura por inferencia.

La revisión readonly S5 preserva 944/945 proyecciones literales, 59.079 aliases
y 140 contadores, sin columnas originales perdidas. El delta de filas es de
menús nuevos; historia/adjuntos necesitan separación técnica demostrada. Hay
36 diferencias de columnas: 33 caídas NOT NULL, dos aumentos y
`hr_payslip_line.name` VARCHAR→JSONB. Tres FK cambiaron sólo ON DELETE:
calendario SET NULL→RESTRICT, compañía RESTRICT→SET NULL y lote CASCADE→SET NULL.
Antes de restaurar CASCADE hay que cerrar `run.unlink` sobre todos sus hijos y
la protección de historias; no confiar en `unlink` de hijos ante cascada SQL.
Hay otras 32 restricciones nuevas que requieren revisión. **No hay aceptación
de conversión por esta revisión**, ni por cero EE en una cohorte aislada.

La revisión S7 independiente confirmó 944/945 entradas literales, 59.079 aliases
y **146 contadores** exactos. Sus 552 vínculos de menús originales permanecen:
hay siete vínculos adicionales sólo en menús nuevos. Se conservaron todos los
1.431 mensajes, 747 seguimientos, 620 seguidores, una actividad y 1.166 adjuntos
originales; sólo se añadió un candidato a icono técnico de menú. Los dos
parámetros de vencimiento comparados también son exactos. Estas observaciones
clasifican la diferencia sin otorgar aceptación productiva ni legal.

S7 añade una cuarta FK alterada: `rule_group_rel.group_id` RESTRICT→CASCADE al
reinicializar únicamente `res.groups`. La corrección mínima delega el updater
original del campo propietario `ir.rule.groups` después del inverso; no escribe
DDL manual ni cambia grupos, membresías o reglas. La prueba real de borrado debe
rechazar por la FK original, bajo actor Settings normal, y conservar su vínculo.
T exige además catálogo readonly antes del upgrade nativo, inmediatamente después
y tras las pruebas, con semántica y metadatos originales idénticos. Conserva
inmutables los contratos R3 y S. Candidato congelado T1: `ab9e7685`.

Las otras 32 FK nuevas están todas sobre columnas nuevas (26 SET NULL y seis
RESTRICT, once tablas). Dos `register_id` apuntan al maestro OCA nuevo, sin
materialización histórica acreditada. No sustituyen una FK anterior ni cierran
la adopción por existir. Las 36 diferencias de columnas y las tres políticas
de borrado de Nómina siguen pendientes; no hay exención para históricos vacíos.

Revisión S7: `12f26677c10e6602e7f0c3e0ab4e9e2a27813d0ee697a2c274b22f79d0a432d8`.
Clasificación readonly: `0e16916aa1c86a271998a69a8327e22cfa99096b00504f01dccff1091da14a77`.
Copias privadas verificadas localmente, sin ejecutar código de los artefactos.

## Referencia real SyS

Una única transacción RR/READ ONLY, sin ORM ni recálculo, capturó 622 cerradas
previas al mes actual, 9.710 líneas con componentes, 753 días y dos entradas.
Las 87.880 work entries son candidatas por contrato: no prueban vínculo directo
al recibo ni aprobación del período. La fuente tenía 727 cerradas; 105 actuales
quedaron fuera del corte. D registraba 627 en otro instante; no se atribuye el
cambio de población a este migrador.

La matriz reproducida liga 39 de las 71 reglas por XML ID original; 23 tienen
líneas históricas en esa cohorte. Sólo 14 coinciden en los campos/expresiones
actuales comparados; 25 difieren y 32 carecen de binding probado. SyS tiene
92 reglas: no se copia su configuración sobre Cerro por código coincidente.
La cronología de maestros sigue sin acreditar en las 71.

Se recontrastaron íntegros el positivo D, el cero F, los cuatro componentes
BASIC y la ambigüedad NET 8/32, conservada sin escoger una regla. La captura
liga 52 archivos listados del proveedor; no certifica archivos extra ni clausura
de ejecución. Artefacto privado A: `488437ac9e936279bf891c6a9c6c7ba053360fb098dd95c786f7921e50ccce77`;
replay independiente exacto: `297c761304a1badea7b23101161ff54793f360b6debbbd612e98f94a4ffd9aa8`.

## Siguiente puerta

Adoptar Foundation 1.16.0 en un overlay anclado nuevo y cerrar las diferencias
de almacenamiento/constraints. Conservar la proyección F y sus dos denegaciones;
conservar la paridad G de menús con el Source nativo real, sin conceder acceso técnico.
Cerrar menús legados y
referencias opacas, y certificar reglas, Previred/libro con casos equivalentes
probados. DTE/CAF/folios/firma/respuestas SII, demás productos y copia integral
restaurable con cero Enterprise continúan en el camino crítico. Quedan 55 apps
instaladas con caminos EE en código; producción conserva 140 EE.

El 31 sigue en riesgo. Esta migración no intervino producción, QA-Cerro,
vencimientos ni saldos. No hubo emisión SII, mensajes externos ni recálculo
de pagadas. T139/T140 es una entrega concurrente de otro frente autorizada
por sus propios tickets; sus cambios fueron conservados e inventariados.

## Prompt de continuación

```text
Continúa desde origin/codex/ambientes-canonicos-reparacion actualizada, en un
worktree propio. Lee AGENTS.md, ~/.odoo/environments.json, operación canónica,
workflow, plan, COMMUNITY_CONTINUACION.md, COMMUNITY_ADOPCION_MAESTROS.md,
COMMUNITY_AUTONOMIA.md y sus referencias e inventario completo vigente.

T2 normal acepta 671 CE/462 nativos, 33 propios/513 archivos y preservación de
925 tablas/proyecciones, 147 contadores y 59.113 XML IDs. Conserva R3/S/Q4/D/H.
Recupera las herramientas experimentales útiles de
origin/codex/community-original-adoption-20261030; no confundas sus ensayos
con la pareja normal aceptada ni integres código experimental sin pruebas.

Prioriza cerrar la adopción original de 120 maestros/71 reglas sobre OCA:
T2 congelada en 10278323 pasó 671/462 con postflight físico de seguridad y
preservó 925 tablas/proyecciones, 147 contadores y 59.113 XML IDs. Conserva sus
recibos separados de S y T1. F proyectó realmente 71 pares, luego cero, con
commit bajo UID7 y sin modificar maestros. No repitas una inserción como si
estuviera pendiente ni atribuyas certificación financiera a esa proyección.
Reutiliza el Sourceproof nativo S7B y conserva su partición 118/2 bajo UID7.
La lectura core de vistas y los savepoints UUID1 quedaron probados con sus
fuentes y objetos reales; no vuelvas a ampliar SQL por conjetura. El Source
real de menús c5a81c31… confirmó categoría oculta y tres visibles; G ya contrastó
Target con ese testigo, cinco formularios y cuatro menús, con cero/cero nuevas
inserciones. No repitas esos bloqueos como si faltara probar origen o Target.
Conserva F y G separados y sus límites: no certifican los importes ni todos
los flujos legados. Recupera las herramientas validadas de la rama indicada.
Usa un overlay nuevo para 1.16.0, sin sobrescribir S7 ni sus fuentes congeladas.
Revisa todos los metadatos, columnas, constraints,
referencias opacas y menús legados antes de aceptar la cohorte. Evita el cambio
VARCHAR→JSONB y restaura la semántica de las tres FK sólo con pruebas y guardas
reales de históricos; CASCADE exige proteger run.unlink incluso ante hijos
ocultos. No adoptes permisos nuevos sobre modelos originales.

Usa la captura SyS A y su replay offline como referencia real, sin sustituir
las reglas de Cerro ni atribuir cronología a sus 71 maestros. Cierra la prueba
equivalente de reglas, días/entradas, redondeos/YTD, asientos, Previred y libro.
Usa los tres agentes disponibles en worktrees separados y coordina SQL/ORM
bajo /run/lock/steps-environments.lock. Conserva fuentes congeladas y reserva.

Preserva IDs, maestros, ACL, relaciones, históricos, saldos y correlativos.
Respeta Calendar, el Boolean bancario y 210233. No toques producción, QA-Cerro,
vencimientos ni recalcules pagadas/validadas; no emitas al SII ni mensajes
externos, no inventes maestros ni copies OEEL. Avanza después DTE/CAF/folios/
firma/respuestas, Calidad y demás productos. Prueba el paquete exacto en CE
oficial y copia fresca de Cerro, integra sólo lo validado, commit/push y
python tools/git/verify_handoff.py --require-pushed. Mantén activa la continuidad
horaria y no declares resuelto el 31 hasta la copia integral restaurable cero EE
y la aceptación; el corte productivo queda fuera.
```
