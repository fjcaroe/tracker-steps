# T49 Hectáreas con dos decimales

El ticket 49 y su adjunto solicitan ingresar valores como `1,14` en
`account.analytic.account.has_cost` y `step.cuartel.line.has_cuartel`.
La entrega del 5 de octubre de 2026 convierte ambos campos a
`fields.Float(digits=(16, 2))` y adapta el relacionado `agri_hectares` del
puente agrícola de Gestión y Costos.

La propuesta anterior `acbab93` usaba cuatro decimales y extendía la modificación
a fundo y cosecha. La entrega conserva dos decimales y limita el cambio a los
campos pedidos y su relacionado. Los campos de fundo y cosecha mantienen su
definición anterior.

## Despliegue comprobado

| Instancia | Base | Centros preservados | Cuarteles preservados | Resultado |
|---|---|---:|---:|---|
| Desarrollo | LAB_TAREAS | 35 | 16 | Migración y prueba ORM correctas |
| Principal | karo_consultorias | 7 | 0 | Migración y prueba ORM correctas |
| Demo | STEPS_DEMO | 85 | 16 | Migración y prueba ORM correctas |
| Demo-SyS | STEPS_DEMO_SYS | 105 | 0 | Migración y prueba ORM correctas |
| Cerro El Plomo | CERRO_EL_PLOMO | 4 | 15 | Migración y prueba ORM correctas |

Se compararon todos los IDs y valores originales, incluidos NULL, dentro de la
transacción de conversión a `numeric`. No se recargaron vistas, datos XML ni
otros componentes del módulo de nómina. Se actualizaron los metadatos de tipo
de los campos y se reiniciaron los servicios correspondientes.

Las pruebas en Odoo comprobaron tipo float, precisión `(16, 2)`, persistencia
tras flush e invalidación de caché, y valores `1.14`, `0.27`, `0`, `3` y `12.99`.
Se probó el relacionado de Gestión y Costos donde está instalado. Las escrituras
de prueba se revirtieron con rollback. Las cinco páginas de acceso respondieron
HTTP 200 y los ocho servicios Odoo inventariados quedaron activos.

SyS y Everfruit no tienen instalado `step_hr`; no se instaló el módulo por este
ticket. Admin no tiene una base fija: se investigaron `steps_dev` y `steps_qa`
como candidatas, pero `steps_dev` conserva `has_cost` en el antiguo modelo
`step.centro.costo`, no en `account.analytic.account`. El intento de migración
se revirtió al faltar esa columna. Se restauraron exactamente los dos archivos
de Admin desde el respaldo y no se confirmó ninguna escritura en esas bases.
Las copias históricas y bases de pruebas quedan fuera de esta promoción.

La comprobación HTTP adicional detectó un error 500 en el selector de bases de
Admin por permisos de lectura sobre `ir_module_module`. El mismo traceback está
registrado a las 12:11 UTC, antes del primer cambio de esta entrega (13:41 UTC).
Es una incidencia previa e independiente de T49; no se ampliaron permisos de
base de datos para resolver este ticket. SyS y Everfruit respondieron HTTP 200.

## Respaldo y evidencia del servidor

Respaldos completos de base y archivos anteriores bajo `/opt/steps_backups/`:

- `t49_development_20261005T134130Z`
- `t49_demo_20261005T134254Z`
- `t49_demo-sys_20261005T134317Z`
- `t49_cerro_20261005T134346Z`
- `t49_admin_20261005T134407Z` (intento revertido y código restaurado)

Cada promoción exitosa conserva los logs de verificación y
`deployed-sha256.json` con las sumas de los archivos resultantes. Los dumps,
logs y adjuntos privados permanecen fuera del repositorio.

## Herramientas y futuras promociones

`tools/ticket49/inventory.py` consulta rutas efectivas, instalación y columnas.
`deploy.py GRUPO` muestra el diff sin escribir; `--apply` respalda, detiene,
migra, aplica solo las declaraciones afectadas y verifica antes de terminar.
Los grupos son `development`, `demo`, `demo-sys` y `cerro`. Desarrollo y la
base principal se coordinan porque comparten el mismo directorio de addons.
En Cerro El Plomo se modifica `steps_addons/step_hr`, que tiene precedencia
sobre la copia de `odoo_agriculture`.

Ejecutar los scripts desde un directorio de entrega propio en el servidor,
con `verify_odoo.py` junto a `deploy.py`. El preflight rechaza esquemas antiguos
antes de parar servicios. No reutilizar esta migración para bases con otro modelo
ni sustituir directorios completos de addons: contienen cambios de otros tickets.

`restore_admin.py` documenta la recuperación limitada a los archivos del intento
de Admin; comprueba el contenido para no sobrescribir cambios concurrentes.
