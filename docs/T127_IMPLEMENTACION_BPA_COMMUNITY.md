# T127: registro BPA como producto propio

## Arquitectura

`step_product_bpa` es un addon AGPL-3 con dependencias exclusivas `product` y
`mail`, disponibles en Community. Implementa siete campos descriptivos de
registro/autorización y el maestro `step.agriculture.pesticide.aptitude` con
nombre traducible, código, observación HTML, secuencia, archivado e historial.
No evalúa vigencia sanitaria ni inventa concentraciones, fechas o aptitudes.

`step_product_bpa_agriculture` integra el núcleo con los modelos agrícolas
existentes. Reutiliza la sustancia activa y las carencias nativas; reúne los
campos en la pestaña BPA actual, sin sustituir maestros por textos. El núcleo
puede instalarse por separado en Community, sin la aplicación agrícola completa.
Este cambio no retira Enterprise del resto del ERP ni modifica licencias.

## Migración

El publicador `product-bpa` ejecuta el archivo versionado
`step_product_bpa/migrate_schema.py` antes de cargar el registro. Renombra la
tabla y sus columnas en el sitio; convierte los metadatos conservando IDs;
actualiza referencias a modelos, chatter, actividades, adjuntos, acciones,
filtros y rutas de campos. Adopta las identidades externas para evitar que la
retirada futura de Studio elimine el maestro convertido. Conserva el nombre
traducible y los permisos históricos equivalentes de usuarios/administradores.

Retira únicamente las inserciones de T127 de las vistas Studio de producto;
las funcionalidades ajenas permanecen intactas. Los antiguos formularios del
maestro se conservan inactivos y las acciones existentes usan las vistas
versionadas. Un esquema paralelo o una automatización activa no inventariada
bloquean la conversión. La instalación directa ante un maestro manual no
preparado también se rechaza.

En destinos sin maestro previo, crea un maestro nativo vacío. No importa
productos ni clasificaciones de otra empresa. Los datos preexistentes de
Desarrollo se migran, no se distribuyen automáticamente a otros destinos.

## Validación y publicación

Se exige copia fresca de Desarrollo y de cada destino. Las huellas comparan
las columnas originales de productos, documentos, stock, contabilidad, nómina,
historial y adjuntos, normalizando únicamente el cambio de nombre autorizado.
Los flujos de formulario usan un usuario existente sin elevar permisos y se
revierten al terminar. Las pruebas verifican texto, fechas vencidas, relaciones,
archivado, edición interna y rechazo de borrado o acceso público no autorizados.

`tools/ops/test_product_bpa_community.py` instala el núcleo en una base vacía con
rutas que contienen exclusivamente addons Community y el paquete inmutable.
Revisa las pruebas y la ausencia de Studio y Web Enterprise instalados.

Promover el mismo paquete en Desarrollo, Cerro y QA-Cerro con respaldo,
exclusión, guardas de concurrencia y verificación posterior. QA-Cerro mantiene
sus datos y aislamiento; esta entrega no refresca su base.
