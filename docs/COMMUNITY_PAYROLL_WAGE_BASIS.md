# Base salarial histórica — 28-10-2026

## Alcance

Continuación de COMMUNITY_PREVIRED_SIMPLEDIGITAL.md desde la canónica 527bf72.
El puente común step_simpledigital_oca_security 18.0.1.4.0 distingue los helpers
vivos de cálculo de los importes históricos almacenados. _get_contract_wage,
_get_paid_amount, _get_unpaid_amount y la propiedad paid_amount no constituyen
snapshots originales de una liquidación cerrada. El contrato y la estructura
pueden haber cambiado desde su validación; BASIC tampoco demuestra por sí solo
cuál fue la base original en todos los casos.

En los dos motores reales se exige lectura autorizada antes de comprobar el
estado. Si la liquidación está cerrada, pagada o cancelada, los tres helpers
rechazan calcular desde el contrato actual. Los contextos no_paid_amount y
salary_simulation tampoco reemplazan un histórico por cero. En borrador se
conserva la implementación efectiva del motor. Continúan disponibles los totales
originales almacenados, sin nuevas columnas, backfill, tablas ni sustitutos.
Es una restricción de seguridad pendiente de una base histórica certificada,
no una implementación completa de esa base ni una certificación del Libro.

No cambian dependencias, modelos, relaciones, vistas, XML IDs ni ACL. No se
modifican reglas originales, maestros, liquidaciones pagadas ni sus importes.
No se despliega a producción ni QA-Cerro. Se mantienen Calendar, el Boolean
bancario, 210233 descontinuada, vencimientos y prohibición de emisión SII real.

## Auditoría de la configuración original

El auditor de orígenes ahora registra todas las reglas de la estructura chilena
y el grafo completo de categorías, referencias, hashes y metadatos de escrituras
directas, sin cuerpos de fórmulas, datos de empleados ni importes. La ejecución
es SQL de solo lectura en Cerro y SyS. Se conservan los identificadores originales.

Cerro mantiene 47 reglas activas en Nómina Chile de las 71 totales. BASIC 25 está
en IMP sin padre; GROSS 26 lee BASIC y ALW. La regla habIMP 41 lee NOP_IMP, por lo
que tampoco conecta automáticamente IMP con GROSS. No se observan escrituras
directas ni métodos mutadores de categories en esas fórmulas; esta revisión
estática no acredita la pureza de funciones arbitrarias ni equivalencia financiera.
El error GROSS_DISCONNECTED_FROM_BASIC continúa bloqueando el cálculo certificado.
SyS conserva dos NET activos, 8 y 32: no se importan fórmulas ni se desactivan reglas
para fabricar una configuración válida. Resolver este origen sigue en el camino
crítico, junto con la adopción de identidad y almacenamiento del motor.

El Libro del proveedor también consulta movimientos, contrato e indicadores del
período; no se presume que un CSV generado hoy conserve todos los importes de una
liquidación antigua. Falta cerrar su semántica histórica y el formato oficial,
además del Libro/tablero propio y sus consumidores.

## Aceptación

Código de addons c8ab6e3; auditor ampliado 780c9c8. Paquete A: **143 pruebas en
Community oficial** (70 módulos instalados, cero Enterprise) y **83 en copia
fresca nativa de Cerro** (379 instalados, 140 Enterprise). La referencia nativa
no instala OCA ni convierte Cerro. Los cuatro contratos nuevos cubren cambio del
sueldo actual sin modificar la fila histórica, contextos que intentan sustituir
historia por cero, canceladas y denegación por permisos antes de leer su estado.
Los contratos anteriores siguen verdes; no se simula hr.payslip.

Se preservan exactamente 919 tablas/proyecciones y 140 contadores
(1059 contratos), **59.036 XML IDs**, metadatos, relaciones, ACL, históricos,
adjuntos de negocio, saldos y vencimientos. Se contrastan con el respaldo las
1.614 relaciones usuario-grupo y 283 implicaciones, todas idénticas. La fuente
fresca ya contiene BPA; los recuentos anteriores de 918/58.956 pertenecen a otro
corte y no se comparan como si fueran pérdidas o altas de esta migración.

