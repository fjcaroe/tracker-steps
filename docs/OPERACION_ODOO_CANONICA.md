# Operación y publicación de Odoo

Este procedimiento aplica a todos los agentes que trabajen en este repositorio.
Las instrucciones específicas de un producto se conservan, pero no reemplazan
la identificación y comprobación del ambiente real.

## Identificar antes de intervenir

Definición vigente del cliente, 06-10-2026:

- **Desarrollo es el único QA** y destino de revisión funcional.
- **Demo-SYS replica exclusivamente el alcance actual de SyS**, incluida Nómina
  Simple Digital y soporte de Luis. No es una copia de Desarrollo ni de Steps;
  no instalar allí aplicaciones para igualar todos los ambientes.
- Producción: **SyS (Luis), Steps / karo_consultorias y Cerro El Plomo**.
- Demo, Admin Studio y Everfruit son instalaciones legadas, fuera de QA y
  promoción. Conservar datos y respaldos; no eliminarlas ni distribuir mejoras
  allí. Su retiro de infraestructura requiere inventario y conservación previa.

Primero instalar y probar en Desarrollo. Las copias privadas de una producción
pueden validar compatibilidad, pero no son otros QA públicos. Promover el mismo
paquete revisado. Nómina oficial: Simple Digital; no instalar el motor anterior
ni recalcular liquidaciones pagadas al cambiar de motor. El retiro de un motor
requiere migración comprobada de estructuras/reglas e históricos antes de
desinstalar dependencias que puedan borrar registros.

La fuente de puertos, bases, servicios y dominios es
[`tools/ops/environments.json`](../tools/ops/environments.json). Por ejemplo,
`http://35.222.25.110:8075/odoo` es Desarrollo / `LAB_TAREAS`, y `8070` es
SyS. `8069` es Steps; no es SyS. Admin es una referencia Studio multi-base,
no una base para copiar ciegamente a los demás ambientes.

1. Leer descripción, adjuntos y comentarios recientes del ticket. Si el cliente
   respondió una decisión, incorporarla aunque haya una nota de análisis anterior.
2. Resolver URL, puerto y nombre del ambiente con el registro; verificar por SSH
   la configuración, base, servicio y rutas efectivas de addons. Una API sin
   acceso no demuestra que el servidor sea inaccesible: SSH sigue disponible.
3. Inventariar versión instalada, versión de manifiesto y hash del código que
   realmente carga cada servicio. `audit_runtime.py` no imprime contraseñas.
4. Consultar el manifiesto de la última entrega instalada, no elegir por la fecha
   de una rama ni por el checkout abierto. Gestión y sus puentes se consolidan
   en `origin/codex/ambientes-canonicos-reparacion`; el stack agrícola previo
   está integrado en esa base. Steps Móvil y Web Tracker conservan sus bases
   propias documentadas. Crear worktree propio y preservar cambios ajenos.

## Excepción específica T115, 24-10-2026

El usuario autorizó crear **QA-CERROELPLOMO** desde la producción de Cerro para
pruebas de implementación y capacitación del cliente. Es una copia aislada,
neutralizada y con fuentes/filestore propios. Desarrollo conserva el QA general
y la revisión previa del circuito de ingeniería. La copia del cliente no cambia
los destinos de publicación genéricos ni autoriza producción, accesos adicionales
entre empresas, envíos reales o una actualización automática de sus datos.
Un refresco futuro requiere conservar primero los ejercicios de capacitación;
no sobrescribir la copia por una ejecución recurrente.

El registro `qa-cerro` documenta esta excepción con `deploy_enabled=false`;
`tools/ops/provision_cerro_qa.py` implementa su creación explícita. Su servicio
no tiene tareas programadas ni salida a Internet, con excepción del acceso a
su propio HTTP local para informes. Los demás ambientes legados y SAG T92/T93
conservan sus restricciones.

## Actualizaciones explícitas T117/T118/T119/T120 de QA-CERROELPLOMO

