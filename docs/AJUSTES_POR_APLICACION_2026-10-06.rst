Ajustes por aplicación — reparación del 06-10-2026
=================================================

En Desarrollo / LAB_TAREAS se reprodujo que Fletes y Maquinaria abren el
formulario de Tesorería con Tope por lote y Aprobador de tope. La vista primaria
``step_account_treasury_batch.view_treasury_batch_approval_settings_form`` tenía
prioridad 16, igual que la vista base. Odoo ordena las vistas por prioridad,
nombre e ID: el nombre del formulario específico precede al de la vista común.
Las acciones sin una vista explícita seleccionaban ese formulario y perdían
el componente que interpreta la sección solicitada en el contexto.

Se establece prioridad 99 para el diálogo específico. Su acción conserva su
referencia explícita y su destino modal; los valores de aprobación permanecen.
No se cambian permisos ni se agrega código en Studio. La opción de Guías de
despacho apuntaba a Ajustes de Inventario: ahora usa una acción propia, vista
base explícita y contexto de Guías de despacho.

Preservación del código vigente
------------------------------

Tesorería estaba instalada en 18.0.1.4.0, mientras la base canónica contenía
18.0.1.2.0. Se recuperó su origen versionado del commit ``52789ba`` de
``origin/ticket/28-bancoestado-aprobacion`` y se preservaron las correcciones
adicionales efectivamente instaladas: comparación del monto absoluto saliente,
su mensaje y las pruebas de cuentas bancarias agregadas después del pago.
La reconciliación previa ``c70504f`` coincide byte a byte con el código efectivo
normalizado: SHA-256 del árbol
``7bde3ff5d4469b179c28fda76d8f9b8a80b32e2c54b53fb9afe96f97613e03d6``.
Esta entrega no distribuye una versión anterior del módulo ni sustituye
las mejoras existentes de aprobación/exportación.

Paquete y comprobación
---------------------

Paquete Git ``8143711cc8346050e6010f64ff5419849064553e``; SHA-256
``b5ab4cd4c31a63d94fd997fade3351188d5569f0aa5a931cb4f920dc87b7466f``.
Incluye únicamente Tesorería por lotes 18.0.1.4.1 y Guías 18.0.2.0.4.
Los módulos de Fletes y las otras aplicaciones mantienen su código.

La copia fresca ``MANAGEMENT_QA_DEVELOPMENT_settings_1006b`` ejecutó 49 pruebas
sin fallos ni errores. La prueba nueva verifica la elección de la vista común
y que el diálogo de aprobación siga usando su vista específica.
La prueba de Guías comprueba su menú tras cargar todos los XML, su contexto
y la presencia de Proveedor DTE en su sección. El primer ensayo detectó que
el XML del menú se cargaba después del de la acción y sobrescribía el destino;
se corrigió en la definición original y se repitió en una copia fresca.
El sondeo ``verify_settings_navigation.py`` comprueba las acciones de todos
los menús activos de ``res.config.settings``, su componente de Ajustes y que
la sección solicitada exista en la arquitectura efectiva. No lee valores
de contraseñas ni guarda configuraciones. Pasaron los 27 accesos activos,
incluidos Fletes, Maquinaria, Guías, Contabilidad, Inventario, Nómina,
Actividades, Movilización, Tracker y Ayuda Steps. El diálogo de aprobación de
lotes conserva su vista específica. La comparación completa de datos pasó.

El publicador exige los dos módulos previamente instalados, rechaza downgrade,
comprueba cambios concurrentes de código y versiones del resto de módulos
Steps y usa el bloqueo común. Compara filas y columnas de tablas operativas,
contables, empresas, contactos y parámetros; solo excluye ``web.base.url`` de
la comparación porque se cambia al servidor local de la copia de pruebas.
Los adjuntos, capturas y paquetes quedan fuera del checkout, bajo
``~/.codex/local-artifacts/settings-navigation``.

Publicación y prueba visual
--------------------------

Se publicó el paquete exacto en Desarrollo con respaldo
``/opt/steps_backups/management_development_20261006T165052Z`` y overlay
``/opt/steps-managed/releases/development/8143711cc8346050e6010f64ff5419849064553e``.
La comparación posterior de registros y parámetros pasó y se repitió el sondeo
de los 27 accesos en LAB_TAREAS. Los logs y el certificado están en
``/opt/steps-validation/management_development_settings_1006b``; la evidencia QA
se descargó al directorio privado local.

En el navegador se comprobaron los accesos desde los menús reales, sin
seleccionar manualmente una sección de la barra lateral: Maquinaria muestra
Configuración Contable Maquinaria / Diario Maquinaria; Fletes muestra
Contabilización de fletes / Diario de provisión; Guías muestra Documento de
despacho / Proveedor DTE; Contabilidad muestra Localización fiscal, Impuestos
y sus otras opciones. Aprobación de lotes abre el diálogo específico de
Tesorería, que se cerró sin guardar ni modificar sus valores.
Capturas: ``ajustes-fletes-verificado.png``, ``ajustes-maquinaria-verificado.png``
y ``ajustes-guias-verificado.png``. No se publicaron estos cambios en producción
ni se modificó la etapa de tickets.