Los dos modos prueban los mismos 149 archivos de addons; SHA256 del mapa:
5436347f9906c13b0955fdfa458f5d315523b425b07e4aa7cd3dfd778c2a1f7f.
El resumidor verifica esos bytes contra Git, el validador ejecutado, conservación,
inspector, auditor completo, reproducción del proveedor y grupos. El mapa parcial
sigue con 984 campos ausentes, una diferencia de tipo, 12 de almacenamiento,
17 de obligatoriedad y cinco de selección; no se declara adoptada su identidad.
Community sigue bloqueando por BASIC/GROSS/NET ausentes en la estructura chilena;
la referencia original conserva GROSS_DISCONNECTED_FROM_BASIC.

Se comprobaron antes de crear bases la reserva de PostgreSQL y artefactos bajo
el bloqueo compartido. No hizo falta otra limpieza en este bloque. Los planes de
retención anteriores no se repiten. Evidencia verificable: evidence-A/,
summary-A.json y verification-A.log en la carpeta privada siguiente.

Evidencia privada: ~/.codex/local-artifacts/community-payroll-wage-basis-20261028/.
Servidor: /opt/steps-validation/community-payroll-wage-basis-20261028A.
El paquete deriva las mismas 52 fuentes runtime AGPL del proveedor original; no
copia fuentes OEEL ni modifica las raíces compartidas. Las pruebas usan motores
y ORM reales, actores normales y fixtures que hacen rollback. Cerro sigue sin
contratos, liquidaciones ni work entries: los casos salariales son fixtures, no
una certificación de nómina productiva ni una conversión de sus históricos.

## Estado acumulado y pendientes

La auditoría vigente registra 376 módulos instalados, 95 propios y 140 Enterprise.
El código candidato mantiene 52 apps instaladas con caminos Enterprise. El repo
incluye 113 manifiestos propios y 22 fuera del inventario instalado de Cerro;
las fuentes privadas/desconocidas también conservan su puerta de aceptación.
No se eliminan bloqueos por un manifiesto con cero dependencias conocidas.

Quedan configuración original/71 reglas/estructuras/entradas, identidad y
almacenamiento del motor, base histórica y consumidores HR, casos chilenos,
YTD restante, contabilización, Previred no vacío y Libro oficial. Siguen DTE,
CAF, folios, firma/respuestas SII, Tesorería, Calidad, Studio/Documentos/Firma y
los demás productos. Falta una copia integral restaurable con cero Enterprise,
conciliación, recuperación y aceptación funcional. El 31 de octubre permanece
en riesgo alto: esta protección parcial no resuelve el vencimiento.

## Siguiente prompt

Continúa desde la canónica actualizada en worktree propio. Lee AGENTS, registro
de ambientes, operación, workflow, plan, continuidad, autonomía, matriz vigente,
COMMUNITY_PAYROLL_CONFIGURATION.md, COMMUNITY_PAYROLL_YTD.md,
COMMUNITY_PREVIRED_SIMPLEDIGITAL.md y COMMUNITY_PAYROLL_WAGE_BASIS.md. Haz fetch y
revisa inventario completo, fuentes privadas y módulos fuera de Cerro. Conserva
los contratos ya probados. Prioriza resolver la configuración original BASIC/IMP/
GROSS sin inventar reglas ni copiar SyS, y la adopción real de identidad/almacenamiento.
Los helpers vivos ahora rechazan históricos cerrados: no los habilites derivando
el sueldo actual ni equiparando BASIC a una base original no demostrada. Cierra
consumidores y Libro desde los importes originales almacenados; si la configuración
sigue bloqueada, avanza otro frente verificable. Mantén DTE/CAF/SII y conversión
integral restaurable cero Enterprise visibles. Comprueba espacio real de PostgreSQL,
usa respaldo, overlays privados y bloqueo compartido. Prueba paquete exacto en
Community oficial y copia fresca aislada de Cerro. No recalcules pagadas, escribas
en producción, alteres vencimientos, refresques QA-Cerro ni emitas al SII real.
Respeta Calendar, Boolean bancario y 210233. Guarda evidencia, commits y push,
integra solo lo validado sin pisar cambios concurrentes y verifica handoff.


Continuación aceptada, evidencia y siguiente prompt vigentes:
[COMMUNITY_PAYROLL_BOOK_LINES.md](COMMUNITY_PAYROLL_BOOK_LINES.md), con lectura
de totales originales del Libro y cierre de permisos sobre líneas ocultas/archivadas.