T118, T119 y T120 solicitan aplicar sus cambios de recepciones de Packing a Desarrollo,
Cerro El Plomo y QA-CERROELPLOMO. La respuesta humana 9692 de T117 solicita
además actualizar la copia QA con las taras ya entregadas en Desarrollo y Cerro.
Los tipos de paquete `reception-revision` y `packing-tare` permiten únicamente
esos destinos dentro de estas autorizaciones explícitas. El registro de la copia conserva `deploy_enabled=false`
y no se habilitan promociones genéricas ni refrescos de datos. Se exige copia
fresca de cada destino, paquete idéntico, respaldo y bloqueo antes de publicar.
La capacitación existente, la neutralización, el correo y la red aislada se
conservan. Para probar la copia del cliente, un contexto temporal autoriza a su
rol únicamente la base clonada por socket local; retira la regla al terminar,
sin modificar claves ni dar acceso a producción.

## Contrato funcional

T123 usa `invoice-payments` en Desarrollo, Cerro y QA-CERROELPLOMO, según
confirmación explícita del usuario en este chat el 26-10-2026. El adjunto pide
seleccionar facturas pendientes y distribuir el pago/cobro total o parcial,
con una contrapartida contable por factura y conciliación nativa. QA-Cerro
conserva sus ejercicios, red y correo neutralizados; no se refresca su base.
La instalación no cambia pagos ni facturas históricos. Las pruebas contables
se ejecutan en copia, publicando el mismo paquete con respaldo y bloqueo.

T114 y T122 autorizan `packing-controls` en Desarrollo, Cerro y QA-CERROELPLOMO:
perfiles por aplicación y analítica de consumos de Packing. Los perfiles no se
asignan automáticamente ni alteran membresías existentes; la contabilidad
conserva sus grupos nativos. El plan nativo OT Packing y las reglas por empresa
se configuran sin generar asientos o movimientos. Las cuentas de OT se crean
al preparar el comprobante. Las correcciones de cargos de asientos anteriores
se presentan como reclasificaciones en borrador, conservando los publicados.
Se exige copia fresca del destino, paquete idéntico, respaldo y bloqueo; QA
conserva sus ejercicios y aislamiento. El stock en kg y cajas separadas de T121
fue confirmado en la respuesta humana 9720, que informa el ciclo probado.

T121 autoriza además el paquete `packing-stock` en Desarrollo, Cerro y
QA-CERROELPLOMO: configurar una bodega nativa Packing, el origen de materiales y
el traslado de tarjas C al proceso. Se reutiliza la bodega existente cuando es
única y compatible. La configuración inicial solo crea registros logísticos
nativos; no inventa existencias ni mueve fruta o materiales de los ambientes
activos. Las tarjas se trasladan cuando el operador valida o cierra la OT.
La prueba en copias permite altas de configuración de la empresa autorizada,
manteniendo huellas de todos los registros previos y de todas las cantidades,
movimientos, reservas, documentos y registros contables. QA conserva su
aislamiento, sin refresco de datos ni autorización genérica de publicación.

Decisión del usuario, 06-10-2026: no crear ni ampliar desarrollos Studio.
Todo nuevo desarrollo se implementa en código versionado. El inventario de
retiro comprende modelos, campos, vistas, reportes, automatizaciones y permisos;
una portada propia no convierte el modelo manual que todavía consulta.
Para la migración de Fletes, la decisión vigente retira los nombres técnicos
`x_`: usar modelos `step.freight.*` y campos descriptivos propios, renombrando
tablas y referencias mediante migración. Conservar los IDs cuando sea posible,
sin crear maestros paralelos. Esta convención se aplica a nuevos desarrollos.
Los campos dinámicos nativos de
planes analíticos y reportes de nómina no se eliminan por ser `manual`.

- Relacionar temporada, especie, variedad, cuenta, productor, fundo y centro
  con los maestros existentes del ERP cuando el documento pide seleccionarlos.
  No reemplazar una tabla por texto ni crear un segundo maestro para simplificar.
- Un texto histórico o importado puede conservarse como snapshot de solo lectura,
  junto con su relación explícita. No resolver coincidencias ambiguas por nombre.
