# Adaptación de contratos Simple Digital–OCA

## Alcance del bloque

Base canónica `128b9ed`, trabajo en `codex/community-payroll-api-20261027`.
El adaptador LGPL-3 `step_payroll_oca_api` extiende los modelos reales de
OCA `payroll`/`payroll_account`, fijados al commit
`4c71cd42e46a09a7512d92f5c63c0a9f7c26ad3e`. No define `hr.payslip` ni
crea un módulo vacío `hr_payroll`. No instala Simple Digital sobre OCA todavía.
Las fuentes efectivas y licencias del proveedor se auditaron en
[COMMUNITY_HR_PAYROLL.md](COMMUNITY_HR_PAYROLL.md).

Contratos implementados:

- Tipo de entrada real `hr.payslip.input.type`, relación restrictiva de la
  entrada al tipo y validación de código, país, estructura, empleado y compañía.
  Conserva el nombre de tabla M2M y columnas comprobados en Cerro; esto prepara
  la adopción futura, pero no acredita que esa adopción ya se haya ejecutado.
- Estructura enlazada al tipo nativo de contratos Community. Regla con FK a su
  estructura primaria, sincronizada con el M2M que realmente calcula OCA.
  No permite quitar una regla primaria del M2M sin mover antes su FK.
- Lectura ORM de importes/cantidad/total por código, con suma de varias
  liquidaciones y permisos del usuario. Los acumulados YTD se rechazan
  explícitamente: no se reemplazan por cero ni por un total mensual.
- Acceso `inputs[code]` y `inputs.get` sobre entradas reales, manteniendo también
  el acceso legado OCA por atributo y su consulta histórica `sum`.
  Las entradas tipadas con código repetido (también mezcladas con entradas sin
  tipo) se rechazan antes de calcular: la agregación del proveedor sigue pendiente.
- `worked_days.get` conserva las líneas reales de OCA. El motor OCA ya entrega
  el registro ORM real `payslip` a las reglas; no fue necesario simularlo.
- Bloqueo de `compute_sheet` si cualquier liquidación está pagada o fuera de
  borrador/verificación. Los tipos ya usados conservan código, país y ámbito.

Las entradas antiguas sin tipo siguen admitidas para respetar el contrato OCA.
No se cambian dependencias de apps instaladas ni se copian reglas chilenas a
un motor incompatible. Cambiar estructura/empleado/compañía/contrato de una liquidación vuelve a
validar sus entradas tipadas, evitando relaciones inconsistentes por API.
Los grupos OCA mantienen sus permisos; solo se añaden
ACL del modelo de tipos: lectura para Nómina y gestión para su responsable.
La conservación de grupos/XML IDs Enterprise al convertir está pendiente.

## Comparación con Cerro

`step_payroll_contracts` contiene pruebas comunes sobre modelos reales.
`step_payroll_enterprise_reference` solo puede instalarse en una base privada
con prefijo `MANAGEMENT_QA_CERRO_PAYROLL_API_`. Ejecuta los mismos contratos
contra el motor actual de Cerro, sin instalar OCA ni el adaptador en esa copia.
Ambas etapas reciben el mismo paquete y comprueban sus huellas, pero instalan
subconjuntos distintos: una comparación de API no es una conversión integral.

`tools/community/validate_payroll_api.py` usa Community oficial limpio y OCA
fijado, bloqueo compartido, overlays privados y una copia nueva de producción.
Desactiva cron y correo únicamente en la copia, conserva el filestore y mide
los datos originales antes/después del upgrade y de las pruebas. Nunca altera
producción, QA-Cerro, vencimientos ni liquidaciones originales pagadas.

## Pendientes obligatorios

1. Adaptar días/ausencias a entradas de trabajo reales:
   `hr.payslip.worked_days.work_entry_type_id` y
   `_get_worked_day_lines_values(domain)`, contratos, jornadas parciales,
   licencias, ausencias y correcciones. No usar días constantes.
2. Adaptar las vistas/XML IDs, grupos y dependencias reales de Simple Digital,
   gastos y sus puentes. Migrar propietario de modelos/campos y M2M conservando
   IDs antes de retirar el motor anterior en una copia. OCA hace heredar
   `hr.payslip.line` de `hr.salary.rule`; la conversión requiere un mapa de campos
   propio, además de adoptar los nombres de modelos. Este adaptador no reescribe
   liquidaciones existentes.
