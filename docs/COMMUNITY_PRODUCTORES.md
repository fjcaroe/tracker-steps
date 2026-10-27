# Productores e informes en Community

El núcleo agrícola 18.0.1.1.0 adopta ocho campos agrícolas de `res.partner`,
su formulario y la acción de contratistas. Conserva columnas, IDs y XMLIDs
`step_hr.*` como alias, además de los modelos y datos ya extraídos. El total
del contrato explícito de propiedad es 260 identificadores y 189 campos.

`step_producers` 18.0.1.9.0 depende del núcleo y de `hr` Community para el
empleado autorizador. Conserva sus modelos, contratos, cuotas, estimaciones,
tarifas, liquidaciones, contabilidad y permisos. No requiere Nómina Enterprise.

Los informes de contratos y estimaciones 18.0.1.1.0 sustituyen Gantt por el
calendario estándar Community, conservando el XMLID histórico `report_gantt`,
la acción, los menús y los enlaces entre acción y vistas. La premigración
modifica únicamente el modo del enlace original, no lo borra ni lo recrea.
La extensión de modalidad de compra también conserva sus vistas y adapta
sus XPath antes de validar el nuevo padre. Se preservan todas las traducciones
del arch de esas dos vistas propias durante la transición.

La consulta mantiene las mismas vistas SQL y sus IDs derivados de cuotas y
semanas. No se escriben fechas ni importes. Calendario, listado y tabla dinámica
siguen disponibles con las reglas por empresa y los mismos permisos de lectura.
El calendario deshabilita altas, edición, borrado, creación rápida y arrastre
de fechas; la ACL del modelo también rechaza escrituras. La agrupación y las
sumas se consultan en la tabla dinámica. No se ofrece la cuadrícula de recursos
de Gantt Enterprise como si fuera la misma presentación.
Los límites `date_stop` y `week_end` de las proyecciones originales son
exclusivos. Calendar añade un día al fin de un evento Date: por eso utiliza
`calendar_end`, calculado sin almacenar como el límite original menos un día.
Su búsqueda traduce los rangos al campo original. Las pruebas comprueban el
vencimiento de un solo día y semanas de lunes a domingo, sin editar las cuotas.

El contacto Community muestra `contact_address`, el campo nativo de dirección.
El mapa original se conserva como vista opcional de `step_hr`, que declara
`web_map` explícitamente. El núcleo no depende del mapa. El override booleano
legado `res.partner.duplicate_bank_partner_ids` permanece en `step_hr`: no se
cambia su tipo ni su columna en destinos existentes. Una instalación pura usa
la relación calculada nativa de Contabilidad. Antes de retirar `step_hr` se
debe auditar expresamente ese override y preservar sus valores; esta extracción
no autoriza una conversión silenciosa del campo.

## Validación y actualización

`tools/community/validate_agriculture_core.py --profile producers` incluye el
paquete agrícola y cinco consumidores: Productores, ambos informes, modalidad
de compra y centros analíticos de Productores. Usa instalación oficial Community
y copias frescas del destino, con exclusión compartida y sin publicar servicios.
Comprueba las tablas de negocio y las dos proyecciones SQL, históricos,
permisos y metadatos. Solo admite dos cambios de modo `gantt` → `calendar` en
los enlaces identificados de los informes; sus IDs y demás atributos deben
permanecer exactos. Los formularios y consultas se comprueban sin `sudo`.

El instalador adopta la propiedad en bases donde no existe el núcleo. También
hay premigración y postmigración para adoptar el contacto al actualizar un
núcleo 18.0.1.0.0. Los ensayos aceptados y el alcance efectivamente comprobado
de cada ruta se registran en `COMMUNITY_CONTINUACION.md`.

No desinstalar `step_hr`, Enterprise, Studio o DTE como consecuencia de esta
entrega. Tampoco sirve por sí sola para publicar en Desarrollo o QA-Cerro:
cada destino exige copia fresca y paquete idéntico, sin refrescar capacitación.
