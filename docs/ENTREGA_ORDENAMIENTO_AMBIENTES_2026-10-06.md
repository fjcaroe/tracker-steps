# Ordenamiento de ambientes y revisión de pendientes

La definición del cliente del 6 de octubre prevalece sobre los destinos de
documentos anteriores: Desarrollo es el único QA, Demo-SYS es Nómina/soporte,
y las producciones son SyS, Steps/Karo y Cerro El Plomo. Demo, Admin y Everfruit
quedan fuera del circuito de publicación. Sus bases se conservan.

## Cambios publicados y comprobados

- Accesos por IP/puerto: redirección 308 al dominio HTTPS correcto, conservando
  ruta y parámetros. 8075 corresponde a Desarrollo. Verificados GET y POST en
  los ocho listeners internos y accesos externos 8075, 8070 y 8069.
- Registro compartido `tools/ops/environments.json`, instrucciones del repositorio,
  bloque administrado de Claude y flujo de su tarea de tickets actualizados.
  Se exige identificar destino, comprobar código cargado, usar worktree propio,
  publicar el paquete probado y conservar respaldo/evidencia. Las credenciales
  existentes no se modificaron. Estas instrucciones no sustituyen los permisos
  de acceso al servidor ni impiden que alguien las incumpla.
- Gestión y Costos en Desarrollo: paquete `6ffa057758a46f24b3e408cb17f77d2514e85ed2`,
  núcleo `18.0.21.1.0`. 354 pruebas, cero fallos/errores; nueve tablas de negocio
  conservaron filas e importes. Verificación independiente del registro efectivo,
  versiones, relaciones, formularios y HTTPS aprobada.

Tickets revisados con movimiento reciente: T50 (selectores reales de temporada,
especie y variedad), T51 (centro único `account.analytic.account`), T52 (maestros
multiempresa), T53 (menús/versión), T44/T47 (días y atrasos), T39 (tabla SII),
y el flujo conjunto T35/T38/T40/T41 (Exportaciones, Productores e Inventario/Packing).
No se enviaron comentarios ni se cerraron tickets automáticamente.

El paquete de Gestión conserva los textos históricos como referencia, elimina
el modelo paralelo de centro de costo del registro y usa las relaciones a los
maestros existentes. El alcance multiempresa se controla por reglas de acceso.
Los datos antiguos no se reinterpretan para inventar vínculos.

Evidencia en el servidor:

- QA: `/opt/steps-validation/management_development_r9/qa-20261006T060304Z.log`.
- Respaldo: `/opt/steps_backups/management_development_20261006T062133Z`.
- Conservación: `tools/ops/check_management_preservation.py development r9`.
- El actualizador inicial terminó la migración, pero rechazó su log por imports
  incondicionales de pruebas de los módulos agrícolas ya existentes. Se comprobó
  posteriormente el despliegue y la conservación; esos imports se corrigen en
  el paquete siguiente. No se trató el error del comando como prueba de éxito.

## Nómina: paquete y condiciones de migración

Paquete publicado `2dc161f26c6d549a00c474bf81e8c3f83e984092`,
SHA-256 `10f8e05ffdaba7351e4dcfa2130c6f5cb2bf14eb452d0352f6a29637c0950646`.
El proveedor Simple Digital se copia privadamente desde el servidor; su hash
queda vinculado a la validación y se exige idéntico antes de publicar.

| Ambiente publicado y verificado | Copia de validación | Pruebas sin fallos/errores | Respaldo privado en `/opt/steps_backups/` |
|---|---|---|---|
| Desarrollo | `PAYROLL_COMPAT_DEVELOPMENT_p17` | 319 | `payroll_development_20261006T073605Z` |
| Demo-SYS | `PAYROLL_COMPAT_DEMO_SYS_p16` | 293 | `payroll_demo-sys_20261006T073912Z` |
| SYS | `PAYROLL_COMPAT_SYS_p16` | 293 | `payroll_sys_20261006T074259Z` |
| Steps/Karo | `PAYROLL_COMPAT_STEPS_p16` | 293 | `payroll_steps_20261006T074525Z` |
| Cerro El Plomo | `PAYROLL_COMPAT_CERRO_p16` | 293 | `payroll_cerro_20261006T074913Z` |

Los cinco destinos aprobaron `PAYROLL_VERIFY_OK`, con formularios efectivos,
versiones y origen de código comprobados, motor anterior ausente y login HTTPS.
Cada actualización conservó el detalle de contratos, liquidaciones, días
trabajados y movimientos/líneas contables mediante comparación antes/después.

