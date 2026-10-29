# BASIC mensual y relación de días trabajados — 28-10-2026

Continuación de 39afbc4. SyS sigue siendo la referencia real indicada por el
usuario. Se reutilizan cápsula positiva y prueba documental ya verificadas;
no se vuelve a pedir la base ni se recalculan originales done/paid.

## Implementación y límites

step_payroll_contracts 18.0.1.9.0 reconoce una segunda base estructural BASIC:
sueldo mensual dividido por treinta, multiplicado por la suma de días de códigos
explícitos. Conserva el reconocimiento anterior de paid_amount. El análisis es
estático, sin eval/exec: asignaciones locales, get de días, guardas de ausencia,
aritmética racional acotada. Rechaza divisor distinto, coeficientes negativos,
llamadas ajenas, shadowing y alteraciones de cantidad/tasa/nombre del resultado.
El resultado identifica códigos y divisor; financial_certified sigue false.

Esto reconoce la forma matemática de la configuración observada en SyS,
sin publicar su expresión privada ni elegir/desactivar reglas. No certifica
qué tipos son legalmente pagados, tope mensual, jornadas, estructuras heredadas,
impuestos, cotizaciones o las 71 reglas. Persisten los controles de ambigüedad,
secuencia y conexión BASIC/GROSS/NET; no se fuerza el GROSS desconectado de Cerro.

step_payroll_oca_api 18.0.1.5.0 cierra una diferencia real: OCA conserva code
obligatorio almacenado en hr.payslip.worked_days; el nativo lo relaciona al tipo.
Al crear una línea tipada abierta, se toma el código del maestro existente.
Cambiar tipo en una línea abierta actualiza el código de forma consistente;
una discordancia se rechaza. No se elimina una relación tipada para sustituirla
por texto. Un tipo ya usado conserva su código, incluso si hay referencias en
otra compañía; la consulta solo comprueba existencia, previa autorización de
escritura, y no expone datos de nómina. No se usan sudo ni ACL nuevas.

Leer una línea legacy sin tipo no crea maestros ni reescribe su código. Las
inconsistencias tipadas se rechazan antes de calcular; no se arreglan al leer.
Se mantiene el almacenamiento original de code, sin convertirlo a related que
pueda reconstruir históricos. Las líneas cerradas no cambian código/relación.
La FK existente, ondelete restrict, IDs, campos y maestros se conservan.

La lista y subformulario de días trabajados exponen el maestro existente sin
creación rápida y dejan code de solo lectura cuando hay tipo. Onchange y backend
coinciden. Se prueba la arquitectura efectiva y el flujo con usuario normal.
No se cambian menús, ACL ni dependencias; la vista añade un XML ID propio.

## Replay parcial real

audit_sys_monthly_basis.py lee la expresión configurada BASIC de SyS por SQL
forzado a lectura; su hash debe coincidir con la cápsula. El reconocedor debe
aceptarla antes de preparar datos. El registro observado carece de XML ID;
no se copian fuentes de archivos OEEL. Su expresión configurada y los importes
quedan privados, con permisos 0600. La fecha registrada de modificación de
regla precede el período; esto no certifica toda la cronología maestra.

probe_monthly_basis.py usa esa expresión, sueldo documental y snapshots de
días/horas sin inventar horas ni crear tipos. Resuelve un maestro existente
inequívoco por código y deja registrada la correspondencia de IDs. Son registros
nuevos de fixture, gerente normal y motor real dentro de TransactionCase;
nunca hr.payslip simulado ni recálculo del original. No intercepta el motor.
El proceso valida después que no quedan empresas ni usuarios de fixture antes
de marcar rollback verificado; no confía en una bandera escrita por el probe.

Alcance: BASIC aislado, no replay completo del período/contrato/empleado, GROSS,
NET, impuestos, YTD, contabilización, Previred o libro. Las fechas/maestros del
fixture no se presentan como cronología original de SyS. No se adopta identidad
del motor. Se compara el total SQL del nuevo BASIC con el snapshot original.
La coincidencia de un concepto/caso no certifica las 71 reglas ni el 31 de octubre.

## Aceptación

Paquete F exportado de 648d15e: 131 pruebas Community oficial/OCA y 68 en copia
fresca aislada de Cerro, cero fallos/errores y cero ERROR de runtime. BASIC del
caso preservado coincide exactamente con el total SQL en ambos motores reales.
Rollback comprobado después del proceso: cero empresas y cero usuarios de
fixture en ambas bases. Maestro WORK100 existente, ID original/objetivo 1 en
ambos; no se crea un maestro para conseguir el resultado.

96 archivos idénticos entre paquetes, fingerprint SHA-256
fd83f74c24677d752bee3bd727d498e81b863985cdcbe53eb17886771fc3de7b.
Pins Community 4b4efe68291d6def5bb7d2e1f2b829e0cda577d4 y OCA
4c71cd42e46a09a7512d92f5c63c0a9f7c26ad3e. Community 68 módulos/cero EE,
referencia 383/140; sin autoinstalaciones adicionales del probe. Versión SQL
del núcleo 18.0.1.9.0 en ambos y API Community 18.0.1.5.0 instalada solo en CE.
Perfil simpledigital; se conserva aceptación previa de Libro/Previred/HTTP/PDF
sin sumar cifras entre perfiles ni repetir rutas sin cambios.

