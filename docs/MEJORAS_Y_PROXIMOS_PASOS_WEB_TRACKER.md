# Web Tracker: mejoras, dataset demostrativo y próximos pasos

Fecha de este handoff: **19 de agosto de 2026**  
Repositorio de trabajo: `C:\Users\tito4\Documents\Odoo`  
Rama base al preparar este documento: `codex/web-tracker-redesign`  
Commit base: `4f469bf` (`Reconstruye vistas y agrega laboratorio demo`)

## Instrucción principal para Claude

Continúa la reconstrucción de Web Tracker como una aplicación de monitoreo vehicular y agrícola utilizable en una demostración real. No entregues solamente un análisis o un mockup: inspecciona el código existente, implementa los cambios, prueba el resultado y documenta las decisiones.

La demostración no puede depender del dispositivo Teltonika ni de una SIM activa. Debe utilizar un dataset **sintético, claramente identificado como demostrativo**, con recorridos sobre calles reales y tiempos realistas. Cuando no haya una máquina seleccionada, el mapa debe mostrar y animar toda la flota; seleccionar un vehículo debe ser opcional.

## Contexto del GPS Teltonika

Anteriormente se instaló un dispositivo Teltonika en un automóvil, con una SIM que enviaba telemetría a una API. Esos puntos se utilizaban para representar la ubicación y los recorridos en el mapa. La SIM lleva mucho tiempo sin uso y ya no es una fuente disponible; tampoco es práctico volver a conducir para registrar nuevos trayectos.

Por ahora se necesita una fuente demostrativa desacoplada de Teltonika. La arquitectura, sin embargo, debe permitir conectar nuevamente una fuente real en el futuro.

- No inventar el formato de paquetes del dispositivo. Antes de implementar una futura integración, identificar modelo, firmware, protocolo configurado y el código receptor existente.
- Si posteriormente se recibe Codec 8, Codec 8 Extended u otro protocolo Teltonika por TCP/UDP, implementar ese adaptador fuera de la interfaz y del motor de reproducción.
- Conservar una interfaz común para datos reales, históricos y demostrativos.
- No guardar ni exponer IMEI, teléfonos, SIM, patentes reales ni datos personales dentro del dataset de demostración.

## Skills y referencias obligatorias

Antes de modificar componentes o estilos, lee por completo estas skills existentes en el proyecto de referencia:

- `C:\Users\tito4\Documents\webtransporte\webTransporte\.claude\skills\web-design-guidelines\SKILL.md`
- `C:\Users\tito4\Documents\webtransporte\webTransporte\.claude\skills\vercel-composition-patterns\SKILL.md`
- `C:\Users\tito4\Documents\webtransporte\webTransporte\.claude\skills\vercel-react-best-practices\SKILL.md`

Sigue también los archivos de reglas que esas skills indiquen. Para este trabajo son especialmente relevantes:

- composición: evitar proliferación de propiedades booleanas, usar variantes explícitas, componentes compuestos y estado elevado;
- estado: exponer una interfaz genérica de estado/acciones/metadata para que el UI no conozca el proveedor concreto;
- rendimiento: evitar cascadas de solicitudes, paralelizar trabajo independiente, cargar módulos pesados de forma diferida y reducir renders durante la animación;
- visual: jerarquía clara, estados de interacción completos, accesibilidad, navegación por teclado y adaptación móvil.

Revisa también el sistema de diseño y los patrones aprovechables de `webTransporte`, pero **no copies piezas ciegamente**. Adáptalos al stack, dominio y estructura de este repositorio. Ejecuta la auditoría indicada por `web-design-guidelines` sobre las pantallas finales y corrige los hallazgos relevantes.

## Veracidad y procedencia de los datos

La demo debe ser convincente sin inducir a error.

- Mostrar permanentemente una insignia como **“Datos de demostración”** o **“Datos sintéticos”** cuando el modo esté activo.
- Nunca presentar esos recorridos como telemetría histórica realmente capturada por Teltonika.
- Cada fixture debe indicar `synthetic: true`, versión, fecha de generación, zona geográfica, motor de ruteo, licencia/atribución y parámetros del escenario.
- Los vehículos y conductores deben usar identificadores ficticios, por ejemplo `Vehículo demo 01` y `Operador demo A`.
- No mezclar registros demo con tablas productivas ni con analítica real.
- El modo demo debe poder apagarse sin dejar registros residuales.

