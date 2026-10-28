# Configuración esencial y procedencia de Nómina — 28-10-2026

## Alcance y hallazgo

Base d12513d; rama propia codex/community-payroll-configuration-20261028.
Código de addons 510b7d2, paquete B; auditor de perfiles e95e90f. Se repitió la
auditoría completa de solo lectura: 374 módulos instalados, 93 propios y 140 EE;
71 reglas, cuatro estructuras y seis tipos de entrada, sin contratos ni
liquidaciones en Cerro. Persisten 53 clausuras EE del candidato sobre las apps
instaladas y 111 manifiestos propios en repo. No se cambian dependencias.

La inspección real identifica una barrera previa a adoptar las 71 reglas:
la categoría de BASIC no tiene una ruta demostrable hacia los operandos de
GROSS en la configuración actual de Nómina Chile de Cerro. El informe devuelve
GROSS_DISCONNECTED_FROM_BASIC. No se modifica esa configuración ni se declara
que sus cálculos estén certificados. Hay que contrastar también las capas
dinámicas del motor y resolver la base imponible antes de trasladar las reglas.

En Community, el proveedor crea 39 reglas en esa estructura: 31 de sus datos y
ocho generadas por los tipos de movimiento. Faltan BASIC/GROSS/NET allí. La
referencia nativa tiene 47 en Chile y 71 entre sus cuatro estructuras. No se
confunde contar registros con demostrar un flujo de remuneración correcto.

Se consultó además SyS en producción exclusivamente en lectura PostgreSQL
forzada. Su GROSS activo referencia IMP y hay dos NET activos. Esto requiere
identificar condiciones, orden y selección efectiva; no demuestra por sí solo
un error de las liquidaciones de SyS. Tampoco permite copiar su perfil a Cerro
sin comparar contratos y configuración. No se leen ni exportan datos personales,
liquidaciones o importes en esta auditoría, ni se publican cuerpos de fórmulas.

## Implementación real

step_simpledigital_oca_security 18.0.1.2.0 valida las tres reglas esenciales
antes de calcular Nómina Chile, conservando los controles de históricos y de
maestros. Comprueba presencia/ambigüedad, orden, forma verificable de BASIC y
conexión positiva de categorías/reglas desde BASIC a GROSS y de GROSS a NET.
Sigue padres reales de categorías y puentes incondicionales anteriores a GROSS.
Una desconexión o fórmula esencial no verificable detiene el proceso antes de
crear líneas; no se inventan reglas, importes cero ni maestros para instalar.

Es un chequeo estructural conservador de remuneración mensual Chile. Analiza
un subconjunto aritmético explícito del AST sin ejecutar Python. No reemplaza
al motor OCA, no acredita condiciones fiscales, porcentajes, cantidades, topes,
los otros conceptos ni toda posible fórmula personalizada. financial_certified
permanece false incluso cuando structural_checks_passed es true. El guard de
cálculo conserva el alcance por nombre usado por el proveedor; otros perfiles
requieren adaptación y evidencia. El informe de estructuras genéricas no es
una certificación general de Odoo Payroll.

Los hooks preparan tres aliases sobre los mismos hr.salary.rule originales de
la copia nativa: BASIC 25, GROSS 26 y NET 32. No sobrescriben fórmulas, categorías,
secuencias ni registros. Los seis aliases anteriores de modelos/grupos permanecen.
El hook de retiro separa únicamente los tres aliases de configuración antes de
que Odoo retire datos del módulo, evitando convertir esos maestros en propiedad
borrable del puente. La prueba verifica que desaparecen las referencias y quedan
las 47 reglas originales intactas. Esto no acredita retirar hr_payroll ni haber
adoptado toda la identidad del motor. La preparación nativa sigue limitada a
clones privados; en Community no se asignan aliases falsos a reglas inexistentes.

inspect_payroll_configuration.py recorre las estructuras reales con un gerente
normal autorizado para la compañía, guarda hashes y diagnósticos y revierte el
actor de inspección. audit_payroll_profile_sources.py solo consulta metadatos de
Cerro/SyS con sesiones forzadas a lectura: IDs, actividad, categorías y huellas;
no copia fuentes OEEL ni cuerpos de reglas privadas. Ambos quedan versionados.

## Aceptación y evidencia

