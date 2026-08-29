# Instrucciones para Claude: separar Movilización de Actividades y construir el módulo integral

## Texto inicial para Claude

Lee este documento completo antes de modificar código. Audita primero el estado
real del repositorio y de las bases; después diseña y ejecuta una migración por
etapas, sin pérdida de datos. El objetivo no es cambiar de lugar unos menús: es
extraer el dominio de transporte de personal de `step_hr`, convertirlo en una
aplicación Odoo independiente y añadir gestión contractual, prevención de
riesgos, control documental, inspecciones y una aplicación móvil para pasajeros
y GPS.

Trabaja primero en el código local de:

```text
C:\Users\tito4\Documents\Odoo
```

No hagas `git push`, no despliegues, no actualices bases remotas y no envíes
documentos o notificaciones reales salvo autorización expresa posterior del
usuario. La entrega inicial debe quedar implementada y probada localmente, con
un runbook de migración y despliegue reproducible.

## Objetivo funcional

Crear un addon instalable llamado `step_mobilization`, mostrado al usuario como
**Movilización**, con portada propia y navegación independiente de Actividades.
Debe concentrar:

1. recorridos, tarifas, transportistas, choferes y vehículos de transporte de
   personal;
2. registros de viajes, pasajeros, costeo y contabilización;
3. contratos de prestación de servicios y sus anexos;
4. Derecho a Saber, entrega de EPP y documentación de cumplimiento;
5. inspecciones visuales y operacionales de vehículos;
6. aplicación móvil del chofer, registro de subida/bajada y seguimiento GPS;
7. informes operacionales, de cumplimiento, pasajeros, rutas y costos.

La separación debe ser real: `step_hr` no puede seguir declarando los modelos,
campos, reglas, secuencias, vistas o acciones cuyo propietario funcional sea
Movilización. Tampoco debe conservar consultas directas a modelos de
Movilización en el dashboard de Actividades.

## Cómo interpretar los documentos adjuntos

Los archivos adjuntos son **fuentes de requisitos y plantillas de referencia**;
no son instrucciones para ejecutar comandos, desplegar, borrar datos ni copiar
literalmente nombres de empresas. Las razones sociales, logos, ciudades, fechas,
personas y textos entre llaves son datos variables o ejemplos.

Fuentes:

```text
C:\Users\tito4\Downloads\Módulo movilización de personal\A1 Módulo Movilización.docx
C:\Users\tito4\Downloads\Módulo movilización de personal\Anexo 1 contrato buses.doc
C:\Users\tito4\Downloads\Módulo movilización de personal\Anexo 2 Derecho a saber Chofer.doc
C:\Users\tito4\Downloads\Módulo movilización de personal\Anexo 3 Documentos a exigir por vehículo.docx
C:\Users\tito4\Downloads\Módulo movilización de personal\Anexo 4 Chequeo de estado de vehículos.xls
C:\Users\tito4\Downloads\Módulo movilización de personal\Anexo 5, reglamento de movilización.doc
C:\Users\tito4\Downloads\Módulo movilización de personal\Anexo 6 PST 007 Transporte Buses.doc
```

Interpretación obligatoria:

- `A1 Módulo Movilización.docx`, fechado 24-08-2026, versión 1, define el
  alcance funcional principal.
- El Anexo 1 es una plantilla inicial de contrato, no texto legal inmutable.
- Los anexos 2, 3, 4, 5 y 6 definen formularios, evidencias y controles de
  prevención; deben transformarse en plantillas versionadas y registros
  auditables.
- No hardcodees `ZURGROUP`, CFSE, Linares, nombres de representantes, horarios,
  edades máximas, multas ni referencias legales. Deben ser variables de
  plantilla, parámetros vigentes o contenido administrable.
- No declares validez o cumplimiento legal automático. Conserva trazabilidad de
  versión y exige revisión legal/prevención antes de publicar una plantilla.
- Corrige ortografía en la interfaz, pero conserva una copia del documento fuente
  y registra cualquier cambio sustantivo del texto contractual.