3. Certificar 71 reglas, cuatro estructuras, seis tipos de entrada, instituciones,
   topes, impuestos, redondeos, cantidades, acumulados y casos chilenos.
   Un asiento genérico balanceado no certifica la contabilización chilena. Las pruebas comunes usan compañía privada en CLP,
   cantidades unitarias y expectativas redondeadas por moneda; no certifican
   jornadas parciales, interacción entre reglas ni todo el redondeo del proveedor.
4. Certificar Previred (dos perfiles) y libro (dos perfiles/42 líneas), con
   comparaciones de archivos/cifras y permisos reales. No publicar datos privados.
5. Probar históricos pagados representativos: Cerro no contiene contratos ni
   liquidaciones originales; las fixtures no sustituyen esa evidencia.
6. Cerrar DTE/CAF/folios/firmas/certificados/respuestas SII y el resto de
   consumidores Enterprise; conversión integral fresca con cero Enterprise,
   restauración, revisión en Desarrollo y aceptación por perfil.

Siguen vigentes Calendar, el override Boolean bancario y `210233` descontinuada.
Producción conserva 140 módulos Enterprise. Las 53 clausuras con Enterprise
sobre 93 apps propias del inventario anterior no bajan por añadir este adaptador.
No hay evidencia suficiente para comprometer una migración integral segura el
31 de octubre de 2026. El riesgo sigue alto y el vencimiento no está resuelto.

## Reproducción

Construir el paquete desde el commit de código `7c95671` con
`git -c core.autocrlf=true -c core.eol=crlf archive`, incluyendo `step_payroll_contracts`, `step_payroll_oca_api`,
`step_payroll_enterprise_reference` y `tools`. Extraer en `addons/` de una raíz
nueva bajo `/opt/steps-validation/`. Usar nuevas bases con los prefijos exigidos;
las etapas aceptadas no se reutilizan como copias frescas.

Ejecutar el validador con los modos `community` y `cerro-reference`, la misma
raíz y paquete, `--runtime` apuntando al checkout oficial
`4b4efe68291d6def5bb7d2e1f2b829e0cda577d4` y `--oca` al commit fijado.
Los argumentos `--root` y `--database` son obligatorios. El proceso exige fuentes
limpias, cuenta pruebas (53/6) y rechaza errores. La copia nativa mide antes y
después del upgrade, antes de ejecutar las fixtures; el motor candidato nunca
se instala simultáneamente con Enterprise en esa referencia.

Exportar únicamente JSON y logs de las dos etapas a un directorio privado,
excluyendo dump, filestore, configuración y enlaces. Verificar el exportado con:

```powershell
python tools/community/summarize_payroll_api.py <evidence-G> --output <summary-G.json>
```

El resumen compara la exportación Git con CRLF fijado y el código local
(normalizando solo finales de línea para esa última comparación), verifica el SHA del validador y vuelve a comparar los datos
e identidades originales. El paquete aceptado conserva los bytes de esa exportación Git con CRLF.
`git archive` aplica filtros de finales de línea; no confundir sus bytes con
los blobs LF almacenados por Git. Publicar el archivo exacto aceptado o verificar
las huellas del exportado antes de usarlo. No sumar los casos nuevos a la
regresión HR previa: son paquetes y alcances de prueba distintos.

## Aceptación del paquete API — 27-10-2026

Código `7c95671`, paquete final G: tres addons/15 archivos, iguales en ambas
etapas y comprobados contra la exportación Git. SHA-256 de `source-files.json`:
`90bab0161a97915b7f67b7c4bdad921e454b57d6df5fd6087fcd8d728ea3e5b3`.

| Ensayo privado G | Pruebas | Instalados / Enterprise | Alcance |
| --- | ---: | ---: | --- |
| Community oficial + OCA + adaptador | 53 (38 OCA + 15 nuevas) | 64 / 0 | Cálculo, entradas, CLP, asiento, relaciones, permisos y protección de pagadas |
| Copia fresca de Cerro + referencia nativa | 6 | 376 / 140 | Los mismos seis contratos genéricos contra Nómina real, sin instalar OCA |