- Inventariar modelos y menús Studio antes de convertirlos; migrar de forma
  versionada. No crear campos ni parchear vistas manualmente por XML-RPC para
  aparentar una entrega de código. No desactivar Studio fuera del alcance.
- Comparar los campos y las vistas efectivas, no solo el XML del repositorio.
  Probar las acciones de menú y el formulario con el perfil de usuario previsto.
- Los maestros compartidos no autorizan a compartir documentos contables:
  mantener reglas por empresa y comprobar las relaciones en el servidor.

## Pruebas, promoción y evidencia

Una comprobación de sintaxis o HTTP 200 es insuficiente para publicar una
migración o cerrar un ticket. El paquete exacto debe pasar en una copia aislada
del ambiente objetivo; no reutilizar una copia con migraciones fallidas como
si representara el estado inicial.

`build_management_release.py` genera el paquete desde Git y registra commit,
versiones y SHA-256 por archivo. `manage_management.py qa` restaura una copia,
desactiva correo y tareas programadas, ejecuta pruebas del flujo y verifica
formularios y preservación de importes/filas. `deploy` exige la prueba del
mismo paquete y rechaza cambios concurrentes o una versión anterior.

Antes de modificar un servicio, adquirir la exclusión compartida
`/run/lock/steps-environments.lock` y comprobar que no haya otro upgrade activo.
Guardar dump y configuración recuperables. Usar una superposición privada de
addons; no reemplazar una raíz compartida con producción. No copiar bases de
clientes entre ambientes. Actualizar solo los módulos instalados afectados y
las dependencias nuevas justificadas.

Para Demo-SYS, comprobar primero los módulos realmente instalados en SyS con
``tools/ops/demo_sys_scope.py``. Su referencia es ``policy.mirrors`` del registro.
Un paquete para Demo-SYS no puede incluir addons ajenos a esa referencia, aunque
no vaya a instalarlos. El publicador de Nómina hace esa comprobación antes de
copiar addons o intervenir el servicio. Preparar su paquete con
``build_management_release.py --kind payroll --environment demo-sys``; no usar
el paquete agrícola combinado. No restringir la definición a dos aplicaciones:
Contabilidad, Colaciones y las otras aplicaciones que ya estén en SyS también
pertenecen a su alcance, respetando los permisos de cada usuario.

La auditoría del 06-10-2026 encontró 330 módulos instalados en SyS y 356 en
Demo-SYS: 26 adicionales, entre ellos Packing, Productores, Exportaciones,
Maquinaria, Gestión y Calidad. Es una diferencia previa que debe retirarse
con inventario de registros/dependencias y ensayo en copia, preservando datos.
Ocultar menús no equivale a desinstalar esos módulos ni a completar la réplica.
Esta corrección de alcance y publicadores no los desinstala ni cambia las
aplicaciones de SyS.

Verificar después: origen del código, versión instalada, servicio, URL HTTPS,
menús, vistas efectivas y un flujo representativo. Registrar qué se probó y
qué requiere hardware o aceptación del cliente. No decir «resuelto» por haber
hecho un commit o instalado el módulo. Conservar los respaldos ante un fallo;
no restaurar una base descartando datos nuevos sin evaluar la recuperación.

Los accesos por puerto redirigen a destinos fijos HTTPS mediante nginx, usando
[`return 308`](https://nginx.org/en/docs/http/ngx_http_rewrite_module.html#return)
y [`listen`](https://nginx.org/en/docs/http/ngx_http_core_module.html#listen) sobre
la dirección privada de la VM. Ruta y query se conservan. Las API deben usar
directamente el dominio canónico porque algunos clientes XML-RPC no siguen
redirecciones. No cambiar claves para resolver esta diferencia de URL.

La etapa y el comentario de un ticket deben describir el ambiente donde se
aplicó y verificó la solución. No cerrar si el ambiente solicitado sigue sin
actualizar. Los comentarios al cliente usan lenguaje de negocio; la evidencia
técnica detallada queda en el acta interna. No enviar mensajes ni notificaciones
externas sin la autorización correspondiente.

Terminar con commits, push y `python tools/git/verify_handoff.py --require-pushed`.
