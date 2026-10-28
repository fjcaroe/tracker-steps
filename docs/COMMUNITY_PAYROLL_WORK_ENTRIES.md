# Entradas de trabajo y cálculo OCA — 28-10-2026

Base canónica `ba3f252`. Continuación de
[COMMUNITY_PAYROLL_API.md](COMMUNITY_PAYROLL_API.md) y
[COMMUNITY_HR_PAYROLL.md](COMMUNITY_HR_PAYROLL.md). Este bloque implementa contratos
sobre los modelos reales OCA; no instala todavía Simple Digital en Community ni
convierte integralmente Cerro. No cambia dependencias de consumidores instalados.

## Contratos operacionales

Los tres addons pasan a 18.0.1.1.0. El candidato usa `hr_work_entry_contract` y
`hr_work_entry_holidays` oficiales Community, además de OCA fijado a `4c71cd4`.
No se copian componentes OEEL-1 ni se crea un `hr_payroll` vacío.

- `hr.contract.get_work_hours` lee entradas activas reales en borrador/validadas,
  con contratos, empresa, permisos, duración y calendario originales. Convierte
  los límites del período desde el huso del calendario a UTC; recorta cruces de
  período y usa el calendario para ausencias parciales. No eleva permisos.
- `hr.payslip.worked_days.work_entry_type_id` conserva una relación real al tipo;
  los métodos `_get_worked_day_lines_values`, `_get_worked_day_lines` y
  `_get_out_of_contract_calendar` ofrecen la frontera que consume el proveedor.
  Los días se derivan de horas/jornada del calendario, sin asumir asistencia
  constante ni reemplazar las reglas chilenas del proveedor por un mes fijo.
- La estructura permite activar **Usar entradas de trabajo**, seleccionar el tipo
  original para fuera de contrato y activar el redondeo de conceptos en CLP.
  El formulario se integra en la configuración nativa de estructuras OCA.
- El cálculo con entradas reales valida el lote completo antes de escribir.
  Rechaza ausencia de entradas, conflictos y líneas antiguas sin relación de tipo
  adoptada. Actualiza días existentes conservando sus IDs; conserva también las
  filas de tipos que desaparecen del período, llevándolas a cero. Un error posterior
  del motor revierte el refresco. No calcula sobre pagadas/validadas.
- La adopción de días heredados es explícita: no asigna maestros por un nombre
  ambiguo ni borra líneas históricas para habilitar el nuevo modo.
- Los días fuera de contrato proceden del calendario. El tipo es una FK de la
  estructura al maestro existente; puede reutilizar el XML ID original del
  proveedor. No crea un maestro paralelo OUT ni imita el XML ID Enterprise.
- Redondeo de días: NO/HALF/FULL, UP/DOWN/HALF-UP y predeterminado DOWN, como
  el contrato nativo. El residuo se concentra en el grupo mayor de horas.

Las estructuras sin activación explícita conservan el cálculo por calendario OCA.
Las lecturas de horas no generan entradas ni cambian sus estados. El modo nuevo
no sustituye los orígenes Enterprise Attendance/Planning: su producción de entradas
sigue pendiente donde se utilice.

## Entradas repetidas, cantidades y conceptos

Las entradas tipadas repetidas de un mismo tipo conservan sus filas e IDs.
El contexto de reglas agrega sus importes sobre esos registros reales. Cuando
el código de una regla coincide con el de las entradas repetidas, evalúa cada
entrada por separado: una regla no lineal sobre 2 y 3 da 4+9=13, no 25.
El contexto posterior conserva los totales agregados de `result_rules` y categorías.
El helper legado OCA `get_salary_line_total` suma esas líneas tipadas repetidas,
en lugar de devolver únicamente la primera; conserva su comportamiento anterior
para datos legados sin tipo.

