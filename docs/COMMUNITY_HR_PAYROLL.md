# HR operacional y candidato de Nómina Community

## Alcance y contratos

`step_hr` 18.0.1.10.0 conserva la aplicación Actividades original, sus menús,
acciones de cliente, assets, Tracker, sincronización, configuración e histórico.
Declara Movilización como consumidor real del dashboard. Los modelos, tablas,
relaciones a empleados/flota y permisos existentes no se copian ni se sustituyen.
La aplicación puede instalarse con fuentes oficiales Community sin Nómina ni mapa
Enterprise. Los núcleos agrícolas y laborales mantienen sus raíces alternativas
inactivas cuando existe la raíz original de HR, también en instalaciones nuevas.
Los verificadores distinguen existencia de la raíz de la edición del servidor.

`step_hr_payroll_bridge` depende de los modelos reales de `hr_payroll`, del puente
`step_labor_payroll_wizards`, de HR y de `web_map`. Conserva `hr.payslip.net_liquido`,
las relaciones de Cuadrillas al lote/estructura, el método real de Tarjas hacia
entradas de trabajo y las cuatro vistas originales. Adopta sus XML IDs antes de
la limpieza de módulos y protege los alias de modelos/campos, incluido el campo
delegado de `res.users`. No crea otro modelo de liquidación ni permisos nuevos.
Debe instalarse explícitamente en la copia de Cerro al actualizar HR; quitar
simplemente las dependencias de HR sin instalar este puente pierde el contrato.
La premigración rechaza actualizar HR con Nómina instalada si el puente no está instalado o programado en el mismo paquete. No se despliega en servicios activos en este bloque.

El override legado `res.partner.duplicate_bank_partner_ids` sigue siendo Boolean
en Cerro a través del puente. Una instalación Community nueva conserva el
Many2many nativo de Contabilidad. Esto **no** convierte el Boolean histórico en
relación ni permite retirar el puente sin una migración bancaria específica.
Los límites visuales de Calendar y la cuenta `210233` descontinuada siguen vigentes.

## Auditoría del proveedor y del motor

`tools/community/audit_payroll_community.py` consulta solo Cerro con sesiones
PostgreSQL forzadas a lectura. Audita los manifiestos efectivos, huellas de fuentes,
modelos, campos, firmas de métodos, llamadas a `super`, referencias de reglas y
configuración de estructuras/entradas/Previred/libros. No publica cuerpos de reglas,
datos de trabajadores, configuración del servidor ni secretos. El resultado se
guarda fuera del checkout. La licencia declarada no acredita compatibilidad de API.

La fuente efectiva de Simple Digital declara AGPL-3 y versión 18.0.1.0.0, pero
sus dependencias `hr_payroll`, `hr_payroll_account` y `hr_payroll_expense` son
OEEL-1. El primero depende a su vez de entradas de trabajo Enterprise. No basta
cambiar esos nombres ni retirar Enterprise de producción para convertir el motor.