## Arquitectura requerida

```text
step_mobilization                    Núcleo de transporte de personal
├── maestros neutrales y multiempresa
├── recorridos, paradas, tarifas y contratos
├── viajes, pasajeros y eventos de subida/bajada
├── documentos, EPP, Derecho a Saber e inspecciones
├── costeo base, contabilidad y auditoría
├── API de integración para la aplicación móvil
├── dashboard, informes y seguridad
└── modelos estables sin dependencia de step_hr

step_mobilization_agriculture        Adaptador agrícola
├── depende de step_mobilization y step_hr
├── fundo, temporada, tarja, labor y actividad analítica
├── distribución agrícola de costos
└── migración de campos y relaciones agrícolas existentes

aplicación móvil / API               Dominio separado del tracker de maquinaria
├── autenticación de chofer/dispositivo
├── sesiones de viaje y pasajeros
├── PIN, código de barras/QR y NFC cuando el equipo lo permita
├── cola offline e idempotencia
├── puntos GPS y cumplimiento de recorrido
└── sincronización segura con Odoo
```

No hagas que `step_mobilization` dependa de `step_hr`; eso mantendría el
acoplamiento que se quiere eliminar. El adaptador agrícola puede depender de
ambos. No crees copias paralelas de los mismos modelos ni dupliques fórmulas
entre el núcleo y el adaptador.

`step_hr` debe seguir funcionando si Movilización no está instalado. Si se
quiere mostrar un acceso cruzado, resuélvelo mediante un adaptador o una
integración opcional, no mediante una referencia obligatoria a un XML ID
ausente.

## Estado actual comprobado en el repositorio

La implementación actual vive dentro de `step_hr` y usa, entre otros:

- `step.movi.registry`, `step.movi.registry.line`, `step.movi.cost.line` y
  `step.movi.cont.line`;
- `hr.route` y `hr.route.line`;
- `product.pricelist.move.line` y extensiones de `product.pricelist`;
- campos de Movilización en `hr.employee`, `res.partner`, `fleet.vehicle`,
  `product.template`, `res.company`, `res.config.settings` y `account.move`;
- secuencia `step_moviliza_seq`;
- vistas, acciones e informes bajo `step_hr.*`;
- accesos CRUD completos para `base.group_user`, sin separación de funciones ni
  reglas multiempresa específicas.

El menú actual contiene:

- Step Tracker;
- Tarifas Movilización;
- Registro Movilización;
- Costeo Movilización;
- Contabilización Movilización.

Además, en otros menús de Actividades existen:

- Análisis de Registro Movilización;
- Análisis de Costeo Movilización;
- Vehículo;
- Proveedor Movilización;
- Recorrido;
- Configuración Contable Movilización.

El dashboard de Actividades consulta directamente `step.movi.registry`, muestra
el KPI Movilizaciones y abre acciones `step_hr.action_step_movi_registry`.

### Riesgos técnicos que deben auditarse y corregirse

No copies ciegamente la implementación actual. Verifica al menos:

- preservación de tablas, registros, chatter, adjuntos y XML IDs al cambiar el
  addon propietario;
- dependencia implícita de `purchase.order`, modelos contables y localización
  chilena;
- ausencia de reglas multiempresa y permisos demasiado amplios;
- secuencia global con `company_id = False`;
- estado `cont` frente a referencias a `conta`;
- tarifa no encontrada antes de acceder a `cobro_type`;
- división por cero y división por cantidad de líneas en vez de pasajeros
  únicos;
- duplicación de líneas de costo al recalcular;
- búsqueda de temporada sin compañía y asignación analítica frágil;
- uso de `account_control_ids[0]` sin validar configuración;
- cambio de estado antes de completar de forma atómica la contabilización;
- dominio de vehículo basado en `driver_id = False`;
- relación incoherente entre `partner_id`, `partner_ids` y transportista;
- `ondelete='cascade'` desde el fundo hacia registros operacionales;
- líneas que mezclan `operacion`, `hr_in` y `hr_out` sin un modelo de eventos;
- campos obligatorios que hoy aceptan vacío;
- método `create` sin `@api.model_create_multi` y que reemplaza siempre el
  nombre recibido;