No mezcla silenciosamente entradas tipadas con entradas antiguas sin tipo bajo
el mismo código. Rechaza esa ambigüedad y un contrato distinto al de la liquidación.
Los accesos por diccionario de categorías/resultados coexisten con el acceso
legado OCA por atributo. No se sustituye el registro real `payslip`.

La política de conceptos CLP replica el puente ya versionado
`step_hr_payroll_rounding`: desde 01-10-2026, solo borrador/verificación, moneda
CLP y estructura configurada o tipo Chile original. Redondea el resultado final
cantidad × importe × tasa antes de acumular categorías. No cambia el puente
instalado en producción ni reescribe importes de períodos anteriores.

Los escenarios conocidos comparan sueldo base 553.553, bono, gratificación,
colación y descuentos de prueba con ambos motores reales:

| Días del escenario | Imponible | Líquido |
| --- | ---: | ---: |
| 28 | 738.071 | 633.904 |
| 29 | 761.136 | 599.279 |

Son escenarios del puente de redondeo, con descuentos de fixture. No equivalen a
certificar impuestos/cotizaciones ni las 71 reglas completas del proveedor.
Se prueban además cantidades fraccionarias, tasas, signos y persistencia CLP.

## Puerta de adaptación e identidad

`tools/community/compare_payroll_schema.py` compara solo bases privadas con
sesiones PostgreSQL forzadas a lectura. Incluye los modelos de Nómina/contratos,
work entries, Previred/libro y campos con XML IDs de Simple Digital o motores
Enterprise. Compara tipos, relaciones, almacenamiento, obligatoriedad y valores
de selección; registra IDs y alias originales para preparar la adopción.
La ausencia en una base Community vacía no autoriza crear modelos ficticios ni
cambiar dependencias. El inventario incluye aplicaciones todavía no instaladas;
no contar sus filas como funciones nuevas que haya que programar una por una.

Las diferencias estructurales conocidas incluyen `rule_ids` One2many nativo
frente a Many2many OCA, tres notas HTML frente a Text, campos del proveedor,
entradas de instituciones, pago diario/quincenal, estados pagados de liquidación
/lote y modalidades de reglas por entrada. Deben cerrarse con mapas y pruebas,
conservando FK/M2M, modelos, grupos, vistas, acciones y XML IDs originales.

YTD sigue rechazado explícitamente; faltan configuración de reinicio, estructuras,
correcciones, notas de crédito y evidencia histórica para implementarlo sin
inventar acumulados. La base original de Cerro no contiene contratos/liquidaciones
pagadas para acreditar esa conversión. No usar fixtures como sustituto.

Quedan la instalación efectiva del proveedor y sus puentes/vistas en OCA,
los 71 registros de reglas, cuatro estructuras/seis tipos de entrada, la política
chilena completa de días/ausencias, Previred (dos perfiles) y libro (dos perfiles,
42 líneas), incluidos archivos oficiales y casos representativos con permisos.
No se cambian sus dependencias ni se afirma certificación normativa en este bloque.

## Camino crítico

Se conservan Calendar, Boolean bancario y `210233` descontinuada. Producción y
QA-Cerro no se actualizan ni se refrescan; no se alteran vencimientos ni se
recalculan pagadas. Siguen 53 apps propias con caminos Enterprise sobre las 93
inventariadas y 140 módulos Enterprise en producción. No convertir esos números
en un porcentaje de migración completa.

DTE/CAF/folios/firmas/certificados/respuestas SII, Calidad/Studio/Documentos/Firma,
Tesorería restante y consumidores pendientes siguen abiertos. No se emite al SII.
Falta una conversión integral fresca con cero Enterprise, recuperación, revisión
en Desarrollo y aceptación por empresa/perfil. Al 28-10-2026 no hay evidencia
para comprometer un corte integral seguro el 31. Riesgo alto; vencimiento pendiente.


## Aceptación y evidencia

