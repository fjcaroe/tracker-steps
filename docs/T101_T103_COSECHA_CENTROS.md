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

## T103: decisión funcional pendiente

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

Se consultó al usuario si quiere navegar a las operaciones actuales conservando
los anteriores como históricos, o convertir también los documentos antiguos.
Hasta resolver esa elección no se reemplazan destinos ni se cierra T103.
El inventario detallado y los adjuntos se conservan fuera de Git, en los
artefactos privados de la tarea.