Preservados 919 tablas/proyecciones, 140 contadores, 59.048 XML IDs originales,
modelos/campos/ACL/relaciones, 1.614 vínculos usuario-grupo y 283 implicaciones;
comparación antes/después del upgrade y las pruebas, históricos idénticos.
Tablespaces privados verificados únicamente para las bases nuevas. No se adopta
almacenamiento ni identidad histórica del motor por este replay parcial.

Verificación reproducible con el checkout publicado:
python tools/community/summarize_payroll_api.py
~/.codex/local-artifacts/community-payroll-real-basis-20261028/evidence-F
--output ~/.codex/local-artifacts/community-payroll-real-basis-20261028/summary-F.json.
Contrasta paquete, versiones, auditores/probe exactos, cápsula/PDF/expresión,
total BASIC original, correspondencia de maestro, rollback y preservación.
La matriz completa se regeneró idéntica. Diagnósticos B/D/E quedan separados;
ninguna de esas aceptaciones parciales sustituye F.

B se rechazó en Community por code obligatorio ausente al crear un día tipado:
motivó cerrar el contrato de API, en lugar de rellenar un texto en el fixture.
La referencia B pasó 67 pruebas y el BASIC parcial; no acepta el paquete final.
C fue preparación sin ejecución. D se rechazó porque readonly se aplicaba solo
a la primera coincidencia XPath; la lista estaba cubierta y el subformulario no.
E separa ambos XPath: 130/67 pruebas verdes y coincidencia BASIC, pero se rechaza
su aceptación de rollback. El alta de empresa desde shell autoinstaló localización
en la base privada Community y dejó una empresa de fixture. Ninguna producción
fue escrita. F mueve el replay al marco transaccional de pruebas, con rutas de
entrada privadas explícitas y verificación posterior de cero empresas/usuarios.

Artefactos privados:
~/.codex/local-artifacts/community-payroll-real-basis-20261028/.
Servidor: /opt/steps-validation/community-payroll-real-basis-20261028F.
basis-input.json contiene expresión e importes: nunca Git. Conservar cápsula,
documento/pruebas previas, fuentes de auditores/probe, JSON/logs y paquete exacto.
La verificación local contrasta sus hashes con el checkout publicado y vincula
la fórmula, sueldo y esperado con la referencia documental/SQL preservada.

## Pendientes y siguiente prompt

Inventario vigente: 380 módulos en Cerro/99 propios/140 EE; 117 manifiestos
propios, 22 fuera de Cerro y 54 apps con caminos Enterprise. Matriz completa y
fuentes privadas revisadas; no se retiran dependencias. Producción y QA-Cerro
no reciben este paquete. Siguen identidad/almacén del motor, estructura/reglas/
entradas/días efectivos, cantidades/redondeos/YTD, contabilización, Previred/libro
no vacíos, DTE/CAF/folios/firma/respuestas SII, Tesorería, Calidad, Studio/
Documentos/Firma y otros productos. Falta conversión integral restaurable cero
Enterprise, conciliación, recuperación y aceptación. El 31 sigue en riesgo alto.

Siguiente prompt: continúa desde canónica actualizada en worktree propio. Lee
AGENTS, ambientes, operación, workflow, plan, continuidad, autonomía, matriz,
COMMUNITY_PAYROLL_REAL_BASIS.md, COMMUNITY_SYS_DOCUMENT_REFERENCE.md y referencias.
Haz fetch y revisa inventario completo/fuentes privadas. Conserva la referencia
humana SyS, caso positivo documental y caso cero; no repetir preguntas resueltas.
El BASIC mensual aislado y el contrato tipo/código de días están probados;
no repetir suites verdes sin cambios. Prioriza ampliar replay a componentes
amount/quantity/rate y estructura/condiciones/categorías/entradas reales, luego
GROSS imponible distinto de total haberes y NET con la anomalía 8/32 intacta.
Para la conversión histórica, cierra explícitamente el almacenamiento del código
de días: nativo related frente a OCA almacenado obligatorio, preservando el valor
visible original, IDs y permisos antes del upgrade, sin recalcular importes ni
autocompletar históricos al leer. Cerro sin nóminas no prueba esa adopción;
usa históricos de SyS en una copia privada cuando corresponda, nunca Demo-SYS.
No elijas/desactives reglas por frecuencia/ID ni relajes controles para instalar.
No recalcules originales done/paid ni sueldos actuales al leer historia.
Mantén visible adopción de IDs/almacén, certificación de las 71 reglas, YTD,
asientos, Previred/libro y conversión integral cero EE. Si un hecho histórico
falta, conserva el límite concreto y avanza DTE/CAF/SII sin emisión real.
No escribir producción, retirar allí EE, alterar vencimientos ni refrescar QA-Cerro.
Respeta Calendar, Boolean bancario y 210233; overlays privados, reserva 5/2 GiB,
respaldo y bloqueo compartido. Prueba paquete exacto en Community y copia fresca
de Cerro, guarda evidencia privada, commits/push, integra solo lo validado y
ejecuta python tools/git/verify_handoff.py --require-pushed.