Código de addons `bebf5ab`, paquete final **F**, tres addons/17 archivos.
Runtime oficial Community `4b4efe68291d6def5bb7d2e1f2b829e0cda577d4` y OCA
`4c71cd42e46a09a7512d92f5c63c0a9f7c26ad3e`, limpios y fijados. Ambos ensayos
reciben los mismos bytes; el manifiesto de huellas coincide con Git exportado
con `core.autocrlf=true` y `core.eol=crlf`.

| Ensayo F | Pruebas | Instalados / EE | Alcance |
| --- | ---: | ---: | --- |
| Community oficial + OCA + adaptador | 68 (38 upstream + 30 propias) | 64 / 0 | Entradas reales, reglas, redondeos, identidades de días, permisos y asientos |
| Copia fresca de Cerro + referencia nativa | 15 | 376 / 140 | Los mismos 15 contratos compartidos contra el motor real instalado |

La copia de referencia **no instala OCA ni convierte el motor**: usa los addons
común y de referencia; Community usa común y adaptador. Es una comparación de
contratos entre motores, no un ensayo integral convertido. No se retira EE.
Los escenarios no certifican el conjunto de reglas chilenas ni archivos oficiales.

Se preservan 1.058 contratos de datos: **918 tablas/proyecciones y 140 contadores
estándar exactos**, antes/después del upgrade y también después de las fixtures,
sin resetearlos. Se mantienen 58.956 XML IDs originales, 1.217 modelos, 26.994
campos, 5.071 selecciones, 2.322 ACL, 610 reglas, 1.328 menús, 417 enlaces acción/
vista, 463 relaciones y 526 restricciones. Permanecen iguales membresías de
usuarios/grupos/empresas, históricos, saldos, configuración, versiones y vencimientos.
El origen conserva cero contratos/liquidaciones y los 71 registros de reglas,
cuatro estructuras, seis tipos de entrada, dos perfiles Previred y dos perfiles/
42 líneas del libro. Las fixtures no sustituyen históricos pagados representativos.

El probe adicional `tools/community/verify_payroll_configuration.py` comprueba
menú y ancestros visibles, acción, formulario, guardado de configuración y el
onchange nativo de una liquidación nueva con entradas reales, sin superpoderes.
Revierte todas sus fixtures. El resumen revalida esas condiciones.

El mapa privado examina 1.836 campos del alcance fuente frente a 7.542 campos
totales del candidato: 1.456 ausentes —incluidos modelos de apps aún no instaladas—,
cuatro diferencias de tipo, 12 de almacenamiento, 18 de obligatoriedad y seis
selecciones incompletas. No son categorías disjuntas ni un porcentaje de avance.
La herramienta registra alias e IDs originales, no valores de remuneraciones.

Las cuatro diferencias de tipo son `rule_ids` y las notas de estructura/regla/
categoría. Las selecciones pendientes incluyen daily/semi-monthly, orígenes
Attendance/Planning, estado paid de liquidación/lote, verify del lote y reglas
por entrada. La selección HALF-UP y el default DOWN de los días se corrigieron
y probaron antes de aceptar F. Este mapa **no acredita adopción de identidades**.

Evidencia privada local:
`~/.codex/local-artifacts/community-payroll-workentries-20261027/`,
`evidence-F/`, `summary-F.json`, `source-F.tar.gz` y `evidence-F.tar.gz`.
El respaldo íntegro queda en
`/opt/steps-validation/community-payroll-workentries-20261027F/cerro-reference/`.
El exportado contiene solo JSON/logs y el mapa, sin dump, filestore, config ni enlaces;
se crea con permisos de propietario.

- SHA-256 de `source-files.json`:
  `a2aeea1871aaa35c8246b3a3c2977b3cde13b55dd902ca910bd99b862e70320e`.
- SHA-256 de `source-F.tar.gz`:
  `0cd94f888cae6a4ac8457337316152e7f90b348a56b476d9d1ad9ab885e104ae`.
- SHA-256 de `evidence-F.tar.gz`:
  `99ffc265da582b2f3fd53177f19851c0b9be61307f0119e5e8dc66de69f0cf09`.

