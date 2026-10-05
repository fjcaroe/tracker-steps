# Asistente Steps para consultas de usuarios

## Producto y entrega

Addons nuevos para **Odoo 18**, independientes de Web Tracker y Steps Móvil.
Base de desarrollo: `origin/develop`, referencia por defecto del repositorio;
rama de entrega: `codex/odoo-support-chatbot`. No se reemplaza código de otros
productos ni se despliegan sus ramas. Primera instalación: Desarrollo,
`LAB_TAREAS`, servicio `odoo18-dev.service`.

## Uso

Abrir el globo **Ayuda** en la esquina inferior derecha de cualquier aplicación,
el icono de la barra superior o **Ayuda Steps → Consultar al asistente**.
El globo no carga ayuda ni llama a OpenAI hasta abrirlo. Cerrar y reabrir conserva
la conversación en memoria; recargar la página la elimina.
Escribir aplicación, tarea y mensaje de error. Enter envía;
Shift+Enter agrega una línea. **Nueva consulta** limpia la conversación.
Las preguntas anteriores se mantienen solo mientras está abierta la pantalla;
no se guarda el contenido del chat en una tabla ni en el almacenamiento del
navegador. El asistente incluye las fuentes y citas literales utilizadas.

También se puede consultar la biblioteca sin habilitar IA. El enlace de
soporte abre `https://soporte.stepsapp.cl`; no envía mensajes ni crea tickets.

## Fuentes y alcance

- `step_support_assistant` instala ocho guías verificadas: alcance del
  asistente, reporte de problemas, permisos y cuatro procesos de Colaciones.
  Las guías de Colaciones se ofrecen solo si el módulo está instalado y el
  usuario tiene permiso de lectura en sus registros.
- **Artículos de ayuda** permite redactar y mantener instrucciones propias.
  Los editores revisan los pasos y marcan **Aprobado para el asistente**.
  Un artículo puede limitarse por compañía, grupos, módulo instalado y ACL
  de un modelo. Nunca publicar secretos, respaldos, datos personales ni
  instrucciones internas de infraestructura como ayuda de usuarios.
- `step_support_assistant_knowledge` conecta la aplicación **Conocimiento**
  cuando está instalada. En **Conocimiento aprobado** un editor selecciona
  artículos y autoriza su uso. No se indexa toda la base automáticamente.
  Los permisos originales, archivos, bajas y cambios del artículo se vuelven
  a comprobar en cada consulta. El contenido no se copia a una guía pública.
  Se usa únicamente su cuerpo de texto; no se leen adjuntos, documentos de
  negocio, widgets ni artículos hijos. Se excluyen plantillas y papelera.

Las fuentes incluyen la compañía **actual** y guías compartidas, no todas las
compañías autorizadas simultáneamente. Las fuentes de Conocimiento se leen
con el usuario conectado, sin `sudo`. El único uso elevado allí obtiene los
IDs y restricciones de las aprobaciones; nunca sus cuerpos originales.

La búsqueda ordena coincidencias de título, palabras clave y contenido. Envía
hasta cinco artículos de un máximo de 12.000 caracteres cada uno. Para textos
más largos en Conocimiento usa los primeros 12.000 caracteres: conviene
separar procedimientos en artículos específicos. Una pregunta nueva cambia
el tema; las dos preguntas previas ayudan únicamente con referencias como
«¿y luego?».

La IA recibe instrucciones de responder únicamente sobre nuestra instalación
y basarse en estas fuentes. Debe indicar insuficiencia de evidencia o fuera de
alcance cuando corresponda. El servidor valida estructura, IDs autorizados y
citas literales; rechaza citas inventadas y respuestas incompletas. Estas
verificaciones no demuestran automáticamente que cada afirmación sea correcta:
hay que revisar las fuentes y evaluar consultas reales antes de ampliar el uso.
El asistente es de consulta y no ejecuta acciones que modifiquen operaciones.

## Consultas de datos reales (sin API)

**Consultar datos reales** ofrece únicamente aplicaciones presentes y legibles
con los permisos del usuario: asientos, facturas, pagos, ventas, compras,
transferencias de inventario, fabricación, tareas, Colaciones, flujos de
Tesorería y proformas de proveedores. Es un catálogo explícito y extensible;
no abre todos los modelos arbitrariamente. No incluye sueldos, RUT, contactos,
contraseñas, adjuntos ni notas privadas.

Las consultas usan el ORM sin elevar permisos, ACL, reglas de registros y
permisos de campos, restringidas a la compañía actual incluso si hay varias
compañías seleccionadas. No aceptan modelos, SQL, dominios ni acciones del
usuario/modelo de IA. La referencia, fechas y campos admitidos son fijos.
Cada búsqueda devuelve como máximo veinte registros, con estado, fecha,
importes/moneda cuando corresponde y enlace al documento. No suma monedas ni
presenta una lista recortada como total. Las relaciones también requieren
permiso antes de mostrar su nombre.

