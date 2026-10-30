# Instalación real Simple Digital sobre OCA — 28-10-2026

Estado vigente y siguiente prompt: [COMMUNITY_MULTIFRENTE.md](COMMUNITY_MULTIFRENTE.md).
H valida 27 addons propios: Tesorería/5 accesos, T138–OCA real y TED/FRMT.
576 casos Community/391 referencia nativa, cero fallos/errores; 72 pruebas puras
más 19 verificaciones de custodia final (se solapan, no sumarlas).
Conserva 921 tablas/proyecciones, 140 contadores y 59.079 XML IDs/noupdate;
1.060 snapshots literales y un testigo numérico de cinco filas. Se admiten cinco acciones
de menú, siete timestamps propios y las ayudas HR anteriores, documentados.
C/C2 frío y su API1.14 siguen conservados. Faltan coadopción de 120 maestros/71
reglas, beneficios, metadata/ACL y certificación SyS, DTE completo y conversión
integral con cero EE. Hay 54 apps instaladas con caminos EE; producción conserva
140 EE. El 31 sigue en riesgo alto. Ver COMMUNITY_PROXIMO_BOOTSTRAP.md.
El contenido inferior conserva su alcance histórico.

## Contrato del bloque

Base canónica 498c09c; rama propia codex/community-simpledigital-20261028.
Leer primero AGENTS, operación canónica, workflow, continuidad, HR Payroll,
Payroll API y Payroll Work Entries. La fuente privada Simple Digital declara
AGPL-3 y conserva nombre, autoría y XML IDs propios. No se copia código OEEL.
Los cambios son un candidato de instalación y una preparación de identidad,
no la conversión integral de Cerro ni la certificación de remuneraciones chilenas.

## Implementación

- step_simpledigital_oca_base depende del motor OCA real y hr_expense Community.
  Añade relaciones reales de estructuras/tipos de entrada/tipos no pagados,
  campos y notas HTML usados por el proveedor, wage_type/hourly_wage y totales
  calculados sobre líneas reales. La base mensual de días pagados usa sueldo/30;
  otras frecuencias no quedan certificadas. La remuneración por hora se rechaza.
- La relación inversa de tipos de entrada no se copia al duplicar estructuras.
  Tanto create como write rechazan ampliar el alcance de tipos ya utilizados,
  incluso por la relación inversa; no eliminan entradas ni cambian sus IDs.
- La plantilla real de liquidación de OCA se extiende con las secciones esperadas
  por Simple Digital. La acción de impresión original mantiene su ID y usa la
  plantilla derivada. La acción desde Personal conserva el dominio por empleado
  y abre vistas reales. No se acredita equivalencia visual total con Enterprise.
- step_simpledigital_oca_security añade reglas por compañía, empleado, responsable
  y gerente, conservando grupos/ACL/reglas originales. Oculta fórmulas de regla
  heredadas por las líneas OCA al empleado. Los tres endpoints Previred/libro
  verifican el rol gerente, compañía activa y alcance antes del sudo del proveedor.
  Esta protección no certifica aún el contenido de los archivos generados.
- En la referencia nativa aislada, seis aliases payroll apuntan a los mismos
  cuatro ir.model y dos res.groups originales de hr_payroll. El hook solo permite
  esa preparación en clones privados identificados. No crea grupos paralelos.
- Antes de calcular Nómina Chile se exige información real de contrato/empleado,
  reglas BASIC/GROSS/NET y work entries reales. El proveedor no inventa salud,
  previsión, comuna ni asistencia mensual. Las obligaciones chilenas se validan
  al procesar, sin imponer NOT NULL a empleados/contratos de otros países.
  Las liquidaciones pagadas/validadas quedan protegidas antes de cualquier cambio.
- El adaptador de work entries comprueba las horas reales antes de invocar las
  transformaciones del proveedor, que podrían sintetizar treinta días. Se mantiene
  el savepoint para no dejar líneas parcialmente actualizadas por un fallo tardío.

paid_amount conserva el contrato de propiedad Python del motor nativo; no es
un campo nuevo de liquidación. Lee importes de días reales o el sueldo mensual
cuando la estructura no usa días, respeta no_paid_amount y rechaza la simulación
salarial no certificada. Los campos de neto/base/bruto derivan de líneas reales.

Odoo selecciona un XML ID principal por grupo al resolver has_group. Un alias
correcto no garantiza que has_group acepte ambas cadenas. La autorización de
exportaciones comprueba pertenencia al grupo real por ID; las pruebas verifican
además que sigue funcionando el XML ID original de hr_payroll. El formulario
privado de Personal conserva el botón de liquidaciones para HR; la acción del
perfil público del empleado se prueba con su usuario normal y reglas propias.

