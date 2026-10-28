# Libro: totales salariales originales y permisos — 28-10-2026

## Contrato implementado

Continuación desde 519b02a, incorporando los cambios concurrentes de entrada manual
de proveedores. step_payroll_contracts 18.0.1.4.0 ofrece stored_payslip_totals sobre
hr.payslip y hr.payslip.line reales. step_simpledigital_oca_security 18.0.1.5.0
lo usa en el controlador del Libro del proveedor AGPL original, con OCA real y
con el motor nativo de referencia. No se simulan modelos ni generadores.

El helper comprueba acceso a los padres, al modelo y campos de líneas, y compara
las líneas visibles con todas las líneas originales de esas liquidaciones. La
búsqueda incluye las líneas archivadas de OCA con active_test=False, manteniendo
las reglas de acceso; la referencia nativa no tiene ese campo. Una
regla que oculta un concepto impide exportar un total parcial, incluso cuando se
solicita otro código. Solo después se agregan los code/total almacenados en SQL.
El cero original es autoritativo; no se reconstruye amount*quantity*rate, no se
consulta el sueldo actual ni se ejecutan fórmulas. Valores o códigos incompletos
se rechazan. Una selección legítima sin el código solicitado sigue dando cero.
No se añade almacenamiento ni se inventan maestros o modifican históricos.

El Libro selecciona done/paid dentro del período original y la compañía activa,
con el entorno normal del usuario. Se elimina el sudo de esa búsqueda. Si recibe
un registro previamente elevado, lo vuelve a consultar con el actor HTTP antes
de leer totales. Se mantiene la API del proveedor para códigos simples/listas,
filtro vacío e int(sum(total)), incluidos negativos; esa truncación no acredita
una nueva política chilena de redondeo. No cambian modelos, IDs, ACL ni dependencias.

La prevalidación abarca todas las líneas antes de los formateadores del proveedor:
sus bloques except no pueden transformar un histórico incompleto en un concepto
cero. El endpoint original todavía convierte algunos errores en texto plano; no
se considera ese HTTP 200 ni un archivo vacío una aceptación del Libro oficial.
Tampoco se certifican aún columnas basadas en movimientos, contrato o indicadores
vivos. El Libro/tablero propio step_hr_remuneration_book conserva su dependencia
nativa hasta cerrar sus modelos, relaciones, vistas, acciones y permisos.

## Pruebas y preservación

Paquete final E, addons 97a1ec9; verificación de planes 882c233. **150 pruebas
Community oficial** (70 instalados, cero Enterprise) y **90 en copia fresca
nativa de Cerro** (380 instalados, 140 Enterprise), sin fallos. La referencia
nativa conserva su motor; no es una conversión de Cerro a Community.

Se preservan exactamente **919 tablas/proyecciones y 140 contadores** (1.059
contratos), **59.039 XML IDs**, maestros, relaciones, ACL, metadatos, históricos,
adjuntos de negocio, saldos y vencimientos. Las 1.614 relaciones usuario-grupo y
283 implicaciones coinciden exactamente con el respaldo. La fuente fresca ya
incluye la entrada manual de contactos: los 59.036 XML IDs del bloque anterior
pertenecen a otro corte y no se comparan como pérdidas/altas de esta migración.

Ambos modos prueban los mismos 149 archivos de addons. SHA256 de su mapa:
e946858ca6e2d1c7d62e36309c21abadd18ebdac3fcb6991cf485575addd4051.
El resumen comprueba esos bytes contra Git y el validador ejecutado, además de
preservación, inspector, proveedor reproducible, grupos y los dos planes de
retención. El mapa parcial mantiene 984 campos ausentes, una diferencia de tipo,
12 de almacenamiento, 17 de obligatoriedad y cinco de selección. No se declara
adoptada la identidad del motor ni certificado Simple Digital completo.

Evidencia verificable: evidence-E/, summary-E.json y verification-E.log en la
carpeta privada indicada abajo. Se conservan también el diagnóstico rechazado C
y las pruebas intermedias D; no se presentan como aceptación del paquete final.

Los siete contratos nuevos cubren cero importado frente a componentes no cero,
NULL sin sustitución, línea oculta, padre elevado entregado a otro actor,
selección real done/paid sin elevación, códigos/truncación positivos y negativos,
líneas archivadas de OCA y padres inválidos. Son fixtures de motores/ORM reales
con rollback. Cerro sigue
sin contratos, liquidaciones ni work entries: no se confunden estos casos con
certificación de nómina productiva ni conversión de históricos reales.

La fuente original del proveedor conserva sus 52 archivos runtime AGPL. No se
copian fuentes OEEL. Evidencia privada en ~/.codex/local-artifacts/community-
payroll-book-lines-20261028/, y servidor /opt/steps-validation/community-payroll-
book-lines-20261028E. El resumidor verifica paquete/Git, validador, conservación,
configuración, auditor, proveedor reproducible, grupos y retención.

## Capacidad y retención

