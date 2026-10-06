T35: navegación de Exportaciones e instructivo de embarque
=========================================================

Alcance solicitado
------------------

Se leyó el mensaje humano del 04-10-2026 y su imagen de menú. El puerto
8075 corresponde a Desarrollo, LAB_TAREAS, https://desarrollo.stepsapp.cl,
odoo18-dev.service y /etc/dev_odoo18.conf. La falta de un perfil API distinto
no implica falta de acceso: se verificó el servicio y su código por SSH.

La navegación superior conserva el orden de la imagen:

* Inicio.
* Planificación: programas de ventas, embalajes, estimación, forecast e historial.
* Embarque: exportación, notas/proformas, facturas, packing lists, informe,
  instructivo, despacho y reservas.
* Recibidor: cuenta corriente, pagos, liquidaciones, reclamos y trazabilidad.
* Gastos exportación: gastos contables por embarque y gastos exteriores por concepto.
* Maestros: clientes, contactos, productos, tarifa, materiales y tipos de pallet.
* Configuraciones: parámetros contables, Fruta, Exportaciones y Packing.

Los maestros abren los registros existentes, incluidos los catálogos de calibre
y categoría efectivamente usados en la carga. No se crean tablas de maestros.
Las consultas comerciales se acotan a recibidores/programas de exportación;
la cuenta corriente presenta todos los saldos abiertos agrupados por recibidor,
con el filtro de vencidas disponible.

Instructivo y conservación
-------------------------

El acceso al instructivo abre step.export.export en estados draft/validated,
el mismo documento que valida carga, registra despacho y confirma embarque.
Elegir programa completa sus relaciones a recibidor, temporada y especie.
El formulario presenta programa/carga y transporte/fechas en dos columnas;
participantes, carga, tarjas/despachos, documentos y notas tienen pestañas.
Las columnas secundarias de carga son opcionales; kilos, cajas, estado y
producto tienen encabezados en español.

La antigua ficha step.export.shipping.instruction y las fichas vacías de
despacho/reserva se conservan para consulta técnica. El menú comercial utiliza
el flujo de embarque y las reservas nativas de transferencias de inventario.
No se afirma que las fichas históricas vacías hayan reservado stock.
Etiquetas y etapas quedan en Archivo técnico, restringido a base.group_no_one
y ausente de la navegación normal; sus registros y XML IDs se conservan.

Paquete y procedimiento
----------------------

Paquete final: commit ecc58f3cbc6f1f3762f9d4c9a3e33e642af91098,
step_export 18.0.2.9.1, SHA-256
0c48bd70199c99b3b2e4abcfbdcdff5b63ceb425f6d78bc9b399645575313555.
Integrado con los avances concurrentes de T27 en la rama canónica
codex/ambientes-canonicos-reparacion; rama propia codex/t35-menus-desarrollo.

El constructor y gestor de releases admiten --kind export, sin instalar
otros módulos. El gestor usa una copia fresca de Desarrollo, desactiva correo
y cron, comprueba versiones, vistas y dominios, y compara filas/importes de
tablas de Exportaciones y contabilidad, incluidas relaciones sin columna id.
Publica el paquete exacto probado en overlay privado, con respaldo, comprobación
de concurrencia y bloqueo /run/lock/steps-environments.lock.

Las evidencias privadas y capturas quedan fuera del repositorio, en
~/.codex/local-artifacts/t35-menus. No se publican datos del cliente ni credenciales.

Validación del paquete final
---------------------------

* Copia fresca MANAGEMENT_QA_DEVELOPMENT_t35menus06d: 17 pruebas,
  0 fallas y 0 errores. Incluye validación de instructivo, barreras de documentos,
  programa, embalajes, forecast, reclamos, contabilidad de recibidor/productor,
  consolidados de temporada, navegación y relaciones de maestros.
* Todas las acciones comerciales: dominio consultable, vistas list/form válidas,
  jerarquía superior exacta y ausencia de etiquetas/etapas en el menú comercial.
* Registros, relaciones e importes de Exportaciones y contabilidad idénticos
  antes y después de actualizar la copia.
* Respaldo final de Desarrollo:
  /opt/steps_backups/management_development_20261006T133814Z.
* Overlay final:
  /opt/steps-managed/releases/development/ecc58f3cbc6f1f3762f9d4c9a3e33e642af91098.
* Desarrollo: versión instalada 18.0.2.9.1, origen del módulo en el overlay final,
  servicio activo, acciones y formularios comprobados después de publicar.
  La sesión web autenticada muestra los siete menús en el orden solicitado,
  Configuraciones sin etiquetas/etapas duplicadas y el instructivo real existente
  con programa, carga, nave, fechas y estado. Se verificó la distribución final
  en dos columnas y sus pestañas; no se alteró el embarque existente.

No se modificaron producciones ni entornos legados. La aceptación del cliente
permanece pendiente; este cambio no cierra el ticket ni da por aceptadas todas
las especificaciones funcionales de Exportaciones.
