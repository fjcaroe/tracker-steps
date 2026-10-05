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

Pruebas: 18 casos aprobados, sin fallos ni errores de prueba, en una copia de
Desarrollo y otros 18 en una copia de Cerro El Plomo. Despliegue completado y
verificado el 5 de octubre de 2026.

| Ambiente | Base | Puente agrícola | Resultado |
|---|---|---|---|
| Desarrollo | LAB_TAREAS | 18.0.1.1.0 | Formulario, onchanges y guardado verificados; HTTP 200 |
| Cerro El Plomo | CERRO_EL_PLOMO | 18.0.1.1.0 | Formulario, onchanges y guardado verificados; HTTP 200 |

Los archivos del producto corresponden al commit `24f9620`. Las sumas SHA-256
del paquete probado y los siete archivos promovidos fueron comprobadas contra
los archivos instalados. Los servicios respectivos quedaron activos.
Las escrituras de verificación se revirtieron: no se agregaron estimaciones,
versiones ni unidades de prueba permanentes.

La migración enlazó cinco versiones de Desarrollo. En Cerro El Plomo los textos
anteriores no tuvieron coincidencia exacta con un maestro: se conservaron, sin
enlaces inventados. Las nuevas selecciones funcionan y la versión existente
puede configurarse seleccionando su temporada desde el maestro.

Respaldos previos completos:

- `/opt/steps_backups/t50_development_20261005T161659Z/`
- `/opt/steps_backups/t50_cerro_20261005T162104Z/`

Logs y manifiestos `deployment_verified.json`:

- `/opt/steps-validation/t50_development_20261005_catalogs/`
- `/opt/steps-validation/t50_cerro_20261005_catalogs/`

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

La carga del registro de Desarrollo informa la ausencia previa de `steps_api`.
Se reproduce en la copia antes de la promoción y no afecta las 18 pruebas.
Además, Packing importa su conjunto de pruebas al cargar el módulo, lo que Odoo
registra como error de importación del framework cuando no está en modo de
prueba. El stack identifica `step_inventory_packing/__init__.py`; no procede
del código de T50. El control admite esos mensajes conocidos concretos y
rechaza otros errores. El primer control de promoción de Desarrollo rechazó
ese diagnóstico de Packing aunque el módulo terminó de actualizarse; luego
se revisó el stack y se verificó la instalación y el formulario real.
No se instalaron ni modificaron esos addons por T50.
