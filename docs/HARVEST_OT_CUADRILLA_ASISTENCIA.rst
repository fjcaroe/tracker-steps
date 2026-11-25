Harvest: cierre de OT, cuadrillas y asistencia
===========================================

Estas acciones corresponden a Harvest 0.0.8. Abra Harvest desde Odoo con
la empresa de la operación seleccionada. La versión aparece junto al nombre
de la empresa; cierre y vuelva a abrir la aplicación para cargar una actualización.
Los pendientes permanecen guardados para el mismo usuario y empresa.

Cerrar, revisar y enviar una OT
------------------------------

1. En Registrar, cierre las tarjas abiertas de la OT.
2. Use Sincronizar hasta que todas sus entregas estén recibidas en Odoo.
3. Abra Jornadas y pulse Cerrar OT en la jornada correspondiente.
4. Revise sus entregas y pulse Marcar revisada.
5. Pulse Enviar OT. El estado cambia cuando Odoo confirma las entregas.

Ver OT en Cosecha (Odoo) permite consultar el registro exacto, incluso si otras OT
comparten la misma referencia visible. Una OT cerrada conserva sus entregas y
rechaza entregas nuevas. Un reintento recupera la confirmación de lo ya recibido.
Estos estados móviles conservan el circuito de aprobación, costeo y contabilidad
de la OT en el ERP. Las acciones requieren el permiso de escritura existente.

Enrolar trabajadores
-------------------

En Cuadrilla, seleccione una cuadrilla existente. Su tipo propio o contratista
y el contratista asociado proceden del maestro. Complete Nombre, NIP, Sexo y
Cargo. El NIP admite hasta ocho dígitos. El enrolamiento crea trabajadores
nuevos y los agrega a la lista existente de la cuadrilla. Las incorporaciones
de empleados que ya están en el maestro se administran en la cuadrilla de Odoo.
Seleccionar trabajador en la app habilita su captura local de entregas.

Guardar enrolamiento en este equipo conserva el alta pendiente. Sincronizar
cuadrilla y asistencia crea el empleado nativo y lo incorpora a esa cuadrilla.
El cargo se elige del maestro; Cosechero es la propuesta inicial. La preparación
de la empresa configura ese cargo nativo y el enrolamiento reutiliza su registro
con los permisos actuales del operador. Al preparar otra empresa, un encargado
de los maestros debe comprobar que el cargo esté disponible. La entrega conserva
los cargos, empleados y permisos anteriores.

Registrar asistencia
--------------------

Seleccione fecha, entrada y salida generales. Ajuste las horas individuales y
quite la marca Presente a quienes no asistieron. Aplicar horario a todos vuelve
a proponer las horas generales. Guarde la asistencia en el equipo y sincronice.
Los enrolamientos se reciben antes que las asistencias y las entregas pendientes.

Odoo calcula las horas trabajadas con el calendario del empleado, incluida la
colación configurada. La entrada y la salida conservan las horas registradas;
el total nativo puede descontar ese descanso.

Inicio muestra los presentes de todos los cargos de la cuadrilla de la OT
seleccionada. En Odoo, consulte o corrija las horas desde Cosecha → Cosecha propia
→ Asistencia o Cosecha → Contratistas → Asistencia. Ambos accesos usan la
asistencia nativa y los permisos existentes de Asistencias.

Revise cualquier rechazo antes de repetir la operación. Las entregas y altas
pendientes conservan su identificador para que un reintento no duplique registros.