Reproducir con `tools/community/validate_payroll_api.py` en sus modos `community`
y `cerro-reference`, en nueva raíz privada/base, desde el mismo paquete Git y
con los commits oficiales fijados. La herramienta rechaza reutilizar etapas.
Usa bloqueo compartido, overlays y copia fresca; cuenta exactamente 68/15 pruebas.
El CLI de comparación exige prefijos privados y fuerza transacciones de lectura.
El probe de configuración se ejecuta por Odoo shell con
`PAYROLL_CONFIGURATION_EVIDENCE` apuntando a su JSON privado, bajo el mismo bloqueo.
El resumen local se reproduce con:

```powershell
python tools/community/summarize_payroll_api.py <evidence-F> --output <summary-F.json>
```

Solo F es aceptación final. A tuvo fallos de fixtures/interfaz; B corrió únicamente
Community. C/D/E son regresiones preliminares verdes de versiones anteriores.
No reutilizar sus clones como bases frescas ni sumar sus pruebas. El paquete HR
468/516 previo no cambia y no se vuelve a ejecutar en este bloque.
Se conserva `simpledigital_certified=false`, `historical_conversion=false` y
`full_cerro_conversion=false`. No se publica en servicios activos.

## Siguiente prompt

```text
Continúa desde origin/codex/ambientes-canonicos-reparacion actualizada, en worktree
propio. Lee AGENTS.md, ~/.odoo/environments.json, operación, workflow, plan,
continuidad, COMMUNITY_HR_PAYROLL.md, COMMUNITY_PAYROLL_API.md,
COMMUNITY_PAYROLL_WORK_ENTRIES.md y sus referencias/matriz Enterprise.

El candidato OCA real fijado a 4c71cd4 pasó 68 pruebas Community y 15 contratos
compartidos contra Nómina real en copia fresca de Cerro. El paquete F de código
bebf5ab conserva 918 tablas/proyecciones, 140 contadores exactos, 58.956 XML IDs,
permisos/históricos/saldos. Hay días/horas reales, tipos y calendarios, recorte
horario, OUT, entradas tipadas repetidas sin perder IDs y redondeo chileno por
concepto. El formulario/configuración/onchange nativos se probaron sin sudo.
La copia de referencia mantiene 140 EE: NO es una conversión de motor ni integral.

Prioriza la instalación/adaptación efectiva de Simple Digital AGPL y sus puentes
sobre OCA, conservando licencia/autoría y sin publicar datos privados. Revisa el
mapa schema-delta.json: identidad de modelos/campos, FK/M2M de reglas, notas HTML,
almacenamiento, selecciones pagadas/lotes, reglas por entrada y contratos antes
de cambiar dependencias. Conserva IDs, alias, grupos/permisos y vistas.
No crees hr_payroll vacío ni hr.payslip simulado. No borres los originales.

Implementa YTD con reinicios, créditos/correcciones/estructuras y evidencia,
certifica 71 reglas, cuatro estructuras/seis tipos de entrada, días chilenos
completos, contabilización y archivos Previred (dos perfiles) y libro (dos/42).
Cerro no contiene liquidaciones pagadas originales: exige evidencia representativa
antes de declarar migrados históricos; las fixtures no la sustituyen.

Mantén visibles DTE/CAF/folios/firmas/respuestas SII, las 53 apps con caminos EE
sobre 93 inventariadas y la conversión integral fresca con cero EE, restauración
y aceptación en Desarrollo. El 31 no está resuelto. No emitas al SII real.
Respeta Calendar, Boolean bancario y 210233. No recalcules pagadas, retires EE en
producción, alteres vencimientos ni refresques QA-Cerro. Prueba el paquete exacto
en Community oficial y copia fresca, con bloqueo/overlays, conserva evidencia,
commits, push, integra lo validado y verifica el handoff con --require-pushed.
Entrega estado, límites, pendientes y valoración honesta de la fecha.
```


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
