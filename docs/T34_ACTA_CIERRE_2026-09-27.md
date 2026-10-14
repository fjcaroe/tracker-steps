# T34: cierre de «Instalar módulos Studio» en Desarrollo

**Fecha:** 27 de septiembre de 2026
**Ticket:** [T34](https://soporte.stepsapp.cl/helpdesk/ticket/34)
**Entorno:** Desarrollo, `https://desarrollo.stepsapp.cl/odoo`, base `LAB_TAREAS` y servicio `odoo18-dev`
**Código:** rama `ticket/34-packing-fruta-app`, [PR #6](https://github.com/fjcaroe/tracker-steps/pull/6) en borrador

## 1. Alcance solicitado y alcance contrastado

La solicitud pide instalar en Desarrollo las aplicaciones Studio de
`https://admin.stepsapp.cl/odoo`. La imagen adjunta del ticket muestra cuatro
aplicaciones: **Packing Campo, Aserradero, Packing Fruta y Exportaciones**. En
Admin, todas están en la base `steps_qa`, con los menús raíz 1814, 1570, 1083 y
998, y ninguna tenía restricción de grupo.

El 23 de septiembre se decidió no copiar el bloque `studio_customization` de
`steps_qa`. Esa copia habría borrado 2.328 registros Studio propios de
Desarrollo y habría chocado con 24 modelos que tienen el mismo nombre técnico.
Las apps se convirtieron a módulos con código, versionados e instalables en
otras instancias (opción C).

Antes de cerrar, las cuatro apps de Admin se compararon con lo que había
realmente en Desarrollo:

| App en Admin (Studio) | Estado en Desarrollo antes de hoy | Faltante real |
|---|---|---|
| Packing Campo | App `step_packing` 18.0.1.0.0 | Sin etapas: la etapa es obligatoria y no se podía crear ningún registro. Sin ícono. |
| Packing Fruta | **No existía como app**; solo «Recepción a Granel» dentro de Packing Campo | App completa: recepción de fruta, reserva de stock, fabricación, movimientos, traslado de lotes, inspecciones, despacho y configuración. |
| Exportaciones | App `step_export` 18.0.2.2.0 (ampliada por T35) | Nada propio de T34. Sus piezas de Packing Fruta no tenían dónde mostrarse. |
| Aserradero | App `step_sawmill` 18.0.1.0.0 | Solo la veía `admin`, mientras que en Studio la veían todos los usuarios internos. Sin ícono. |

Las ampliaciones de Exportaciones hechas en T35 (programas de venta, packing
list, liquidaciones, parámetros contables) **no se modificaron**. Solo se
subió la versión de `step_export` a 18.0.2.3.0 para colgar cuatro menús en
Packing Fruta.

## 2. Qué se entregó

### Packing Fruta (`step_packing` 18.0.1.1.0)

App nueva con el ícono y la estructura de la app Studio:

- **Planificación → Estimaciones**: estimación de cosecha de `step_export`.
- **Recepciones → Recepción fruta**: traslados de entrada. **Recepciones → Recepción a Granel**: se movió aquí desde Packing Campo, como estaba en Studio. **Recepciones → Reservar Stock**: `step_export`.
- **Operaciones**: Orden de fabricación, Movimiento stock y Traslado lotes.
- **Inspecciones**: Inspección SAG, Inspección USDA y Control de temperatura.
- **Despacho**: Orden de despacho (`step_export`) y Despacho (traslados de salida).
- **Configuración**: Productor - Fundo, líneas y tipos de proceso, tarjas, detenciones y causas de corrección. También especie, grupo de variedad, variedad, categoría, clase y calibres, además de actividades, labores y naves.

En Studio, la «Recepción fruta» y el «Despacho» eran traslados estándar de
Inventario con campos agregados. Esos campos se portaron a una pestaña
**Fruta** del traslado:

- **Origen:** productor/fundo, especie, variedad (filtrada por especie),
  categoría, clase de origen, tipo de fruta y temporada.
- **Recepción:** lote, fecha de cosecha, número de guía, tipo de pesaje y
  contrato del productor.
- **Flete:** si paga flete, transportista, patente del camión, tramo y tarifa.
- **Detalle de tarjas:** número de tarja, embalaje, calibre, categoría,
  marca/etiqueta, cantidad, kilos y unidad, con totales.

La orden de fabricación recibe una pestaña **Fruta** con los datos de
cabecera que tenía Studio: tipo de proceso, turno, tipo de fruta, productor,
fundo, especie, variedad y variedad comercial. También incluye cliente de
servicio, recibidor, embarque y pedido.

### Packing Campo y Recepción a Granel

- Se cargaron las mismas etapas de Studio: **Nuevo, En progreso, Listo**. Un
  registro nuevo parte en la primera etapa.
- Se agregó el ícono original de Studio.

### Aserradero (`step_sawmill` 18.0.1.0.1)

- Se agregó el ícono original de Studio.
- Se configuró el acceso en Desarrollo (ver sección 5).

### `step_packing_batch` 18.0.1.0.0 (nuevo)

Agrega **Operaciones → Traslado lotes** a Packing Fruta. Es un módulo puente
con instalación automática cuando están `step_packing` y
`stock_picking_batch`.

## 3. Por qué se implementó así

- **Módulos y no una copia de Studio:** la copia habría borrado la
  personalización Studio que ya usa Desarrollo. Los módulos se versionan, se
  prueban y se pueden instalar en otras instancias.
- **Packing Fruta dentro de `step_packing`:** esa app agrupa objetos de
  Packing, Inventario y Fabricación. `step_packing` sigue siendo instalable sin
  Exportaciones. Si `step_export` está instalado, agrega sus propias piezas al
  mismo menú.
- **Traslado lotes en módulo aparte:** Cerro El Plomo tiene `step_packing`
  instalado sin `stock_picking_batch`. Si se agregaba como dependencia
  directa, la próxima actualización habría instalado un módulo que esa empresa
  no usa.
- **Recepción fruta y Despacho con filtro:** en Studio ambos menús abrían
  *todos* los traslados. Aquí «Recepción fruta» muestra solo entradas y
  «Despacho» solo salidas. Es el comportamiento que indica el nombre del menú.
  No se agregó ninguna automatización que Studio no tuviera.
- **Qué no se portó:** las grillas de costeo que Studio había agregado a la
  orden de fabricación (mano de obra, maquinaria, servicios, materia prima)
  tenían un solo registro de uso y duplican el costeo de Gestión y Costos.
  Tampoco se portaron los menús vacíos «Packing» y «Otros Procesos», porque
  Studio no tenía contenido en ellos.

## 4. Pruebas y resultados

**Copia aislada** `T34_PACKING_FRUTA_TEST` de `LAB_TAREAS`, con filestore,
cron y correo saliente desactivados:

- Actualización de `step_packing`, `step_export`, `step_sawmill` e instalación
  de `step_packing_batch`: sin errores.
- **33 pruebas automáticas, 0 fallas y 0 errores.** Cubren los menús y el
  ícono de Packing Fruta, la visibilidad según permisos y el flujo de
  recepción de fruta (creación con datos de fruta y tarjas, confirmación y
  validación). También cubren que la recepción aparezca en «Recepción fruta»
  y no en «Despacho», la copia y el borrado de las tarjas, el bloqueo a
  usuarios sin Inventario, los datos de fruta en fabricación, la carga de
  vistas, las etapas por defecto, los menús de Exportaciones en Packing Fruta
  y las 15 pruebas previas de Aserradero.

**Recorrido funcional**, en la copia y después en `LAB_TAREAS` real. Se usó
el administrador `fcaro.ruiz@gmail.com`, un operador con Inventario,
Fabricación, Ventas y Aserradero, y un usuario interno sin rol de
administrador. Cada perfil abrió cada menú de las 4 apps.

| App | Menús con acción | Vistas cargadas por usuario | Registro de prueba |
|---|---|---|---|
| Packing Campo | 31 | 62 | Proceso creado en etapa «Nuevo»; Recepción a Granel en «Nuevo» |
| Packing Fruta | 31 | 77 | Recepción validada (estado Hecho), con fundo, lote, guía y 100 kg en tarjas; visible en «Recepción fruta» |
| Exportaciones | 33–35 | 65–69 | Estimación creada en etapa «Borrador» |
| Aserradero | 18 | 35 | Orden de producción y Aserrío autorizado |

- Los datos de prueba se revirtieron y no quedaron residuos (0 usuarios y 0
  traslados de prueba). La única huella es que el Aserrío de prueba consumió
  el correlativo `ASE-00009` en Desarrollo: las secuencias de Odoo no
  retroceden.
- Las 4 apps quedaron visibles, con ícono, para los 7 usuarios internos
  activos de Desarrollo.
- El servicio `odoo18-dev` quedó activo. `http://127.0.0.1:8075/web/login` y
  `https://desarrollo.stepsapp.cl/web/login` respondieron HTTP 200, sin
  errores en el log posterior al reinicio.
- La revisión visual en el navegador depende de una sesión en Desarrollo. Esta
  corrida no escribió contraseñas y el servidor no tiene Chrome para pruebas
  de interfaz. Por eso la interfaz se validó en el servidor, con las mismas
  llamadas que hace el cliente web para abrir cada vista, como cada uno de los
  tres perfiles.

**Versiones finales en `LAB_TAREAS`:** `step_packing` 18.0.1.1.0,
`step_packing_batch` 18.0.1.0.0, `step_export` 18.0.2.3.0 y `step_sawmill`
18.0.1.0.1. No cambió ningún otro módulo `step_*`; la huella de antes y
después está en el respaldo.

## 5. Parámetros que el administrador puede cambiar

| Parámetro | Dónde | Valor actual en Desarrollo | Cuándo cambiarlo |
|---|---|---|---|
| Acceso a Aserradero | **Ajustes → Usuarios y compañías → Usuarios →** *usuario* **→ Aserradero** | *Responsable*: admin, fcaro.ruiz@gmail.com, fernandocaro1198@gmail.com, grobles@blueminds.cl y luis.sepulveda@asesoressys.cl, los administradores del sistema. *Usuario*: contacto@stepsapp.cl y jamie.escalante7@gmail.com. | Al crear un usuario que deba usar Aserradero, porque no lo recibe automáticamente, o para quitar el acceso. El *Responsable* puede reabrir registros valorizados. |
| Etapas de Packing Campo | **Packing Campo → Configuración → Packing Campo (etapa)** ([abrir](https://desarrollo.stepsapp.cl/odoo/action-2025)) | Nuevo, En progreso, Listo | Si el proceso usa otras etapas. Un registro nuevo parte en la etapa de menor secuencia. |
| Etapas de Recepción a Granel | **Packing Fruta → Configuración → Recepción a Granel → Etapas** ([abrir](https://desarrollo.stepsapp.cl/odoo/action-2026)) | Nuevo, En progreso, Listo | Igual que el caso anterior. |
| Quién ve Recepción fruta, Despacho, Movimiento stock y Traslado lotes | Ficha del usuario → **Inventario** | Requiere *Inventario: Usuario* o superior | Si un usuario de packing debe registrar recepciones o despachos. |
| Quién ve Orden de fabricación | Ficha del usuario → **Fabricación** | Requiere *Fabricación: Usuario* o superior | Si un usuario debe registrar procesos de fabricación. |
| Tipos de operación de la recepción | **Inventario → Configuración → Tipos de operación** | «Recepción fruta» muestra todos los tipos de entrada; «Despacho», todos los de salida | Opcional. Crear un tipo de operación propio, como *Recepción fruta granel*, sirve para numerar las recepciones de fruta aparte. Luego se puede filtrar por ese tipo en la lista. |

Enlaces directos en Desarrollo:
[Recepción fruta](https://desarrollo.stepsapp.cl/odoo/action-2048),
[Despacho](https://desarrollo.stepsapp.cl/odoo/action-2049),
[Packing Campo](https://desarrollo.stepsapp.cl/odoo/action-2027),
[Estimaciones](https://desarrollo.stepsapp.cl/odoo/action-1996) y
[Órdenes de producción de Aserradero](https://desarrollo.stepsapp.cl/odoo/action-1965).

## 6. Respaldo y despliegue

- Respaldo previo en `odoo-new`:
  `/opt/steps_backups/ticket34_packing_fruta_dev_20260927T195016Z/`.
  Contiene `LAB_TAREAS.dump` (22 MB), `modules_before.tgz` con el código
  anterior de los 3 módulos, `SHA256SUMS`, el estado del servicio y los
  módulos antes y después, el log de actualización, el cambio de accesos de
  Aserradero y el resultado de la verificación.
- Servicio: antes, PID 3951235 activo desde 06:40:30 UTC; después, PID 4017568
  activo desde 19:51:27 UTC.
- Árbol de addons: `/opt/dev_odoo18/odoo_agriculture`. Ese árbol también lo
  leen `karo_consultorias` y `Everfruit`, pero ninguna de esas bases tiene
  `step_packing`, `step_export` ni `step_sawmill` instalados, así que no las
  afecta.
- **No se modificaron** SyS, Demo, Demo-SyS ni Cerro El Plomo: tienen árboles
  de addons propios. Llevar Packing Fruta a esos entornos es una decisión
  aparte.
- Commits: `956754d` (Packing Fruta, íconos y módulo puente), `888010f`
  (etapas) y la integración de la rama de Aserradero `de856bf`.

## 7. Límites

- Packing Fruta replica lo que Studio capturaba. Studio no tenía cálculos ni
  automatizaciones en esos modelos, y no se inventaron: por ejemplo, la
  recepción no crea tarjas de inventario automáticamente. Si se necesitan,
  corresponde abrir un ticket nuevo.
- Los menús de Exportaciones y los procesos que en Studio eran solo un nombre
  sin campos siguen con el alcance que fijó T35.
- Queda como mejora aparte, sin bloquear T34, desacoplar `step_packing` y
  `step_export` de `step_hr` para Fundo, Especie, Variedad y Temporada.
