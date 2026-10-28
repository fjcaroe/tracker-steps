# YTD almacenado en OCA — 28-10-2026

## Contrato y procedencia

Base canónica 297f8f8; rama propia codex/community-payroll-ytd-20261028.
Código final 7191d77 (motor 092d80e, fixtures corregidas y guard de permisos);
verificador b6ba5a0. Primero se observó el
motor nativo con fixtures privadas y gerente normal, sin leer/copiar fuentes OEEL.
El probe versionado no escribe producción; revierte sus registros y exporta solo
resultados sintéticos. No es una certificación tributaria ni un traspaso del motor.

En la referencia real, ytd de hr.payslip.line es un importe almacenado, no un campo
calculado al leer. Con reglas de entrada simples: diciembre anterior queda fuera;
enero cerrado aporta 10, febrero cerrado 30, febrero borrador 20 queda fuera y
marzo actual 40 da 80. Un período cerrado solapado con cierre anterior al actual
aporta 15 y da 95; otra cerrada del mismo período aporta 9 y da 104. Se observan
además exclusiones de una estructura distinta, nota de crédito anterior y período
que comenzó el año anterior. Cambiar flags de configuración y volver a calcular
la misma fixture no basta para certificar reinicios fiscales; quedan restringidos.

## Implementación

step_payroll_oca_api 18.0.1.3.0 añade los campos reales ytd (Monetary almacenado),
ytd_computation de estructura y su relación de liquidación, y la configuración de
reinicio de compañía. Con año calendario y una sola línea por concepto, el motor
OCA calcula normalmente y guarda el total actual más los totales almacenados de
cerradas anteriores del mismo empleado, compañía y estructura, con comienzo en
el año y fin no posterior al período actual. Excluye créditos y usa permisos
normales; si faltan liquidaciones o líneas históricas por reglas de acceso, falla
en lugar de sumar una
parte. Sin activar acumulación, guarda el total actual como la referencia nativa.
_get_line_values acepta ytd y compute_sum leyendo esos valores almacenados.

El alcance inicial exige mismo contrato y reinicio 1 de enero. Se rechazan antes
de calcular los reinicios especiales, créditos actuales y períodos que cruzan el
año. Las líneas repetidas con acumulación activa fallan atómicamente, conservando
las entradas originales. Su acumulación necesita contraste nativo específico.
No se promete equivalencia para los casos explícitamente bloqueados.

Los hooks preinstall/preupgrade exigen valores YTD originales completos en líneas
cerradas: si falta columna o valor, no inventan cero ni reconstruyen el acumulado.
Las lecturas son directas y no dependen del sueldo actual ni recalculan pagadas.
El puente de permisos 18.0.1.3.0 también impide cambiar credit_note de una cerrada,
porque ese cambio alteraría el universo histórico acumulable. No se adopta ningún
XML ID nativo nuevo ni se cambia una dependencia antes de cerrar la conversión.

La fixture inicial alteraba date_start del contrato, lo que activó asignación de
vacaciones del proveedor con un tipo ligado a otra compañía. Su error de acceso
rechazó la ejecución aunque las aserciones nativas pasaron. La aceptación final
mantiene ese maestro intacto: el motor admite los períodos históricos de la
fixture sin cambiar su fecha actual. La compatibilidad multiempresa de esas
vacaciones queda pendiente; no se amplían permisos ni se cambia el tipo original.
También se corrigieron una aserción de API obsoleta y la codificación de las
fixtures antes de repetir desde bases frescas. No se acepta ningún paquete fallido.

## Aceptación y evidencia

Paquete E, código 7191d77: 106 pruebas Community oficial/OCA (68 módulos, cero EE)
y 46 en copia fresca nativa (377 módulos, 140 EE), sin errores de registro. Los siete
contratos nuevos cubren ventana/estados/solapamiento, flag desactivado, lectura e
inmutabilidad del YTD cerrado y admisión de snapshots en ambos motores; los guards
de reinicios/créditos, conceptos repetidos e histórico oculto son exclusivos OCA.
El probe nativo del paquete aceptado se ejecuta también con actor normal y rollback.
No se suman suites de bloques anteriores ni se presenta la referencia como conversión.

