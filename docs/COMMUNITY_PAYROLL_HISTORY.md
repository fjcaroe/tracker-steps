# Históricos monetarios de Nómina sobre OCA — 28-10-2026

## Alcance integrado

Base f4297ca, rama propia codex/community-payroll-history-20261028. Código de
addons 434fc86, paquete C; probe de upgrade be43f38. No se cambian dependencias
ni se convierte el motor de Cerro. Producción y QA-Cerro quedan intactos.
La auditoría de solo lectura se repitió: 374 instalados, 93 propios, 140 EE;
71 reglas/cuatro estructuras/seis entradas; cero contratos/liquidaciones reales.
La matriz completa mantiene 53 clausuras EE entre las apps instaladas y 111
módulos propios en repo, incluidos soportes de ensayo que no son productos.

## Protección de importes y relaciones

step_simpledigital_oca_base y step_simpledigital_oca_security pasan a 18.0.1.1.0.
Cinco campos conservan ahora almacenamiento real en sus modelos/tablas originales:
hr.payslip basic_wage/gross_wage/net_wage y hr.payslip.worked_days amount/is_paid.
Los borradores siguen calculando desde sus datos reales. Una liquidación cerrada
restaura los valores SQL originales en caché limpia, sin evaluar reglas, usar el
sueldo vigente, redondear de nuevo ni escribir importes/auditoría en esas filas.
El cambio posterior de sueldo o de tipos no pagados deja intacto su histórico.

step_history_locked es un indicador adicional en hr.payslip, de solo lectura y
no copiable. Se fija al validar/pagar y permanece aunque se cancele/reabra el
estado. La vista oculta el cálculo para esas liquidaciones y el modelo lo impide
ante RPC directo. No puede resetearse el pago ni desbloquearse el indicador desde
write. Los importes se materializan antes de cerrar, mientras todavía son borrador;
el cierre y los cambios de período/contrato/entradas deben hacerse por separado.

Se impiden modificaciones, borrado, incorporación o movimiento de líneas de
salario, entradas y días hacia liquidaciones cerradas. Se protegen sus fechas,
estructura, empleado/contrato/compañía y totales. Los códigos de reglas utilizados
en históricos cerrados no se renombran; se conserva la identidad referenciada.
Las cancelaciones y devoluciones estándar pasan las pruebas upstream de OCA;
esto no certifica todavía toda la política de créditos/correcciones chilena.

La referencia nativa recibe controles de escritura y verificaciones SQL compatibles,
sin redefinir sus campos/almacenamiento. La protección de caché y el indicador
permanente son del candidato OCA; no se instala ese candidato encima del motor nativo.

## Admisión antes del upgrade

Los hooks pre-init y pre-migración revisan globalmente los históricos protegidos
antes del auto-init de campos. Si faltan columnas o valores originales almacenados,
se rechaza el upgrade: no se rellenan ceros ni se reconstruye el pasado con el
contrato actual. Los originales NULL/incompletos requieren clasificación y
procedencia antes de cualquier adopción. El hook posterior marca el cierre
existente sin alterar sus importes ni fechas de auditoría.

Un guard separado rechaza instalar/actualizar el puente Community si hr_payroll
sigue activo. La conversión de identidad/propiedad debe retirar primero ese
motor de una copia mediante el procedimiento auditado; este bloque no lo hace.
No hay tablas paralelas, maestro convertido en texto, hr_payroll vacío ni
hr.payslip simulado. No existe un contexto RPC para saltarse estas protecciones.

## Evidencia aceptada

Paquete C: 88 archivos idénticos entre inventarios y coincidentes con el checkout,
SHA256 3c74fbdf6f286ac09b77c56562209c48ca9ce865957d0409d32147bb44a3bbd7.
Community oficial/OCA fijados a los pins anteriores: 90 pruebas, 68 instalados,
cero Enterprise. Copia fresca nativa de Cerro: 30 pruebas, 377 instalados/140 EE.
Se preservan 918 tablas/proyecciones y 140 contadores exactos después del upgrade
y de las fixtures, 58.956 XML IDs, 1.217 modelos, 26.994 campos, 5.071 selecciones,
2.322 ACL, 610 reglas, 1.328 menús, 417 vínculos acción-vista, 463 relaciones y
526 restricciones. También membresías originales, históricos, saldos y parámetros
protegidos. No sumar las suites antiguas ni los ensayos diagnósticos.

Los siete contratos nuevos de OCA comprueban conservación SQL completa tras
cambiar el sueldo y el tipo no pagado, lectura/recompute sin evaluar líneas,
actualización normal de borradores, bloqueo después de reabrir, códigos usados,
rechazo de creación cerrada y rechazo previo a crear una columna faltante.
Tres contratos nuevos compartidos comprueban admisión no mutante, rechazo de
originales NULL y bloqueo de superposición con el motor nativo. Se amplía además
el caso existente para impedir edición/borrado de líneas cerradas. La prueba de
redondeo usa ahora borradores independientes por período/estado.