- mensajes `print`, imports sin uso, campos duplicados en vistas y textos
  heredados de otros dominios.

## Regla especial sobre Step Tracker

El código actual llamado **Step Tracker** sincroniza maquinaria agrícola,
órdenes de trabajo y sesiones GPS desde una API FastAPI. No representa viajes
de buses ni pasajeros.

Por tanto:

1. no reutilices las tablas `step.tracker.*` de maquinaria para pasajeros;
2. no rompas su dashboard, cron, API ni configuración actual;
3. mantén el tracker de maquinaria en Actividades/Operaciones salvo evidencia
   funcional contraria;
4. en la nueva aplicación Movilización crea un acceso **Seguimiento en línea**
   —o **Step Tracker Movilización** si se necesita conservar el nombre visible—
   respaldado por entidades y endpoints propios;
5. se permite reutilizar patrones técnicos del frontend, PWA y backend, pero no
   mezclar identidades, sesiones o puntos GPS de ambos dominios.

Si la auditoría demuestra que el antiguo menú `Step Tracker` era sólo un acceso
vacío destinado a Movilización, migra ese acceso sin trasladar los modelos de
maquinaria. Documenta la decisión.

## Fase 1: auditoría antes de modificar

### 1.1 Inventario de código

Genera una matriz con estas columnas:

| Elemento actual | Tipo | Addon propietario actual | Dependencias | Destino | Estrategia de migración |
|---|---|---|---|---|---|

Incluye modelos, campos, tablas, constraints, secuencias, XML IDs, acciones,
menús, vistas, plantillas, reglas, accesos, crons, parámetros de compañía,
assets, pruebas y llamadas desde otros addons.

Busca referencias en todo el repositorio, no sólo en `step_hr`. Confirma qué
campos de `fleet.vehicle`, `res.partner`, `hr.employee`, `product.template`,
`product.pricelist`, `account.move` y `res.company` son exclusivamente de
Movilización y cuáles también usa maquinaria, cosecha u otros módulos.

### 1.2 Inventario de datos

En cada base autorizada, sólo mediante consultas de lectura en esta fase,
registra conteos por compañía y estado de:

- viajes y líneas de pasajeros;
- líneas de costo y contabilización;
- recorridos y paradas;
- tarifas y líneas de tarifa;
- transportistas, choferes y vehículos relacionados;
- asientos o facturas vinculados;
- adjuntos y mensajes;
- XML IDs y modelos/campos registrados por Odoo.

Busca registros huérfanos, duplicados, viajes sin fecha, tarifa, ruta, vehículo,
transportista o compañía, y referencias contables inválidas. No “arregles” esos
datos durante la auditoría; genera un reporte y una estrategia explícita.

### 1.3 Contrato de compatibilidad

Antes de mover código, define:

- modelos y nombres de tabla que se conservarán;
- XML IDs que se renombrarán y aliases temporales que permanecerán;
- endpoints o acciones externas que deben seguir resolviendo;
- orden exacto de instalación/actualización;
- rollback probado;
- período de compatibilidad y fecha de retiro de aliases.

No continúes si la migración propuesta implica recrear tablas o volver a cargar
registros desde cero.

## Fase 2: crear el núcleo `step_mobilization`

### 2.1 Dependencias y propiedad

Usa sólo addons estándar realmente necesarios, por ejemplo `base`, `mail`,
`web`, `hr`, `contacts`, `fleet`, `product`, `account` y `analytic`. Confirma los
nombres exactos en Odoo 18 y añade la localización sólo si un modelo referenciado
la exige realmente.

El núcleo debe poseer los modelos neutrales, la seguridad, datos base, secuencias,
dashboard, informes y configuración de Movilización. El adaptador agrícola debe
poseer exclusivamente las extensiones hacia `step.fundo`, `step.temporada`,
tarjas, labores y actividades agrícolas.

### 2.2 Maestros