La obligatoriedad de income_tax_type y work_schedule_id conserva los valores
por defecto originales del proveedor. El código de las líneas conserva el
contrato original obligatorio, relacionado a salary_rule_id.code y de solo lectura.
No se modifica el código de reglas originales para fabricar líneas de prueba.

## Fuente y reproducción

simpledigital_runtime_source.json fija por SHA256 solamente los archivos runtime
permitidos. build_simpledigital_candidate.py deriva el proveedor en un overlay
privado: adapta referencias/vistas a OCA y dependencias, mantiene autoría/licencia
AGPL y registra procedencia y transformaciones. No hay addon hr_payroll vacío ni
hr.payslip simulado. No se incluyen cotizaciones, documentos comerciales, Git,
configuración local del proveedor ni datos de prueba con personas.

La fuente externa original no se publica en este repositorio. Su ruta efectiva y
las huellas completas permanecen en la auditoría privada. El builder rechaza
cualquier deriva de la fuente. El proveedor derivado no debe instalarse en ningún
servicio activo por interpretar que este documento autoriza un despliegue.

## Aceptación

Paquete K de addons, código c930d5a:
Community oficial 80 pruebas, 68 módulos instalados y cero Enterprise. Incluye
38 pruebas de OCA/payroll_account, 30 de API y 12 de frontera del proveedor.
La copia fresca nativa pasa 27 pruebas: 15 contratos compartidos y 12 de frontera.
No se suman las regresiones agrícolas/HR 468/516 ni las ejecuciones preliminares.
El paquete de cinco addons propios y el proveedor contiene 82 archivos idénticos
en ambos inventarios de ensayo. OCA y Community mantienen los pins documentados.
Los 52 archivos derivados del proveedor se reconstruyen y comparan byte a byte.

La comparación de la copia fresca conserva 918 tablas/proyecciones y 140
contadores de negocio exactos, tanto después del upgrade como después de las
fixtures. Se conservan los 58.956 XML IDs originales, 1.217 modelos, 26.994 campos,
5.071 selecciones, 2.322 ACL, 610 reglas, 1.328 menús, 417 vínculos acción-vista,
463 relaciones y 526 restricciones agrícolas/laborales. Se verifican también
las membresías originales, históricos, saldos y parámetros protegidos. Las
adiciones de vínculos de las nuevas reglas se aíslan explícitamente; ningún
vínculo original desaparece. La fuente activa, su configuración/versiones y los
archivos originales del proveedor conservan sus huellas. No hay escrituras a
producción ni refresco de QA-Cerro.

Evidencia privada final: ~/.codex/local-artifacts/community-simpledigital-20261028/
evidence-K y summary-K.json; servidor /opt/steps-validation/community-simpledigital-
20261028K. Bases COMMUNITY_PAYROLL_API_SD_20261028K y
MANAGEMENT_QA_CERRO_PAYROLL_API_SD_20261028K. Los ensayos A–J son diagnósticos o
versiones previas, no aceptación del paquete final. G pasó 79/26 antes de cerrar
las tres diferencias de obligatoriedad. F solo pasó Community; su referencia
en espera se detuvo antes de ejecutarse. I pasó Community y falló el contraste
de obligatoriedad con el motor nativo; se corrigió preservando su contrato real.
J pasó Community; una aserción nueva asumía una sola línea en el motor nativo.
K comprueba la pertenencia real del código y la estabilidad de todos los IDs.
No se publican dumps, reglas privadas, archivos del proveedor ni identidad privada.

El resumen local verifica que los 82 archivos del paquete coinciden con el
checkout y entre entornos; huella e05c899312a3110172d76ef6d6ead1cd87f793a81f2879b1d859ddb921e80854.
El mapa final compara 1.836 campos de origen con 8.130 del perfil candidato.
Los campos atribuidos al proveedor coinciden en tipo, modelo relacionado,
almacenamiento, obligatoriedad y selecciones: cero diferencias en ese alcance.
El motor y consumidores pendientes mantienen 1.081 ausencias en este perfil
parcial (incluye módulos aún no cargados), una diferencia One2many/Many2many en rule_ids, 17 diferencias de
almacenamiento, 17 de obligatoriedad y seis de selección. El mapa conserva
identity_migration_accepted=false y el resumen mantiene full_cerro_conversion,
simpledigital_certified y deadline_resolved en false.

## Brechas que permanecen abiertas

La instalación limpia conserva nombres/XML IDs del proveedor; todavía falta la
adopción integral in situ de todos los modelos/campos/XML IDs del motor nativo,
almacenamiento, selecciones, restricciones y puentes de consumidores. Los seis
aliases probados no acreditan esa conversión completa. La copia de referencia
conserva su motor y Enterprise; OCA no se instala encima del motor nativo. En particular, antes de convertir
históricos debe conservarse el almacenamiento original de importes de días y
neto/base/bruto: leer una liquidación pagada no puede recalcular importes usando
el sueldo actual. La equivalencia de esos campos del motor sigue abierta en el
mapa de almacenamiento; el adaptador nuevo no se instala sobre historias pagadas.

