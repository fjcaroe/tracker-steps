# Administración de maestros

La pantalla **Maestros** administra datos productivos reales; no usa el dataset
del laboratorio demo.

## Capacidades por maestro

| Maestro | Consultar | Crear | Editar | Eliminar |
|---|---:|---:|---:|---:|
| Máquinas | Sí | Sí | Sí (`PUT`) | Sí |
| Conductores | Sí | Sí | Sí (`PATCH`) | Sí (desactivación lógica) |
| Actividades | Sí | Sí | Sí (`PUT`) | Sí (desactivación lógica) |
| Labores | Sí | Sí | Sí (`PUT`) | Sí (desactivación lógica) |
| Implementos | Sí | Sí | Sí (`PATCH`) | Sí (desactivación lógica) |
| Centros de costo | Sí | Sí | Sí (`PATCH`) | Sí |
| Especies | Sí | Sí | Sí (`PATCH`) | Sí |
| Variedades | Sí | Sí | Sí (`PATCH`) | Sí |
| Regiones | Sí | Sí | Sí (`PATCH`) | Sí |
| Comunas | Sí | Sí | Sí (`PATCH`) | Sí |
| Fundos | Sí | Sí | Sí (`PATCH`) | Sí |
| Sectores | Sí | Sí | Sí (`PATCH`) | Sí |
| Predios/polígonos | Sí | Sí | Sí (`PUT`) | Sí |

Los formularios usan los contratos publicados en el OpenAPI productivo. Las
eliminaciones solicitan confirmación y los errores de dependencias se muestran
sin cerrar el formulario.

Los maestros se presentan en tres grupos para facilitar su ubicación:

- **Operación:** máquinas, conductores, actividades, labores e implementos.
- **Estructura agrícola:** centros de costo, especies y variedades.
- **Territorio:** regiones, comunas, fundos, sectores y predios/polígonos.

La carga de cada catálogo es independiente. Una falla en sesiones u otro
endpoint no oculta los polígonos ni los restantes maestros que sí respondieron.

Conductores, actividades, labores e implementos usan desactivación lógica para
proteger sesiones y partes de trabajo históricos. Sus endpoints `GET` aceptan
`include_inactive=true` para tareas administrativas o recuperación.

## Editor de polígonos

- El mapa se presenta en modo satelital.
- Un clic sobre el mapa agrega un vértice.
- Cada marcador numerado es arrastrable.
- Al seleccionar un marcador se habilita **Quitar punto seleccionado**.
- Se requieren al menos tres vértices para guardar.
- El polígono se persiste como una lista de objetos `{lat, lon}` en `/fields`.

La edición permite cambiar nombre, centro de costo y color junto con la
geometría. Los campos de especie y variedad, si existen, se conservan porque el
`PUT` enviado es parcial y no los sobrescribe.
