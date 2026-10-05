# T50 Selección de maestros en estimaciones de cosecha

El ticket solicita seleccionar Temporada, Especie y Variedad desde los modelos
`step.temporada`, `step.especie` y `step.variedad` de Steps. La respuesta del
cliente identifica esos modelos y autoriza actualizar Desarrollo y Cerro El
Plomo. Los tres maestros están instalados en ambas bases.

La corrección pertenece a `step_management_costs_agriculture`, el puente que ya
depende de Gestión y Costos y `step_hr`. Agrega relaciones `season_id`,
`species_id` y `variety_id`, con filtro por empresa y variedad por especie.
La temporada de la versión se copia al seleccionar una versión de estimación.
Al cambiar la especie se limpia una variedad que deja de corresponder.

Los campos de texto del núcleo se conservan como snapshots compatibles con
estimaciones, revisiones, importaciones y planes de cosecha. Seleccionar un
maestro guarda su nombre en ese snapshot. Renombrar el maestro no cambia
estimaciones existentes. Las relaciones nuevas también quedan protegidas al
validar la estimación. El núcleo sigue funcionando sin instalar el puente.

La actualización enlaza textos anteriores únicamente cuando coinciden con un
nombre o código único de la misma empresa. No crea maestros, no adivina
coincidencias ambiguas y no modifica textos ni snapshots históricos. Aunque el
cliente indicó que no tenía datos reales, el inventario encontró una estimación
guardada en Cerro El Plomo: se preserva con este criterio.

## Validación y promoción

Estado: implementación registrada; pruebas y despliegue en curso.

Las pruebas se ejecutan en copias de las bases de cada ambiente con el código
real instalado y una superposición de los archivos del puente afectados por
T50. Se incluyen formularios, persistencia de relaciones y textos, cambios de
especie, controles de empresa, importaciones por nombre/código, ambigüedad,
inmutabilidad y migración idempotente.

`tools/ticket50/manage.py qa AMBIENTE --release PAQUETE --commit SHA --run-id ID`
crea el ambiente de prueba, actualiza el puente y ejecuta los tests.
`deploy` con los mismos argumentos exige una prueba aprobada del mismo paquete,
comprueba que nadie haya cambiado los archivos de destino, respalda la base y
el puente, detiene su servicio, actualiza únicamente el puente y verifica el
formulario real mediante Odoo antes de terminar.

Los ambientes admitidos son `development` y `cerro`. Los archivos de
`step_management_costs` y `step_hr` del servidor se conservan, incluidos cambios
de otros tickets y la corrección T49. Las pruebas, dumps, logs y sumas de los
archivos desplegados quedan en `/opt/steps-validation/` y `/opt/steps_backups/`,
fuera del repositorio. `verify_odoo.py` revierte todas las escrituras de prueba.