validate_payroll_history_upgrade.py prueba un upgrade auténtico Community
18.0.1.0.0 -> 18.0.1.1.0 con el paquete anterior K, sin falsear versiones:

1. Crea datos sintéticos en el motor OCA real, calcula y contabiliza con un usuario
   normal, y captura los valores originales todavía en borrador antes de cerrar.
2. El upgrade rechaza la ausencia de almacenamiento histórico y conserva las filas.
3. Adopta exclusivamente esos valores originales auditados en las mismas columnas
   y los mismos IDs, y repite el upgrade correctamente.
4. Verifica el marcador del post-migración, los 131 IDs de campos originales,
   las filas originales de liquidación/días/líneas y el asiento con sus dos apuntes.
   Un aumento posterior de sueldo mantiene valores y filas originales intactos.

El probe aceptado es B. A falló por inicialización diferida del plan contable de
la compañía de prueba; B finaliza esa inicialización real antes del diario.
El paquete A de modelos pasó 29 referencias nativas y detectó una prueba antigua
que editaba repetidamente un histórico cerrado. B se preparó pero no se ejecutó;
C es la aceptación completa final. Ningún diagnóstico se reutiliza como aceptación.

Evidencia privada: ~/.codex/local-artifacts/community-payroll-history-20261028/
evidence-C y summary-C.json. Servidor /opt/steps-validation/community-payroll-
history-20261028C y community-payroll-history-upgrade-20261028B.
El resumen verifica hashes, reconstrucción de los 52 archivos del proveedor,
conservación y fuente exacta del probe de upgrade. Los datos/respaldos permanecen
fuera de Git. Las fixtures sintéticas no acreditan historias pagadas de clientes.

## Pendientes y siguiente bloque

Las diferencias de almacenamiento del mapa parcial bajan de 17 a 12. Permanecen
1.081 campos ausentes de módulos no cargados/motor/consumidores, una diferencia
One2many/Many2many, 17 de obligatoriedad y seis de selección. El candidato contiene
8.131 campos; los atributos comparados del proveedor mantienen cero diferencias.
Quedan la adopción integral de campos/modelos/XML IDs/ACL/relaciones del motor,
las 71 reglas/cuatro estructuras/seis entradas originales, YTD, casos chilenos,
asientos, dos perfiles Previred y dos perfiles/42 líneas de libro, gastos y
consumidores HR. Cerro no contiene pagadas reales: hace falta evidencia
representativa antes de certificar conservación de históricos de clientes.

Siguen DTE/CAF/folios/firma/respuestas SII, Tesorería y los demás productos,
la conversión integral cero EE, restauración y aceptación en Desarrollo.
Se conserva historical_conversion=false, simpledigital_certified=false,
full_cerro_conversion=false y deadline_resolved=false. El riesgo del 31 es alto.

## Siguiente prompt

Continúa desde la canónica actualizada en worktree propio. Lee AGENTS, registro
de ambientes, operación, workflow, plan, continuidad, COMMUNITY_SIMPLEDIGITAL_OCA.md,
COMMUNITY_PAYROLL_HISTORY.md, COMMUNITY_AUTONOMIA.md y matriz Enterprise vigente.
El paquete C pasó 90 pruebas Community y 30 en copia fresca nativa, conservando
918 tablas/proyecciones, 140 contadores y 58.956 XML IDs. Hay almacenamiento y
protección de los cinco importes/flags críticos, admisión sin inventar originales
y upgrade Community real 1.0->1.1 con datos sintéticos/IDs/asiento conservados.
Esto no convierte Cerro ni certifica pagadas reales. No retires los guards para
forzar una instalación sobre hr_payroll activo o históricos sin valores originales.
Prioriza la configuración privada original (71 reglas, cuatro estructuras, seis
entradas) y la adopción de identidad/relaciones del motor. No recalcules pagadas
ni sus importes al leer; conserva las protecciones y los otros 12 contratos de
almacenamiento pendientes. Certifica reglas, YTD, asientos, Previred y libro.
Mantén visibles DTE/CAF/SII y conversión integral cero EE. No escribas producción,
retires allí EE, alteres vencimientos, refresques QA-Cerro ni emitas al SII real.
Respeta Calendar, Boolean bancario y 210233. Prueba el mismo paquete en Community
oficial y copia fresca aislada, commits/push, integra solo lo validado y ejecuta
python tools/git/verify_handoff.py --require-pushed. Actualiza evidencia y siguiente bloque.


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