Los 93 archivos del paquete coinciden entre ambos entornos y con Git; SHA256
7c183a51efed8ab120496a15c1b2e4dc0481c966090f7d07a9e5c3d1e87fa44d.
Se conservan 918 tablas/proyecciones y 140 contadores de negocio durante upgrade y
pruebas, 58.956 XML IDs originales, modelos/campos, ACL, reglas, relaciones,
restricciones, históricos y saldos. La fuente efectiva y sus versiones no cambian.
Los 52 archivos del proveedor AGPL se reproducen byte a byte. Cinco campos pasan
a existir: el mapa parcial baja de 1.081 a 1.076 ausencias; conserva una diferencia
de tipo, 12 de almacenamiento, 17 de obligatoriedad y seis de selección, con cero
diferencias en los atributos comparados del proveedor. No es adopción de sus IDs.
La matriz completa regenerada coincide con la vigente; no cambian sus 53 clausuras.

Evidencia privada: ~/.codex/local-artifacts/community-payroll-ytd-20261028/evidence-E,
summary-E.json y verification-E.log. Servidor: /opt/steps-validation/community-payroll-
ytd-20261028E; auditoría de solo lectura en community-payroll-ytd-20261028-audit.
El resumidor verifica hashes contra Git, conservación, inspector de configuración,
reproducción y fuente/observaciones del probe nativo. A/B quedan rechazados; C se
detuvo antes de crear bases por contener pruebas obsoletas; D pasó 105/45 y E añade
el guard de líneas ocultas. Solo E es la aceptación final. Producción y QA-Cerro,
pagadas, vencimientos, Calendar, Boolean bancario y 210233 permanecen intactos.

## Pendientes y siguiente prompt

La configuración original Simple Digital sigue bloqueada: faltan BASIC/GROSS/NET
en la estructura Chile Community y Cerro conserva GROSS_DISCONNECTED_FROM_BASIC.
No se reescriben fórmulas ni se copian perfiles de SyS para ocultar esa barrera.
Las 71 reglas, estructuras, entradas y campos/IDs del motor requieren adopción
real; este bloque añade un caso YTD acotado, no certifica todo el frente YTD.

Siguen pendientes reinicios fiscales, cambios de contrato, créditos y conceptos
repetidos con YTD, YTD de días trabajados, asistentes/campos de configuración,
casos chilenos, contabilización, Previred/libro y consumidores HR. Una base OCA
antigua con cerradas sin ytd queda bloqueada hasta disponer de valores originales;
la prueba anterior de upgrade 1.0->1.1 no certifica este upgrade nuevo. Cerro no
tiene liquidaciones originales para certificar históricos reales de otros clientes.

Producción mantiene 374 módulos, 93 propios y 140 Enterprise; quedan 53 apps propias
con caminos EE en el candidato y 111 manifiestos propios en repo. DTE/CAF/folios/
firma/respuestas SII, Tesorería, Calidad, Studio/Documentos/Firma y otros productos,
conversión integral cero Enterprise, restauración y aceptación siguen pendientes.
El 31 de octubre mantiene riesgo alto; no está resuelto por este paquete parcial.

Siguiente prompt: continúa desde la canónica actualizada en worktree propio. Lee
AGENTS, ambientes, operación, workflow, plan, continuidad, autonomía, matriz completa,
COMMUNITY_PAYROLL_CONFIGURATION.md, COMMUNITY_PAYROLL_RULE_ORDER.md y
COMMUNITY_PAYROLL_YTD.md. Conserva lo comprobado y revisa inventario completo.
Prioriza adoptar la configuración original Simple Digital y las 71 reglas sin
reescribir maestros para pasar un test. Contrasta la desconexión BASIC/GROSS, sus
capas dinámicas y procedencia. Cierra identidad/almacenamiento del motor, entradas,
estructuras y consumidores antes de cambiar dependencias. YTD calendario tiene
un alcance acotado; verifica los casos bloqueados y el upgrade real con snapshots
originales antes de ampliarlo. Prueba paquete exacto en Community oficial y copia
fresca aislada, preservando maestros, IDs, ACL, relaciones, históricos, saldos y
correlativos. No recalcules pagadas ni modifiques producción, vencimientos o
QA-Cerro; respeta Calendar, Boolean bancario y 210233. No emitas SII real. Guarda
commits, push, integra solo lo validado y verifica handoff. Mantén visibles DTE/CAF/
SII, Previred/libro y conversión integral restaurable cero Enterprise.