Paquete B: 90 archivos idénticos entre inventarios y coincidentes con el checkout;
SHA256 9b075f5a6f79b83222aef0e0f8d815a66473403e45823e9fa98d458de2a97888.
Community oficial/OCA con los mismos pins: 96 pruebas, 68 instalados/cero EE.
Copia fresca nativa: 36 pruebas, 377 instalados/140 EE. Se conservan 918 tablas/
proyecciones, 140 contadores exactos antes/después del upgrade y las fixtures,
58.956 XML IDs originales, modelos/campos, permisos, relaciones, restricciones,
históricos y saldos. Las configuraciones originales y la fuente activa conservan
sus valores/huellas. Producción y QA-Cerro no se modifican.

Los seis contratos nuevos por entorno cubren el diagnóstico de la configuración
real, aliases originales y retiro seguro, ruta válida y padre real de categoría,
rechazo sin reescritura de un GROSS desconectado, ausencia de BASIC inactivo,
orden esencial y rechazo antes de calcular. No sumar suites anteriores. A pasó
96/36; B agrega la protección de retiro de aliases y es aceptación final fresca.
Los 52 archivos del proveedor se reconstruyen byte a byte.

Evidencia privada: ~/.codex/local-artifacts/community-payroll-configuration-20261028/
evidence-B y summary-B.json. Servidor /opt/steps-validation/community-payroll-
configuration-20261028B; auditoría en community-payroll-configuration-20261028-audit.
Los informes de configuración y procedencia, sus inspectores y el paquete se
verifican contra Git. El informe de Cerro conserva los tres IDs originales; el
inspector usa permisos normales y revierte su actor. No se exportan fórmulas a Git.

## Pendientes y siguiente prompt

El mapa parcial mantiene 1.081 campos ausentes de módulos/motor/consumidores,
una diferencia One2many/Many2many, 12 de almacenamiento, 17 de obligatoriedad y
seis de selección, con cero diferencias en los atributos comparados del proveedor.
Sigue pendiente el traspaso real del motor, sus 71 reglas/cuatro estructuras/seis
entradas, el origen de los conceptos y los perfiles, YTD, casos chilenos, asientos,
Previred/libro, gastos y consumidores. Cerro no tiene pagadas reales para certificar
históricos de clientes. No desactivar reglas repetidas ni reescribir maestros para
hacer pasar la inspección; preservar sus IDs y las referencias históricas.

DTE/CAF/folios/firma/respuestas SII, los otros productos y conversión integral cero
EE, recuperación y aceptación siguen en el camino crítico. El 31 no está resuelto.
La automatización horaria permanece activa y no está autorizada a escribir producción.

Continúa desde la canónica actualizada en worktree propio. Lee AGENTS, ambientes,
operación, workflow, plan, continuidad, COMMUNITY_PAYROLL_HISTORY.md,
COMMUNITY_PAYROLL_CONFIGURATION.md, autonomía y matriz completa. El paquete B
pasó 96 Community/36 copia fresca nativa, preservando 918 tablas/proyecciones,
140 contadores y 58.956 XML IDs. Hay chequeo estructural antes de calcular y aliases
originales con retiro seguro; no se han adoptado/certificado las 71 reglas.
Resuelve en un paquete privado y verificable la desconexión estructural BASIC/GROSS
de Cerro, contrastando el comportamiento dinámico y la procedencia. SyS fue leído
sin cambios: GROSS refiere IMP y tiene dos NET activos; investiga su selección
real y conserva ambas identidades antes de usarlo como referencia. No copies
ciegamente fórmulas ni alteres maestros o históricos de producción. Prototipa y
prueba las reglas reales en Community y copia fresca con comparaciones, sin
inventar datos para ocultar brechas. Si falta evidencia, conserva el bloqueo y
avanza otra frontera operativa concreta. Mantén las protecciones de históricos,
Calendar, Boolean bancario y 210233; no recalcules pagadas, alteres vencimientos,
retires EE en producción, refresques QA-Cerro ni emitas al SII real. Guarda commits,
push, integra solo lo validado y verifica handoff. Actualiza estado y siguiente bloque.


Continuidad posterior: el usuario aportó SyS como referencia real. Ver
[COMMUNITY_SYS_REFERENCE.md](COMMUNITY_SYS_REFERENCE.md) para aceptación del
lector histórico, evidencia privada y siguiente bloque. No repetir la pregunta
sobre qué base usar; certificación financiera e identidad siguen pendientes.
