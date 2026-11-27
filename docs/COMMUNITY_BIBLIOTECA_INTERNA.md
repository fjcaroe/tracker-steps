# Biblioteca interna de SyS y Cerro

## Biblioteca histórica interna de SyS

En la copia privada U41L, `step_document_library` 18.0.1.0.4 abre los
registros de `documents.document` y `documents.access` en sus tablas
originales. El menú histórico conserva su identificador y sus grupos. El
formulario permite navegar por carpetas, abrir el archivo o la URL y gestionar
el permiso individual de una cuenta interna. Las visitas previas se conservan
al retirar un permiso. La operación no envía notificaciones.

El programa de captura registra el resultado de la búsqueda original por
usuario y combinación de compañías. El ensayo Community compara los IDs
visibles y sus niveles de lectura y edición, incluyendo archivados. Un segundo
catálogo guarda la huella del marcador que produce Odoo para cada registro.
Su adopción exige que coincidan los originales y todos los IDs y rechaza
conflictos. La repetición en SyS produjo cero escrituras.

| Comprobación en SyS U41L | Resultado |
| --- | ---: |
| Documentos y marcadores originales | 1.430 |
| Permisos individuales preexistentes | 3.955 |
| Usuarios internos originales | 2 |
| Contextos de usuario y compañía, incluido el usuario público | 59 |
| Comparaciones de permiso por registro | 84.370 |
| Objetos restaurados del filestore completo | 2.679 |
| Módulos instalados / Enterprise | 187 / 0 |

Un editor recorrió el menú original y sus carpetas hasta un archivo TXT
histórico restringido. El controlador normal de descargas devolvió los bytes
correspondientes al tamaño y SHA-1 existentes. Tras el permiso de lectura,
el segundo usuario abrió ese mismo archivo y obtuvo el mismo SHA-256. Su
intento de gestionar accesos fue denegado. La repetición de la concesión
conservó la misma fila y su retirada restituyó el alcance anterior. El ensayo
comprobó también el marcador autenticado y la acción de la URL original,
sin visitar su destino. Después del rollback volvieron a coincidir la matriz
de permisos, las huellas y las 859 secuencias.


### Biblioteca interna de Cerro El Plomo

U41L conserva los 48 documentos, los 48 marcadores y las 32 filas de acceso
de la biblioteca nativa. Las identidades y las huellas de los registros
originales coinciden en el control nativo, la semilla Community y la derivada
ensayada. La segunda adopción de marcadores escribió cero filas.

| Comprobación en Cerro U41L | Resultado |
| --- | ---: |
| Usuarios internos originales | 15 |
| Contextos de usuario y compañía, incluido el usuario público | 65 |
| Comparaciones de permiso por registro | 3.120 |
| Objetos del filestore restaurado | 677 |
| Módulos instalados / Enterprise | 148 / 0 |

El usuario original recorrió el menú, carpeta y formulario y descargó un TXT
restringido. El destinatario comprobó el mismo contenido después de la
concesión. La repetición mantuvo la fila del permiso, la revocación restituyó
el acceso anterior y el usuario público recibió la denegación. También se
abrieron el marcador autenticado y la acción que conserva la URL original.
Tras el rollback coincidieron la matriz, las huellas históricas y las 1.247
secuencias.

El directorio de contactos original usa el inverso de los fundos. La derivada
adoptó los proveedores libres de agricultura, directorio y fundos compartidos.
El paquete `d20e40fe40f8e92687978e898ff47f3578bc668f021ee0bd697a843ab3cfc83b`
preservó 53 fundos, 95 asignaciones a compañías, cuatro reglas, quince
permisos y seis identidades originales. La revisión de cierre contrastó las
8.370 restricciones de la semilla, incluidas las tres columnas de la
unicidad histórica de estimaciones. El recibo del flujo se guarda en
`~/.codex/local-artifacts/community-resume-20261125/U30/u41l-cerro-internal-proof.json`.
