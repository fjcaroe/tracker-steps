# Implementación de Steps Tracker: nueva experiencia y Protección GPS

**Fecha:** 30 de septiembre de 2026
**Estado:** especificación de implementación; no acredita funciones desplegadas
**Objetivo:** llevar a la aplicación real el layout propuesto y desarrollar monitoreo continuo con protocolo antirrobo para flota agrícola y transporte.

## 1. Alcance y resultado esperado

Construir una aplicación Steps con tres áreas conectadas:

1. **Operación:** mapa de toda la flota, lista filtrable, selección de vehículo y detalle con última señal, calidad, actividad e incidencias.
2. **Control de flota:** tabla con los mismos resultados del mapa, filtros combinables, ordenación, columnas e indicadores configurables y vistas guardadas.
3. **Steps Protección:** armado, detección, avisos, expediente de incidente, autorización, resultado de actuación y restitución. La actuación sobre el vehículo se habilita únicamente para un conjunto GPS/firmware/relé/instalación que haya superado las pruebas indicadas abajo.

El cortacorriente aparece en la cotización de la competencia. El rasgo comercial a construir en Steps es el flujo completo de respuesta y su evidencia, unido al contexto de labores, conductores, mantenimiento y costos. El objetivo físico inicial es **inhibir un próximo arranque** en instalaciones diseñadas para ello. El producto no debe presentar una orden de «apagar motor» como si fuera inocua cuando el vehículo está en uso.

Este documento convierte el [plan de producto](PLAN_STEPS_TRACKER_GPS_COMERCIAL.md) en tareas técnicas y condiciones de entrega. La propuesta visual previa es una referencia de composición con datos sintéticos; la implementación se hace en React/FastAPI/Odoo y conserva los controles existentes hasta sustituirlos con datos reales.

## 2. Punto de partida comprobado

- Repositorio público `fjcaroe/tracker-steps`; rama que sigue producción: `codex/web-tracker-redesign`. El checkout local inspeccionado está en otra rama y contiene cambios ajenos. Preparar un checkout aislado de la rama correcta antes de implementar.
- Frontend: React 19, Vite, TypeScript, Google Maps. [App.tsx](../src/App.tsx) define navegación y shell; [OperationsWorkspace.tsx](../src/pages/OperationsWorkspace.tsx) concentra vistas, filtros y modo demo; [OperationsMap.tsx](../src/components/OperationsMap.tsx) dibuja el mapa; [redesign.css](../src/redesign.css) contiene la identidad actual.
- `OperationsWorkspace` inicia `demoMode=true`. La vista real `live` deriva vehículos visibles de sesiones abiertas y últimos puntos de esas sesiones. Para un servicio GPS comercial se requiere **última posición continua por dispositivo**, independiente de abrir una sesión laboral.
- La API FastAPI registra rutas en [main.py](../backend/tracker_py/app/main.py). [machines.py](../backend/tracker_py/app/models/machines.py) ya tiene `created_at`; el modelo revisado no implementa un `tenant_id` de cliente externo. [trackerApi.ts](../src/services/trackerApi.ts) contiene llamadas de sesiones; se extenderá con contratos tipados de flota/Protección.
- `step_tracker_odoo` ya contiene modelos `step.tracker.*` y sincronización; `step_hr` tiene declaraciones relacionadas. Hay que identificar propietario de cada modelo antes de agregar uno nuevo.
- Receptor Teltonika y API existentes pueden conservarse para su hardware. El Coban requiere recepción y decodificación verificadas para cada firmware. **Traccar es candidato, no componente ya incorporado.**

## 3. Resultado de diseño que debe respetar el frontend

### 3.1 Estructura

Mantener el verde profundo `#123c33`, lima `#d8ff62`, superficies claras, tipografía del sistema y foco visible. Conservar los patrones válidos de navegación de Steps mientras se simplifica la pantalla de monitoreo:

| Vista | Composición escritorio | Composición móvil |
|---|---|---|
| Operación | Cabecera corta; buscador y filtros; métricas compactas; flota a la izquierda, mapa dominante, detalle a la derecha | Mapa primero; lista y detalle accesibles sin perder selección; filtros desplegables |
| Control de flota | Tabla de comparación a ancho disponible; selector de columnas; misma búsqueda y filtros | Filas adaptadas a pantalla o tabla con columnas prioritarias, sin etiquetas truncadas |
| Protección | Lista de incidentes con severidad y hora; detalle del activo y línea temporal de decisiones | Incidente, última posición y contactos en orden de atención; acciones sujetas a permisos |

