# Portada comercial Steps — 1 de octubre de 2026

## Referencia y decisión comercial

Se revisaron en navegador la portada de https://desarrollo.stepsapp.cl/ y
https://woworker.com/precios/ el 1 de octubre de 2026.

Woworker presenta planes por trabajadores, modalidades mensual/anual, siete días
de marcha blanca gratis, carga inicial, capacitación y soporte online. Para el
tramo de 1 a 10 trabajadores, el selector mostró $150.000 mensuales y $1.250.000
anuales, más IVA; la modalidad anual expresa también $104.167/mes. Son valores
observados en esa fecha, no una comparación contractual ni una tarifa de Steps.

La oportunidad para Steps es explicar mejor el punto de entrada y la adopción,
y hacer visible la conexión de campo con personas, costos y finanzas. La portada
anterior priorizaba el catálogo de funciones y no describía una oferta de inicio.

| Necesidad del comprador | Respuesta de la nueva portada |
| --- | --- |
| Entender qué resolverá | Beneficios de operación, personas y negocio, antes del catálogo |
| Elegir por dónde empezar | Campo, Campo + Personas y Gestión integral |
| Entender el costo completo | Cotización con módulos, licencias, implementación, carga, capacitación, soporte y terceros separados |
| Llegar con datos existentes | Revisión de planillas y carga inicial acordada |
| Adoptar sin desplegar todo de una vez | Demo por proceso, capacitación por rol y marcha blanca acotada |
| Dimensionar la temporada | Selector de trabajadores y estacionalidad; diferencia entre trabajadores registrados y usuarios |
| Resolver dudas antes de contactar | Siete preguntas sobre precio, módulos, temporada, offline, migración, pruebas y soporte |
| Solicitar una conversación pertinente | Selección de paquete que prepara un resumen por correo; formulario existente como alternativa |

No se publicaron precios, descuentos, pruebas gratuitas, garantías de devolución,
plazos de implementación ni SLA sin condiciones comerciales aprobadas. Los
paquetes son referencias sujetas a cotización. La marcha blanca se ofrece para
acordar alcance, duración y costo, no como un servicio gratuito automático.

## Diseño y alcance técnico

- Mensaje principal: «Tu campo, bajo control. Tu negocio, conectado».
- Fondo claro, verdes de marca y esquema de una labor desde terreno hasta costo,
  identificado como flujo ilustrativo, sin métricas ficticias.
- Tarjetas comparables para los tres paquetes; navegación orientada a compra.
- Catálogo completo de 20 soluciones conservado desde la versión T42 del código,
  dentro de un desplegable nativo para reducir la longitud inicial de la página.
- Cinco accesos web y estados de las apps móviles conservados.
- Resumen de demo en el navegador, sin almacenamiento, envío automático ni nuevo
  servicio de terceros. El botón abre el correo del visitante; /contactus queda
  disponible como alternativa. No se enviaron correos durante las pruebas.
- No se implementaron nuevas funcionalidades del ERP: se mejoró su presentación
  comercial, el recorrido de compra y la solicitud de demo.

## Publicación y separación de ambientes

Módulo `step_demo_homepage`, versión `18.0.2.5.0`.
Rama `codex/home-commercial-20261001`, basada en `codex/t42-homepage-apps`.
Se utilizó la versión de la portada que ya existía en el servidor: los archivos
versionados coincidían con T42; las vistas servidas por desarrollo aún mostraban
13 soluciones. La migración actualiza también las copias activas por website.

Producción usa `/opt/dev_odoo18/odoo_agriculture` como parte de su addons_path.
Para que los estilos nuevos no alcancen producción, la portada de Desarrollo
se aisló en `/opt/dev_odoo18/homepage_addons/step_demo_homepage` y se antepuso
esa carpeta **solamente** en `/etc/dev_odoo18.conf`.

| Entorno | Base | Servicio | Carpeta de esta entrega |
| --- | --- | --- | --- |
| Desarrollo | LAB_TAREAS | odoo18-dev.service | /opt/dev_odoo18/homepage_addons/step_demo_homepage |
| Demo | STEPS_DEMO | odoo18-demo.service | /opt/demo_odoo18/odoo_agriculture/step_demo_homepage |

Script reproducible: `scripts/deploy_home_commercial.sh`.
Paquete: `/tmp/steps-home-commercial-18.0.2.5.0.tar.gz`.
SHA-256: `7803372ae9f99ea9c93f713bf9c448a99a0296bd0033eba4525e8754fb45f7d3`.

El script valida destino y hash, respalda configuración, módulo y base de datos,
actualiza solo el módulo indicado, arranca el servicio y valida página, assets y
rutas públicas. Compara además los hashes de todos los archivos de la carpeta
original compartida con producción y el H1 servido por producción.

Respaldo Desarrollo: `/opt/steps_backups/home-commercial-dev-20261001T144538Z`.
Respaldo Demo: `/opt/steps_backups/home-commercial-demo-20261001T144701Z`.

Para futuras entregas de esta portada en Desarrollo usar la carpeta aislada,
no el directorio compartido. El resto de módulos mantiene las rutas existentes.

## Verificación

- XML y JSON-LD válidos, un H1, IDs únicos y anclas internas resueltas.
- Compilación SCSS y sintaxis JavaScript verificadas.
- Tres paquetes, 20 soluciones, cinco apps web y siete FAQs.
- Seleccionar Campo + Personas, 101–300 trabajadores y equipo estacional genera
  el resumen y el correo codificado correspondientes.
- El filtro Exportaciones muestra exactamente tres soluciones.
- Desplegables nativos del catálogo y FAQ operativos.
- Revisión visual de escritorio y móvil a 390 px; sin desbordamiento horizontal.
- Desarrollo y Demo: HTTP 200 en inicio, contacto, login y páginas de soluciones;
  estilos comerciales presentes en el bundle real de Odoo.
- Navegador contra ambas URLs: versión `2026.10`, resumen por correo activo;
  selección de Gestión integral verificada también en Demo. Sin errores de
  consola en la revisión de Demo. Odoo conserva su aviso de base neutralizada.
- Archivos compartidos con producción y portada productiva sin cambios.

## Reversión

Detener únicamente el servicio del entorno afectado. El respaldo contiene
`odoo.conf.before`, `module.before.tar.gz` y `database.before.dump`.
En Desarrollo, restaurar primero la configuración anterior devuelve la resolución
del módulo a su ruta previa. En Demo, restaurar el módulo en su carpeta original.
Las vistas guardadas en la base también necesitan restauración: realizarla de
forma selectiva mediante Odoo usando el respaldo, o restaurar el dump completo
solo tras evaluar los cambios de negocio posteriores a la entrega. No ejecutar
una restauración completa automática sobre una base que haya recibido trabajo.

## Siguientes decisiones de venta

Para convertir estos paquetes en planes con precio público, acordar una matriz
de usuarios/licencias, trabajadores estacionales, empresas, costo de puesta en
marcha y cobertura de soporte. Evaluar después una marcha blanca con condiciones
comerciales explícitas y casos de éxito con métricas y autorización del cliente.
La portada no presupone aprobadas esas condiciones.