Implementa o migra, sin pérdida de identidad:

- transportistas de personal y sus contactos;
- choferes vinculados a transportista, con vigencia y estado;
- vehículos de transporte, capacidad sentada, propietario/transportista y
  habilitación;
- recorridos, paradas ordenadas, coordenadas/geocercas, distancia, duración y
  tipo de viaje;
- tarifas por contrato, recorrido, sentido, mínimo de pasajeros, vigencia,
  moneda y compañía;
- tipos de documento, EPP, inspección y riesgos como datos configurables.

No uses el PIN del empleado como identificador visible o clave almacenada en
texto plano. Define un identificador móvil opaco y una estrategia segura de
verificación.

### 2.3 Viajes y pasajeros

Conserva `step.movi.registry` si eso minimiza el riesgo de migración, pero mejora
su semántica y trazabilidad. Como mínimo debe incluir:

- UUID externo e idempotente;
- compañía, fecha, ruta, sentido, transportista, chofer y vehículo;
- hora programada, inicio real, término real y zona horaria;
- origen móvil/manual/importado;
- estado controlado: borrador, abierto, cerrado, validado, costeado,
  contabilizado y cancelado;
- responsable y motivo obligatorio para correcciones/cancelaciones;
- conteo de abordados, a bordo y descendidos;
- capacidad y alerta/bloqueo por sobrecupo;
- vínculo inmutable al asiento generado.

No representes subida y bajada ambiguamente en una sola selección. Usa eventos
append-only o un modelo normalizado que registre por cada marcación:

- pasajero;
- tipo `boarding`/`alighting`;
- fecha y hora del dispositivo y del servidor;
- latitud, longitud, precisión y fuente;
- método PIN, código, NFC o manual;
- dispositivo, UUID e idempotency key;
- estado de sincronización y motivo de corrección.

Mantén una proyección de “pasajeros actualmente a bordo”, pero conserva los
eventos originales para auditoría.

### 2.4 Costeo y contabilidad

Separa el cálculo del efecto contable. El costeo debe ser determinista,
recalculable y auditable; la contabilización debe ser atómica e idempotente.

- valida tarifa, vigencia, moneda, ruta, sentido y cantidad antes de calcular;
- define explícitamente si la tarifa es fija, por pasajero, mínima, proporcional
  o por ida/vuelta;
- no dividas por líneas duplicadas de entrada/salida;
- guarda versión de tarifa y desglose usados;
- nunca dupliques líneas al recalcular;
- no contabilices si hay documentos, inspecciones o configuración contable
  bloqueantes;
- valida diario, cuentas y distribución antes de cambiar estado;
- no publiques automáticamente el asiento salvo requisito confirmado;
- impide una segunda contabilización del mismo viaje;
- toda reversa debe usar mecanismos contables, no borrar el asiento.

La asignación a fundo, temporada, centro de costo y labor agrícola pertenece al
adaptador. El núcleo debe exponer hooks/payloads estables para esa distribución.

## Fase 3: contratos y prevención

### 3.1 Contratos de movilización

Crea gestión de contratos con compañía, transportista, representante, temporada
o período, faena/servicio, vigencia, moneda, rutas/tarifas, vehículos, choferes,
responsables, anexos, estados, aprobaciones y chatter.

Estados mínimos:

```text
borrador -> en revisión -> aprobado -> vigente -> vencido/terminado/cancelado
```

Genera un PDF desde una plantilla versionada. El contrato debe insertar como
anexo o numeral una tabla de las tarifas efectivamente asociadas, con recorrido,
sentido, mínimo de pasajeros, valor, moneda y vigencia. Congela una instantánea
de los datos al emitir para que una modificación futura de la tarifa no cambie
un contrato ya firmado.

Variables mínimas identificadas en el Anexo 1:

- compañía, RUT, dirección, representante y cargo;
- transportista, RUT, dirección, contacto y representante;
- ciudad y fecha;
- temporada, faena y vigencia;
- capacidades y condiciones de servicio;
- tarifas y recorridos;
- fiscalizador, árbitro y firmas.