El proveedor trae 31 reglas en sus datos; la configuración original auditada tiene
71 reglas en cuatro estructuras y seis tipos de entrada. BASIC/GROSS/NET no están
en los datos del proveedor: no se inventan resultados cero para fingir cálculo.
Falta adoptar y contrastar esa configuración original, YTD, casos chilenos completos
(licencias, ausencias, ingresos/salidas, topes y correcciones), asientos, dos perfiles
Previred y dos perfiles/42 líneas de libro. Cerro no tiene contratos/liquidaciones
históricas para certificar pagadas; las fixtures no sustituyen evidencia representativa.
Faltan el flujo de gastos/anticipos y consumidores HR específicos sobre el nuevo motor.

La auditoría actual conserva 374 módulos instalados, 140 EE y 93 propios en Cerro;
53 apps propias aún tienen clausuras Enterprise en el código candidato. El repo
contiene 111 módulos propios con manifiesto, incluidos núcleos/puentes y herramientas
de ensayo; 22 no están instalados en Cerro. Clasificar cuáles son productos o
soportes de validación antes de intentar instalar todo indiscriminadamente.
DTE/CAF/folios/firma/respuestas SII, Tesorería restante, Calidad, Studio/Documentos/
Firma y el paquete integral con cero EE, restauración y aceptación siguen pendientes.
No se considera resuelto el 31 de octubre. El riesgo continúa alto.

## Siguiente prompt

Continúa desde origin/codex/ambientes-canonicos-reparacion actualizada, en worktree
propio. Lee AGENTS, ~/.odoo/environments.json, operación, workflow, plan,
continuidad, HR Payroll, Payroll API, Payroll Work Entries,
COMMUNITY_SIMPLEDIGITAL_OCA.md, COMMUNITY_AUTONOMIA.md y matriz Enterprise vigente.
Revisa todo el inventario antes de implementar. Prioriza adoptar la configuración
real de Simple Digital (71 reglas/cuatro estructuras/seis entradas) y cerrar el
mapa de identidad para convertir una copia a OCA sin perder campos/IDs/ACL/FK/M2M.
No declares esa conversión acreditada por los seis aliases de referencia.
Mantén las protecciones pagadas, sin maestros inventados ni motor simulado.
Certifica días, redondeos, YTD, asientos, Previred y libro con evidencia real.
Mantén visibles DTE/CAF/SII, los restantes consumidores y productos, e integral cero
Enterprise con recuperación y aceptación. Respeta Calendar, Boolean bancario y
210233. No escribas en producción, retires allí EE, alteres vencimientos, recalcules
pagadas ni refresques QA-Cerro. Prueba el paquete exacto en Community oficial y
copia fresca aislada de Cerro; commits, push, integra lo validado y ejecuta
python tools/git/verify_handoff.py --require-pushed. Actualiza estado y próximo bloque.


## Históricos monetarios OCA — continuidad del 28-10-2026

Paquete C de código 434fc86: 90 pruebas Community (68/0 EE) y 30 en copia fresca
nativa (377/140 EE). Se conservan 918 tablas/proyecciones, 140 contadores,
58.956 XML IDs y metadatos/relaciones/permisos/saldos originales. Se cierran cinco
contratos de almacenamiento monetario; las diferencias de store bajan de 17 a 12.
Hay protección de históricos al leer/cambiar sueldos y admisión antes del upgrade,
con un upgrade Community real 1.0->1.1 sobre fixtures, sin convertir Cerro.
Estado, evidencia, límites y **siguiente prompt vigente** en
[COMMUNITY_PAYROLL_HISTORY.md](COMMUNITY_PAYROLL_HISTORY.md). La configuración
original, histórico real, DTE/CAF/SII y conversión integral siguen pendientes;
no se considera resuelto el 31 y no se modifican producción ni QA-Cerro.


## Configuración esencial y procedencia — 28-10-2026

Paquete B de código 510b7d2: 96 pruebas Community y 36 en copia fresca nativa,
conservando 918 tablas/proyecciones, 140 contadores y 58.956 XML IDs. El guard
estructural detecta que la configuración de Cerro no demuestra la conexión
BASIC/GROSS. Se conservan sus reglas y los aliases de tres IDs originales, con
retiro seguro. SyS fue consultado únicamente en lectura para contrastar perfiles;
no se trasladan ni corrigen configuraciones automáticamente. Estado, evidencia,
límites y **siguiente prompt vigente** en
[COMMUNITY_PAYROLL_CONFIGURATION.md](COMMUNITY_PAYROLL_CONFIGURATION.md).
No hay conversión integral ni certificación financiera; el 31 sigue en riesgo.