Los saldos requieren el código exacto de una cuenta visible de la compañía.
Suman Debe, Haber y saldo de líneas de asientos **publicados**, excluyendo
borradores y respetando reglas de registros. Sin inicio son acumulados hasta
la fecha final (hoy si se omite); con inicio representan el movimiento neto
del período, sin apertura. Se expresan en moneda de la compañía e informan
que permisos parciales pueden mostrar solo parte del libro contable.

Ejemplos: `últimos asientos`, `facturas desde 2026-09-01 hasta 2026-09-30`,
`saldo cuenta 110101 hasta 2026-09-30`. El reconocedor local es conservador:
no interpreta filtros libres por cliente/proveedor/estado ni fechas escritas
como «septiembre»; pide usar el formulario o la aplicación correspondiente.
Para referencias de documentos usar el campo del formulario o `referencia`.

**Los registros de negocio no se envían a OpenAI.** Se consultan, calculan y
formatean dentro de Odoo, sin consumir tokens y aunque la IA esté desactivada.
La generación con IA se reserva a ayuda documental. Sin consultas de IA no
hay llamadas, tareas periódicas, embeddings ni almacenes remotos en esta
implementación. La facturación de la API depende de los tokens utilizados:
[precios oficiales](https://developers.openai.com/api/docs/pricing).

## Configuración y secretos

La clave se toma **solo** de `OPENAI_API_KEY` en el entorno del proceso servidor.
No hay campo para escribirla en Odoo, parámetro almacenado en la base, clave
en JavaScript ni variable `VITE_*`. La solicitud usa un destino HTTPS fijo,
sin seguir redirecciones, y no registra errores del proveedor que puedan
contener autorización o preguntas.

Crear la clave mediante el selector seguro de OpenAI Platform y confirmar
su destino local antes de escribirla. Luego configurar un archivo privado
de entorno exclusivo para Desarrollo, por ejemplo
`/etc/steps/assistant-dev.env`, propiedad de root, modo 0600, y un drop-in de
`odoo18-dev.service` con `EnvironmentFile=`. No agregar ese archivo a Git ni
imprimir su contenido. Reiniciar solo ese servicio después de configurar el
archivo. Crear/configurar la clave requiere completar el flujo seguro de
selección de cuenta, proyecto y destino; la autorización general del desarrollo
no define esos valores.

En **Ayuda Steps → Ajustes**, administradores del sistema pueden habilitar
IA, seleccionar modelo y fijar límites. Predeterminados:

| Parámetro | Valor |
|---|---|
| Respuestas con IA | Desactivadas al instalar |
| Modelo | `gpt-4.1-mini` |
| Consultas por usuario por hora | 20 |
| Consultas por base por día UTC | 500 |
| Tiempo de conexión/lectura de OpenAI | 5/30 segundos |
| Máximo de tokens de respuesta | 1.800 |

Las preguntas y fragmentos permitidos se envían a OpenAI mediante Responses
con `store=false`. Esto desactiva el almacenamiento de la respuesta en esa
API; no constituye una garantía de retención cero por parte del proveedor.
Se usan [salidas estructuradas](https://developers.openai.com/api/docs/guides/structured-outputs),
compatibles con [GPT-4.1 mini](https://developers.openai.com/api/docs/models/gpt-4.1-mini).
La interfaz informa del envío y pide evitar contraseñas y datos personales.

El consumo registra únicamente usuario, compañía, fecha, estado y tokens;
solo administradores del sistema pueden leerlo. Se elimina automáticamente
después de 30 días mediante autovacuum. Las reservas se serializan con un
bloqueo transaccional PostgreSQL para aplicar el límite entre workers. Esta
primera versión mantiene el bloqueo durante la petición: con mucho tráfico
habrá que mover la generación a una cola antes de subir los límites.

## Validación e instalación

Pruebas locales sin Odoo:

```powershell
python -m unittest discover -s tools/chatbot -p test_core.py -v
node --check step_support_assistant/static/src/assistant.js
python tools/chatbot/build_release.py
```

El empaquetador valida Python/XML y genera el archivo en el directorio temporal
del sistema, fuera del checkout, incluyendo únicamente extensiones permitidas
de los dos addons. Imprime su SHA-256; no incluye claves ni configuración.

`tools/chatbot/preflight.sh` verifica servicio, rutas, módulos y operaciones
pendientes sin mostrar configuración privada. `test_odoo.sh` instala y prueba
ambos addons en `STEPS_ASSISTANT_TEST_20261005`, creada vacía, con archivos de
datos y código propios en `/opt/steps-assistant-validation`. Las pruebas
mockean OpenAI; no requieren clave ni envían datos al proveedor.

Validación del 05-10-2026 UTC: 15 pruebas locales de búsqueda/respuestas y
20 casos funcionales de Odoo (11 de ayuda, 4 de datos y 5 de Conocimiento) pasaron.
Se verificaron aislamiento entre compañías, grupos, borradores, archivos,
revocación de permisos, límites y rechazo de citas inventadas. Las llamadas
del proveedor están simuladas: falta prueba real de IA hasta configurar la clave.

```bash
bash /tmp/test_odoo.sh /tmp/steps_assistant_release.tar.gz <SHA256>
```

Tras revisar un resultado de pruebas correcto, `deploy_dev.sh`:

1. Comprueba SHA-256, servicio y ausencia de módulos pendientes.
2. Respalda `LAB_TAREAS` y versiones anteriores de ambos addons en
   `/opt/backups/steps-assistant-dev-<fecha>`.
3. Muestra un dry-run y copia únicamente los nuevos addons sin borrar archivos.
4. Instala/actualiza esos dos addons, reinicia solo Desarrollo y verifica HTTP.

```bash
bash /tmp/deploy_dev.sh /tmp/steps_assistant_release.tar.gz <SHA256>
```

Transferir también `tools/chatbot/validate_assets.py` junto a `deploy_dev.sh`.
El despliegue compila los estilos con el libsass del servidor antes de copiarlos
y espera la disponibilidad HTTP después del reinicio. Las unidades de alto
en `vh` se limitan mediante `max-height`, compatible con el compilador de Odoo.

Por autorización del usuario se despliega además a Demo, Demo-SyS, Cerro El
Plomo y producción Steps. `deploy_environment.sh` reemplaza el script específico
de Desarrollo para esta entrega. `environments.sh` es la lista explícita de
cinco destinos; SyS real es un servicio diferente y no está incluido.
`preflight_all.sh` revisa estado y módulos de todos antes de modificar código.
Se respalda cada base y los dos directorios, se comprueba el SHA, se compila
SCSS y se instala/actualiza solo el asistente. El puente se instala únicamente
donde Conocimiento ya está instalado. No se instala Conocimiento por arrastre.
El script usa el usuario y Python del servicio, lo detiene durante la
actualización y vuelve a iniciarlo también ante error. Los respaldos permiten
revisión/recuperación; no hay restauración destructiva automática.

```bash
bash /tmp/deploy_environment.sh <desarrollo|demo|demo-sys|cerroelplomo|produccion> /tmp/steps_assistant_release.tar.gz <SHA256>
```

Producción Steps y Desarrollo comparten el directorio de addons. El respaldo
de Desarrollo preserva la versión anterior de ese directorio compartido;
cada base se actualiza por separado. El Python de producción es su venv.
Probar luego chat, apertura de fuentes, pantalla pequeña, permisos y consultas sin evidencia.
Después de configurar la clave, ejecutar consultas reales y casos de intento
de cambio de tema/instrucciones antes de activar el acceso general.

Para revertir la entrega, desactivar IA desde Ajustes y restaurar el código
respaldado. Si es necesaria restauración de la base, revisar primero el respaldo
y los cambios posteriores; no restaurarla automáticamente, pues reemplazaría
operaciones hechas después del despliegue.

## Evidencia de instalación del 05-10-2026 UTC

- Ambos addons instalados en Desarrollo, versión `18.0.1.0.0`; siete guías
  activas y aprobadas. La IA sigue desactivada y pendiente de configuración
  segura de la clave. No se hicieron llamadas reales a OpenAI.
- Código de producto desplegado: commit `847eea2`, paquete SHA-256
  `04d4c9637380c801cd6453864a70adb54effd4022a25a284b9e53a24795cf0cb`.
- Respaldo final: `/opt/backups/steps-assistant-dev-20261005T003944Z`.
- Postflight: módulos `installed`, servicio activo y `/web/login` responde.
  `tools/chatbot/postflight.sh` conserva la verificación reproducible.
- Navegador: chat visible, consulta de Colaciones muestra fuentes relacionadas,
  apertura del artículo correcta y consulta sobre capitales sin respuesta general.
- Móvil 390 × 844: ancho de documento 390 px; ancho y scrollWidth del asistente
  375 px; scroll vertical del asistente cambia de 0 a 588 px. Se restauró el
  tamaño normal del navegador.
- El registro de inicio de Desarrollo advierte que falta el addon instalado
  `steps_api`. Estos cambios no incluyen ni modifican ese addon. La advertencia
  no impidió cargar y probar Ayuda Steps; su revisión corresponde al producto
  móvil y no se considera resuelta por esta entrega.
- [PR draft #18](https://github.com/fjcaroe/tracker-steps/pull/18), hacia `develop`.

Para finalizar la activación todavía se debe completar la selección segura de
cuenta/proyecto de OpenAI, confirmar dónde se escribe la clave, instalarla en
el entorno privado del servicio y probar la generación real y los intentos de
salir del alcance. Los artículos existentes de Conocimiento requieren aprobación
explícita del editor antes de usarlos; no se publicaron automáticamente.
