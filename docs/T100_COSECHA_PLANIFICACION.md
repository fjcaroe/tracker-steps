# T100: planificación y maestros en Cosecha

Alcance solicitado: Desarrollo y Cerro El Plomo. Adjunto 3381, leído junto con
las imágenes del menú existente antes de implementar. Código en
`step_cosecha_planning`, rama canónica `codex/ambientes-canonicos-reparacion`.

## Funcionalidad

- Cosecha → Planificar Cosecha → Plan de cosecha abre exactamente la acción
  `step_management_costs.action_harvest_plan`, conservada también en Gestión y
  Costos → Planificación → Plan de cosecha. Son los mismos registros, revisión,
  líneas por centro/semana, recursos y snapshot de confirmación.
- Cosecha → Maestros → Tipos de pallet abre el maestro `stock.package.type`
  y sus vistas existentes de Exportaciones.
- Cosecha → Maestros → Embalajes abre `product.packaging`, con las vistas
  existentes de Exportaciones y búsqueda nativa. No hay maestros paralelos.
- Grupo embalaje, selección de Exportación / Nacional / Cosecha, está definido
  en código sobre el maestro nativo. Aparece en los formularios y listas
  nativos y de Exportaciones, y permite buscar/agrupar. No se deduce ni asigna
  grupo a los históricos: conservan sus identificadores, relaciones y valores.

No se cambia el modelo ni el flujo del plan. El nuevo acceso respeta los
perfiles de Gestión y Costos existentes: consulta para lectura, operador para
crear/editar. No otorga nuevos permisos a usuarios de Cosecha ni evita las
reglas por empresa. Los maestros mantienen sus permisos nativos.

## Pruebas

La primera prueba crea una estimación con curvas validadas, genera el plan
centro/semana y lo confirma con un operador. Comprueba ambos menús sobre la
misma acción, lectura del mismo hash desde el otro módulo y la inmutabilidad.
La segunda usa el formulario efectivo para editar las tres clasificaciones en
el mismo embalaje y comprueba la conservación de producto/cantidad. También
crea un pallet en el maestro original. El probe comprueba versión y ruta,
formularios/listas/búsqueda, visibilidad de menús y permisos de consulta,
operación y usuario básico. Todos los fixtures se revierten.

Paquete `a7ed6df9f980a11d228a382b3570d3affc423b12`, módulo 18.0.1.0.0.
SHA-256 `064a749a92255d64f564d51acb30f4b5cdd56fba6492145cd0cf8f5b87d6bd6e`.
Copia fresca de Desarrollo `MANAGEMENT_QA_DEVELOPMENT_t100qa1`: dos pruebas
sin fallos ni errores, probes efectivos y conservación de datos aprobados.
El bundle no incorpora JavaScript ni plantillas OWL nuevas.

Desarrollo publicado con respaldo `management_development_20261021T180721Z`.
Verificación posterior: origen efectivo del código, versión 18.0.1.0.0,
acción compartida, formularios/listas/búsqueda, maestros nativos, servicio y
URL HTTPS correctos. Sin nuevos modelos de negocio ni cambios en los permisos.


Copia fresca de Cerro `MANAGEMENT_QA_CERRO_t100ce1`: dos pruebas sin fallos
ni errores; probes de formularios, menús, permisos y preservación aprobados.
Publicado el mismo paquete con respaldo `management_cerro_20261021T181212Z`.
Verificación posterior del origen, versión, menús, maestros, formularios,
servicio y HTTPS correcta. Se usaron overlays privados, baseline sin cambios
concurrentes y bloqueo compartido; no se alteraron raíces compartidas.

Entrega interna 9578. T100 quedó en Solved tras verificar ambos ambientes.
El cierre se hizo con `tracking_disable` para omitir la plantilla automática:
se comprobaron antes ausencia de SLA y automatizaciones activas del ticket,
y después solo la nota interna nueva, cero notificaciones y cero correos.
No se modificó la plantilla global ni se enviaron mensajes a terceros.
No había respuestas adicionales ni tickets posteriores al 100 al entregar.