B se detuvo antes de crear/restaurar bases porque PostgreSQL estaba por debajo
de 5 GiB disponibles. No es una aceptación y no se reutiliza su carpeta de modo.
Se aplicó un plan nuevo, explícito y revisado a seis bases antiguas de ensayos
propios, todas sin conexiones, bajo /run/lock/steps-environments.lock. Se liberan
671.954.074 bytes; la reserva sube a 6.039.609.344 bytes antes de los nuevos ensayos.
No se borran dumps en este bloque. Antes de retirar se decodificaron completamente
cuatro respaldos retenidos y se comprobaron sus hashes. Se conservan el caso dorado
de upgrade, la prueba autónoma sin motor y la última pareja validada de base salarial;
además queda la nueva pareja una vez aceptada. Código, logs y JSON previos continúan
conservados. No se tocan producción, QA-Cerro ni copias de otros productos.

Plan/resultado/ejecutor privados: community-payroll-book-lines-20261028B/retention.
A solo preparó un paquete preliminar, sin ejecutar bases. C detectó un padre aún
no guardado y una expectativa de
fixture que omitía líneas adicionales del motor nativo; queda rechazado. D
pasó 150/90 contratos regulares, pero no incluía el caso de líneas archivadas.
La aceptación final E incorpora ese caso en los contratos existentes y repite
ambos motores en bases nuevas, sin reutilizar ensayos anteriores.
Las dos bases rechazadas C se retiraron después, con un segundo plan bajo el
mismo bloqueo y sin sesiones activas: 227.346.142 bytes adicionales. Se conservan
su respaldo, código, logs y snapshots. El segundo plan está en la carpeta
community-payroll-book-lines-20261028E/retention-failed-C. En total este bloque
retira ocho ensayos y cero dumps; ambos planes y sus ejecutores se verifican
por hash en el resumidor. Los planes consumidos no se repiten. Las copias intermedias D quedan
supersedidas por E; pueden retirarse mediante un nuevo plan de retención cuando
se necesite reserva, conservando código, logs, JSON, caso dorado y referencia final.

## Estado acumulado y siguiente bloque

Inventario actualizado: 377 módulos instalados, 96 propios y 140 Enterprise.
El repo tiene 114 manifiestos propios; 22 están fuera del inventario instalado.
Se mantienen 52 apps instaladas con caminos Enterprise y las fuentes privadas o
sin consolidar, aun si su cierre de dependencias conocidas es cero.
El aumento de inventario procede de la entrada manual de contactos publicada por
otro frente; esta automatización no escribe ni publica en producción.

Continúan pendientes la configuración original, identidad y almacenamiento del
motor, las 71 reglas/cuatro estructuras/seis entradas y casos chilenos; YTD restante,
contabilización, Previred no vacío y Libro oficial. Sigue GROSS_DISCONNECTED_FROM_BASIC:
BASIC 25 está en IMP sin padre y GROSS 26 lee BASIC+ALW; habIMP 41 lee NOP_IMP.
SyS tiene dos NET activos y no sustituye automáticamente la referencia de Cerro.
Se solicitó al usuario una configuración/caso aprobado y su responsable para
resolver este origen sin inventar políticas salariales. El bloqueo se conserva
mientras se avanza en los demás contratos.

Faltan también HR/consumidores, DTE/CAF/folios/firma/respuestas SII, Tesorería,
Calidad, Studio/Documentos/Firma y el resto de productos. No hay copia integral
restaurable con cero Enterprise, conciliación, recuperación y aceptación completa.
El 31 de octubre sigue en riesgo alto; esta extracción parcial no resuelve el
vencimiento. No se recalculan pagadas, alteran vencimientos ni refresca QA-Cerro.
Se respetan Calendar, el Boolean bancario, 210233 y la prohibición de emisión SII.

## Siguiente prompt

Continúa desde la canónica actualizada en worktree propio. Lee AGENTS, ambientes,
operación, workflow, plan, continuidad, autonomía, matriz Enterprise vigente,
COMMUNITY_PAYROLL_CONFIGURATION.md, COMMUNITY_PAYROLL_YTD.md,
COMMUNITY_PAYROLL_WAGE_BASIS.md y COMMUNITY_PAYROLL_BOOK_LINES.md. Haz fetch y
revisa el inventario completo, módulos fuera de Cerro y fuentes privadas. Conserva
lo probado e incorpora la respuesta humana sobre configuración/caso aprobado si
ya llegó. Prioriza configuración original e identidad/almacenamiento del motor;
no copies SyS ni actives reglas para fabricar un resultado. Los helpers vivos
siguen bloqueados para cerradas y los totales del Libro ahora leen snapshots
originales con control de líneas ocultas: no reconstruyas importes ni vuelvas a
sudo. Cierra el Libro propio y sus consumidores antes de cambiar dependencias,
además de las columnas dinámicas y el archivo oficial real. Mantén DTE/CAF/SII y
conversión integral restaurable cero Enterprise visibles. Comprueba el volumen
real de PostgreSQL, conserva referencias y respaldos y no repitas planes consumidos.
Prueba el mismo paquete en Community oficial y copia fresca aislada de Cerro con
respaldo, overlay privado y bloqueo compartido. No escribas en producción, recalcules
pagadas, cambies vencimientos, refresques QA-Cerro ni emitas al SII real. Respeta
Calendar, Boolean bancario y 210233. Guarda evidencia, commits y push, integra solo
lo validado y ejecuta python tools/git/verify_handoff.py --require-pushed.


Continuación aceptada, evidencia y siguiente prompt vigentes:
[COMMUNITY_OWN_BOOK_CONTRACTS.md](COMMUNITY_OWN_BOOK_CONTRACTS.md). Su alcance
Community es biblioteca real del Libro, con la aplicación completa aún pendiente.