Se fija el candidato real [OCA/payroll](https://github.com/OCA/payroll/tree/4c71cd42e46a09a7512d92f5c63c0a9f7c26ad3e),
con módulos `payroll` 18.0.1.4.0 y `payroll_account` 18.0.1.0.6, LGPL-3.
Se ensaya en una base Community nueva y aislada: motor nativo, reglas/contratos,
entrada, cálculo y contabilización propios; nunca un stub de `hr.payslip`.
Este ensayo **no** adapta ni instala Simple Digital sobre OCA.

| Contrato requerido por el stack actual | Brecha a cerrar con OCA |
| --- | --- |
| Módulos y XML IDs `hr_payroll*` | OCA usa `payroll*`; hay que adaptar dependencias y adoptar IDs de modelos, grupos, reglas, acciones y vistas sin fachadas vacías. |
| `hr.payroll.structure.type`, `hr.contract.structure_type_id` | Los modelos base sí existen en Community oficial. OCA usa además `hr.contract.struct_id`; faltan el enlace `hr.payroll.structure.type_id` y los complementos del proveedor, conservando IDs y semántica. |
| `hr.salary.rule.struct_id` | OCA usa reglas asociadas a estructuras por M2M; falta conservar la relación original y demostrar equivalencia. |
| `hr.payslip.input.type` e `input_type_id` | OCA usa entradas con código y `hr.rule.input`; faltan tipos, restricciones por estructura e identidad de entradas originales. |
| `hr.payslip.worked_days.work_entry_type_id` y `_get_worked_day_lines_values(domain)` | Simple Digital genera asistencia/ausencias por tipos de entradas; OCA no ofrece esa misma API. No reemplazarla por días constantes. |
| `_get_line_values`, alcance líquido y contexto de reglas | Las reglas reales usan métodos, `env`, instituciones y relaciones del registro de liquidación. Hay que adaptar el contexto del motor con cálculo real y conservar las líneas originales. |
| Nómina contable/gastos | Conciliar asientos, diarios, cuentas, gastos y redondeos del motor real, sin recalcular liquidaciones pagadas. |
| Previred y libro | Mantener contratos del proveedor, controlador de salida, 105 campos/variantes, mapeos DT, estados, instituciones, permisos y cifras; certificar resultados con casos chilenos. |

Inventario de la auditoría: 4 estructuras, 5 tipos de estructura, 71 reglas,
6 tipos de entrada, 8 tipos de movimiento, 2 perfiles Previred y 2 perfiles de
libro con 42 líneas de mapeo. No hay contratos, liquidaciones, entradas de trabajo,
movimientos ni exportaciones históricas en esta base. Las pruebas con fixtures
no acreditan una conversión de liquidaciones pagadas reales ni certificación
normativa chilena. La auditoría incluye los puentes efectivos de Previred,
libro, ciclo de contratos, correcciones y transición del motor.

## Importación masiva sobre Nómina real

El wizard original ya no busca la primera liquidación o contrato del empleado.
Exige empresa activa, lote, estructura, un empleado por usuario y una liquidación
única coincidente. Toma bloqueo de filas, vuelve a leer estados y valida todo el
conjunto antes de crear entradas. Solo acepta lote abierto (`draft`/`verify`) y liquidación en borrador y no
pagada, conserva el contrato de la propia liquidación y rechaza un tipo de entrada
ya existente. Una repetición no duplica importes ni reemplaza registros originales.
No usa `sudo`, no incorpora ACL nuevos al wizard y no llama a `compute_sheet`.
La API nativa cambia el lote a `verify` al agregar una liquidación todavía en borrador; se conserva esa semántica y se rechazan lotes `close`/`paid`. El flujo APR legado sigue separado y no constituye un motor salarial.

## Pruebas y evidencia

Con esta versión, el ensayo de Cerro usa `--profile hr`: los perfiles históricos
no incluyen el nuevo puente y no autorizan una actualización aislada de HR.
El perfil `hr` de `tools/community/validate_agriculture_core.py` incorpora toda
la regresión agrícola anterior, HR operacional y el puente opcional en Cerro.
Compara el paquete completo de addons por archivo, los datos, identidades,
permisos, traducciones, históricos y contadores. El upgrade se mide antes de
las fixtures; el consumo posterior de secuencias estándar queda identificado,
monótono y sin resetear contadores. Incluye tablas originales de Tracker, histórico
y Nómina, no solo las tablas agrícolas previas.

`tools/community/validate_payroll_engine.py` fija el commit OCA y exige fuentes
limpias oficiales, DB privada nueva y bloqueo compartido. Ejecuta las pruebas
del proveedor OCA y un flujo nativo de cálculo/asiento balanceado como usuario
sin superpoderes. El resultado enumera la API faltante y mantiene
`simpledigital_compatible=false` hasta cerrar la adaptación real.

Aceptación final del código de addons `6e418ef` (27-10-2026):

| Ensayo privado | Pruebas | Instalados / Enterprise | Resultado |
| --- | ---: | ---: | --- |
| Community oficial, perfil HR F | 468 | 135 / 0 | Aprobado, incluidos formularios, menús y flujos nativos |
| Copia fresca de Cerro F | 516 | 381 / 140 | Aprobado, usuario existente 6/compañía 2/sin `sudo` |
| Motor OCA real, candidato C | 38 + flujo nativo | 62 / 0 | Cálculo, entrada y asiento balanceado; compatibilidad Simple Digital pendiente |

Los **28 addons / 837 archivos** son idénticos en ambos ensayos del paquete HR y
coinciden con el checkout. SHA-256 de `source-files.json`:
`a73b802e1bf4c0ce0f2c1e93327c66bf34f2ada5f2de0c1d34c6f81d7fda70e8`.
Runtime oficial: `4b4efe68291d6def5bb7d2e1f2b829e0cda577d4`.

La copia conserva **918 tablas/proyecciones**, **140 contadores estándar exactos
durante el upgrade**, **58.956 XML IDs originales**, 1.217 modelos, 26.994 campos
originales, 5.071 selecciones, 2.322 ACL, 610 reglas, 1.328 menús originales,
417 vínculos acción/vista, 463 registros de relación y 526 restricciones SQL/FK.
Los 1.614 vínculos usuario/grupo, 36 usuario/compañía, 283 grupos implicados y
338 grupos de reglas conservan sus hashes. Los únicos campos nuevos de ese
contrato son los dos `calendar_end` visuales ya documentados. El total posterior
es 60.126 XML IDs, 26.996 campos y 1.351 menús; los 23 menús nuevos de los núcleos
mantienen las raíces alternativas inactivas en Cerro. Se preservan los registros
originales y las dos filas propietarias de `step_hr_payslip_rel`.

Las fixtures consumen después **30** contadores estándar de la copia de modo
monótono; no se resetean para ocultar el consumo. El upgrade anterior a esas
fixtures conserva exactamente los 140. Se mantienen 1.389 mensajes, 738 cambios
seguidos, 601 seguidores, cero actividades, 1.125 adjuntos de negocio y los
parámetros de vencimiento. Las fuentes, configuración y versiones de producción
permanecen iguales al contrato de origen. Producción y QA-Cerro no reciben este
paquete. No se invoca la API externa de Tracker ni se emite al SII real.

Evidencia privada reproducible en
`~/.codex/local-artifacts/community-hr-payroll-20261027/evidence-F/`, con resumen
`summary-F.json`. Archivo `evidence-F.tar.gz`, SHA-256
`4f39c9d22cf48523c9c0829079062792cd18cf8509eccd24c5bf736a36191df4`,
exportado con permiso de propietario y sin dump, filestore, enlaces ni configuración.
El respaldo íntegro permanece en la etapa privada. Paquete de fuentes probado
`source-F-final.tar.gz`, SHA-256
`56c06ccf7121aa3df2e22ef6fcac847c5516e7fa30d30b1fc1a86b372bf631df`.
El resumen se reproduce con `tools/community/summarize_hr_evidence.py` y comprueba
otra vez los archivos del repo contra las huellas aceptadas.

Las etapas A/E y los preflights fallidos son diagnósticos conservados, no aceptación.
Las etapas B/C de HR se cancelaron mientras esperaban el bloqueo, antes de crear
bases. La aceptación corresponde únicamente al paquete final F y al motor OCA C.


La regresión ampliada de Cerro incorpora también las 34 pruebas de Exportación.
Sus expectativas se adaptan a los consumidores realmente instalados: raíz
adicional Control, roles de participantes y protección de guías con packing list.
La navegación comprueba padre, acción y formulario; conserva el orden guardado
que coloca Notas de venta antes de Instructivo. La prueba de desvinculación
acepta el error de usuario de la protección y exige que la relación siga intacta.
Los 48 casos dirigidos (14 de Nómina/puente y 34 de Exportación) aprobaron antes
de repetir el paquete completo. Las operaciones de SII/CAF siguen fuera de esta
aceptación; se preservan las políticas y las relaciones vigentes.

## Camino crítico al 31 de octubre

A 27-10-2026, quedan cuatro días hasta la fecha indicada. El cierre operacional
de HR libera dependencias, pero no resuelve el vencimiento. No hay evidencia
suficiente para comprometer un corte integral seguro el 31; riesgo alto.

1. Adaptar el motor salarial real para Simple Digital y preservar contratos,
   tipos, estructuras, reglas, entradas, estados y contabilización. Probar los
   casos chilenos y la equivalencia de Previred/libro, además de históricos reales.
2. Cerrar DTE/CAF/folios/certificados/firmas/respuestas SII y Exportación; ensayar
   sin emisión real ni reutilización de folios de producción.
3. Cerrar Calidad, Studio, Documentos/Firma, lotes/conciliación de Tesorería y
   consumidores todavía Enterprise, incluidas apps sin fuentes consolidadas.
4. Convertir una copia integral fresca con **cero Enterprise**, comparar datos,
   saldos, permisos e históricos; ensayar restauración y aceptación por perfil.
5. Revisar en Desarrollo y ejecutar el circuito de publicación autorizado con
   paquete exacto, respaldo, ventana y recuperación. QA-Cerro conserva sus datos.

Producción mantiene 140 Enterprise. No se modifica la fecha de vencimiento ni
se interpreta una extracción parcial o una prueba aislada de OCA como solución.

## Siguiente bloque y prompt de continuidad

La revisión estática de los consumidores liberados por HR no encontró llamadas
a Nómina/mapa en los seis consumidores con fuentes revisadas. `step_task`
(21 archivos en el servidor) y `step_harvest_launcher` (8) todavía necesitan
consolidación de fuentes y aceptación aislada; su manifiesto libre no acredita
el flujo Community completo. El inventario actual tiene 93 apps propias; sobre
ese mismo conjunto, la extracción de HR reduce de 60 a 53 las clausuras con
Enterprise. El bloque anterior contaba 59 sobre 91 apps; no comparar esos números
como un porcentaje de conversión. Los puentes nuevos opcionales no forman parte
de las apps instaladas de ese conteo.

```text
Continúa desde origin/codex/ambientes-canonicos-reparacion actualizada, en un
worktree propio. Lee AGENTS.md, ~/.odoo/environments.json, operación, workflow,
plan, continuidad, Productores, Operaciones, Tarjas/Cuadrillas, Cosecha,
COMMUNITY_HR_PAYROLL.md y la matriz Enterprise. Revisa la evidencia final allí.

Prioriza la adaptación real de Simple Digital a OCA payroll/payroll_account,
fijados a 4c71cd42e46a09a7512d92f5c63c0a9f7c26ad3e. El paquete HR pasó
468 pruebas en Community y 516 en copia fresca de Cerro,
con 837 archivos idénticos, 918 tablas/proyecciones, 58.956 XML IDs y 140
contadores preservados durante upgrade. El candidato OCA pasó 38 pruebas
y cálculo/asiento nativo en Community oficial 4b4efe6, pero NO es compatible aún
con Simple Digital: quedan al menos siete brechas de API comprobadas. Los modelos base
hr.payroll.structure.type y hr.contract.structure_type_id sí existen en Community;
faltan vínculos/complementos, tipos de entradas, worked_days por work entries,
relación de reglas a estructuras y métodos/contexto de cálculo. No inventes
hr.payslip ni un módulo vacío hr_payroll para engañar al cargador. Usa el motor real.

Audita y conserva los 71 registros de reglas, 4 estructuras, 6 tipos de entrada,
2 perfiles Previred y 2 de libro/42 líneas, además de los puentes de contratos,
redondeos, días, correcciones y transición del motor. Adopta XML IDs, campos,
grupos y relaciones antes de cambiar dependencias. Certifica casos chilenos,
contabilización, Previred y libro, con permisos reales y pruebas de no recálculo
pagado. Cerro no contiene contratos/liquidaciones originales ni snapshots del
motor previo: no presentes sus fixtures como conversión de históricos pagados.
El lote nativo pasa a verify al contener borradores; no confundirlo con cierre.

Mantén explícito el camino crítico DTE/CAF/folios/firmas/respuestas SII y el ensayo
integral de Cerro con cero Enterprise. Producción conserva 140 Enterprise;
53 apps propias aún tienen caminos declarados Enterprise sobre 93 inventariadas.
No está resuelto el vencimiento del 31 de octubre. No emitas al SII real.

Preserva IDs, maestros, relaciones, permisos, históricos, saldos y correlativos.
Respeta Calendar, 210233 descontinuada y el Boolean bancario legado del puente HR.
No recalcules liquidaciones pagadas, retires Enterprise en producción, alteres
vencimientos ni refresques QA-Cerro. Prueba primero los casos nuevos dirigidos
y después el paquete exacto completo en Community oficial y copia fresca de Cerro,
con overlays privados, bloqueo compartido, sin downgrade ni cambios concurrentes.
Guarda commits, push, integra solo lo validado y ejecuta
python tools/git/verify_handoff.py --require-pushed. Entrega estado acumulado,
evidencia, pendientes, valoración honesta del 31 y siguiente prompt.
```


## Contratos API Simple Digital–OCA — 27-10-2026

Nuevo bloque de código `7c95671`: adaptador sobre OCA real, sin `hr.payslip`
simulado ni fachada `hr_payroll`. Paquete G: tres addons/15 archivos idénticos,
53 pruebas Community oficial (64 instalados/0 EE) y seis contratos compartidos
en copia fresca nativa de Cerro (376/140 EE). Se preservan 918 tablas/proyecciones,
140 contadores exactos incluso tras fixtures, 58.956 XML IDs, permisos, relaciones,
históricos y saldos. No se repite ni se suma la regresión HR anterior 468/516.

Se implementan tipos de entrada/FK, enlace de tipos de estructura, relación
primaria de reglas con M2M OCA, totales por código y acceso real a entradas por
diccionario. Se bloquea recálculo pagado/validado, repetición ambigua de entradas
tipadas y cambios de relación inconsistentes. `payslip` ya era un registro real
OCA; no se sustituyó. La comparación genérica incluye moneda CLP y asiento real.
Las siete brechas del inventario de API anterior son el diagnóstico inicial;
no interpretar su implementación parcial como certificación de Simple Digital.

Quedan días/ausencias/work entries, agregación, cantidades/redondeos/YTD,
instalación real del proveedor sobre OCA, adopción de modelos/campos/XML IDs/grupos,
71 reglas chilenas, Previred/libro e históricos pagados representativos. OCA
hereda líneas desde reglas: requiere mapear ese esquema en la conversión.
Siguen DTE/CAF/SII y la conversión integral con cero EE, recuperación y aceptación.
No cambian las 53 clausuras Enterprise sobre 93 apps del inventario anterior;
producción conserva 140 EE. El riesgo del 31 sigue alto y el vencimiento no
está resuelto. No se modifican producción, QA-Cerro, vencimientos ni pagadas.

Estado detallado, límites, hashes, evidencia privada reproducible y **prompt de
continuidad vigente** en [COMMUNITY_PAYROLL_API.md](COMMUNITY_PAYROLL_API.md).


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