La copia preserva los 1.058 contratos de datos: **918 tablas/proyecciones y
140 contadores exactos**, tanto durante el upgrade como después de las fixtures.
No se resetean contadores. Conserva **58.956 XML IDs**, 1.217 modelos, 26.994 campos,
5.071 selecciones, 2.322 ACL, 610 reglas, 1.328 menús, 417 vínculos acción/vista,
463 relaciones y 526 restricciones originales. Los 1.614 vínculos usuario/grupo,
36 usuario/compañía, 283 grupos implicados y 338 grupos de reglas permanecen iguales.
También 1.389 mensajes, 738 cambios seguidos, 601 seguidores, cero actividades y
1.125 adjuntos de negocio; vencimientos, configuración y versiones de producción
sin cambios. Las comparaciones incluyen saldos, maestros y relaciones originales.

Evidencia privada: `~/.codex/local-artifacts/community-payroll-api-20261027/`,
`evidence-G/`, `summary-G.json`, `evidence-G.tar.gz` y `source-G.tar.gz`.
SHA-256 del exportado de evidencia:
`f26420f7244646274ee1926ca0e765aad562209849dd8f1ba7b4f748f58d63c4`.
SHA-256 del paquete de fuentes:
`7263d928ce3e24382ad89ef393a42892efc4fa4159d6579a7096d4b454878689`.
El respaldo íntegro y filestore permanecen privados en
`/opt/steps-validation/community-payroll-api-20261027G/cerro-reference/`.
El exportado tiene permisos de propietario y excluye dump, filestore y configuración.

Solo G es aceptación final. A/B/C/D/F contienen diagnósticos; no acreditan el
paquete final. Los dos controladores E y la referencia F se cancelaron esperando
el bloqueo, antes de crear esas bases. D sí pasó los seis contratos nativos y
preservación; su ensayo Community detectó una comparación de caché monetaria.
G verifica filas persistidas completas antes/después del recálculo rechazado.

La regresión HR previamente aceptada (468/516) conserva su alcance anterior.
Este bloque no la vuelve a ejecutar ni cambia sus 28 addons. Las 53/6 pruebas
nuevas no se suman para anunciar una certificación integral. No se publica en
ambientes activos y no se emite al SII real. Se mantiene
`simpledigital_certified=false`, `historical_conversion=false` y
`full_cerro_conversion=false`.

## Siguiente prompt

```text
Continúa desde origin/codex/ambientes-canonicos-reparacion actualizada, en un
worktree propio. Lee AGENTS.md, ~/.odoo/environments.json, operación, workflow,
plan, continuidad, COMMUNITY_HR_PAYROLL.md, COMMUNITY_PAYROLL_API.md y documentos
referenciados, además de la matriz Enterprise. La API OCA real pasó 53 pruebas
Community y seis contratos contra Nómina real en copia fresca de Cerro; el
paquete G conserva 918 tablas/proyecciones, 140 contadores exactos y 58.956 XML IDs.
La copia de referencia conserva 140 Enterprise: NO es una conversión integral.

Prioriza días/ausencias y hr.work.entry reales, work_entry_type_id y
_get_worked_day_lines_values, agregación de entradas repetidas, cantidades,
redondeos entre reglas y YTD. Adapta Simple Digital y sus puentes/vistas/IDs/grupos
sin un hr_payroll vacío ni un hr.payslip simulado. Usa OCA fijado a
4c71cd42e46a09a7512d92f5c63c0a9f7c26ad3e. Audita también la herencia de líneas
OCA; adopta modelos, campos, relaciones y permisos antes de cambiar dependencias.
Certifica 71 reglas, cuatro estructuras, seis tipos de entrada, contabilización,
Previred (dos perfiles) y libro (dos perfiles/42 líneas) con casos chilenos.
Cerro no tiene contratos/liquidaciones originales: exige evidencia representativa
para históricos pagados; las fixtures no la sustituyen.

Mantén visible DTE/CAF/folios/firmas/respuestas SII y la conversión integral fresca
con cero Enterprise, recuperación y aceptación en Desarrollo. Siguen 53 apps con
caminos Enterprise sobre 93 del inventario, y 140 Enterprise en producción.
El vencimiento del 31 no está resuelto. No emitas al SII real.

Preserva IDs, maestros, relaciones, permisos, históricos, saldos y correlativos.
Respeta Calendar, Boolean bancario y 210233. No recalcules pagadas, retires
Enterprise en producción, alteres vencimientos ni refresques QA-Cerro.
Prueba el paquete exacto en Community oficial y copia fresca de Cerro, con
bloqueo compartido y overlays privados. Publica solo el paquete exacto aceptado.
Guarda commits, push, integra lo validado y ejecuta
python tools/git/verify_handoff.py --require-pushed. Entrega evidencia, pendientes
y valoración honesta del 31.
```


