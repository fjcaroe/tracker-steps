# Entradas guardadas y cálculo real de lotes — 29-10-2026

Paquete de implementación congelado en `4bb59f9b`, desde la canónica `f589ba62`.
La aceptación conjunta está en curso; este documento no acredita todavía el cierre.
API **18.0.1.13.0**, Base **18.0.1.6.0**, Security **18.0.1.7.0**.
Conserva [Schema B](COMMUNITY_IDENTIDAD_REGLAS_NOMINA.md), Período C y sus guardas.

## Ruta implementada

El formulario OCA original de lotes incorpora «Calcular borradores guardados»
para el responsable de Nómina. Calcula liquidaciones existentes con el motor
OCA real; exige borradores, compañía activa, contrato mensual original abierto
y único que cubra el período, estructura explícita y revisión original completa.
No crea liquidaciones, contratos, maestros, entradas ni días trabajados.
Las devoluciones quedan bloqueadas: las diferencias de signo y contabilización
observadas entre los motores todavía no están certificadas.

La admisión comprueba todos los borradores antes del primer cálculo, usando
el actor normal incluso con sudo entrante o caché previamente elevada. Verifica
filas físicas completas y permisos de modelo, registro y campo antes de leer
importes. Las referencias ocultas impiden procesar el lote parcial.

Cada entrada debe conservar su tipo explícito, código, contrato, país y
cobertura de estructuras. Los descriptores heredados se admiten sólo con
correspondencia inequívoca; no se asignan tipos por semejanza de nombres/códigos.
Se permiten líneas repetidas del mismo tipo mediante la agregación existente.
Un importe guardado cero es válido; no certifica su procedencia ni aprobación.
SQL NULL se distingue del cero que presenta la caché Float de OCA y se rechaza,
igual que NaN e infinitos. El operador debe completar y guardar el valor.
La escritura explícita de `amount` invalida sólo su caché después de permisos e
historia y delega al ORM real sin prefetch; así un cero solicitado se persiste
aunque la caché anterior presentara NULL como cero. Una lectura o una escritura
sin ese campo no convierte NULL en cero.
Las vistas reales de entradas exponen el maestro sin permitir crearlo desde allí.

Los días ya guardados deben coincidir con los obtenidos de entradas de trabajo
reales del contrato, recortadas al período en su zona horaria. Se rechazan
conflictos, solapamientos, tipos incompletos y diferencias de horas/días. No se
completan ausencias con horas teóricas. Se reutiliza la admisión chilena vigente,
extraída en un helper de sólo comprobación sin alterar su cálculo global.

La acción encierra admisión, cálculo y verificación posterior en un savepoint.
Bloquea cabeceras, contratos, empleados, hijos y configuración real y vuelve a
comprobar el grafo antes del cálculo. Un error real en la segunda liquidación
revierte también la primera. Las entradas y work entries conservan sus filas
completas; los días conservan IDs y valores comerciales, aunque el refresco OCA
puede actualizar `write_uid`/`write_date`. Se conservan los números ya asignados.
Un borrador sin número puede recibirlo del motor; una secuencia PostgreSQL
`standard` puede consumir números ante un error tardío y no se rebobina.

El helper reutilizable de entradas admite estados mutables draft/verify; la
nueva acción de lote admite exclusivamente draft. Ninguna lectura histórica
calcula importes ni reabre liquidaciones pagadas o validadas.

## Aceptación pendiente

A queda como diagnóstico: cero fallos y cuatro errores de 460 casos CE. Tres
eran fixtures de permisos (copia completa de contrato sensible, eliminación de
work entry y vista de lotes exclusiva de manager). El cuarto reveló la omisión
del cero explícito por la caché Float; B incorpora el ajuste del producto y
pruebas de escritura explícita, denegaciones y conservación de NULL. La rama
nativa de A no se ejecutó. No se reutilizan sus bases como aceptación B.

Se prepararon doce casos funcionales nuevos: seis de entradas y seis de lotes,
incluidos cero/NULL, agregación, permisos con caché elevada, cobertura, formulario,
dos cálculos reales, conflictos, límite horario local y rollback ante fórmula errónea.
Las 28 pruebas puras de herramientas pasan: 17 del upgrade, seis del verificador
y cinco del auditor de beneficios. Son adicionales a las pruebas de Odoo.