Los anexos 5 y 6 deben poder incorporarse al paquete contractual como versiones
vigentes y dejar evidencia de entrega/aceptación.

### 3.2 Derecho a Saber

Implementa una plantilla versionada por compañía y un registro por chofer que
conserve:

- empresa empleadora/transportista;
- chofer y RUT en la salida documental, con permisos restringidos;
- puesto, fecha, lugar, relator y versión de plantilla;
- matriz actividad-riesgo-consecuencia-medidas preventivas;
- firmas o evidencia de aceptación;
- PDF emitido e inmutable;
- renovación y vencimiento cuando corresponda.

Incluye inicialmente los riesgos de mantención y desplazamiento descritos en el
Anexo 2, pero como datos administrables.

### 3.3 Entrega de EPP

Registra entregas por chofer con ítem, cantidad, talla, certificación, fecha,
estado, reposición, motivo, entregado por, recibido por y firma/evidencia.
Considera chaleco/peto reflectante y, según riesgo, gorro, bloqueador, manguillas
y calzado de seguridad. No concluyas que la lista es exhaustiva.

### 3.4 Documentos de cumplimiento

Implementa tipos de documento configurables con alcance `transportista`,
`chofer`, `vehículo` o `contrato`; fechas de emisión/vencimiento; adjunto;
estado de revisión; observaciones; responsable; recordatorios; y regla
bloqueante/no bloqueante.

La configuración inicial debe contemplar, al menos:

- revisión técnica;
- seguro obligatorio y pólizas requeridas;
- permiso de circulación;
- autorización de transporte aplicable;
- padrón;
- letrero de trabajadores agrícolas de temporada;
- licencia de conducir adecuada;
- contrato de trabajo del chofer;
- Derecho a Saber;
- entrega de EPP;
- curso de manejo defensivo;
- contrato de arriendo cuando vehículo/transportista no coincidan;
- registros sanitarios sólo si la compañía confirma que siguen vigentes.

No conviertas referencias históricas como COVID-19 en bloqueos permanentes sin
configuración vigente.

### 3.5 Inspección del vehículo

Crea plantillas versionadas, inspecciones y líneas con resultado `sí`, `no`, `no
aplica`, observación, evidencia fotográfica y criticidad. Registra inspector,
fecha/hora, odómetro, vehículo, chofer, ubicación, firma y estado final
`aprobado`, `aprobado con observaciones` o `rechazado`.

Carga como plantilla inicial los controles del Anexo 4:

**Inspección visual**

- letrero de trabajadores agrícolas de temporada;
- espejos exteriores e interiores;
- neumáticos, profundidad y presión;
- botiquín;
- extintor y mantención vigente;
- instrumentos y bocina;
- puertas de servicio y escape;
- ventanas y sistema de expulsión;
- panel del conductor;
- piso, peldaños y parabrisas;
- salidas de escape y pasamanos.

**Inspección operacional**

- luces altas, bajas, traseras e intermitentes;
- freno de estacionamiento, servicio y motor;
- lavador, desempañador y limpiaparabrisas;
- dispositivo que impide marcha con puerta abierta.

Los valores numéricos del formulario fuente deben ser parámetros o texto de la
versión de plantilla, no constraints universales hardcodeados. Un defecto crítico
debe poder bloquear la apertura de un viaje hasta su cierre o autorización
documentada.

## Fase 4: aplicación móvil del chofer

### 4.1 Flujo mínimo

1. El chofer inicia sesión de forma segura y selecciona vehículo y recorrido.
2. La aplicación valida contrato, habilitación, capacidad, documentos e
   inspección previa.
3. El chofer define el método de marcación disponible.
4. Al subir, cada trabajador se identifica por PIN, código de barras/QR o NFC.
5. Se registra evento, hora, posición y precisión, incluso sin conexión.
6. Al bajar, se registra el evento equivalente.
7. La aplicación muestra pasajeros a bordo y alerta sobre duplicados,
   desconocidos, recorrido incorrecto o sobrecupo.
