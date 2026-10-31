# I9 — Servicios y nómina de pasajeros

Arquitectura confirmada por Fernando en este chat el 31-10-2026: servicios y
pasajeros viven en PostgreSQL de Tracker, con sincronización hacia Odoo.
Se conserva el origen Tracker y no se reactiva el sistema Redis antiguo.

## Alcance de esta iteración

I9 entrega el modelo, migración aditiva, API, contrato de sincronización y la
consulta «Mi servicio» en Hoy. La aceptación crea un servicio con paradas y tres
pasajeros y comprueba su consulta por el conductor asignado. Abordajes, descenso,
QR, eventos sin señal, avance y cierre del servicio pertenecen a I10/I11.
El importador periódico de Odoo no se instala en esta iteración: aquí se define
su contrato, como establece el plan. No se modifican addons ni bases Odoo.

## Datos y relaciones

- `machines.passenger_capacity`: cantidad real de asientos de pasajeros, sin
  contar al conductor. Inicialmente NULL; un administrador debe configurarla
  desde la API de vehículos. No se inventa una capacidad ni se rellenan datos.
- `mobile_passenger_services`: UUID estable, nombre, FK a `mobile_routes`, FK
  al usuario conductor activo, capacidad histórica, autor y fecha de creación.
- `mobile_service_stops`: paradas ordenadas del servicio, nombre, horario con
  zona y coordenadas opcionales. Los horarios se guardan en UTC.
- `mobile_service_passengers`: nómina histórica por servicio, UUID, nombre,
  RUT/ID, FK a paradas de subida/bajada y asiento opcional.

Se reutilizan vehículos, usuarios y rutas existentes. La nómina es una lista
del viaje, no otro maestro de personas. El conductor es un usuario autenticable
del Tracker; no se deduce una identidad por nombre ni por el RUT de otra tabla.
La capacidad histórica no cambia al editar la capacidad del vehículo.

Se rechazan paradas duplicadas, horarios sin zona o desordenados, bajadas
anteriores a la subida, paradas ajenas, documentos repetidos, exceso de ocupación
por tramo y asientos repetidos o fuera de rango. Un asiento puede reutilizarse
después de la bajada de su pasajero. La operación es atómica y repetir el mismo
UUID/contenido devuelve el servicio existente; otro contenido obtiene 409.

## API y permisos

| Método y ruta | Uso | Permiso |
|---|---|---|
| `PUT /machines/{id}` con `passenger_capacity` | Configurar capacidad real | Administrador existente |
| `POST /mobile/services` | Programar servicio con paradas y nómina | Administrador existente |
| `GET /mobile/services?mine=true` | Consultar servicios asignados | Usuario activo; solo conductor asignado |
| `GET /mobile/services?mine=false` | Consultar servicios de administración | Administrador; un conductor sigue viendo solo los propios |
| `GET /mobile/services/{uuid}` | Consultar un servicio y su nómina | Conductor asignado o administrador |

Además se valida el acceso vigente del conductor al centro de costo del vehículo.
Compartir centro de costo no concede acceso a otros servicios. Asignar a un
usuario inactivo o sin acceso se rechaza. Una ruta cancelada se muestra como tal
sin borrar la nómina. Se conserva la autenticación JWT y los permisos existentes.

El payload de creación contiene `id`, `name`, `route_id`, `driver_user_id`,
`stops[]` (`id`, `name`, `scheduled_at`, `lat`, `lon`) y `passengers[]` (`id`,
`name`, `document`, `boarding_stop_id`, `alighting_stop_id`, `seat`). Los IDs
son UUID salvo el usuario conductor. La capacidad procede del vehículo de la
ruta y no es un parámetro libre del servicio.

## Contrato hacia Odoo

La respuesta conserva los UUID de servicio/paradas/pasajeros y añade `sync`:
`schema_version=1`, `source=tracker`, `service_id`, `content_hash`,
`machine_external_id`, `cost_center_id` y `cost_center_external_id`.
El futuro consumidor servidor a servidor debe:

1. Autenticarse con una cuenta de integración y alcance explícito. La sesión
   del conductor no se comparte con el proceso de sincronización.
2. Resolver vehículo y centro contra sus IDs externos ya configurados en el
   origen Tracker autorizado para la compañía Odoo. No interpretar nombres ni
   enteros de otro ambiente como IDs locales. Si falta el vínculo, detener ese
   registro y solicitar su configuración, sin crear maestros paralelos.
3. Actualizar por `(origen Tracker configurado, service_id)`, conservando UUID de
   líneas y el hash de contenido. Reintentar sin duplicar y conservar históricos.
4. Tratar la copia Odoo como consulta del origen Tracker. Cambios de operación
   siguen entrando por la API autorizada de Tracker, no por una segunda nómina.

I10/I11 ampliarán el contrato versionado para estados y eventos. I9 no publica
un cursor incremental ni promete sincronización automática ya instalada.

## Validación y publicación

Pruebas HTTP sobre API real de FastAPI/ORM con aislamiento y validaciones;
ensayo adicional en una copia PostgreSQL del destino, migración ejecutada dos
veces, comparación de todas las columnas antiguas y rollback de los datos de
prueba. La interfaz usa el mock del contrato a 375 px; no sustituye pruebas de
GPS ni de teléfono físico. La nómina no se persiste en localStorage ni en la
cola; respuestas y consulta usan `no-store`.

Publicar desde un checkout fresco de `codex/steps-movil`, commit exacto y base
del servidor revisada. `scripts/deploy-steps-movil.sh` exige ambos SHA, bloqueo
compartido y del producto, respaldo decodificado y fuente sin concurrencia.
Prueba el mismo paquete en copia, migra de forma aditiva y publica API antes de
app. Verifica contrato y hashes de todos los JS/CSS servidos. Ante fallo restaura
fuentes/frontend; conserva las nuevas estructuras aditivas sin borrar datos.