### Fuente de geometría vial

Los trayectos deben seguir el grafo de calles: no dibujar segmentos aleatorios entre coordenadas ni líneas que atraviesen manzanas, edificios o predios.

Para un fixture persistente, preferir **OpenStreetMap más OSRM, Valhalla u OpenRouteService**, conservando la atribución y cumpliendo ODbL y las condiciones del proveedor. Google Routes puede utilizarse desde el backend para cálculo en vivo si la configuración y las condiciones de Google Maps Platform lo permiten, pero no se debe asumir que sus resultados se pueden almacenar indefinidamente o distribuir como fixtures. Verificar las condiciones vigentes antes de persistir geometría obtenida desde Google.

Nunca exponer una clave de Google Routes en el bundle de Vite. La clave de Maps JavaScript debe tener restricciones de dominio; una clave de Routes debe permanecer en el backend, restringida por API y entorno.

## Dataset sintético de agosto de 2026

Crear un generador reproducible y versionado; no preparar manualmente una nube de puntos. Una misma semilla debe producir el mismo escenario.

Al 19 de agosto de 2026, los días completamente transcurridos del mes son del 1 al 18. Para que la vista se denomine “histórica”, utilizar ese rango. Si se decide generar el mes completo, las fechas posteriores al 19 deben figurar expresamente como **escenario sintético planificado**, no como viajes históricos ocurridos.

### Alcance mínimo

- Entre 20 y 40 vehículos ficticios, con colores e identificadores estables.
- Al menos 30 jornadas con actividad variada y un total mínimo de 300 viajes.
- Un área geográfica coherente con el negocio. Si se reutiliza el dominio urbano de `webTransporte`, usar Santiago u otra ciudad justificada; si se simula operación agrícola, separar claramente caminos públicos, caminos interiores y polígonos de predios.
- Orígenes y destinos plausibles: base, taller, centro de distribución, predios o puntos operacionales.
- Viajes simultáneos para comprobar la vista de flota completa.
- Paradas breves, detenciones operacionales, pérdida controlada de algunos puntos y retorno de señal.
- Velocidad, aceleración y frenado plausibles según tipo de vía y vehículo.
- Eventos sintéticos útiles: inicio/fin, ignición, detención, ralentí, exceso de velocidad configurado y entrada/salida de geocerca.
- Geocercas o polígonos válidos y documentados; no inventar polígonos que crucen calles sin sentido.

### Esquema de datos recomendado

Usar unidades inequívocas y timestamps ISO 8601. Almacenar en UTC y presentar en `America/Santiago`.

```ts
type DemoDataset = {
  datasetVersion: string
  generatedAt: string
  synthetic: true
  label: string
  timezone: 'America/Santiago'
  seed: number
  routing: {
    provider: string
    profile: string
    attribution: string
    generatedAt: string
  }
  vehicles: DemoVehicle[]
  trips: DemoTrip[]
  points: DemoPoint[]
  geofences: DemoGeofence[]
}

type DemoTrip = {
  id: string
  vehicleId: string
  startedAt: string
  endedAt: string
  distanceM: number
  durationS: number
  routeId: string
  status: 'completed' | 'cancelled'
}

type DemoPoint = {
  tripId: string
  sequence: number
  recordedAt: string
  latitude: number
  longitude: number
  speedMps: number
  headingDeg: number
  accuracyM: number
  ignition: boolean
  event?: string
}
```

Se puede ampliar el esquema, pero no reemplazar nombres claros por abreviaturas ambiguas. Evitar duplicar distancia o velocidad con unidades diferentes sin expresarlo en el nombre.

### Construcción temporal realista

1. Obtener una ruta válida del motor vial entre origen, destinos intermedios y destino.
2. Conservar el orden y distancia acumulada de la geometría.
3. Crear un perfil temporal por tramo que respete velocidades plausibles, detenciones y límites configurados.
4. Remuestrear la trayectoria a un intervalo constante, preferentemente 5 segundos, agregando puntos exactos para los eventos importantes.
5. Calcular `headingDeg` desde el segmento efectivo, no aleatoriamente.
6. Agregar ruido GPS pequeño y acotado sólo si no saca los puntos de la vía de forma visualmente absurda.
7. Validar monotonía de tiempo, secuencia, límites de coordenadas, velocidad, distancia y pertenencia aproximada a la ruta.

