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

Candidato versionado `2dc161f26c6d549a00c474bf81e8c3f83e984092`,
SHA-256 `10f8e05ffdaba7351e4dcfa2130c6f5cb2bf14eb452d0352f6a29637c0950646`.
El proveedor Simple Digital se copia privadamente desde el servidor; su hash
queda vinculado a la validación y se exige idéntico antes de publicar.

La transición archiva los registros del motor anterior, conserva identificadores
y detalle de liquidaciones/asientos y guarda PDFs originales de las liquidaciones
cerradas. Desinstala el motor y sus extensiones conocidas, bloquea su reinstalación
y el cálculo con estructuras antiguas. Los contratos migrados o incompletos
exigen revisión explícita por un responsable antes de calcular nuevas liquidaciones.
No se recalculan liquidaciones pagadas ni se contabilizan operaciones reales.

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
físicas. El paquete agrícola y la nueva Gestión de Cerro no se promocionan a
producción como si ya tuvieran esa aceptación.

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

Los logs completos, datos de clientes, paquetes privados y respaldos quedan
fuera de Git. Este documento registra el alcance técnico; no sustituye la
aceptación funcional ni declara cerrados los pendientes anteriores.
