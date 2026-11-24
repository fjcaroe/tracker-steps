# Cuartel al crear una jornada en Harvest

T233 se entrega con Harvest 0.0.5, commit
`e14075aaef7a9e71448e087b52bd80e9cebacff0`, y el backend
`3bdbd5bbf62d65e9e005cf34b35757e4b730adda`, módulo
`step_harvest_launcher` 18.0.1.2.1. Los destinos del requerimiento son
Desarrollo, QA-Cerro y Cerro El Plomo.

Para usar el campo:

1. Abrir Harvest y revisar la empresa del selector **Empresa**.
2. En **Configuración**, elegir **Cuartel** en **Nivel de ubicación**.
3. Ir a **OT → Nueva OT** y elegir el centro de costo.
4. Elegir uno de los cuarteles disponibles y crear la jornada local.

La configuración se guarda en el navegador por base, usuario y empresa.
Elegir Cuartel en QA-Cerro o en otra empresa no configura automáticamente
el mismo modo en Cerro. Si el navegador conserva una pantalla anterior a
la publicación, recargar Harvest y comprobar que muestre la versión 0.0.5.

El selector de Cuartel permanece deshabilitado hasta elegir un centro con
cuarteles accesibles. Si el centro no tiene cuarteles, el formulario lo indica.
Al cambiar de centro se borra la elección anterior; no se pueden guardar
cuarteles de otro centro. La jornada local conserva la relación nativa hasta
sincronizarla.

Ante un aviso de actualización faltante, contrastar primero el código efectivo
del backend, la versión y todos los archivos web publicados. Revisar también
el formulario en la empresa y el modo de ubicación indicados. Conservar las
capturas y resultados en los archivos privados de la entrega. Repetir una
publicación sin encontrar diferencias no cambia una pantalla ya abierta.

La revisión de Cerro del 24-11-2026 comprobó el formulario móvil, los cuarteles
filtrados por centro, el reinicio de la selección y el guardado de la jornada
local. Las pruebas de esta revisión no sincronizaron documentos de producción.