8. Cuando baja el último pasajero, ofrece/cierra automáticamente la sesión según
   política configurable. Siempre existe cierre manual con motivo.
9. La sincronización actualiza Odoo de forma idempotente y nunca duplica un
   viaje o una marcación.

### 4.2 Offline, NFC y compatibilidad

- La app debe seguir registrando sin red mediante una cola durable local.
- Cada evento debe tener UUID generado en el dispositivo e idempotency key.
- La sincronización debe tolerar reintentos, orden distinto y reloj incorrecto.
- Nunca borres eventos locales antes de confirmación del servidor.
- Web NFC no está disponible de forma uniforme, especialmente en iOS. Detecta
  capacidad y ofrece siempre PIN y código/QR como fallback.
- No guardes PIN, RUT completo, token permanente ni lista completa de empleados
  en texto plano en el dispositivo.
- Usa tokens de corta duración, refresh seguro, cierre remoto y asociación de
  dispositivo.

### 4.3 GPS y privacidad

Registra GPS sólo durante una sesión activa, con indicador visible. Define
frecuencia adaptable, precisión, tolerancia offline, consumo de batería,
retención y acceso por rol. Conserva consentimiento/base operacional y no
recolectes ubicación fuera del viaje.

El backend debe poder calcular:

- posición actual y última actualización;
- recorrido real y distancia;
- paso por paradas/geocercas;
- adelanto/atraso respecto del horario;
- desvíos y detenciones;
- porcentaje de cumplimiento de lugares y horario.

No uses sólo coordenadas enviadas por el cliente para decisiones sensibles sin
registrar precisión, antigüedad y señales de manipulación.

### 4.4 API

Versiona endpoints bajo un namespace propio, por ejemplo `/mobilization/v1`.
Aplica autenticación, autorización por compañía/chofer, rate limiting, límites
de payload, validación estricta y logs sin datos sensibles.

Contratos mínimos:

- autenticación y registro de dispositivo;
- catálogo permitido de vehículos, rutas y pasajeros identificables;
- apertura/consulta/cierre de sesión;
- envío por lote de eventos de pasajeros;
- envío por lote de puntos GPS;
- estado de sincronización y resolución de conflictos;
- health/capabilities compatible con el cliente instalado.

La API no debe exponer credenciales de Odoo ni permitir que un chofer consulte
viajes, pasajeros o documentos de otra compañía/transportista.

## Fase 5: experiencia Odoo e informes

### 5.1 Aplicación y menús

La aplicación raíz **Movilización** debe contener una portada y, como mínimo:

```text
Movilización
├── Inicio
├── Operación
│   ├── Seguimiento en línea
│   ├── Viajes / Registro de Movilización
│   ├── Costeo
│   └── Contabilización
├── Contratos y cumplimiento
│   ├── Contratos
│   ├── Derecho a Saber
│   ├── Entrega de EPP
│   ├── Documentos
│   └── Inspecciones de vehículos
├── Tarifas y recorridos
├── Informes
│   ├── Análisis de Registro
│   ├── Análisis de Costeo
│   ├── Pasajeros por día y vehículo
│   ├── Cumplimiento de recorrido
│   └── Vencimientos y no conformidades
├── Maestros
│   ├── Vehículos
│   ├── Transportistas
│   ├── Choferes
│   ├── Recorridos y paradas
│   └── Plantillas
└── Configuración
    ├── Contabilidad
    ├── Aplicación móvil/GPS
    └── Reglas de cumplimiento
```

Elimina los menús equivalentes de Actividades sólo después de verificar que los
nuevos accesos funcionan y que no hay favoritos/acciones rotas. No dupliques la
aplicación en Home.

### 5.2 Dashboard

Incluye KPI y accesos útiles:

- viajes abiertos, cerrados y con atraso;
- vehículos activos/en ruta y última posición;
- pasajeros transportados y actualmente a bordo;
- capacidad/sobrecupo;
- contratos próximos a vencer;
- documentos vencidos o faltantes;
- inspecciones rechazadas;
- costo por período, ruta, transportista y pasajero;
- alertas de sincronización móvil.

