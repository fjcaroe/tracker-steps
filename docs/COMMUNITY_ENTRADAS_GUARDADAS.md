# Entradas guardadas y cálculo real de lotes — 29-10-2026

Paquete de implementación congelado en `5343efe1`, desde la canónica `f589ba62`.
Aceptados Inputs C y upgrade D; resumen privado reproducible verificado.
Se cierra esta ruta de borradores guardados, con la certificación chilena pendiente.
358 archivos de addons; huella común `6a471a2115e519f598dcdff597a94cede079bde3e18b41658e03434a8d0437eb`.
Tar Git C SHA256 `8840f905a138595f6e30696fc459415438636c3a51fe749683fdc1873345afdc`.
El paquete incluye el verificador corregido en `26c6923f`;
el verificador original de versiones consultaba dos módulos aunque actualizaba tres.
Los intentos de upgrade A/B conservan ese rechazo diagnóstico y no se aceptan.
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
Los resultados de un borrador siguen la regeneración estándar de líneas OCA;
esta acción no adopta ni recalcula líneas históricas cerradas. La preservación
de IDs del upgrade y de la copia nativa se comprueba por separado.

El helper reutilizable de entradas admite estados mutables draft/verify; la
nueva acción de lote admite exclusivamente draft. Ninguna lectura histórica
calcula importes ni reabre liquidaciones pagadas o validadas.
La admisión completa de cobertura y NULL se aplica a esta acción y a su helper;
no se añadió un rechazo global a `compute_sheet` que rompiera los contratos
genéricos anteriores. Los demás puntos de entrada deben adoptar esa política
explícitamente con sus pruebas. El generador de lotes continúa rechazando
entradas configuradas sin valores originales; esta acción no le inventa ceros.

## Aceptación y preservación

**460 casos Community y 294 nativos**, cero fallos/errores. Se mantienen dos
omisiones CE y cinco nativas documentadas, sin contarlas como equivalencia entre
motores. Community instala **96 módulos y cero Enterprise**; la copia fresca
nativa instala **391 y conserva 140 EE**. Esta última sigue siendo una referencia,
no una conversión. El paquete conserva los cinco consumidores HR, Tesorería y CAF.

En la copia nativa se preservan **921 tablas/proyecciones y 140 contadores
comerciales** (1.061 contratos), **59.079 XML IDs con noupdate**, maestros, ACL,
relaciones, saldos e históricos. Los 88 aliases originales y los tres nuevos
de referencia están clasificados sin deriva. Los registros pasivos conservan
615 contratos CE y 1.602 nativos. Los dos PDF nuevos, cuatro páginas renderizadas
e inspeccionadas, mantienen NULL en blanco, cero, negativos, BASIC y firma.

A queda como diagnóstico: cero fallos y cuatro errores de 460 casos CE. Tres
eran fixtures de permisos (copia completa de contrato sensible, eliminación de
work entry y vista de lotes exclusiva de manager). El cuarto reveló la omisión
del cero explícito por la caché Float; B incorpora el ajuste del producto y
pruebas de escritura explícita, denegaciones y conservación de NULL. La rama
nativa de A no se ejecutó. B terminó con un fallo y cero errores: la expectativa
de un aviso de país no respetaba la denegación anterior de la regla de acceso
original. C corrige sólo esa expectativa; mantiene la regla y prueba el paquete
completo en bases nuevas. Las ramas nativas de A/B no se ejecutaron.

C ejecutó doce casos funcionales nuevos: seis de entradas y seis de lotes,
incluidos cero/NULL, agregación, permisos con caché elevada, cobertura, formulario,
dos cálculos reales, conflictos, límite horario local y rollback ante fórmula errónea.
Las 29 pruebas puras de herramientas pasan: 18 del upgrade, seis del verificador
y cinco del auditor de beneficios. Son adicionales a las pruebas de Odoo.

El perfil de upgrade `saved-inputs` parte exclusivamente de Schema B aceptado y
actualiza los tres módulos: API1.12→1.13, Base1.5→1.6 y Security1.6→1.7.
El ensayo D compara **674 filas de veinte tablas**: conserva **672 literalmente**
y audita los dos `write_date` XML previstos, sin llamarlos byte-idénticos.
Conserva **529 IDs de modelo y 10.265 de campo**, las tres relaciones no vacías,
JSON, columnas y contadores, sin campos nuevos. Verifica la negativa real a
admitir entradas de historia cerrada y la lectura sin recálculo. Origen Schema B
y filestore intactos; respaldo decodificado en el servidor. El fixture de cierre
es privado y sintético; no acredita migrar o recalcular nóminas comerciales.

El resumen offline verifica el paquete contra Git, derivaciones, upgrade, PDF,
preflight, seguridad, identidad y contratos de beneficios. El export privado
excluye dumps, filestore y fuentes OEEL; no se presenta como una nueva restauración
del respaldo fuera del servidor. Los diagnósticos A/B permanecen separados.

Ejecución privada C: `/opt/steps-validation/community-payroll-inputs-20261029C`.
Upgrade: `/opt/steps-validation/community-inputs-upgrade-20261029D`.
Preflight: `/opt/steps-validation/community-inputs-preflight-20261029C`.
Exportación local: `C:/Users/tito4/.codex/local-artifacts/community-payroll-inputs-20261029`.
Resumen: `acceptance-C/summary.json`. El recibo sellado y handoff están en
`accepted-evidence-C-final.receipt.json`, en la carpeta padre.

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
La referencia CE mantiene 48 reglas, con BASIC/GROSS/NET de Chile sin adoptar;
la nativa conserva 71 y su diagnóstico `GROSS_DISCONNECTED_FROM_BASIC`.
Las guardas chilenas siguen bloqueando esa configuración incompleta. La referencia
SyS contiene 627 liquidaciones cerradas (626 completas sin ambigüedad), pero sólo
se ha contrastado BASIC mensual y el documento de referencia, no toda la nómina.
Los conteos 27/7/5 corresponden a configuración. Las entradas conservan otras
diferencias: `code` y `contract_id` son relacionados no almacenados en la
metadata nativa y almacenados en OCA. Su adopción histórica, tipos físicos y
precisión necesitan evidencia propia; este cálculo de borradores no los convierte.

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
> y sus referencias. Conserva Inputs C, upgrade D, Schema B y sus guardas.
> Prioriza el bootstrap sin demo ni semillas salariales y la identidad/configuración
> original: propietarios O2M, estructuras/tipos, ACL y 120 maestros/71 reglas
> antes de cambiar dependencias; no infieras propietarios, valores ni maestros.
> Usa SyS como referencia real sin recalcular pagadas. Mantén los bloqueos de
> traducciones y devoluciones, y certifica días/períodos, redondeo/YTD, asientos,
> Previred/libro; cierra los otros consumidores de entradas sin relajar sus permisos.
> Avanza DTE/folios/firma/respuestas y la conversión integral
> cero EE. Prueba el paquete exacto en ambos motores y upgrade, preserva evidencia,
> guarda commits/push, integra sólo lo validado y verifica el handoff.
