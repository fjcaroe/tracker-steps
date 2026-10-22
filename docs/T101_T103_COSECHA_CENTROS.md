# T101–T103: Cosecha y accesos desde centros de costos

## T101 y T102

Destino autorizado: Desarrollo y Cerro El Plomo. Módulo aislado
`step_cosecha_operations`, sobre `step_cosecha_planning` y `step_packing`.

- Mueve el menú existente de Procesos de Cosecha a Recepción, sin reemplazar
  su acción ni sus registros.
- Configuración reutiliza Clase de fruta, Estado de tarja y Tipo de tarja.
  El nombre técnico real del segundo maestro es `step.packing.tag.state`;
  no existe un segundo maestro `step.packing.state`.
- Expone el `partner_id` nativo de la cabecera de Cuadrilla Contratista.
  El contratista de cada línea ya es una relación de solo lectura con esa
  cabecera; se retira la columna redundante. La selección de trabajadores
  usa su relación explícita `contratista_id` con el contratista de la cuadrilla.
- La personalización heredada del formulario de cosecha insertaba una copia
  completa del formulario de empleado, con seis campos que ya no existen.
  El hook versionado retira exclusivamente esa subvista obsoleta y conserva
  el resto de la personalización. El campo calculado de empleados disponibles
  se muestra como etiquetas de solo lectura. No se borran campos ni registros.

Las pruebas requieren copias frescas de ambos destinos. Cubren alta/edición
de maestros con perfil administrador agrícola, cuadrilla con contratista y
trabajador, incorporación de la cuadrilla a un registro de cosecha, guardado,
reapertura, aprobación y retorno a Ingresado. La sonda comprueba rutas/versiones,
menús, campos de subformularios y lectura de registros existentes mediante
el serializador del cliente web. Todos los datos de prueba se revierten.

Paquete funcional probado: commit
`86ed636fe69cd7bf53b26264e20dfd0b10836978`, SHA-256
`79eb9943ea723182d9e3251e00b0930a526ed68cc62ed0ce595b692f60fe6b5e`.
Las copias frescas `t101qa3` (Desarrollo) y `t101ce1` (Cerro) pasaron las
tres pruebas, sin fallos ni errores; ambas sondas confirmaron conservación
de registros, formularios efectivos y maestros nativos. El error de apertura
original también se reprodujo en el navegador autenticado de Desarrollo:
`"hr.employee"."firstname" field is undefined`.

Publicación del mismo paquete completada en ambos destinos, con sondas
posteriores de versión, ruta efectiva, menús, formularios y lectura de
registros existentes. Respaldos:

- Desarrollo: `management_development_20261022T005222Z`.
- Cerro El Plomo: `management_cerro_20261022T005353Z`.

En el navegador autenticado de Desarrollo se comprobaron la apertura de un
registro contratista nuevo y uno existente, el contratista en la cabecera de
una nueva cuadrilla, la ausencia de esa columna en sus líneas y el árbol de
menús con Procesos en Recepción y los tres maestros en Configuración.
Los formularios nuevos se descartaron sin guardar documentos.

T101 y T102 quedaron resueltos mediante notas internas 9595 y 9596. El
registrador comprobó ausencia de respuestas nuevas, SLA y automatizaciones
antes del cambio de etapa, y ausencia de correos y notificaciones después.
T103 permanece abierto, sin sustituir sus formularios históricos.

## T103: conversión de históricos autorizada

El adjunto muestra trece botones, incluidos los del desbordamiento «Más».
El inventario de Desarrollo distingue:

| Botón | Destino existente |
| --- | --- |
| Costos | `step.tarja.cost.line`, relación `cost_id_domain` |
| Maquinaria | `step.hrs.machinery.line`, relación `cost_id` |
| Movilización | `step.movi.cost.line`, relación `cost_id` |
| Contratistas | `step.tarja.cost.line`, relación `cost_id` |
| Tarja propia | `step.tarja.line`, relación `cost_id` |
| Pronóstico cosecha | Modelo manual `x_planificar_cosecha` |
| Cosecha | Modelo manual `x_registro_cosecha` |
| Riego | Líneas manuales de sectores de riego |
| Aplicación foliar | Líneas manuales de aplicaciones |
| Monitoreo / plaga | La misma relación de líneas manuales de monitoreo |
| Asesoría | Modelo manual de asesoría, con líneas y automatización |
| Inspecciones | Modelo manual de inspecciones, con líneas y automatización |

La acción Studio de Cosecha tiene dominio vacío aunque su contador filtra el
centro; una conversión debe hacer coincidir ambos. Los contadores actuales son
campos manuales calculados. La migración debe contemplar formularios heredados,
líneas, relaciones con maestros, automatizaciones, permisos y datos históricos.
Un contenedor de botones que siga dependiendo de esos modelos manuales no
acredita su conversión a código.

El usuario eligió convertir también los documentos y formularios antiguos.
La implementación y la decisión pendiente sobre equivalencias de estados están
en `docs/T103_MIGRACION_DOCUMENTOS_AGRICOLAS.md`. T103 continúa abierto hasta
terminar y comprobar la migración.
El inventario detallado y los adjuntos se conservan fuera de Git, en los
artefactos privados de la tarea.
