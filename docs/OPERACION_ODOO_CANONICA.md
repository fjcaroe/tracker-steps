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

T141 autoriza `reception-report` en Desarrollo, Cerro y QA-Cerro: adaptar el
recibo de entrega nativo para recepciones entrantes de fruta según el adjunto.
Conservar acción, logo, direcciones y documentos de stock ajenos a Packing.
Guía, tipo/clase, lote, operaciones, tarjas con pesos y totales y transporte
proceden de los registros existentes. El recibo conserva formato numérico y
fechas de español de Chile sin cambiar el idioma del usuario. No validar recepciones reales ni cambiar
pesos o existencias. Mismo paquete en copias frescas, PDF nativo corto y largo,
revisión visual, respaldo, bloqueo, paridad e aislamiento de QA-Cerro.


T139/T140 autorizan `agriculture-multicompany` en Desarrollo, Cerro y QA-Cerro:
selección explícita de empresas y sucursales para Fundos de productores,
categoría, clase, calidad y color de fruta. Reutilizar los maestros y conservar
IDs, datos, empresa de origen y relaciones. No compartir documentos contables
ni inventario, ni asignar automáticamente otras empresas. Incorporar Fundos
a Packing / Maestros. La lectura de los operadores no debe requerir acceso
a fichas de compañías ajenas. Copias frescas, mismo paquete, respaldo, bloqueo y
paridad del módulo afectado; no refrescar capacitación ni retirar aislamiento.


### Paridad de las entregas de Cerro y QA-Cerro — 30-10-2026

El usuario indicó mantener QA-Cerro incluido en los cambios aplicables que se
entreguen a Cerro producción, para evitar versiones dispares y promociones
erróneas. Para cada módulo afectado, comprobar versión y código efectivo de
ambos antes de registrar la entrega. Usar el mismo paquete certificado en
Desarrollo, con prueba fresca de cada destino, respaldo y bloqueo. La copia
del cliente conserva capacitación, aislamiento y datos propios; no se refresca.
No promover código, configuraciones de ejercicio o datos desde QA-Cerro hacia
producción por coincidencia de versiones. Las restricciones de prototipos SAG
y de la migración Community se conservan; esta regla no publica prototipos.

La ampliación actual de T138 incluye expresamente QA-Cerro con `payroll-days`,
mismo paquete y versión 18.0.1.2.0 que ya se verificó en Cerro. Se conserva
deploy_enabled=false para promociones genéricas; los gestores incorporan cada
tipo de paquete conforme a su alcance, sin habilitar instalaciones arbitrarias.
Comprobar los módulos de la entrega con
`python tools/ops/verify_cerro_release_pair.py --module nombre_del_modulo` en
el servidor; compara estado instalado, versión y hash del código efectivo.
No anunciar paridad de todos los addons por haber comprobado solo un módulo.

T138 autoriza `payroll-days` en Desarrollo, SyS, Demo-SYS, Cerro y QA-Cerro:
inasistencias injustificadas de contratos mensuales que cubren el mes completo,
base de 30 días menos faltas. Conservar licencias, contratos parciales, atrasos
y liquidaciones almacenadas. Probar los casos reportados por cálculo nativo en
copia de SyS; no recalcular recibos reales ni históricos al publicar. Demo-SYS
exige el alcance instalado de SyS, sin addons adicionales. Mismo paquete en
copias frescas de cada destino, respaldo, bloqueo y overlays privados.

T137 amplía `packing-stock` en Desarrollo, Cerro y QA-Cerro para admitir las
tarjas E/N ya validadas de la misma OT que aún no tienen existencias ni
movimientos. La validación de la tarja no genera inventario. Conservar las
validaciones de origen, empresa, productor, variedad, balance, reservas y
materiales; impedir reutilizar tarjas con stock o historial de movimiento.
Prueba en copias frescas, mismo paquete, respaldo y bloqueo. No validar ni cerrar
la OT real del cliente durante el despliegue ni cambiar la definición de sus
productos sin resolver el dato pendiente. QA mantiene ejercicios y aislamiento.

T132/T133/T134 amplían `reception-revision` en Desarrollo, Cerro y QA-Cerro:
envases físicos independientes del peso, detalle de tarjas, selector de Packing,
informes que consultan stock/recepciones nativos y encabezado de proceso.
Convertir los cuatro campos de los prototipos de QA en el sitio, con IDs y datos
conservados y vistas originales archivadas. No refrescar capacitación ni crear
maestros paralelos. La divergencia de fecha nativa/prototipo de una OT requiere
la decisión humana solicitada antes de cambiar el valor nativo. Se pueden
adoptar ambos campos conservando los dos valores mientras se espera. Copias frescas, mismo
paquete, respaldo y bloqueo compartido; no simular una entrega con Studio.


