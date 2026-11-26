# Restauraciones privadas de los tres productos Odoo

El 26 de noviembre de 2026 se restauraron tres respaldos SQL nativos y todos los
objetos referenciados por sus adjuntos. Cada copia conserva su propio filestore,
su propietario SQL y el rol original de la prueba. Los ensayos usaron el bloqueo
compartido y arrancaron Odoo con red aislada, sin HTTP ni cron. Se verificaron
también los respaldos fuera del servidor, mediante el SHA-256 de ambos archivos
y el tamaño y SHA-1 de cada objeto. Las cifras de Enterprise corresponden a los
módulos instalados en cada referencia nativa restaurada.

| Producto | Enterprise / instalados | Filas de adjuntos | Referencias a archivo | Objetos verificados | Prueba ORM |
| --- | ---: | ---: | ---: | ---: | --- |
| SyS | 142 / 336 | 5.440 | 5.186 | 2.678 | UID2 leyó cinco PDF de nómina, un TXT y un CSV recuperados. |
| Steps | 123 / 310 | 2.430 | 2.068 | 1.744 | UID2 leyó tres adjuntos de tickets y nueve de vistas. |
| Cerro El Plomo | 140 / 414 | 1.261 | 1.009 | 676 | UID7 leyó doce adjuntos de vistas. |

En SyS se recuperaron nueve objetos ausentes. Los cinco PDF proceden del
respaldo de nómina del 2 de septiembre de 2026. El índice SQL conservaba las
líneas imprimibles del TXT y del CSV. Los separadores y caracteres recuperados
se verificaron con los tamaños y hashes originales. Para los dos SVG de
contactos, el generador oficial de Odoo produjo los bytes originales usando el
nombre y la fecha de creación de cada maestro. Las filas y permisos originales
se conservaron. Los nueve objetos se incorporaron al respaldo privado.

| Producto | SHA-256 del respaldo SQL | SHA-256 del filestore |
| --- | --- | --- |
| SyS | `669f58d3eb1f5240bcd248b2f2a905d52b76752274dfc5396d14b5ad118c17f0` | `43addeaac97d59cf02125bd33d7a5de8603bdd509cda1ee1b2e7a066a2c0252e` |
| Steps | `8247457c4469d314fb3eeb44202604a1c294cfa374d426f30f31c9a16144f7ca` | `b12ea5063cf2a1ef2db7e85bb66ee19dcf842ca39ce087524e5d43113da58bed` |
| Cerro El Plomo | `1d8c636dba84fbc851368fa3fd4d7785c32fbc88efc6d19652557c1aa4e0310c` | `b2e8884bb67a26d37c742f740ed061328dcdefab901f184d0f205fb424175efe` |

La copia privada de SyS usa el respaldo U33. La de Cerro reutiliza el respaldo
U40D. Steps usa un respaldo nuevo. Los recibos y las copias verificadas fuera
del servidor están en
`~/.codex/local-artifacts/community-resume-20261125/U30/u40-offhost`.
`tools/community/restore_native_product_backup.py` reproduce las pruebas
nativas de Steps y Cerro. El primer intento con un directorio de addons vacío
terminó antes de cargar Odoo. Las pruebas finales U40Q usaron un overlay
privado con el mismo proveedor `base` del runtime y los mismos respaldos SQL.

Steps omitió `steps_transport` al arrancar con sus rutas configuradas.
Su fuente candidata sigue fuera de esas rutas. La recuperación de los datos
de los tres productos deja pendientes sus pruebas funcionales de conversión
a Community y la restauración integral con cero Enterprise.
