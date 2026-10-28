# Orden e identidad de reglas repetidas — 28-10-2026

## Alcance

Base canónica 7c4e68a; rama propia codex/community-payroll-rule-order-20261028.
Código f79071a; auditor de referencias históricas a1e42ad. El adaptador OCA
18.0.1.2.0 ordena explícitamente las reglas reales por (sequence, id), conservando
el desempate por ID original en lugar de depender del orden de una relación M2M.
No modifica reglas, secuencias, fórmulas, categorías, estructuras ni dependencias.
El informe estructural enumera todos los IDs candidatos de cada concepto esencial.
Si NET no es único, conserva NET_AMBIGUOUS: observar la ejecución en una fixture
no autoriza elegir una regla del cliente ni convertir su configuración.

## Contratos funcionales

Tres contratos nuevos compartidos usan los motores reales y un gerente normal:
NET repetido en la misma secuencia, NET posterior condicionado a falso y rechazo
estructural de la ambigüedad sin alterar sus registros. Se comprueban importe,
identidad de la línea resultante, acumulación de categoría y conservación de ambas
reglas. Las fixtures son contratos privados nuevos, no liquidaciones del cliente.

En lectura forzada PostgreSQL se vuelve a auditar Cerro y SyS. La auditoría añade
condición/modalidad de las reglas y referencias históricas NET agrupadas por ID,
sin nombres de empleados, importes ni cuerpos de fórmulas. SyS tiene dos NET
activos, pero sus líneas históricas también referencian una tercera identidad.
Por eso no se desactiva, borra ni reasigna ninguna regla como limpieza del motor.

## Aceptación

Paquete A, código de addons f79071a: 99 pruebas en Community oficial/OCA y
39 en copia fresca nativa de Cerro, cero fallos/errores. Ambos escenarios prueban
que el NET posterior por (sequence,id) conserva su ID en la única línea NET y
su total de 30 se acumula una sola vez; si su condición es falsa, quedan el ID y
el total 10 del anterior. No se elige automáticamente una regla original ni se
certifican políticas chilenas mediante estos importes sintéticos.

Los 90 archivos del paquete coinciden entre entornos y con Git;
SHA256 e562e78c066138e19536f7b6cf3380c0ca4b898f97ca51a65446cb2067efee4c.
Community tiene 68 módulos instalados/cero Enterprise; la referencia nativa,
377/140. Se preservan 918 tablas/proyecciones y 140 contadores originales durante
upgrade y pruebas, 58.956 XML IDs, modelos/campos, ACL, reglas, relaciones,
restricciones e históricos. Los 52 archivos AGPL derivados son reproducibles
byte a byte; cero diferencias en los atributos del proveedor comparados. El mapa
parcial mantiene 1.081 campos ausentes, una diferencia de tipo, 12 de almacenamiento,
17 de obligatoriedad y seis de selección. Esto no equivale a convertir Cerro.

La matriz completa se regenera desde la auditoría vigente y coincide exactamente
con COMMUNITY_INVENTARIO_ENTERPRISE_20261028.md: 111 manifiestos propios en repo,
con los productos no instalados en Cerro también inventariados. Las fuentes
privadas activas y configuraciones originales conservan sus huellas. Producción,
QA-Cerro, pagadas, vencimientos, Calendar, Boolean bancario y 210233 no se alteran.

Evidencia privada: ~/.codex/local-artifacts/community-payroll-rule-order-20261028/
evidence-A y summary-A.json. Servidor: /opt/steps-validation/community-payroll-
rule-order-20261028A; auditoría en community-payroll-rule-order-20261028-audit.
El resumidor verifica paquete/Git, comparaciones de conservación, inspector con
actor normal y rollback, fuentes del auditor y reproducción del proveedor.

## Estado acumulado y siguiente bloque

El inventario de producción permanece en 374 módulos, 93 propios y 140 Enterprise;
53 apps propias instaladas aún alcanzan Enterprise en el grafo candidato. La matriz
incluye también productos fuera de Cerro y fuentes privadas; no cambia por ordenar
reglas de Nómina. Las 71 reglas de Cerro no están adoptadas/certificadas. Sigue
GROSS_DISCONNECTED_FROM_BASIC en Cerro; Community aún carece de las tres reglas
esenciales de Chile. No se traspasan fórmulas de SyS por similitud de nombres.

Faltan conversión de identidad/almacenamiento del motor y adopción real de las
estructuras, entradas y reglas originales; días, redondeos/YTD, casos chilenos,
contabilización, Previred/libro y consumidores. Cerro no tiene liquidaciones reales
para certificar históricos de otros clientes. DTE/CAF/folios/firma/respuestas SII,
Tesorería, Calidad, Studio/Documentos/Firma y los demás productos, conversión integral
con cero Enterprise, restauración y aceptación continúan en el camino crítico.
El 31 de octubre mantiene riesgo alto: ninguna prueba parcial resuelve el vencimiento.

Siguiente prompt: continúa desde la canónica actualizada en worktree propio. Lee
AGENTS, ambientes, operación, workflow, plan, continuidad, autonomía, matriz completa,
COMMUNITY_PAYROLL_CONFIGURATION.md y COMMUNITY_PAYROLL_RULE_ORDER.md. Revisa el
inventario vigente y conserva los contratos ya comprobados. El orden original de
reglas repetidas está cubierto en ambos motores; la ambigüedad sigue bloqueando la
adopción automática. Contrasta las capas dinámicas BASIC/GROSS y la procedencia de
las 71 reglas en un paquete privado versionado; cierra la configuración original
antes de cambiar dependencias. Preserva también las identidades NET históricas y
condiciones, no copies a ciegas fórmulas de otros perfiles. No recalcules pagadas,
modifiques producción, vencimientos, QA-Cerro ni emitas SII real. Respeta Calendar,
Boolean bancario y 210233. Prueba paquete exacto en Community oficial y copia fresca,
guarda evidencia privada, commits, push, integra solo lo validado y verifica handoff.
Mantén visibles YTD, Previred/libro, DTE/CAF/SII y conversión integral cero Enterprise.