El dashboard debe ser multiempresa, rápido con volúmenes reales y usable en
móvil. No cargues todos los puntos GPS para construir la portada.

## Fase 6: seguridad y auditoría

Crea grupos específicos, sin conceder CRUD total a `base.group_user`:

- usuario/consulta de Movilización;
- operador/despachador;
- chofer móvil, sin acceso backend general;
- gestor de contratos;
- prevención de riesgos;
- costeo;
- contabilización;
- aprobador;
- auditor/administrador.

Aplica reglas por `company_id` y, cuando corresponda, por transportista/chofer.
Separa emitir, aprobar, costear, contabilizar y anular. Los documentos con RUT,
firmas, ubicación y datos laborales requieren permisos restringidos.

Registros cerrados, firmados, aprobados o contabilizados no se eliminan. Usa
cancelación, reversa y bitácora. Registra cambios de estado, usuario, fecha,
motivo y versión de datos/documentos.

## Fase 7: migración sin pérdida de datos

Implementa migraciones idempotentes y un comando de verificación. Estrategia
esperada:

1. respaldar base, filestore y addons;
2. desplegar juntos núcleo, adaptador y versión de `step_hr` que deja de declarar
   Movilización;
3. instalar `step_mobilization` y `step_mobilization_agriculture` en el orden
   validado;
4. conservar nombres de tabla cuando sea razonable;
5. reasignar de forma controlada metadatos `ir.model.data` de modelos, campos,
   vistas, acciones, secuencias y reglas;
6. mantener aliases temporales para XML IDs externos usados por favoritos,
   dashboards u otros addons;
7. migrar configuración por compañía;
8. recalcular sólo campos derivados, nunca asientos o importes históricos;
9. comparar conteos, relaciones, adjuntos, mensajes y sumas antes/después;
10. abortar con mensaje claro ante registros imposibles de mapear.

No desinstales `step_hr` para efectuar la separación. No renombres tablas con
SQL improvisado. No borres los antiguos XML IDs hasta demostrar que no existen
referencias. No uses IDs numéricos hardcodeados.

Incluye un rollback ensayado que restaure simultáneamente código, base y
filestore del mismo punto temporal.

## Fase 8: pruebas

### 8.1 Pruebas estáticas e instalación

- compilación de Python;
- parseo de XML/CSV;
- lint/sintaxis de JavaScript o TypeScript;
- instalación limpia del núcleo;
- instalación limpia del adaptador agrícola;
- actualización desde el estado actual con datos representativos;
- reinstalación/upgrade idempotente;
- ausencia de dependencia circular;
- desinstalación controlada sólo en una base descartable para verificar que no
  afecta `step_hr` ni el tracker de maquinaria.

### 8.2 Pruebas de dominio

- tarifa faltante, vencida y con distintos sentidos;
- cero pasajeros, un pasajero y eventos duplicados;
- ida/vuelta con el mismo pasajero;
- sobrecupo;
- recálculo sin duplicar costos;
- contabilización única, falla atómica y reversa;
- viaje sin documentos o con inspección crítica rechazada;
- contrato emitido con snapshot de tarifas;
- cambio de tarifa posterior sin alterar PDF histórico;
- vencimientos y recordatorios;
- permisos y aislamiento entre compañías.

### 8.3 Pruebas móviles

- PIN, código/QR y NFC cuando exista soporte;
- fallback cuando NFC no existe;
- pérdida de red antes, durante y después de un viaje;
- reintentos y lotes duplicados;
- reinicio de la app con cola pendiente;
- dispositivo con hora incorrecta;
- GPS denegado, impreciso o intermitente;
- cierre automático al bajar el último pasajero;
- cierre manual con pasajeros a bordo y motivo;
- dos dispositivos intentando operar el mismo viaje;
- token vencido o dispositivo revocado;
- rendimiento y batería en un recorrido prolongado.

### 8.4 Regresión

