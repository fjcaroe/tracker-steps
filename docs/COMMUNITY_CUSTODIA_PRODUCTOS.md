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


## Respaldo de la cohorte SyS convertida U40J

La copia U40J tenía 190 módulos activos, todos con licencia libre. El paquete
conserva el SQL, el filestore, el núcleo de Odoo, sus requisitos de Python y
los archivos de los 190 proveedores que resolvió realmente ese entorno. Se
incluyeron los ocho módulos cuyas fuentes se encontraban fuera de las raíces
privadas del ensayo. El archivo de código contiene 22.235 archivos y ocupa
176.678.599 bytes comprimido.

| Componente sellado | SHA-256 |
| --- | --- |
| SQL de la cohorte | `94db4529d4f3230a96f7df3d628d485878a978f67a826a5cf534037f237eb65e` |
| Objetos referenciados | `3cdbab1b9d6095dbb2e321d93b12d2c209d279bb189c61670d93cf7bef19813b` |
| Núcleo y proveedores | `10d896c4b5eee9d350c429d3be856869683ee644ed3e1b9221903dda460164be` |
| Paquete original U40J | `f9a7be026a550acf3e383f92414ed18161d6336d771184ee0936daeaf81d39e7` |

En seis módulos, U40J declaraba una versión instalada anterior a la de los
archivos que usaba para arrancar. La recuperación conserva las versiones que
había en la captura. La validación de las actualizaciones usa una copia aparte.

| Origen | Módulo | Versión registrada | Versión del manifiesto |
| --- | --- | --- | --- |
| Odoo Community oficial | `hr_timesheet` | 18.0.1.0 | 18.0.1.1 |
| Odoo Community oficial | `project_sms` | 18.0.1.0 | 18.0.1.1 |
| Odoo Community oficial | `l10n_latam_invoice_document` | 18.0.1.0 | 18.0.1.1 |
| Proveedor de la cohorte | `step_hr_previred` | 18.0.3.8.7 | 18.0.3.8.8 |
| Proveedor de la cohorte | `step_hr_previred_simpledigital` | 18.0.2.4.1 | 18.0.2.4.2 |
| Proveedor de la cohorte | `l10n_cl_simpledigital_payroll` | 18.0.1.0.0 | 18.0.1.1.0 |

U41R arrancó dos veces con las carpetas del entorno original ocultas y las
190 fuentes extraídas del paquete. Ambos arranques se ejecutaron en modo de
lectura. Antes y después de cada uno coincidieron las 1.138 tablas, 608.840
filas, 858 secuencias, 12.010 columnas, 5.816 restricciones y 1.996 registros
de propietario y permisos con la captura congelada de U40J. En el intervalo
entre el sello y la prueba, los ensayos paralelos sobre U40J habían avanzado
siete contadores. El recibo conserva ambos valores de esos contadores. La
comparación confirmó que U40J conservaba las mismas filas y permaneció sin
cambios durante los dos arranques.

Una cuenta original con permisos de nómina y ajustes, sin elevar privilegios,
leyó un PDF restringido de 27.070 bytes y doce adjuntos de menú en ambos
arranques. Coincidieron el tamaño y las huellas del PDF. Otro contexto de
compañía de esa misma cuenta y el usuario público recibieron la denegación
del mismo adjunto.

El DDL completo del archivo, del origen y de la restaurada produjo el mismo
SHA-256, `97a572d842a51acc6ba194c46ad3389c18f291973c58e4ed33d53874382dbb10`,
incluidas 26 vistas y 2.484 índices. La copia de custodia de la estación
de trabajo verificó individualmente los 13 componentes del paquete y todos
los archivos de código mediante el manifiesto
`d4c78ebc528648221c158e9968e63137a530a184fe3e5d8422f317a8fa84c1bd`.

El SQL y los 2.679 objetos referenciados del primer respaldo corresponden al
mismo instante. Entre esa captura y el barrido físico posterior se ejecutaron
ensayos con rollback en U40J. El barrido posterior conservó además 11 objetos
sin referencia y 14 marcadores del recolector de Odoo. Los 2.704 archivos de
ese barrido coincidieron byte por byte en la restaurada y fuera del servidor.
El recibo privado está en
`~/.codex/local-artifacts/community-resume-20261125/U41R/converted-cohort/offline-verification.json`.
