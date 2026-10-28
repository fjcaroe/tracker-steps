# Instalación real del Libro con Simple Digital–OCA — 28-10-2026

## Alcance aceptado

Continuación desde ebb796b. Código 9b415b4, paquete B: **158 pruebas Community
oficial** (71 módulos instalados, cero Enterprise) y **98 en copia fresca nativa**
(380 instalados, 140 Enterprise), sin fallos. El Libro está realmente instalado
en ambos modos, con sus modelos, herencia de hr.payslip, formularios, menús,
permisos y reportes. Ya no es únicamente la biblioteca del bloque anterior.
Esto no convierte Cerro a Community ni certifica nómina chilena.

Se prueban vistas compiladas, visibilidad de menús, acciones reales de cada motor,
rechazo del libro completo al usuario parcial, dataset consolidado con actor normal,
Excel binario y acción/renderizado HTML del informe. No se declara verificado el
PDF binario, el navegador completo ni el archivo oficial DT con casos productivos.
Los fixtures usan modelos/motores reales y hacen rollback; su perfil sintético no
se importa a producción ni constituye la referencia financiera aprobada pendiente.

Se preservan **919 tablas/proyecciones, 140 contadores y 59.039 XML IDs** originales,
maestros, relaciones, permisos, históricos, adjuntos de negocio, saldos y vencimientos.
Las 1.614 relaciones usuario-grupo y 283 implicaciones coinciden exactamente con
el respaldo. El mapa parcial baja de 984 a **934 campos ausentes**, al registrar
realmente los modelos del Libro; mantiene una diferencia de tipo, 12 de store,
17 de obligatoriedad y cinco de selección. No se adopta aún la identidad del motor.

## Identidades y prerequisitos reales

step_hr_remuneration_book pasa a 18.0.3.5.0. Sus aliases engine_user/engine_manager
y los dos menús apuntan a registros existentes del motor. No se fabrican grupos,
modelos ni menús Enterprise vacíos. El pre-init y la migración preparan esas
identidades antes del XML; las colisiones se rechazan. El hook de retiro elimina
solo los aliases propios antes de desinstalar, preservando los grupos y menús
prestados. El ensayo comprueba esa protección directamente, sin desinstalar
Enterprise ni la aplicación del cliente.

Las ACL conservan sus IDs y grupos efectivos. Las comprobaciones Python usan
la identidad real del rol, evitando has_group sobre un alias no primario. Las
acciones del tablero se resuelven contra el motor existente; el control estándar
sin equivalente OCA queda oculto, sin un enlace ficticio. Se conserva el menú
nativo anterior y no se vuelve a modificar su registro ajeno. El departamento
usa las relaciones reales disponibles de contrato/empleado; la ausencia del campo
auxiliar nativo en OCA no crea un maestro paralelo y mantiene las advertencias
históricas del extractor. El tablero agrega snapshots SQL y respeta un GROSS/NET
original cero, en lugar de reemplazarlo por otra regla por su valor falsy.

El manifiesto genérico canónico conserva hr_payroll para no forzar Simple Digital
en otros productos/proveedores aún no auditados. build_book_candidate.py produce
una variante privada específica de Cerro/Simple Digital: cambia SOLO ese
prerequisito por step_simpledigital_oca_security, que aporta el motor real ya
validado. Mantiene nombre, versión, licencia LGPL-3, namespace, modelos, XML IDs y
todos los demás bytes. No es un sustituto vacío de hr_payroll. El mismo candidato
se prueba en Community y en la referencia nativa. El resumidor verifica cada archivo
original contra Git, el único cambio permitido del manifiesto y el hash del builder.

El paquete privado derivado es el alcance aceptado aquí. No se publica en servicios
ni se presenta el manifiesto nativo genérico como paquete desplegado. Antes de una
promoción se debe construir y probar el paquete exacto del destino conforme a la
operación canónica. La variante no acredita compatibilidad con fuentes privadas
BlueMinds desconocidas ni retira la dependencia genérica para todos los productos.

## Archivo oficial y límites financieros

En el Libro propio, el CSV oficial Simple Digital sobre OCA queda deshabilitado
con una explicación explícita. También se bloquea el método público de generación
si no existe una fuente certificada para ese modo. La fuente nativa conserva su
selección anterior. El consolidado interno no se confunde con el CSV oficial.

