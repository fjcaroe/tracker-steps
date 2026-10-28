# Puente Previred Simple Digital sobre OCA — 28-10-2026

## Alcance

Base canónica 657c731; rama propia codex/community-previred-simpledigital-20261028.
Se conserva el inventario completo: 374 instalados, 93 propios, 140 Enterprise en
producción y 52 apps instaladas con caminos EE pendientes. El proveedor original
sigue bloqueado por BASIC/GROSS y la adopción de las 71 reglas. Esta etapa cierra
interfaces del puente; no certifica liquidaciones chilenas ni el archivo oficial.

## Cambios reales

step_hr_previred_simpledigital 18.0.2.4.2 usa los grupos reales de Nómina mediante
el contrato compartido. No exige el XML ID Enterprise en Community ni fabrica
aliases. Conserva su permiso propio de generación, compañías habilitadas y acceso
corporativo completo. El guard consulta el mismo intervalo date_from del proveedor,
incluyendo liquidaciones parciales; no autoriza una búsqueda sudo si esas filas
están ocultas por permisos.

El adaptador ejecuta el cuerpo original del generador AGPL a través de
original_endpoint, conservando su implementación. Así no depende de que Odoo ya
haya completado el mapa HTTP para un decorador que no declara type. Los clientes
siguen entrando por el asistente/controlador autorizados. El proveedor no se copia
ni sustituye por un generador de pruebas. Un resultado vacío es error y la ruta
heredada tampoco entrega un TXT vacío como si fuera una exportación correcta.

El normalizador lee los totales SQL almacenados con permisos reales. Cero conserva
su significado y NULL bloquea la salida; no se reconstruye un importe usando
amount, quantity y rate. Las lecturas de cerradas no recalculan ni escriben líneas.
Las fixtures importan una anulación de total mientras están en borrador y después
cierran normalmente para comprobar el histórico sin recalcularlo.

step_payroll_oca_api 18.0.1.4.0 añade paid a la selección del motor OCA real. El perfil
original lo admite, mientras OCA solo tenía draft/verify/done/cancel: sin cerrar esa
brecha el XML del puente ni siquiera instalaba. El estado terminal se conserva,
queda protegido frente al recálculo y su retiro se bloquea si todavía tiene registros.
No representa una certificación de pagos bancarios ni una conversión integral.
step_payroll_contracts 18.0.1.3.0 aporta la lectura estricta del snapshot.

## Aceptación

Paquete C: 139 pruebas Community oficial/OCA/proveedor (70 módulos, cero EE) y
79 en copia fresca nativa (377 módulos, 140 EE), sin fallos ni errores. Código de
addons 647fa7a; guard de capacidad b05ec7e; verificación de retención 8e74d19.
Los 149 archivos coinciden en ambos entornos y con Git, SHA256
7db6bda0bd8c4bbd7ad1d0f0787c6341428bffa73be0d3c303b6139310970e1e.

Se conservan 918 tablas/proyecciones, 140 contadores, 58.956 XML IDs, modelos,
campos, relaciones, ACL, históricos, adjuntos de negocio, saldos y vencimientos.
Las 1.614 relaciones usuario-grupo y 283 implicaciones se contrastan exactamente
contra el respaldo. La fuente efectiva del proveedor y sus 52 archivos AGPL siguen
intactos y reproducibles. Se actualiza el puente nativo 2.4.0->2.4.2 solo en la copia.

Además de los contratos ya aceptados, se ejecutan 14 pruebas de matriz/perfiles/
movimientos/menús y cinco pruebas HTTP reales de rechazo de permisos, compañía y
período. Siete contratos nuevos usan los motores y modelos reales: autorización
por rol, bloqueo de salarios parciales ocultos, generador real sin registros como
error, cero AFP histórico, total NULL, cero empleador y estado paid inmutable.
Solo el contexto HTTP del ensayo directo del generador es local; no se reemplazan
el generador ni hr.payslip. Las pruebas de normalización no certifican un TXT real
no vacío ni políticas chilenas. La matriz de caminos EE permanece en 52 apps.