T128 y T135 autorizan `payroll-review` exclusivamente en Desarrollo y SyS:
mensajes con trabajadores y contratos pendientes, y validación de entradas del
período local del lote. No confirmar parámetros, corregir asistencias ni calcular
nómina real durante la publicación. Probar el asistente en copias frescas,
conservar las liquidaciones históricas y publicar el mismo paquete con respaldo
y bloqueo compartido. SyS continúa con Simple Digital.


T131 amplía `company-form` en Desarrollo, Cerro y QA-Cerro para corregir la
validación del contacto generado al crear sucursales nativas. La respuesta
humana 9790 y el adjunto 3432 permiten reproducir la validación del cliente web.
No modificar la obligatoriedad ORM del contacto ni crear sucursales reales
durante la verificación. Exigir copias frescas, mismo paquete, respaldo, bloqueo
y preservación de la capacitación y aislamiento de QA-Cerro.

T130 autoriza `company-form` en Desarrollo, Cerro y QA-Cerro para recuperar
el formulario completo de Ajustes / Empresas. Se conservan los formularios
específicos de Folios y Bodega Packing, los datos y los permisos. Copia fresca
de cada destino, paquete idéntico, respaldo y bloqueo; no refrescar QA-Cerro.

El 28-10-2026 el usuario autorizó `manual-contact` en Cerro y QA-Cerro para
crear proveedores sin el aviso de créditos del autocompletado IAP. Se revisa
primero en Desarrollo y se exige copia fresca de cada destino, paquete idéntico,
respaldo y bloqueo. Se conserva la búsqueda local, permisos, contactos y datos
de capacitación; no se compran créditos ni se refresca QA-Cerro.

T127 autoriza `product-bpa` en Desarrollo, Cerro y QA-CERROELPLOMO. El
28-10-2026 el usuario confirmó implementar como producto Community los campos
y el maestro BPA heredados de Studio. El núcleo depende solo de Product y Mail;
el puente reutiliza los maestros agrícolas actuales. Migrar en el sitio, con
IDs, relaciones, textos, fechas e historial conservados. QA-Cerro mantiene sus
ejercicios y aislamiento; no se refrescan datos ni se retira Enterprise.
Exigir copias frescas, paquete idéntico, respaldo y bloqueo compartido.

El 27-10-2026 el usuario autorizó reemplazar las cinco acciones de informes de
Tesorería por alternativas Community y desplegar el paquete en QA-Cerro para
probar, sin modificar producción. Esta autorización es específica de
`step_treasury_community_reports` y la extracción contable que necesita.
`tools/community/manage_community_reports.py` solo publica en Desarrollo y
QA-Cerro, exige pruebas del mismo paquete en Community, copia fresca de Cerro
y copia fresca del destino, ausencia de cambios concurrentes, respaldo y bloqueo.
No refresca QA-Cerro, no retira Enterprise, no asigna perfiles ni altera
vencimientos. La revisión inicial continúa en Desarrollo. El registro conserva
`deploy_enabled=false` para promociones genéricas de QA-Cerro.

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


## Ampliación de capacidad autorizada — 28-10-2026

El usuario autorizó explícitamente ampliar odoo-data-balanced-20260923 de 100
a 150 GiB, con respaldo verificado y bloqueo compartido. Se completó en odoo-new
(stepsconsulting/us-central1-c): dumps SyS/CERRO_EL_PLOMO totalmente decodificados,
snapshot odoo-data-pre150-20261028-205103 READY y ext4 ampliado en línea.
Sin DML de negocio, reinicio, cambio de credenciales o particionado.
Prueba privada: /opt/steps-validation/community-payroll-disk-resize-20261028/
proof.json y resize.py, verificables con tools/community/summarize_payroll_api.py.
No repetir la operación ni interpretar esta autorización de infraestructura como
permiso para desplegar cambios de negocio en producción o refrescar QA-Cerro.
Ver COMMUNITY_SYS_REFERENCE.md para paquete F y alcance pendiente.

## Tickets 141 y 144 — 30-10-2026

La respuesta humana 9868 reabre T141 para imprimir el folio nativo en el título
“RECIBO DE RECEPCIÓN N° …”. Mismos destinos y controles de reception-report.

T144 (mensaje 9881, adjunto 3449) autoriza packing-company en Desarrollo, Cerro
y QA-Cerro: conservar la compañía nativa de las tarjas E/N según su OT, incluso
sin existencias. Completar únicamente compañías vacías de tarjas vinculadas;
rechazar contradicciones con stock u origen. Preservar ubicación, cantidades,
estados, IDs y entrenamiento. Mismo paquete, copias frescas, respaldo, bloqueo,
paridad y aislamiento. No crear existencias ni validar OT reales.
