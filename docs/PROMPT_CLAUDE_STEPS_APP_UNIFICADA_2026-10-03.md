# Encargo para Claude: una aplicación móvil Steps, administrada desde Odoo

Fecha: 03-10-2026. Producto propuesto: **Steps**, para Android, iOS y acceso web compatible.

## Instrucción principal

Construye la estructura funcional de una aplicación Steps que reúna los procesos móviles de nuestros productos. Odoo debe permitir administrar personas, empresas, roles y módulos disponibles. Empezaremos con Colaciones y conductores de Movilización; integraremos Tracker conservando su funcionamiento y sus datos. Otros módulos se incorporarán gradualmente.

Trabaja sobre el código existente: audita qué está implementado, qué solo está documentado y qué necesita adaptación. Entrega código ejecutable, pruebas, documentación y commits publicados. Una pantalla de botones sin autenticación, administración ni un flujo completo no constituye la entrega.

Claude se encarga de arquitectura, backend, integración Odoo, autenticación, almacenamiento, sincronización y una interfaz funcional. Después GPT/Astra trabajará la presentación visual sobre contratos estables. Este encargo define el nuevo producto y su piloto; publicar en las tiendas o sustituir instalaciones actuales requiere una etapa de lanzamiento específica.

## 1. Decisión de producto

Queremos **una app Steps con módulos**, una sesión personal y una portada que muestre las tareas y herramientas habilitadas para esa persona y empresa. El administrador asigna accesos desde un módulo Odoo llamado, provisionalmente, «Steps App».

El menú de Odoo de la captura sirve como inventario de dominios. No implica trasladar cada aplicación de escritorio al teléfono. Cada módulo móvil debe resolver tareas concretas: registrar, consultar, aprobar, escanear, fotografiar o ejecutar una jornada.

Separar tres conceptos:

- **Identidad:** quién inició sesión, aunque todavía no pertenezca a una empresa.
- **Membresía y autorización:** en qué empresas participa, con qué rol y qué acciones puede realizar.
- **Dispositivo:** desde dónde opera; un teléfono personal y un tótem compartido requieren credenciales y reglas diferentes.

Una persona recién registrada verá su estado de incorporación y podrá aceptar una invitación o solicitar acceso. Registrarse con Google no entrega permisos sobre empresas, empleados, pasajeros o colaciones.

## 2. Fuentes existentes y ramas

