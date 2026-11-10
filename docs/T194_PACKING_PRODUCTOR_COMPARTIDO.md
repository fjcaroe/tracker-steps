# T194: validar la recepción de un fundo asignado a otra sucursal

En **Packing → Recepciones → Fruta a proceso**, el fundo podía estar asignado
a la sucursal receptora mientras el contacto del productor pertenecía a otra
sucursal. El lote automático de recepciones intentaba leer ese contacto al
confirmar. Activar las dos sucursales permitía leerlo, pero Inventario seguía
rechazando la relación entre empresas.

La regla de lectura admite el productor de un fundo asignado a una compañía
activa para usuarios de Inventario que ya tengan acceso a la compañía del
contacto. La excepción de compañía de Inventario se aplica al productor
exacto del fundo de la recepción entrante y a las existencias identificadas
por sus tarjas, dentro del mismo grupo de empresas. Se conservan los
controles nativos de escritura de contactos, los demás controles de compañía
y la titularidad de la fruta.

El paquete `agriculture-multicompany` contiene únicamente
`step_agriculture_multicompany` 18.0.1.0.4.

- Commit del paquete: `6ee1b33af06f3449b3f3a0247a26f55fe64fe2d3`.
- SHA-256: `1e3ab05de07d9a240584963952165d00bda46f9d7d51a5ee621b36583ee5c667`.

La prueba del caso reportado en la copia de Cerro abrió el formulario
efectivo con el perfil afectado y solo la sucursal receptora activa. El
botón Validar terminó la recepción. Las dos tarjas C quedaron validadas,
con la misma cantidad recibida y el productor original como propietario.
Las pruebas de regresión también verifican la denegación en transferencias
ordinarias, para fundos sin asignación y para usuarios sin acceso a la
compañía de origen.

Las copias independientes de Desarrollo, Cerro El Plomo y QA-Cerro El Plomo
pasaron 16 pruebas cada una. El verificador comprobó el menú, el formulario
efectivo, la versión y el origen del código. El 10-11-2026 se publicó el
mismo paquete en los tres ambientes, con respaldo por destino, bloqueo
compartido y rutas privadas de addons. El control de publicación comprobó
la conservación de los registros comerciales, y el verificador de paridad
confirmó el mismo código efectivo en Cerro y QA-Cerro.

En Cerro activo, el usuario afectado pudo leer el contacto y el formulario
de la recepción pasó el control de compañía. La recepción original quedó
en borrador. QA-Cerro conservó su base de capacitación.