## Días reales, entradas repetidas y redondeo OCA — 28-10-2026

Código `bebf5ab`, paquete F: tres addons/17 archivos idénticos, 68 pruebas
Community oficial (64/0 EE) y 15 contratos compartidos contra Nómina real en
copia fresca de Cerro (376/140 EE). Se conservan 918 tablas/proyecciones,
140 contadores exactos incluso después de fixtures, 58.956 XML IDs, relaciones,
permisos, históricos y saldos. Menú, formulario, configuración y onchange de
liquidación se comprueban con permisos normales y fixtures revertidas.

Se implementan horas/días sobre work entries y calendarios reales, tipos FK,
OUT sin maestros paralelos y actualización de días conservando IDs. El cálculo
con ese modo rechaza entradas faltantes, conflictos y relaciones heredadas sin
adoptar. Las repeticiones tipadas homogéneas ahora se evalúan y agregan sin perder
filas, incluidos conceptos no lineales, categorías y el helper de totales OCA;
la mezcla ambigua con entradas sin tipo sigue rechazada. Se contrasta el
redondeo CLP por concepto con dos escenarios del puente chileno, sin cambiarlo
en producción ni recalcular pagadas. YTD sigue explícitamente pendiente.

La copia es referencia con su motor original; no instala OCA ni representa una
conversión integral. El nuevo mapa de lectura registra diferencias de campos,
FK/M2M, HTML/selecciones/estados que deben cerrarse antes de cambiar dependencias.
Simple Digital completo, las 71 reglas, Previred/libro, históricos pagados,
DTE/CAF/SII y el ensayo integral cero EE siguen pendientes. No se actualizan
servicios activos ni QA-Cerro, no se cambian vencimientos. Siguen 53 clausuras EE
sobre 93 apps inventariadas y 140 EE en producción. El 31 continúa con riesgo alto.

Alcance vigente, hashes, evidencia, mapa y **siguiente prompt** en
[COMMUNITY_PAYROLL_WORK_ENTRIES.md](COMMUNITY_PAYROLL_WORK_ENTRIES.md).


## Instalación Simple Digital–OCA — 28-10-2026

Paquete K, código c930d5a: 80 pruebas Community oficial (68 módulos/0 EE) y
27 en copia fresca nativa de Cerro (377/140 EE), con 82 archivos idénticos.
Se conservan 918 tablas/proyecciones, 140 contadores, 58.956 XML IDs y metadatos,
permisos, relaciones, históricos y saldos originales. El proveedor real instala
sin campos faltantes ni diferencias en los atributos comparados de sus campos;
se prueban aliases de IDs originales, acceso propio/ajeno, formulario/acción e
informe. La referencia mantiene su motor: la conversión integral, almacenamiento
histórico, 71 reglas, YTD, Previred/libro y DTE/CAF/SII siguen pendientes.
El vencimiento del 31 no está resuelto. Producción y QA-Cerro no se modifican.

Estado, alcance, evidencia privada y **prompt vigente** en
[COMMUNITY_SIMPLEDIGITAL_OCA.md](COMMUNITY_SIMPLEDIGITAL_OCA.md).
La continuidad horaria autorizada y sus puertas de cierre están en
[COMMUNITY_AUTONOMIA.md](COMMUNITY_AUTONOMIA.md); la matriz completa actualizada es
[COMMUNITY_INVENTARIO_ENTERPRISE_20261028.md](COMMUNITY_INVENTARIO_ENTERPRISE_20261028.md).