El mapa parcial conserva 984 campos ausentes, una diferencia de tipo, 12 de store,
17 de obligatoriedad y ahora cinco de selección (antes seis, por paid). No se
considera adoptada la identidad del motor. Evidencia privada:
~/.codex/local-artifacts/community-previred-simpledigital-20261028/evidence-C,
summary-C.json y verification-C.log. Servidor: /opt/steps-validation/community-
previred-simpledigital-20261028C; auditoría y retención en las carpetas homónimas.
El resumidor verifica paquete/Git, conservación, inspector, reproducción, grupos,
plan de limpieza, hash del ejecutor y decodificación de los respaldos retenidos.

A detectó el problema del decorador y el estado ausente; queda rechazado. B falló
por capacidad del volumen PostgreSQL; tampoco es aceptación. No se reutilizan
esas bases para declarar éxito y no se integra un paquete fallido.

## Capacidad y retención autorizada

El usuario autorizó retirar respaldos antiguos el 28-10-2026. El volumen PostgreSQL
estaba lleno aunque /opt tenía 53 GB libres: son volúmenes distintos. Se retiraron
60 bases temporales inactivas de ensayos propios y 19 dumps antiguos, conservando
seis referencias y tres respaldos completos decodificados y comprobados antes de
retirar nada. Quedan código, logs, JSON y evidencia local de los bloques anteriores;
las bases retiradas son entornos temporales reproducibles, no producción ni QA-Cerro.

El plan explícito y los resultados están fuera del checkout en
/opt/steps-validation/community-previred-simpledigital-20261028-retention. La primera
baja falló por capacidad; se reintentó una base y las 59 restantes se retiraron con
el plan de continuación. No se terminan sesiones ni se usa DROP FORCE. Se recuperan
unos 6 GB de bases y 0,4 GB de dumps; PostgreSQL pasa a unos 6,5 GB disponibles.

El validador comprueba bajo el bloqueo compartido el volumen real de data_directory:
exige 5 GiB libres allí y 2 GiB en artefactos antes de crear/restaurar. pg_restore
ahora se detiene al primer error y guarda el diagnóstico privado, evitando una
cascada de intentos sobre una restauración incompleta. No se modifican producción,
QA-Cerro, credenciales, vencimientos, Calendar, Boolean bancario ni 210233.

## Pendientes y siguiente prompt

Faltan configuración original, identidad/almacenamiento del motor, las 71 reglas,
estructuras y entradas, casos chilenos y el contraste de archivos no vacíos con
datos válidos. La matriz de 105 campos, menús, perfiles y controles de acceso no
sustituye esa aceptación. Siguen Libro/tablero y otros consumidores, YTD pendiente,
contabilización, DTE/CAF/folios/firma/respuestas SII, Tesorería, Calidad,
Studio/Documentos/Firma y los demás productos. No hay conversión integral restaurable
cero Enterprise ni aceptación completa; el 31 de octubre sigue en riesgo alto.

Siguiente prompt: continúa desde la canónica actualizada en worktree propio. Lee
AGENTS, ambientes, operación, workflow, plan, continuidad, autonomía, matriz completa,
COMMUNITY_PAYROLL_CONFIGURATION.md, COMMUNITY_PAYROLL_YTD.md,
COMMUNITY_PREVIRED_CORE.md y COMMUNITY_PREVIRED_SIMPLEDIGITAL.md. Conserva lo probado
y revisa inventario completo. Prioriza la configuración original Simple Digital,
la identidad del motor, 71 reglas/estructuras/entradas y la desconexión BASIC/GROSS.
El puente ya carga contra OCA y conserva estados/totales/permisos; no está certificado
el archivo oficial no vacío. Cierra ese flujo con datos originales válidos y sin
fabricar maestros o simular generadores. Si sigue bloqueado, avanza Libro y otros
consumidores cerrando modelos, relaciones, vistas, acciones y ACL antes de cambiar
dependencias. Verifica espacio del volumen PostgreSQL, aplica solo la retención
explícita de ensayos propios y conserva una referencia reciente validada y respaldos
comprobados. Prueba paquete exacto en Community oficial y copia fresca aislada, con
preservación de IDs, maestros, ACL, relaciones, históricos, saldos y correlativos.
No recalcules pagadas ni modifiques producción, vencimientos o QA-Cerro; respeta
Calendar, Boolean bancario y 210233. No emitas SII real. Guarda evidencia privada,
commits, push, integra lo validado y verifica handoff. Mantén visible la conversión
integral restaurable cero Enterprise y el riesgo del 31.