La animación no debe avanzar un porcentaje fijo por frame. En reproducción **1×**, un segundo del reloj de la demo representa un segundo del dataset. Interpolar la posición por timestamp y distancia dentro del segmento. Incorporar pausa, reanudación, salto en la línea de tiempo y velocidades 0,5×, 1×, 2× y 5×; 1× debe ser el valor inicial.

Pausar y reanudar no puede producir saltos. Al mover manualmente el cursor temporal, todos los vehículos deben quedar en posiciones deterministas para ese instante.

## Arquitectura de proveedores de datos

Evitar condiciones `if (demo)` dispersas por las pantallas. Crear una frontera común, por ejemplo:

```ts
interface TrackerDataSource {
  getMetadata(): Promise<TrackerSourceMetadata>
  listVehicles(filters?: VehicleFilters): Promise<Vehicle[]>
  listTrips(filters: TripFilters): Promise<Trip[]>
  getTrack(tripId: string): Promise<Track>
  getSnapshot(at: Date): Promise<FleetSnapshot>
  subscribePositions?(listener: PositionListener): Unsubscribe
}
```

Implementar al menos:

- `RealTrackerDataSource`: consume la API actual sin alterar su contrato innecesariamente.
- `DemoTrackerDataSource`: lee fixtures versionados y alimenta el motor de reproducción.

El contexto de React debe exponer estado, acciones y metadata genéricos. Los componentes de mapa, historial y analítica no deben importar directamente fixtures demo. La activación debe cambiar el proveedor de la sesión y limpiar correctamente consultas, selección, reloj y animaciones.

Por defecto, no persistir el modo demo entre sesiones. Si producto decide recordarlo, usar una preferencia explícita y nunca confundirla con datos de negocio.

## Laboratorio de demostración

Mantener o reconstruir un apartado claramente visible donde el usuario pueda:

- activar o desactivar datos de prueba;
- elegir escenario y fecha disponible;
- iniciar, pausar y reiniciar la reproducción;
- cambiar velocidad de reproducción;
- ver fecha/hora simulada y tiempo transcurrido;
- filtrar por vehículo sin que el filtro sea obligatorio;
- volver con una acción clara a **“Toda la flota”**;
- entender qué funciones están simuladas y cuál es la procedencia del dataset.

El botón no debe insertar miles de puntos en producción. La demo debe operar con fixtures aislados o un namespace/base de datos de demostración, según lo que revele la arquitectura existente.

## Comportamiento obligatorio del mapa

El estado de selección debe aceptar `null`:

```ts
type SelectedVehicleId = string | null
```

`null` significa **toda la flota**, no “seleccionar automáticamente el primer tractor”.

- Al abrir el mapa, mostrar todos los vehículos disponibles.
- En modo demo, todos los vehículos activos deben moverse simultáneamente según el reloj común.
- Ajustar límites para incluir la flota y la geometría pertinente sin reajustar el zoom en cada tick.
- Al pulsar un marcador o tarjeta, enfocar ese vehículo y mostrar sus detalles.
- Incluir una acción visible para limpiar la selección y regresar a toda la flota.
- Seguir la cámara sólo si existe una selección y el usuario activó **“Seguir vehículo”**.
- Si el usuario arrastra o acerca el mapa, suspender seguimiento automático sin borrar la selección.
- No destruir y recrear la instancia de Google Maps en cada actualización.
- Actualizar posición de marcadores eficientemente; los ticks de animación de alta frecuencia no deben provocar el render completo de toda la página.
- Cuando existan muchos vehículos, evaluar clustering en vista general, pero no ocultar movimiento o estados importantes.
- Distinguir visualmente recorrido realizado, recorrido pendiente, geocercas, calles y polígonos.

Para operación agrícola, no llamar “ruta vial” a líneas de trabajo dentro de un predio. Modelar por separado:

- rutas por calles/caminos públicos;
- caminos interiores conocidos;
- pasadas o surcos agrícolas;
- polígonos/geocercas.

## Historial reconstruido

La pantalla histórica debe permitir explorar, no sólo leer tarjetas estáticas.