Usar estados explícitos **cargando, vacío, error, sin cobertura, dato antiguo, dato recibido y dato físico no confirmado**. La ausencia de señal no puede parecer «detenido». El mapa nunca mueve un marcador basándose en una posición anterior sin marcar su antigüedad.

### 3.2 Filtros y preferencias

Filtros iniciales: texto por nombre/patente, tipo de activo, centro de costo/fundo, estado de movimiento, antigüedad de señal, Protección y modelo de GPS. Combinarlos con semántica `AND`; recuento y métricas se calculan sobre el conjunto filtrado. El mapa, la lista y la tabla deben consumir una única consulta/estado de filtros.

Columnas obligatorias por defecto: **equipo, estado, última señal y Protección**. Opcionales: tipo, fecha de alta, GPS instalado, centro de costo, responsable, contacto ACC, horas/distancia cuando haya datos válidos. Etiquetas de fecha diferenciadas:

- `created_at`: «Fecha de alta»; no se deduce de un punto GPS.
- `recorded_at`: hora que declaró el dispositivo; «Última posición registrada».
- `received_at`: hora en que llegó al servidor; «Recibido por Steps».

Guardar preferencias por `tenant_id + user_id + view_key`, con versión de esquema, lista permitida de columnas, filtros y orden. Compartir una vista solo mediante identificador autorizado, sin credenciales en URL. Un cliente no puede elegir columnas que revelen campos prohibidos por su rol. En demo, conservar preferencias locales sin escribir en datos reales.

### 3.3 Componentes a crear o extraer

| Zona | Ubicación propuesta | Responsabilidad |
|---|---|---|
| Navegación | `src/App.tsx` | Entradas Operación, Control de flota y Protección; organización y usuario visibles |
| Contenedor | `src/pages/OperationsWorkspace.tsx` | Separar carga y vista; conservar rutas y páginas actuales durante transición |
| Consulta de flota | `src/hooks/useFleetSnapshot.ts` y `src/services/trackerApi.ts` | Filtros, paginación/actualización, errores y tipado |
| Lista/tabla | `src/components/FleetList.tsx`, `FleetTable.tsx`, `FleetFilters.tsx` | Selección común y preferencia de columnas |
| Detalle | `src/components/FleetAssetDetail.tsx` | Posición, señal, hardware, sensores e incidente |
| Protección | `src/pages/ProtectionPage.tsx` y componentes de incidente | Atención, auditoría y estados de comando |
| Estilos | `src/redesign.css` y hojas de componentes | Reusar variables `--ops-*`; probar 320/360/768/1024 px |

Estos nombres son propuestas de archivo, no archivos existentes. Mantener `OperationsMap` como base y adaptar sus entradas al nuevo modelo de flota. Evitar una segunda implementación de mapa con reglas distintas. Probar teclado, foco, etiquetas y color más texto en todos los estados.

## 4. Datos y contratos de backend

### 4.1 Modelo mínimo nuevo

Crear migraciones versionadas, reversibles y ensayadas en copia. No cambiar de forma implícita el significado de `machines`, `tracking_sessions` ni `tracking_points`.

| Entidad | Campos indispensables | Restricción |
|---|---|---|
| `tenant` | ID estable, nombre, zona horaria, retención | Frontera de autorización |
| `asset` o ampliación controlada de `machine` | `tenant_id`, tipo, nombre, patente, alta, centro de costo | Identidad del vehículo separada del GPS |
| `device` | `tenant_id`, IMEI único, marca, modelo, firmware, protocolo, SIM, capacidades homologadas | IMEI no es credencial de usuario |
| `device_assignment` | cliente, dispositivo, activo, `valid_from`, `valid_to` | Un solo activo vigente por GPS; conservar historia |
| `gps_position` | origen/ID, cliente, dispositivo, activo, `recorded_at`, `received_at`, lat/lon, velocidad, calidad | Idempotencia; índices por cliente/activo/tiempo |
| `device_state` | última señal, frescura, ACC/energía disponibles, calidad | Proyección reconstruible desde eventos |
| `security_policy` | vehículo, horario, zona, contactos, estado armado, versión | Cambios auditados |
| `security_incident` | cliente/activo, tipo, severidad, estado, evidencia, responsable, fechas | Eventos agrupados con trazabilidad |
| `device_command` | tipo permitido, solicitante, aprobador, motivo, expiración, asignación/versión, estados, respuestas | Auditoría e idempotencia por intención |
| `view_preference` | cliente, usuario, clave, versión, columnas/filtros/orden | Validar lista permitida en servidor |