- Actividades abre sin consultar modelos ausentes;
- Tracker de maquinaria, cron y dashboard siguen funcionando;
- Cosecha, nómina, colaciones, flota y contabilidad no cambian sus flujos;
- favoritos o URLs antiguas muestran el nuevo destino o un mensaje controlado;
- no aparecen nuevos `ERROR`, `CRITICAL` ni `Traceback`.

## Despliegue posterior, sólo con autorización

Si el usuario autoriza desplegar, lee primero:

```text
C:\Users\tito4\Documents\Odoo\docs\AUDITORIA_HOMOLOGACION_ODOO_2026-08-24.md
C:\Users\tito4\Documents\Odoo\docs\PROMOVER_DEMO_A_DESARROLLO.md
```

Antes de escribir en servidor:

- confirma ambientes, bases, rutas, servicios y versiones actuales;
- verifica que no exista otro upgrade, copia o despliegue activo;
- crea respaldos nuevos con `pg_dump -Fc`, filestore, addons y SHA-256;
- usa una copia de prueba o Desarrollo primero;
- presenta `dry-run` de archivos;
- actualiza sólo los addons necesarios;
- valida Odoo con `--stop-after-init --no-http` antes de reiniciar;
- reinicia únicamente el servicio del ambiente objetivo;
- valida navegador de escritorio y móvil, RPC, logs y HTTP;
- no copies bases entre ambientes ni modifiques proveedores externos.

No uses Producción como primer ambiente. No declares éxito sólo porque el
servicio quede activo.

## Entregables obligatorios

1. `step_mobilization` y `step_mobilization_agriculture` instalables.
2. Aplicación móvil y API versionada, o un prototipo ejecutable completo si el
   alcance se entrega por hitos.
3. Migraciones pre/post idempotentes.
4. Matriz de inventario y mapeo de propiedad.
5. Reporte de datos antes/después.
6. Plantillas iniciales derivadas de los anexos, versionadas y editables.
7. Pruebas automatizadas y evidencia de resultados.
8. Manual breve de operador, chofer, contratos, prevención y contabilidad.
9. Runbook de instalación, despliegue y rollback.
10. Registro de decisiones, supuestos y asuntos legales pendientes.

## Criterios de aceptación

La tarea sólo está completa cuando:

- Movilización aparece como aplicación independiente y no como sección de
  Actividades;
- `step_hr` funciona sin `step_mobilization` y no consulta sus modelos;
- los datos históricos, adjuntos, chatter, relaciones y asientos se conservan;
- no existen modelos duplicados ni dependencias circulares;
- contratos incorporan una instantánea auditable de tarifas;
- Derecho a Saber, EPP, documentos e inspecciones tienen versiones, evidencias,
  estados y permisos;
- la app registra subida y bajada con hora/lugar por PIN, código o NFC con
  fallback;
- el modo offline sincroniza sin duplicados;
- el seguimiento GPS funciona sólo durante el viaje y permite medir recorrido y
  horario;
- los tres informes solicitados —seguimiento en línea, pasajeros por día y
  vehículo, cumplimiento de recorrido— producen resultados verificables;
- costeo y contabilización son idempotentes, auditables y multiempresa;
- el tracker de maquinaria no presenta regresiones;
- las pruebas de instalación, migración, seguridad, móvil y regresión pasan;
- no hay errores nuevos atribuibles a los addons;
- cualquier despliegue autorizado cuenta con respaldo validado y rollback.

## Forma de trabajo y reporte

Mantén un plan actualizado y avanza de fase sólo con evidencia. Si encuentras
una decisión que cambia datos, arquitectura o alcance —por ejemplo renombrar
modelos, elegir backend móvil o alterar la fórmula contractual— documenta las
alternativas y elige la opción más conservadora compatible con estos criterios.

Al finalizar informa de forma concreta:

- archivos y addons creados o modificados;
- decisiones arquitectónicas;
- estrategia de migración y conteos;
- pruebas ejecutadas y resultados;
- limitaciones o asuntos legales pendientes;
- pasos exactos aún no autorizados, como despliegue o publicación móvil.