El perfil de upgrade `saved-inputs` parte exclusivamente de Schema B aceptado y
actualiza los tres módulos. Debe conservar historia cerrada, almacenamiento,
IDs, relaciones, contadores y origen/filestore, con respaldo decodificado, además
de comprobar la negativa real a admitir entradas de historia cerrada.

Ejecución privada B: `/opt/steps-validation/community-payroll-inputs-20261029B`.
Upgrade: `/opt/steps-validation/community-inputs-upgrade-20261029B`.
Preflight: `/opt/steps-validation/community-inputs-preflight-20261029B`.
Exportación local: `C:/Users/tito4/.codex/local-artifacts/community-payroll-inputs-20261029`.

## Estado acumulado y siguiente puerta

Inventario fresco, repetido con el auditor exacto del candidato: Cerro
**381/140/100**, Steps **310/123/19**, SyS **332/142/17**
(instalados/Enterprise/propios), sin cambios. Repo: **126 módulos propios**,
**30 fuera de Cerro**, **54 apps instaladas con caminos Enterprise**.
Las fuentes privadas están incluidas; `steps_transport` sigue recuperado e inactivo.

Siguen pendientes la identidad original del motor y la adopción de **120
maestros/71 reglas**, siete brechas de campos y cinco físicas, tres observaciones
de selecciones, 12 bloqueos de seguridad, 24 IDs ocupados, 60 colisiones XML y
la acción 462. Este bloque admite valores guardados explícitos; no importa la
configuración original ni resuelve esas colisiones. El catálogo de beneficios
nativo tampoco se sustituye por modelos vacíos o por ventajas OCA no equivalentes.

El siguiente bloque debe preparar un bootstrap privado sin demo ni semillas
salariales del proveedor y comprobar su cierre XML antes de adoptar datos.
Quitar demo solamente no basta: Simple Digital carga reglas/estructuras desde
XML productivo y `hr_contract` crea cuatro tipos reales. Su coadopción requiere
demostrar identidad completa, PK y aliases; no sobrescribir por coincidencia de
nombre/ID. También deben cerrarse compañías, calendarios, tipos de trabajo,
diarios, propiedades y el renderer original 462 antes de importar los maestros.
La proyección del FK original de cada regla a su mismo par M2M puede conservar
el motor genérico optional/copy/share; no implica cambiar su campo global a O2M.

Falta certificar reglas chilenas con los procesos reales de SyS, períodos
parciales, redondeo/YTD, reembolsos, asientos, Previred/libro y consumidores HR.
Continúan DTE/CAF/folios/firma/transporte/respuestas SII, Tesorería restante,
Calidad, Studio/Documentos/Firma y todos los productos fuera de Cerro.
La puerta final exige copia integral restaurable con cero Enterprise,
preservación, flujos por rol y aceptación en Desarrollo.

**El 31 sigue en riesgo alto; no está acreditado llegar con todo migrado.**
Una instalación Community de referencia y pruebas sintéticas no equivalen a
convertir Cerro ni certificar nóminas de clientes. Producción y QA-Cerro siguen
intactos; no se alteran vencimientos, saldos históricos ni liquidaciones cerradas.
Calendar, Boolean bancario y 210233 continúan protegidos.

> Continúa desde la canónica actualizada en worktree propio. Lee AGENTS,
> registro, operación, workflow, autonomía, continuidad, COMMUNITY_ENTRADAS_GUARDADAS.md
> y sus referencias. Conserva el paquete de entradas/lotes aceptado sólo si su
> evidencia conjunta y upgrade están cerrados. Prioriza identidad/configuración
> original: propietarios O2M, estructuras/tipos, ACL y 120 maestros/71 reglas
> antes de cambiar dependencias; no infieras propietarios, valores ni maestros.
> Usa SyS como referencia real sin recalcular pagadas. Mantén los bloqueos de
> traducciones y devoluciones, y certifica días/períodos, redondeo/YTD, asientos,
> Previred/libro. Avanza DTE/folios/firma/respuestas y la conversión integral
> cero EE. Prueba el paquete exacto en ambos motores y upgrade, preserva evidencia,
> guarda commits/push, integra sólo lo validado y verifica el handoff.