- Rango de fecha/hora, vehículo opcional, estado y tipo de evento.
- Lista de viajes sincronizada con mapa y línea de tiempo.
- Selección de un viaje para ver ruta, inicio, fin, duración, distancia y eventos.
- Reproducción de un viaje o de toda la flota durante un intervalo.
- Gráfico de velocidad versus tiempo con cursor sincronizado al mapa.
- Tabla accesible como alternativa a gráficos y tooltips.
- Estados vacíos, carga, error y reintento.
- Badge inequívoco de datos sintéticos cuando corresponda.

## Analítica y definiciones de cálculo

Toda métrica debe indicar definición, unidad, rango temporal y filtros. No promediar promedios.

- **Distancia:** sumar distancias consecutivas válidas, ordenadas por tiempo, o usar distancia del motor vial cuando corresponda. Documentar cuál se muestra y evitar doble conteo al unir viajes.
- **Duración total:** `endedAt - startedAt`.
- **Tiempo en movimiento:** intervalos sobre un umbral de velocidad configurable, con histéresis o ventana mínima para evitar alternancia por ruido GPS.
- **Tiempo detenido:** duración válida menos tiempo en movimiento, separando detención e inactividad si existe información de ignición.
- **Velocidad media en movimiento:** distancia recorrida dividida por tiempo en movimiento; no promedio simple de muestras.
- **Velocidad máxima:** máximo de muestras validadas, con detección de outliers.
- **Odómetro:** base conocida más distancia validada; no recalcular todo el odómetro a partir de una ventana filtrada.
- **Paradas:** evento derivado de permanencia dentro de un radio durante un tiempo mínimo, no de un único punto con velocidad cero.
- **Utilización:** tiempo operativo dividido por ventana elegible, dejando claro qué horas son elegibles.

Los filtros de vehículo, fecha y modo de datos deben afectar consistentemente KPIs, gráficos, mapa y tabla. Añadir tooltips con definición y permitir profundizar desde una métrica hacia los viajes que la componen.

## Pantallas y experiencia visual

Completar la sustitución de las pantallas antiguas de Resumen, Monitoreo, Odómetro, Indicadores, Analítica, Maestros e Historial. No basta con cambiar colores: cada vista debe responder una pregunta operativa.

- **Resumen:** estado actual, alertas accionables, actividad reciente y acceso al mapa.
- **Monitoreo:** mapa dominante, lista de flota, filtros, selección opcional y seguimiento.
- **Odómetro:** lectura actual, variación, procedencia, calidad del dato y mantenimiento asociado.
- **Indicadores:** KPIs definidos, comparables y con navegación al detalle.
- **Analítica:** tendencias, distribución, utilización y comparación entre vehículos/períodos.
- **Maestros:** gestión clara de vehículos, dispositivos, operadores, geocercas y asociaciones.
- **Historial:** viajes, eventos, mapa y reproducción sincronizada.

Usar la paleta y componentes ya establecidos por el rediseño salvo que una revisión justifique cambios. Mantener contraste WCAG, estados de foco visibles, controles con nombre accesible, objetivos táctiles de al menos 44 px y una versión móvil funcional. Evitar densidad decorativa sin información.

Los componentes legacy pueden eliminarse después de comprobar con búsqueda estática y build que no siguen importados. No mantener dos implementaciones activas de la misma pantalla.

## Backend, seguridad y costos

- Cualquier llamada a un servicio de ruteo con credencial secreta debe ejecutarse en FastAPI/backend.
- Separar la clave de Maps JavaScript y la clave de servicios de ruteo; aplicar restricciones independientes.
- No imprimir claves, IMEI, tokens ni payloads sensibles en logs.
- Aplicar caché permitida, cuotas, rate limiting y timeouts.
- El generador de fixtures debe ser una herramienta administrativa o de desarrollo, no un endpoint público sin protección.
- Registrar el proveedor y la licencia/atribución en el artefacto generado.
- No ejecutar `npm audit fix --force` ni actualizaciones mayores indiscriminadas durante este trabajo.

## Entregables esperados

