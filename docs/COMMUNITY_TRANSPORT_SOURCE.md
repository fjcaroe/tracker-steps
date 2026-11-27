# Fuente histórica Steps Transport localizada

## Transporte y lista de precios en la copia Community de Steps

El 26 de noviembre de 2026 se restauraron el SQL y los 1.744 objetos del
respaldo de Steps en la derivada U42T2. Se habilitó una cohorte de 21 módulos
del inventario original de 310. Se usaron el runtime oficial Community y la
fuente privada original de Transporte enlazada en su ubicación verificada.
Los 21 módulos figuraban instalados y ninguno tenía licencia Enterprise.

El usuario interno 7 abrió el formulario de once campos, seleccionó una
lista de precios existente y se comprobó su clave foránea a
`product.pricelist`. Creó una ruta con el correlativo original, registró la
subida y la bajada de un trabajador existente, cambió el sentido de la ruta
y comprobó el borrado en cascada de su línea. Se revirtió el ensayo y se
verificaron las filas originales, las dos listas de acceso, los 41
identificadores y los 804 contadores. El catálogo original tenía dos listas
de precios activas y carecía de vehículos para probar su selección.

El primer arranque con 20 módulos encontró una regla de visibilidad que usa
`fleet.vehicle.driver_employee_id`. La última prueba cargó su proveedor libre
original `hr_fleet` y mantuvo las cinco reglas de visibilidad que lo usan.
Las herramientas `prepare_steps_transport_cohort.py` y
`probe_restored_transport.py` delimitan la copia y prueban el flujo. La
conversión de los otros 289 módulos de Steps, los consumidores web de
Transporte y los derechos de redistribución de su fuente siguen pendientes.

## Ensayo nativo en copia privada del 26 de noviembre

U40T arrancó la fuente histórica mediante un enlace exclusivo de la derivada
de Steps, con HTTP y cron deshabilitados y la red aislada. Se verificaron los
ocho archivos antes y después. La versión instalada 18.0.1.5 corresponde al
manifiesto 1.5. Coincidieron los 41 XML IDs de octubre y los 21 campos
declarados, incluidos tipo, almacenamiento, obligatoriedad, edición,
relaciones y campo inverso. El control U40Q conservó sus rutas de addons.

El usuario interno 7, sin administración del sistema, abrió el formulario
generado de once campos y creó una ruta con el correlativo original. Seleccionó
un empleado existente, registró subida y bajada, cambió la operación de
entrada a salida y comprobó el borrado en cascada de la línea. La fuente
contiene cero rutas, líneas y vehículos de negocio y carece de vistas,
acciones y menús de transporte propios. La prueba se revirtió. En la
derivada, los tres contadores que avanzaron durante el ensayo recuperaron
su valor y estado previos. Se compararon los 804 contadores de la base,
las filas de negocio, las dos ACL, los campos y los XML IDs.

El recibo privado `u40t-transport-proof.json` tiene SHA-256
`70162ddf0b28bfd60781bf5301f117ec1bcc1e6a9ba2322128b15f1d614fb8f9`.
La firma de los archivos originales es
`cb56a2012adffbed0f99a5bb9613ac955f8cad1b06888e7c97e417278a83be64`.
El registro de precios requiere `product.pricelist`. La clausura de los tres
módulos declarados por el manifiesto comprende 17 módulos de Community
oficial y carece del proveedor `product`. Steps ya tiene ese proveedor
instalado. Debe probarse la selección de una tarifa y su relación en el
producto convertido. Sigue pendiente acreditar la procedencia y licencia
para redistribución y certificar los consumidores HTTP. El ensayo nativo
usó la fuente privada en su ubicación original.

Auditoría de solo lectura durante el bloque Community del 29-10-2026.
No se habilita ni se publica este módulo; no se crean modelos sustitutos.

La fuente `steps_transport` versión `1.5` existe en
`/opt/odoo18/custom_addons/steps_transport`, fuera del `addons_path` de Steps.
La ubicación ya figuraba en `ENTREGA_ORDENAMIENTO_AMBIENTES_2026-10-06.md`,
commit `38af2984`. La búsqueda en todas las referencias Git locales disponibles
no halló historia del directorio del módulo. La carpeta del servidor no pertenece
a un repositorio Git. No se copió su código al repositorio público ni se leyó
contenido de registros de negocio.

## Correspondencia con metadata conservada

La base Steps `karo_consultorias` conserva instalado `18.0.1.5`. Los dos modelos
declarados por la fuente son `steps.transport.route` y `steps.transport.route.line`.
Los 21 campos declarados coinciden por nombre con los de la base, que conserva
33 campos al incluir los automáticos; se inventariaron 41 XML IDs. Esto identifica
una candidata recuperable compatible por metadata, no certifica todavía cada
método, constraint, relación, secuencia o flujo contra la instalación histórica.

El manifiesto declara `base`, `hr` y `fleet`. Solo carga dos entradas de datos:
ACL y secuencia. Ambas ACL conceden CRUD a `base.group_user`; la base no tiene
reglas de registro para esos modelos. Hay 21 rutas HTTP/JSON: ocho `auth=public`
y trece `auth=user`. El conteo AST detecta 32 llamadas `sudo`, cinco `create`
y una `write`. Estos conteos son señales para una revisión concreta de cada
ruta; por sí solos no prueban una vulnerabilidad ni autorizan activar la API.

El manifiesto omite licencia, autor y sitio. Los valores `LGPL-3`/`Odoo S.A.` en
metadata instalada pueden proceder de defaults y no acreditan autoría/licencia.
La procedencia legal y la recuperación versionada de la fuente siguen como puerta
explícita. No se leyó ni copió código OEEL; tampoco se importó o ejecutó el addon.

## Evidencia y siguiente puerta

Evidencia privada local bajo
`C:/Users/tito4/.codex/local-artifacts/community-caf-core-20261029/`:
`transport-source-metadata.json`, `transport-native-schema.json` y el resultado
reproducible `transport-source-inventory.json`. Incluye hashes SHA256 de los ocho
archivos de fuente, campos, modelos, rutas y ACL; no incluye cuerpos de funciones,
credenciales, recorridos, personas ni datos de vehículos. La auditoría SQL usó
una transacción REPEATABLE READ READ ONLY y conservó los IDs existentes.

`tools/community/transport_source_inventory.py` reproduce la inspección estática
en la ruta explícita, sin importar módulos ni activar controladores. Exige salida
privada fuera del código y rechaza escaneo de cuerpos con licencia OEEL declarada.

Antes de habilitar una candidata: confirmar propietario y licencia; preservar
fuentes legítimas en su repositorio autorizado; comparar tipos/relaciones/IDs,
constraint y secuencia originales; auditar autorización, empresa y alcance de
cada ruta pública/sudo; probar roles, formularios y flujos en copia aislada de
Steps con el paquete exacto. No añadir toda la raíz antigua al `addons_path`.
La conversión de Steps conserva este frente pendiente aunque la fuente ya esté
localizada; no se silencia el diagnóstico con stubs o desinstalaciones.