Versiones comunes: proveedor Simple Digital `18.0.1.0.0` (copia privada),
Previred `18.0.3.8.4`, puente Simple Digital `18.0.2.4.0`, días/atrasos
`18.0.1.1.0`, ciclo de contratos `18.0.2.0.1`, adaptador de contratos
`18.0.1.1.0`, libro de remuneraciones `18.0.3.4.0`, política de ambiente
`18.0.1.0.1` y archivo histórico `18.0.1.0.0`.

La transición archiva los registros del motor anterior, conserva identificadores
y detalle de liquidaciones/asientos y guarda PDFs originales de las liquidaciones
cerradas. Desinstala el motor y sus extensiones conocidas, bloquea su reinstalación
y el cálculo con estructuras antiguas. Los contratos migrados o incompletos
exigen revisión explícita por un responsable antes de calcular nuevas liquidaciones.
No se recalculan liquidaciones pagadas ni se contabilizan operaciones reales.
Para consultar una liquidación del motor anterior, abrir su PDF original adjunto.
Se archivaron también cuatro menús Studio que apuntaban a maestros retirados;
las causales vigentes se mantienen en el maestro nativo de ciclo de contratos.

Se reparó el reporte base sobrescrito por el motor anterior. También se aisló
un reporte Studio de entrega de EPP que reemplazaba el cuerpo del diseño global
y rompía impresiones de Nómina/otras aplicaciones. Se conserva su diseño mediante
una plantilla exclusiva para EPP, con respaldo de la vista original.

La política de Demo-SYS limita las aplicaciones visibles a Nómina, sus dependencias
y soporte. No borra datos de aplicaciones instaladas ni sustituye sus permisos
de acceso a los registros.

## Revisión agrícola y reunión del jueves

Desarrollo conserva el flujo nativo de Packing, Productores y Exportaciones.
Packing anterior y prototipos Studio de Cosecha se separan como historial
administrativo, con sus registros preservados. Separar menús no equivale a
migrar completamente todo Studio ni a aprobar el flujo con el cliente.

La corrección del paquete de Nómina incluye, solo donde ya están instalados,
el uso correcto de Luxon en la captura de balanza y la eliminación de imports
incondicionales de pruebas agrícolas. No instala aplicaciones agrícolas en las
bases contables.

El recorrido para aceptación está en [Revisión del jueves](REVISION_CLIENTE_2026-10-08.md).
Incluye Actividades/Task, Cosecha/Harvest, Gestión y Costos, Contabilidad,
costeo/capitalización por OT, liquidación de productores y gastos/IVV de exportación.
Falta aceptación funcional del cliente y homologación con balanzas/impresoras
físicas del flujo agrícola. Gestión y Costos se publicó después en Cerro por
instrucción explícita del usuario, tras comprobar su migración en una copia
actual. Esa publicación no acredita aceptación del flujo agrícola completo.

## Publicación de T50 a T53 en Cerro El Plomo

Publicado y verificado el mismo paquete `6ffa057758a46f24b3e408cb17f77d2514e85ed2`
que Desarrollo: Gestión y Costos `18.0.21.1.0`, selectores a maestros nativos,
centro analítico único y selección de varias empresas. Los catálogos actuales
de Cerro quedaron compartidos con todas las empresas, según la respuesta del
cliente. No se actualizaron a ciegas los módulos antiguos de Exportaciones.

- Compatibilidad actual: `MANAGEMENT_QA_CERRO_r10c`, 305 pruebas sin fallos/errores.
- Respaldo: `/opt/steps_backups/management_cerro_20261006T113045Z`.
- Comprobación efectiva: `MANAGEMENT_REGISTRY_OK` y `MANAGEMENT_VERIFY_OK cerro`.
- Publicados comentarios breves en T50–T53 para confirmar la revisión en Cerro,
  y en T27/T30/T35/T38/T41 para solicitar casos concretos en Desarrollo.
  Los comentarios no cerraron automáticamente ningún ticket.

## Diferencias preexistentes que no se ocultan

- Desarrollo conserva una referencia instalada a `steps_api` sin fuente disponible,
  registrada también en auditorías anteriores. Las APIs vigentes de Task/Harvest
  son otros componentes; esta referencia no acredita un fallo de esas apps.