Asignar `tenant_id` desde la sesión y la asociación del dispositivo en el servidor. El cliente no elige el tenant efectivo enviando un parámetro. Migrar datos existentes con correspondencia explícita entre base Odoo, compañía y cliente; registrar los no atribuibles para resolución manual. Probar reasignación de un GPS sin transferir historia a otro cliente.

### 4.2 API propuesta bajo `/v1`

Los contratos actuales de sesiones permanecen durante migración. Cada ruta nueva exige autenticación, pertenencia al cliente y autorización sobre los IDs solicitados.

| Ruta | Método | Uso |
|---|---|---|
| `/v1/fleet/snapshot` | GET | Flota filtrada, último estado y recuentos; paginación estable |
| `/v1/assets/{id}` | GET | Detalle y capacidades válidas para el usuario |
| `/v1/assets/{id}/positions` | GET | Histórico paginado por tiempo, con calidad |
| `/v1/view-preferences/{view_key}` | GET/PUT | Preferencias permitidas, versionadas |
| `/v1/security/policies` | GET/PUT | Armado, horarios, geocercas y contactos |
| `/v1/security/incidents` | GET/POST | Lista y registro de incidente; cambios de estado con motivo |
| `/v1/security/incidents/{id}` | GET/PATCH | Línea temporal, evidencias y reconocimiento |
| `/v1/security/commands` | POST | Solicitud de una acción predefinida; **no envía inmediatamente** |
| `/v1/security/commands/{id}/approve` | POST | Aprobación separada y revalidación |
| `/v1/security/commands/{id}` | GET | Estado, respuesta y resultado verificable |

Ejemplo abreviado de respuesta para un equipo; **es un contrato objetivo, no una respuesta actual de la API**:

```json
{
  "asset_id": "a-123",
  "name": "Tractor 03",
  "type": "tractor",
  "last_position": {
    "recorded_at": "2026-09-30T17:32:00Z",
    "received_at": "2026-09-30T17:32:05Z",
    "lat": -35.426,
    "lon": -71.662,
    "quality": "gps"
  },
  "signal_state": "stale",
  "motion_state": "unknown",
  "protection_state": "incident_open",
  "capabilities": {
    "tracking": "approved",
    "remote_start_inhibit": "not_approved"
  }
}
```

Calcular `signal_state` por `received_at` y política de frescura del modelo; no inferir movimiento actual de un punto vencido. Separar `motion_state` de ACC y de motor funcionando. No crear horas de motor, combustible medido ni PTO si el dispositivo no entrega señal suficiente.

### 4.3 Ingesta GPS continua

Evaluar Traccar en entorno aislado con versión fijada y dos dispositivos reales. Probar protocolo del 403A y 401C por firmware, tramas de posición, ACC, energía, reconexión, pérdida de cobertura, respuestas y comando. Si no supera la prueba, definir receptor Coban dedicado sin reutilizar a ciegas el decodificador Teltonika.

`GPS → receptor → adaptador Steps → cola durable → posiciones/estado/eventos → API → web/Odoo`. El adaptador debe tener ID de origen, deduplicación y recuperación por cursor o mecanismo equivalente. Una sesión laboral es una relación derivada o iniciada por la operación; la recepción de puntos continúa sin sesión. El servicio GPS conserva la operación aunque Odoo esté indisponible.

**Puerta de salida:** un GPS real envía a servidor propio, pierde red una hora, reconecta y el histórico recuperable se muestra con sus marcas de tiempo originales, sin duplicados lógicos ni sustituir la posición más nueva por una atrasada. Documentar si el firmware no tiene buffer histórico.

## 5. Protección: funcionamiento y límites de control

### 5.1 Incidente

El cliente arma la protección por activo, horario y zona. Detectar reglas como movimiento/ACC fuera de horario, salida de zona, desconexión de alimentación y SOS cuando existe. Tratar falta de señal como **falla de comunicación**; un desplazamiento con ACC apagado como **sospecha**. Un responsable reconoce, contrasta uso autorizado, notifica a contactos y cierra con motivo. El expediente guarda eventos, última posición con antigüedad, destinatarios, confirmación de entrega y decisiones.

Las alertas se agrupan para que la retransmisión de un evento no genere varias incidencias. Probar falsas alarmas y escalamiento. No anunciar atención humana 24/7 sin servicio contratado.

### 5.2 Solicitud de inhibición de arranque

No usar una acción directa en la ficha. Flujo del producto:

