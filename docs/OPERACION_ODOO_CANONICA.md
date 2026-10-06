# Operación y publicación de Odoo

Este procedimiento aplica a todos los agentes que trabajen en este repositorio.
Las instrucciones específicas de un producto se conservan, pero no reemplazan
la identificación y comprobación del ambiente real.

## Identificar antes de intervenir

Definición vigente del cliente, 06-10-2026:

- **Desarrollo es el único QA** y destino de revisión funcional.
- **Demo-SYS: solo Nómina Simple Digital y soporte de Luis.**
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

## Contrato funcional

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