- Steps conserva `steps_transport` instalado y dos modelos sin cargar. Se localizó
  su fuente original `1.5` en `/opt/odoo18/custom_addons/steps_transport`, fuera del
  `addons_path`. Su manifiesto concede CRUD a todos los usuarios internos y no
  carga reglas multiempresa; no se habilita esa API antigua sin revisar permisos
  y controladores. La recuperación se conserva como pendiente del flujo de
  movilización T46, con los registros intactos; no se inventan modelos para
  silenciar el diagnóstico ni se añade toda la raíz de addons antiguos.
- En Steps, `step_hr` informa versión instalada `18.0.1.1.0` y su fuente compartida
  es `18.0.1.4.0`. Su actualización requiere la migración coordinada de movilización;
  el cambio de Nómina no actualiza ese módulo a ciegas.
- Admin devolvía HTTP 500 antes de la redirección. Queda fuera de promoción;
  redirigir su puerto no certifica sus aplicaciones.
- El cron de detección de ausencias de Desarrollo encuentra una asistencia
  anterior aún abierta. Requiere que el responsable revise ese registro; no
  se inventó una hora de salida ni se modificó su asistencia para cerrar el aviso.

## Conservación del trabajo de otros agentes

El worktree de esta entrega está limpio y publicado. El barrido global detectó
reportes de tickets pendientes en los checkouts anteriores, worktrees con HEAD
separado y ramas antiguas atrasadas. No se cambiaron esas ramas ni sus archivos.
Los reportes y los tres commits locales de documentación de Gestión se respaldaron
en `~/.codex/local-artifacts/ambientes-canonicos/previous-ticket-reports/`; el
bundle de esos commits fue verificado. No contienen una implementación pendiente
que deba reemplazar el paquete actual. El control de Claude ahora exige guardar
los reportes privados de tickets fuera de los checkouts del producto.

## Aislamiento y capacidad del servidor

Los cinco servicios vigentes quedaron fijados a su base exacta mediante
`db_name`, `dbfilter` anclado y `list_db=False`. SYS antes no declaraba una base
única; Steps no tenía filtro HTTP explícito. Se mantuvieron los dominios y los
listeners de redirección existentes. El verificador aprobó los ocho puertos
internos, GET/POST, y los logins HTTPS de los cinco destinos activos.

Se encontró `The Connection Pool Is Full` al iniciar el cliente web de Desarrollo.
Desarrollo y Demo-SYS tenían un límite de seis conexiones: se amplió a dieciséis
después de comprobar la reserva disponible en PostgreSQL. Ambos aprobaron doce
logins concurrentes. La interfaz de Gestión y Costos cargó después con sus menús
ordenados y estilos; las llamadas de inicio dejaron de producir los errores
observados antes del ajuste.

- Respaldo de la fijación de bases:
  `/opt/steps_backups/canonical_ports_20261006T075939Z`.
- Respaldo y prueba de capacidad:
  `/opt/steps_backups/canonical_ports_20261006T080030Z`.
- `canonical_ports.py verify`: `CANONICAL_VERIFY_OK environments=8`.

El proceso de Admin estaba abriendo conexiones a múltiples copias de pruebas
y a SYS. Su cron global quedó deshabilitado (`max_cron_threads=0`); conserva
su configuración y sus definiciones de tareas como referencia legada. No se
cambiaron intervalos de tareas ni se habilitaron correos en Demo-SYS.

Se detuvo de forma gradual el servidor privado antiguo de
`T_SYS_REFRESH_20260929`, puerto local 18091. Ese proceso también mantenía una
conexión a Demo-SYS. Sus argumentos originales quedaron en un respaldo privado;
su base y archivos no fueron eliminados. La revisión posterior no encontró el
servidor antiguo ni conexiones Odoo a esas copias de QA.

La primera espera de cierre agotó veinte segundos; el proceso terminó después
de ese plazo. Se comprobó su ausencia y se repitió la verificación de forma
idempotente, sin forzar la terminación. Resultado final:
`RUNTIME_SCOPE_OK`, respaldo `/opt/steps_backups/runtime_scope_20261006T081216Z`.
Tras estos cambios se repitió `PAYROLL_VERIFY_OK` en los cinco servicios.

Los logs completos, datos de clientes, paquetes privados y respaldos quedan
fuera de Git. Este documento registra el alcance técnico; no sustituye la
aceptación funcional ni declara cerrados los pendientes anteriores.
