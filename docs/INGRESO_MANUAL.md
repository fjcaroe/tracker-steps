# Módulo de ingreso manual

El módulo **Ingreso manual** es una pantalla administrativa separada de
**Historial**. Historial conserva la trazabilidad generada automáticamente por
GPS; Ingreso manual permite transcribir y revisar partes de trabajo provenientes
de libretas, planillas u otros registros anteriores.

## Persistencia

La pantalla usa el recurso real de la API Tracker:

- `GET /work_orders`: revisión de partes existentes.
- `POST /work_orders`: creación de un parte manual.
- `PUT /work_orders/{id}`: corrección de implemento, horómetros, combustible y
  observaciones.

El contrato se verificó en el OpenAPI publicado por producción el 2026-08-19.
Los datos quedan centralizados; no se guardan en `localStorage`.

## Experiencia de uso

- Formulario de dos pasos, controles grandes y revisión antes de confirmar.
- Campos obligatorios claros: fecha, temporada, máquina, actividad y labor.
- Las labores se filtran según la actividad elegida.
- Búsqueda y revisión de partes históricos en la misma pantalla.
- La edición bloquea los datos estructurales del parte porque el contrato
  `WorkOrderUpdate` solo admite lecturas, implemento y observaciones.
- Actualmente `WorkOrderOut` no devuelve `machine_id`, aunque `WorkOrderCreate`
  lo exige. Por ello la máquina se selecciona y guarda al crear, pero la tabla
  histórica muestra predio y centro de costo en lugar de inventar ese dato.

## Diferencia con Historial

Un parte manual declara información administrativa y conserva su código
`MAN-AAAAMMDD-HHMMSS`. No crea puntos GPS, sesiones ni distancias artificiales.
Por tanto, no se mezcla con el Historial de sesiones y mantiene explícito el
origen de cada tipo de dato.