```text
incidente abierto → solicitante autenticado → motivo → segundo aprobador
→ validación de equipo, asignación, vigencia y condición física
→ despacho con vencimiento → respuesta del dispositivo si existe
→ actuación físicamente confirmada o resultado desconocido
→ restitución autorizada y confirmada → cierre
```

Exigir roles separados, autenticación reforzada, registro de identidad y hora, serialización por dispositivo e identificador único de intención. Bloquear repetición ciega, permisos revocados, reasignaciones y acciones contradictorias. El navegador y Odoo nunca poseen credenciales de administración de Traccar ni acceso a comandos arbitrarios.

**Condición física:** el instalador y fabricante deben confirmar un circuito que inhiba el próximo arranque sin detener un motor en marcha ni afectar un implemento activo. Velocidad GPS cero y ACC apagado no bastan para demostrarlo. Si el hardware no puede garantizar esa condición al ejecutarse la orden, la capacidad queda deshabilitada para esa instalación.

**Orden tardía:** [Traccar documenta](https://www.traccar.org/commands/) que puede encolar comandos de dispositivos desconectados y enviarlos al reconectar. La ruta elegida debe impedir que una orden de inhibición vencida permanezca en esa cola, incluso ante la carrera entre comprobar `online` y despachar. Un TTL aplicado solo en FastAPI no basta si el comando ya pasó al motor o al equipo. No usar SMS como respaldo automático, porque también puede llegar tarde. Probar el comportamiento en la versión concreta. Si no se puede garantizar, no habilitar la acción física.

Mostrar por separado **solicitado, aprobado, enviado, recibido, actuación confirmada, fallido, vencido y resultado desconocido**. Un ACK de transporte no prueba la salida del relé. Si el GPS no devuelve realimentación física, presentar «resultado no confirmado» o añadir un sensor apropiado. Cancelar después del despacho significa «cancelación solicitada» hasta demostrar que no podrá actuar.

### 5.3 Coban 403A y 401C

| Paso | 403A | 401C | Evidencia requerida |
|---|---|---|---|
| Identidad | Variante y firmware exactos | Variante y firmware exactos | Manual de lote, acceso administrativo y SIM |
| Alimentación | Ficha revisada: 12–24 V | Integradores: 12–24 V; ficha de familia difiere | Medición/documento de la unidad entregada |
| Posiciones | Receptor candidato `gps103` por probar | Protocolo `coban` documentado por integradores; Traccar por probar | Tramas reales y pruebas en servidor Steps |
| Relé/salida | El anuncio declara cortacorriente | El anuncio declara cortacorriente; integración Navixy documenta salida | Kit incluido, límites eléctricos, instalación y prueba de banco |
| Resultado | Desconocido sin prueba | Desconocido sin prueba | Respuesta real y, si aplica, realimentación externa |
| Campo | Tractor y camión, después de banco | Tractor y camión, después de banco | Acta por combinación firmware/vehículo/instalación |

El [fabricante presenta la familia 401C](https://pdt.static.globalsources.com/IMAGES/PDT/SPEC/123/K1216849123.pdf), y [Navixy documenta BN-401C](https://navixy.com/en/devices/coban/coban-bn-401c/). La compatibilidad con nuestro motor y la instalación del ejemplar anunciado siguen pendientes. Evaluar **una muestra de cada modelo** y después completar dos unidades del elegido para probar tractor y camión. La compra masiva espera esa decisión.

No introducir en la interfaz comandos genéricos de «cortar corriente». La capacidad se define por un perfil `modelo + firmware + relé + tipo de instalación` con estado `tracking_approved` y `control_approved` independientes.

## 6. Odoo y operación de soporte

- Mantener Tracker como fuente de posiciones, incidentes y comandos. Sincronizar hacia Odoo resúmenes y vínculos con `fleet.vehicle`, máquina, labor, orden de trabajo y centro de costo.
- Auditar modelos/XML IDs de `step_hr` y `step_tracker_odoo` antes de proponer `step.tracker.security.incident` u otro modelo. No crear definiciones duplicadas.
- Cambiar la sincronización limitada a últimas N sesiones por cursor paginado con reintentos e idempotencia. La caída de Odoo no debe interrumpir el monitoreo ni el incidente.
- El soporte ve calidad de señal, firmware, fecha de instalación, SIM/operador, último evento, errores de notificación y estado de homologación. Su acceso es temporal y auditado.
- El módulo `tracking_manager` de OCA sigue siendo auditoría de cambios de campos Odoo; no es el receptor GPS ni la base de esta función.

## 7. Orden de implementación y entregas verificables

| Entrega | Trabajo concreto | Evidencia de salida |
|---|---|---|
| **E0. Base y hardware** | Checkout aislado de `codex/web-tracker-redesign`; inventario de datos y módulos; dos clientes de prueba; muestras 403A/401C; decisión del receptor | Documento de protocolo/firmware, costos y matriz de hardware; captura real de cada muestra |
| **E1. Flota continua** | Tenant, dispositivo, asignación, ingesta, última posición y API `/v1/fleet/snapshot` | Dos clientes aislados; recepción sin sesión abierta; reconexión sin duplicación |
| **E2. Layout Steps** | Navegación, mapa, lista, detalle, filtros, tabla y preferencias | Misma flota/filtros en mapa y tabla; fecha de alta y última señal correctas; móvil y teclado |
| **E3. Protección digital** | Armado, reglas, incidentes, avisos, expediente y soporte | Falsa alarma, alimentación cortada y pérdida de señal diferenciadas; cierre auditado |
| **E4. Control homologado** | Aprobaciones, adaptador de comandos, instalación, pruebas de seguridad y restitución | Suite negativa y acta física por instalación; órdenes tardías imposibles; resultado verificable |
| **E5. Odoo y comercialización** | Resúmenes, vínculos operativos, documentación, costos y piloto | Conciliación con ERP, piloto de cinco vehículos y alcance contractual medido |

**Dependencias:** E0 precede a ingesta de hardware; E1 precede a una UI de flota con datos reales; E2 y E3 pueden avanzar con contratos simulados y pruebas de integración mientras E1 se completa; E4 necesita E0/E1/E3 y aceptación física; E5 integra entregas estables. E2 puede publicarse gradualmente con datos reales existentes, mostrando su cobertura limitada hasta tener E1.

El plazo de E4 se fija después de recibir el hardware y comprobar cómo el firmware maneja relé, confirmación y reconexión. No sumar E4 por defecto al plazo del MVP de monitoreo.

## 8. Matriz mínima de pruebas

| Escenario | Resultado exigido |
|---|---|
| Dos clientes consultan mapa, tabla, detalle, exportaciones y canal en vivo | Cero acceso cruzado, incluso con IDs adivinados |
| GPS pasa de un cliente/vehículo a otro | Asociación e historia del antiguo cliente permanecen privadas |
| Punto antiguo llega tras pérdida de red | Historial lo incorpora; la ficha conserva el punto más reciente |
| Equipo no reporta durante el umbral | «Sin señal reciente» y hora visibles; movimiento actual desconocido |
| Filtros se combinan y se cambia mapa ↔ tabla | Mismos IDs y recuentos; selección conservada o estado vacío claro |
| Columnas/indicadores personalizados | Persisten por usuario y cliente; no elevan permisos |
| Incidente por alimentación, falsa alarma y falta de red | Causas distintas, notificación auditada y cierre con motivo |
| Solicita usuario sin rol, otra compañía o asignación vencida | Rechazo y evento de auditoría; cero despacho |
| Equipo offline, reconecta tras expirar orden | Cero actuación tardía, incluso con cola del motor/SMS |
| ACK perdido o resultado físico ausente | «Resultado desconocido»; no éxito supuesto ni reintento ciego |
| Solicitud de inhibición mientras se opera o con datos insuficientes | Denegación; ningún circuito crítico se interrumpe |
| Restitución y contingencia local | Arranque recuperado y evidencia registrada |
| Odoo o frontend indisponibles | Captura GPS y estado de incidente recuperables |

Automatizar contratos, aislamiento, filtros, deduplicación y máquina de estados. Las pruebas de relé, circuito y recuperación local requieren banco y revisión del instalador; ningún test de software sustituye ese acta.

## 9. Despliegue y definición de terminado

Implementar y revisar por entregas. Para desplegar la rama que sigue producción, seguir **[DEPLOY_WEB_TRACKER.md](DEPLOY_WEB_TRACKER.md)**: publicar primero API/migraciones compatibles, después frontend, finalmente integración Odoo cuando corresponda. Los secretos `.env` y `.env.production` permanecen solo en el servidor; nunca usar variables `VITE_*` para credenciales privadas. Separar el nuevo motor GPS y sus respaldos del despliegue estático de Vite.

Una entrega se considera terminada cuando su criterio de la sección 7 y sus casos de la sección 8 pasan con evidencia reproducible, existe procedimiento de reversión y la UI describe fielmente la calidad de los datos. **Steps Protección con control físico** se ofrece únicamente tras superar E4 para cada perfil de hardware/instalación; hasta entonces se puede ofrecer monitoreo y atención de incidentes con su alcance claramente indicado.