1. Generador reproducible del dataset de agosto de 2026, con semilla y validaciones.
2. Fixture o almacenamiento aislado, versionado y con metadata de procedencia/licencia.
3. Proveedor demo y proveedor real bajo una interfaz común.
4. Reloj/motor de reproducción testeable, independiente del mapa.
5. Laboratorio demo con activación, fecha/escenario y controles temporales.
6. Mapa de toda la flota por defecto y selección opcional.
7. Historial y analítica interactivos, sincronizados con los mismos filtros.
8. Definiciones de cálculos y pruebas unitarias de distancia, tiempos, velocidad, paradas y odómetro.
9. Pruebas de integración del cambio real/demo y de la reproducción multi-vehículo.
10. Auditoría visual, accesible y de rendimiento usando las skills indicadas.
11. README técnico para regenerar el dataset sin exponer credenciales.
12. Informe final con archivos cambiados, pruebas ejecutadas, riesgos y asuntos pendientes.

## Criterios de aceptación

- Al activar datos de prueba aparece una advertencia inequívoca de que son sintéticos.
- Con ningún vehículo seleccionado se ven **todos** los vehículos y ninguno se selecciona automáticamente.
- Varios vehículos se mueven simultáneamente durante la demo.
- Limpiar una selección vuelve a la vista de toda la flota.
- A 1×, el avance del reloj simulado coincide con el tiempo real dentro de una tolerancia razonable y documentada.
- Pausar/reanudar no salta posiciones y hacer seek produce siempre el mismo snapshot.
- Las rutas viales siguen calles reales y no atraviesan manzanas por interpolación directa.
- Las fechas históricas de agosto de 2026 se muestran correctamente en `America/Santiago`.
- Cambiar filtros actualiza mapa, KPIs, gráficos y tabla con el mismo universo de datos.
- Desactivar la demo restaura el proveedor real y limpia reloj, selección y caché demo.
- Recargar la aplicación no inserta ni convierte fixtures en registros productivos.
- Todas las claves secretas permanecen fuera del cliente y del repositorio.
- No hay errores nuevos de TypeScript, lint o build.
- Los cálculos centrales tienen pruebas con casos normales, puntos desordenados, gaps, duplicados y outliers.
- La navegación por teclado, foco, contraste y vista móvil fueron verificadas.

## Plan recomendado

### P0 — Contrato y aislamiento

- Auditar API, modelos y componentes actuales.
- Definir tipos canónicos y `TrackerDataSource`.
- Separar estado real, demo y selección de mapa.
- Corregir inmediatamente la selección obligatoria del primer tractor.

### P1 — Dataset reproducible

- Elegir zona y proveedor vial con licencia compatible.
- Implementar generador, semilla, validaciones y metadata.
- Generar fechas del 1 al 18 de agosto de 2026 para el escenario histórico inicial.
- Comprobar rutas visualmente y mediante distancia a la geometría vial.

### P2 — Reloj y mapa multi-vehículo

- Implementar motor temporal independiente del UI.
- Integrar posiciones interpoladas de toda la flota.
- Incorporar controles 0,5×/1×/2×/5×, pausa y seek.
- Optimizar renders, cámara y actualización de marcadores.

### P3 — Historial y analítica

- Sincronizar viajes, mapa, timeline, velocidad y eventos.
- Centralizar cálculos y definiciones.
- Agregar comparación, drill-down, estados vacíos y tabla accesible.

### P4 — Pulido y validación

- Aplicar auditorías de diseño, composición y rendimiento.
- Probar desktop/móvil, teclado y lectores de pantalla básicos.
- Ejecutar build, lint y tests.
- Documentar operación, regeneración del dataset y futura reconexión Teltonika.

## Deuda y precauciones conocidas

- El rediseño tiene como base el commit `4f469bf`; confirmar que la rama no recibió cambios nuevos antes de trabajar.
- Revisar si la capa de ruteo actual llama servicios desde el navegador; migrarla al backend cuando utilice credenciales privadas.
- Hay componentes antiguos que pueden seguir físicamente en el repositorio aunque ya no estén enrutados. Eliminarlos sólo tras confirmar que no tienen consumidores.
- Tratar advertencias históricas de lint y vulnerabilidades de dependencias como una línea de trabajo controlada. No ocultarlas ni resolverlas con cambios mayores automáticos que puedan romper Odoo o Vite.

## Definición de terminado para Claude

El trabajo no termina al verse bien en una captura. Termina cuando el modo demo está aislado y claramente etiquetado, el dataset es reproducible y sigue calles reales, toda la flota funciona sin selección obligatoria, el tiempo se reproduce correctamente, historial y analítica comparten cálculos consistentes, las pruebas pasan y existe documentación suficiente para regenerar y desplegar el resultado de forma segura.