Repositorio principal: [fjcaroe/tracker-steps](https://github.com/fjcaroe/tracker-steps).

| Producto | Fuente y situación verificada | Acción |
| --- | --- | --- |
| Steps Móvil / Tracker | `origin/codex/steps-movil`; `mobile/` contiene React, TypeScript, Vite y Capacitor 7. Configuración actual: `cl.stepsapp.movil`, nombre Steps Móvil. | Base inicial del cliente; conservar jornadas, GPS, historial y datos pendientes. |
| Colaciones Odoo | `step_colaciones/`, `docs/API_COLACIONES.md` y `docs/COLACIONES_WEB_Y_APP_MOVIL.md`, disponibles en la rama de mantenimiento `codex/cierre-cambios-locales`. | Revisar implementación y contrato de captura; no confundir permisos de tótem con los de una persona. |
| Proyecto móvil de Colaciones | [steps_colaciones_mobile](https://github.com/fjcaroe/steps_colaciones_mobile), rama por defecto `develop`. En la raíz consultada hay README y documentación; no se comprobó una app compilable. | Inventariar antes de prometer reutilización. El documento del monorepo también menciona una PWA `web/`: localizar su código real y rama. |
| Movilización Odoo | `step_mobilization/`, especialmente `controllers/mobilization_api.py` y modelos de dispositivos de conductores. | Reutilizar dominio, asignaciones y eventos; adaptar acceso personal sin debilitar permisos existentes. |
| Web Tracker | `origin/codex/web-tracker-redesign`; tiene su propio despliegue y PR draft hacia `develop`. | Mantener su ciclo de entrega; no usar su rama como base accidental del móvil. |

Los archivos de Odoo y los del cliente no necesariamente están presentes en la misma rama. Consultar el árbol y el historial, comparar versiones e integrar commits concretos. No fusionar ramas completas de productos distintos para conseguir un archivo.

Leer `AGENTS.md`, `CLAUDE.md`, `docs/WORKFLOW_GIT_COMPARTIDO.md` y las instrucciones dentro de cada producto. Obtener `origin` actualizado, inventariar worktrees y partir de la base correcta. Crear un worktree propio. Proponer una rama de integración para la app unificada, derivada de `origin/codex/steps-movil`, evitando convertir el piloto incompleto en la versión productiva vigente.

La implementación de transporte de personas de `step_mobilization` y las jornadas/GPS de maquinaria de Tracker son dominios distintos. Pueden compartir sesión, componentes y mecanismos de cola; sus reglas de negocio y permisos permanecen explícitos.

### Revisión pendiente de la PR #15

[PR #15](https://github.com/fjcaroe/tracker-steps/pull/15) aporta mejoras útiles para recuperación y sincronización. No considerar el informe de pruebas como autorización para integrarla sin revisión. En el head `8797edb8ccc02a50b17c307bea74d8025aa14013` se reprodujeron tres problemas:

1. Un fallo al guardar puntos rechazados puede acabar eliminándolos de la cola pendiente: pérdida de datos.
2. El límite de 5.000 puntos descarta registros antiguos sin recuperación ni aviso.
3. Una respuesta de recuperación atrasada puede volver a ofrecer una jornada cuyo cierre se encoló y sincronizó mientras se esperaba la respuesta.

Consultar el [informe con reproducción](https://github.com/fjcaroe/tracker-steps/blob/codex/cierre-cambios-locales/docs/reviews/2026-10-03-pr15-movil.md). Comprobar el head actual, corregir los casos que sigan presentes y añadir regresiones antes de incorporar esa lógica. El head revisado pasa 47 pruebas móviles; eso no demuestra conservación de datos en los escenarios anteriores.

## 3. Arquitectura propuesta

Conservar React/TypeScript y Capacitor como punto de partida. No reescribir en Flutter o React Native ni actualizar versiones mayores sin una necesidad documentada y pruebas de compatibilidad. Una base compartida puede producir Android, iOS y web; los servicios nativos tendrán adaptadores específicos.

Organizar el cliente alrededor de:

- `app`: arranque, sesión, empresa activa, navegación y portada.
- `modules`: Colaciones, Movilización, Tracker y futuros módulos con rutas y servicios propios.
- `shared`: contratos, componentes, errores y utilidades realmente compartidas.
- `platform`: almacenamiento seguro, cámara, escáner, GPS y tareas nativas.
- `sync`: cola durable, estados, recuperación e idempotencia.

Adaptar estos nombres al repositorio real; no crear una segunda estructura paralela si ya existe una adecuada. Evitar tanto copiar lógica entre módulos como imponer una abstracción universal sobre reglas diferentes.

Cada módulo tendrá un manifiesto tipado: identificador estable, versión de contrato, nombre, icono, rutas, capacidades y permisos requeridos. El código de los módulos viaja en la aplicación. Odoo entrega catálogo y autorizaciones, no JavaScript remoto ejecutable. Una asignación administrativa habilita un módulo instalado y compatible; no sustituye una actualización del binario cuando se agrega funcionalidad nueva.

El backend valida todos los permisos. Ocultar un botón o una tarjeta no autoriza ni protege una API. Definir una fachada de API para sesión, membresías y catálogo, y adaptadores hacia los dominios existentes; decidir con un ADR dónde vive, considerando el backend actual y Odoo, antes de añadir otro servicio.

## 4. Administración desde Odoo

Crear un módulo central pequeño, provisionalmente `step_mobile_portal`, y puentes opcionales a Colaciones, Movilización y Tracker. El núcleo no debe obligar a instalar todos los módulos empresariales.

El administrador autorizado podrá:

- Ver personas registradas, proveedor de identidad, estado y solicitudes de incorporación.
- Invitar, aprobar, suspender o revocar una membresía en su empresa.
- Vincular explícitamente una persona con su contacto, empleado o conductor existente.
- Asignar módulos y roles, con vigencia y alcance de compañía.
- Consultar dispositivos, revocar sesiones y revisar auditoría de cambios de acceso.

Modelar persona móvil, identidad externa, membresía, concesión de módulo/rol, dispositivo e invitación. Separar estados de cuenta y de membresía: suspender una empresa no debe borrar la identidad ni impedir otras membresías legítimas.

Un registro público no crea automáticamente un usuario interno de Odoo, un empleado ni un acceso administrativo. Resolver el tipo de cuenta y vínculo según el proceso real y documentarlo. No asociar automáticamente a alguien con un empleado por un nombre o correo coincidente.

Si existen varias bases Odoo, sus IDs locales no son identidades globales. Definir un directorio de organizaciones con identificadores estables y conectores autorizados. No permitir que el usuario introduzca una URL/base arbitraria y enviar allí sus credenciales. Documentar cuál instalación administra identidad y cuál es autoridad sobre cada empresa; validar esta decisión en la fase de inventario.

Aplicar permisos tanto a lectura como a escritura, consultas, descargas y sincronización. Un administrador de una empresa no puede habilitarse datos de otra. Evitar `sudo()` general: donde el dominio existente lo requiera, autenticar primero y limitar registros explícitamente al alcance autorizado.

## 5. Registro y autenticación

Implementar un flujo completo de cuenta personal y recuperación de acceso usando un proveedor o mecanismo mantenido. Incorporar Google mediante el flujo apropiado para cada plataforma. Prever Apple para iOS y evaluar el requisito 4.8 según el tipo de distribución y cuentas; no asumir una excepción empresarial si habrá registro público.

Validar los tokens externos en servidor con bibliotecas mantenidas: firma, emisor, audiencia y expiración. Identificar cuentas Google por el identificador estable del proveedor, no únicamente por email. Vincular proveedores adicionales exige demostrar control de la cuenta existente; nunca unir cuentas solo porque sus correos coinciden. [Verificación oficial de Google](https://developers.google.com/identity/gsi/web/guides/verify-google-id-token).

Para OAuth nativo usar navegador del sistema y el flujo recomendado con PKCE cuando corresponda; no pedir la contraseña de Google dentro de una WebView propia. [RFC 8252](https://www.rfc-editor.org/rfc/rfc8252.html).

Emitir sesiones propias revocables, definir expiración y renovación, y proteger credenciales nativas mediante Keychain/Keystore con una biblioteca mantenida. No guardar secretos en variables `VITE_`, repositorio, logs, capturas ni archivos de ejemplo. La sesión web requiere su propio análisis de cookies, CSRF y XSS; no asumir que el almacenamiento nativo existe en navegador.

Si faltan credenciales de Google/Apple, dejar integración, configuración y pruebas de contrato preparadas, con proveedores de prueba claramente separados. Informar exactamente qué falta para validación real. No mostrar un inicio de sesión aparentemente exitoso que no autentica, ni afirmar que está verificado en dispositivo.

Flujo inicial: registro → verificación aplicable → cuenta pendiente de empresa → invitación/aprobación → elección de empresa si hay varias → portada con módulos autorizados. Revalidar permisos al recuperar conexión y al cambiar de empresa.

Incluir privacidad, cierre de sesión, gestión de dispositivos y solicitud/eliminación de cuenta. Distinguir eliminación de identidad de registros empresariales que deban conservarse bajo la política correspondiente. Para distribución iOS, verificar las reglas de login y eliminación antes del lanzamiento. [Reglas oficiales de Apple, 4.8 y 5.1.1](https://developer.apple.com/app-store/review/guidelines/).

## 6. Primeros módulos funcionales

### Colaciones

Separar dos experiencias:

- **Persona:** consultar su habilitación y registros propios; implementar solicitud/reserva solo si el dominio existente lo admite, dejando explícito su alcance.
- **Operador autorizado/dispositivo compartido:** identificar beneficiario, capturar entrega y sincronizar con el contrato real. El modo tótem necesita emparejamiento y acceso restringido propios; no se habilita a cualquier usuario registrado.

El token de tótem existente no reemplaza la sesión personal ni permite consultar información de todos los trabajadores. Conservar validaciones de producto, proveedor, cantidad, valorización y duplicados en servidor. Reutilizar UUID de operación y confirmación por registro. La UI debe distinguir solicitud, entrega efectiva y sincronización.

Entregar al menos un recorrido completo: un administrador asigna acceso, la persona consulta lo permitido y un operador autorizado registra una entrega que llega a Odoo, también tras un corte de red. Usar datos sintéticos y ambiente de prueba; no generar consumos contables reales.

### Conductores de Movilización

Consultar servicios/rutas asignados y pasajeros autorizados; registrar embarque/desembarque con el método que el contrato actual soporte. Implementar inicio/cierre del servicio y controles del conductor según modelos existentes, sin inventar registros incompatibles.

La API actual usa `/mobilization/v1` y credenciales de dispositivo mediante `X-Device-UUID` y `X-Device-Token`; el emparejamiento vincula al conductor. Adaptar este vínculo a la sesión personal y revocación sin entregar credenciales compartidas entre conductores.

Entregar un recorrido completo: asignación en Odoo → conductor ve su servicio → registra eventos con y sin red → sincroniza sin duplicados → supervisor autorizado consulta el resultado. Geolocalización únicamente si el proceso lo necesita, con permisos y comportamiento de segundo plano documentados y probados.

### Tracker y expansión

Preservar los flujos actuales de jornadas, tareas, historial y supervisión. Integrarlos como módulo sin confundir jornada de maquinaria con servicio de transporte. La migración no debe borrar jornadas ni cambiar sus IDs.

Siguientes candidatos: asistencias, actividades/tareas, cosecha, inspecciones, protección laboral, gastos y documentos. Priorizar con evidencia del trabajo en terreno; no implementar todos los iconos de Odoo en este primer encargo. Contabilidad, configuración global y administración compleja seguirán centradas en Odoo.

## 7. Funcionamiento sin señal y conservación de datos

Las operaciones de campo deben persistirse antes de anunciar éxito local. Separar almacenamiento por identidad, organización/compañía y módulo, con IDs estables e idempotencia de servidor. En nativo evaluar SQLite; en web IndexedDB. Elegir según garantías de transacción y soporte, documentando migración y recuperación.

Una operación tendrá estados explícitos: pendiente, enviando, confirmada, requiere autenticación o rechazada de forma definitiva. Separar rechazo de falta de red. Un rechazo de una jornada no puede detener indefinidamente todos los módulos. Clasificar errores por contrato del endpoint, no interpretar cualquier HTTP 400 como autorización para descartar datos.

No borrar datos pendientes o rechazados por cuota, cierre de sesión, cambio de cuenta, actualización o un límite arbitrario. Un archivo de rechazados también necesita persistencia verificable, diagnóstico y recuperación/exportación autorizada. Eliminar del origen solo tras una transferencia durable comprobada o confirmación del servidor. Nunca reenviar operaciones de A con la sesión de B.

Mostrar pendientes, problemas y estado de sincronización. «Reintentar» debe producir un intento real cuando sea posible. Una sesión expirada debe pedir autenticación y conservar la cola, sin presentarse como rechazo definitivo del negocio.

Definir una autorización offline de duración limitada para cuentas previamente validadas. Documentar el compromiso: una revocación remota no puede llegar instantáneamente a un teléfono sin conexión. Tras el vencimiento impedir nuevas acciones protegidas y conservar las existentes para resolución segura. El servidor debe aplicar una política explícita para eventos capturados antes de una revocación.

Probar cierre de app, fallos de escritura, cuota llena, reinicios, respuestas fuera de orden, doble pulsación, reenviar un lote, cambio de empresa/usuario y recuperación de señal. Proteger especialmente el cierre de jornada y las respuestas tardías que podrían volver a ofrecerla.

## 8. Migración y compatibilidad

Inventariar claves y estructuras actuales de Tracker, versiones de API, emparejamientos y credenciales Colaciones/Movilización. Las claves locales antiguas pueden no identificar empresa o propietario: no atribuirlas automáticamente al nuevo usuario.

Preparar migración versionada, recuperable tras interrupción y probada con datos sintéticos representativos. Conservar el origen hasta verificar la persistencia del destino. Si no puede demostrarse el propietario, ofrecer recuperación segura en lugar de borrar o importar a otra cuenta.

Documentar el impacto de conservar o cambiar `cl.stepsapp.movil`, firma y nombre de la app. No cambiar identificadores silenciosamente: afecta actualización y acceso al almacenamiento previo. Mantener las instalaciones actuales operativas durante el piloto; definir coexistencia, reversión y adopción gradual.

El despliegue de Web Tracker no es el de Steps Móvil. Leer los procedimientos de cada producto. Nunca compilar para producción con el backend localhost de respaldo ni copiar secretos a Git. Entregar una propuesta de despliegue verificable para el nuevo producto, sin alternar builds de ramas divergentes.

## 9. Interfaz preparada para GPT/Astra

Entregar una interfaz sobria pero completa y utilizable: bienvenida/login, incorporación pendiente, selección de empresa, portada, ambos módulos piloto, perfil y sincronización. Contemplar carga, vacío, error, permiso denegado y estado offline. No dejar pantallas principales como placeholders.

Separar reglas de negocio de vistas y centralizar tokens de color, tipografía, espaciado, radios y estados. Crear pocos componentes compartidos útiles: botón, campo, tarjeta, navegación, estado y confirmación. Mantener contratos tipados y una única fuente de estilos base.

La portada mostrará los módulos disponibles y acciones frecuentes, con contexto de empresa y sincronización visibles. Diseñar para teléfono: navegación breve, objetivos táctiles cómodos, tamaños de texto adaptables, contraste y etiquetas accesibles. Pedir cámara/GPS cuando la acción lo requiera y ofrecer estados claros si se deniega el permiso.

Entregar `docs/STEPS_APP_UI_CONTRATO.md` con mapa de pantallas, componentes, estados, datos de demostración y límites entre vistas y servicios. GPT/Astra podrá cambiar composición, jerarquía, iconografía y apariencia manteniendo permisos, migración y sincronización. La mejora visual vendrá después del piloto funcional, evitando rehacer simultáneamente contratos y presentación.

## 10. Etapas y criterios de entrega

### Etapa 0 — inventario y decisiones

Registrar código/ramas por producto, funciones existentes, APIs, bases Odoo, identidad y permisos actuales. Preparar ADR de arquitectura, matriz de módulos/roles y plan de migración. Identificar código reutilizable con su procedencia. Resolver la revisión pendiente de sincronización antes de reutilizar sus cambios.

### Etapa 1 — núcleo y administración

Implementar sesión, incorporación, membresías, catálogo, elección de empresa y administración Odoo. Demostrar que asignar/revocar un módulo cambia el acceso real a API y pantalla, y que una persona de otra empresa no puede leer ni escribir datos ajenos. Preparar autenticación externa y declarar lo que necesite configuración externa.

### Etapa 2 — dos recorridos completos

Colaciones y conductores de Movilización funcionales en ambiente de prueba, incluida persistencia offline, idempotencia y trazabilidad en Odoo. Integración gradual de Tracker con regresiones y conservación de datos. El desarrollo debe producir operaciones reales sobre un entorno sintético, no únicamente mocks de pantallas.

### Etapa 3 — validación nativa y entrega visual

Generar Android de prueba si están disponibles SDK y herramientas; registrar prueba en dispositivo/emulador y limitaciones del segundo plano. Preparar proyecto iOS y validar en macOS/Xcode o CI macOS cuando esté disponible. Un build web no demuestra funcionamiento en Android/iOS. [Requisitos de Capacitor](https://capacitorjs.com/docs/getting-started/environment-setup).

Entregar recorridos reproducibles y capturas con datos ficticios para el trabajo visual. Separar claramente «implementado», «probado en web», «probado en Android», «probado en iOS» y «pendiente por configuración/herramientas».

### Pruebas mínimas de aceptación

- Registro sin empresa: no permite consultar datos empresariales; invitación válida habilita únicamente lo asignado.
- Cuenta y proveedor: token inválido/expirado se rechaza; no se unen cuentas por email sin verificación del vínculo.
- Dos empresas/usuarios: aislamiento en API, caché, colas, dispositivos y administración; cambio de cuenta no mezcla ni elimina pendientes.
- Revocación online y vencimiento offline: conducta coherente con la política documentada.
- Colaciones: duplicado o reenvío no produce una segunda entrega; permisos personales y de tótem separados.
- Movilización: un conductor no accede al servicio de otro; eventos offline llegan una sola vez y mantienen su autoría.
- Tracker: cuotas/fallos de persistencia no pierden GPS; jornadas cerradas no reaparecen por una respuesta atrasada.
- Reinicio/actualización/migración: registros pendientes conservados y recuperación tras interrupción.
- Permisos nativos denegados, pérdida de señal y retorno desde segundo plano: mensajes y estado correctos.

Ejecutar las pruebas y builds exigidos por cada `AGENTS.md`, además de las pruebas pertinentes de los módulos Odoo modificados. No escribir «pasan» si no se ejecutaron. No usar datos ni cargos reales para validar el piloto.

## 11. Trabajo conjunto y cierre en Git

No empezar desde la rama abierta por casualidad. No cambiar el checkout utilizado por otro agente ni desarrollar el mismo núcleo simultáneamente con cambios visuales. Trabajar en un worktree propio y publicar avances coherentes en la rama de entrega.

Mantener una rama de integración claramente identificada para Steps App. Las ramas de trabajo deben entregar PR/commits concretos hacia esa base; documentar qué se integró y qué sigue pendiente. No declarar consolidación mientras la funcionalidad útil exista solo en una rama aislada. Mantener referencias antiguas recuperables hasta verificar integración; no eliminarlas para aparentar orden.

Al cerrar una etapa:

1. Revisar diferencias y archivos nuevos, incluidos los ignorados que puedan contener código útil.
2. Guardar código y documentos en rutas versionadas; dejar APK, logs, capturas y respaldos fuera del checkout.
3. Hacer commits comprensibles, push y PR con base correcta. No usar stash como entrega ni commitear secretos.
4. Ejecutar `python tools/git/verify_handoff.py --require-pushed`; revisar `--all-worktrees` cuando corresponda, sin tocar el trabajo de otro agente.
5. Informar rama, SHA, PR, pruebas ejecutadas, integración conseguida y límites reales.

Entregar documentación de arquitectura, API/autorización, migración, operación offline, pruebas, contrato visual y configuración sin secretos. Si una dependencia externa bloquea una validación, preservar el código publicado y explicar el paso concreto que falta; continuar las partes independientes.

## Resultado esperado

Una base Steps utilizable para crecer: personas se registran, Odoo administra su acceso, el teléfono muestra módulos autorizados y Colaciones/Movilización completan sus procesos sin perder operaciones al quedarse sin señal. Tracker conserva su funcionalidad. El siguiente trabajo de GPT/Astra mejora una app funcional y comprobable sobre una estructura compartida.