Faltan certificación del archivo completo, columnas basadas en datos vivos y rutas
directas del proveedor, casos chilenos, asientos, Previred no vacío, YTD restante,
configuración original e identidad/almacenamiento del motor. Las 71 reglas/cuatro
estructuras/seis entradas no se consideran certificadas por un perfil de software.
Sigue GROSS_DISCONNECTED_FROM_BASIC: BASIC pertenece a IMP y GROSS consulta
BASIC+ALW. SyS mantiene dos NET activos y no se importa como sustituto automático.
La configuración/caso aprobado y su responsable siguen pendientes de respuesta
humana. No se recalculan pagadas ni se inventan maestros para superar ese bloqueo.

## Evidencia privada y retención

Paquete de 196 archivos de addons, idéntico en ambos modos, SHA256 de su mapa:
9b2dee15074a49b69a05cead8fddb1a5705773406a458a2369c3d92f2f46fe28.
Los 52 archivos runtime AGPL del proveedor siguen intactos y reproducibles. No
se copian fuentes OEEL. Evidencia: ~/.codex/local-artifacts/community-book-install-
20261028/evidence-B, summary-B.json y verification-B.log. Servidor:
/opt/steps-validation/community-payroll-book-install-20261028B. El resumen valida
paquete/Git, derivación de ambos módulos, ámbitos instalados, conservación,
inspector, grupos, proveedor reproducible y plan de retención.

La versión de origen se verificó en sesión SQL de solo lectura: 3.4.0->3.5.0,
sin downgrade. Para reservar espacio se retiraron cuatro ensayos propios inactivos
con un plan nuevo revisado, bajo /run/lock/steps-environments.lock: 455.052.732 bytes.
Se conservaron caso dorado, prueba sin motor, última pareja validada y cuatro
respaldos completamente decodificados. No se borraron dumps ni copias de otros
productos. Resultado/plan/ejecutor en la carpeta A/retention de este bloque.
A quedó rechazado por la invocación incompleta del writer en el test; B repite
en bases nuevas con la firma real de stream/dataset y el bloqueo del CSV OCA.
Se preservan diagnóstico, logs, JSON y respaldo. No repetir planes consumidos.

## Estado acumulado y siguiente prompt

Producción conserva 377 módulos instalados, 96 propios y 140 Enterprise. El repo
mantiene 114 manifiestos propios y 22 fuera de Cerro; siguen 52 apps con caminos
Enterprise en la dependencia genérica, además de fuentes desconocidas pendientes.
Continúan DTE/CAF/folios/firma/respuestas SII, Tesorería, Calidad, Studio/Documentos/
Firma y demás productos. Falta copia integral restaurable cero Enterprise,
conciliación, recuperación y aceptación completa. El 31 de octubre sigue en riesgo
alto; esta instalación parcial no resuelve el vencimiento. No hubo escritura en
producción, retiro de Enterprise allí, cambios de vencimiento ni refresco QA-Cerro.
Se respetan Calendar, Boolean bancario y 210233. No se emite al SII real ni se
envían mensajes externos.

Siguiente prompt: continúa desde la canónica actualizada en worktree propio.
Lee AGENTS, ambientes, operación, workflow, plan, continuidad, autonomía, matriz,
COMMUNITY_PAYROLL_CONFIGURATION.md, COMMUNITY_PAYROLL_YTD.md,
COMMUNITY_OWN_BOOK_CONTRACTS.md y COMMUNITY_BOOK_INSTALL.md. Haz fetch y revisa
inventario completo, productos fuera de Cerro y fuentes privadas. Conserva lo
probado e incorpora la referencia humana aprobada si llegó. El Libro ya se instala
realmente con OCA mediante el candidato específico de Simple Digital y consolida;
no regreses al ensayo de biblioteca ni declares completado el CSV. Prioriza reglas
originales e identidad/almacenamiento, y cierra tablero/rutas HTTP/PDF binario y
fuentes históricas pendientes sin reactivar el CSV OCA antes de certificarlo.
Mantén la dependencia genérica hasta resolver los demás proveedores y usar un
puente real; conserva aliases/IDs y protección al retirar metadatos compartidos.
Mantén DTE/CAF/SII y conversión integral restaurable cero Enterprise visibles.
Verifica la reserva de PostgreSQL, no repitas planes consumidos y conserva caso
dorado, referencia reciente y respaldos. Prueba paquete exacto en Community oficial
y copia fresca aislada de Cerro, con respaldo, overlay y bloqueo. No escribas en
producción, recalcules pagadas, alteres vencimientos, refresques QA-Cerro ni emitas
SII real. Respeta Calendar, Boolean bancario y 210233. Guarda evidencia, commits y
push, integra solo lo validado y ejecuta verify_handoff.py --require-pushed.
