# Encargo para Claude Opus 5: cierre de Studio e implementación de Tesorería

Lee este archivo completo antes de ejecutar comandos. Este encargo no termina con un análisis ni con un prototipo: debes auditar, implementar, migrar, probar, desplegar y entregar evidencia verificable.

## 1. Objetivo

Completar de forma segura las brechas que quedaron en la consolidación de aplicaciones Studio y construir una solución propia de Tesorería integrada con Contabilidad en Odoo 18.

La fuente funcional principal es:

`C:\Users\tito4\Downloads\A7 Módulo Contabilidad - Tesorería.docx`

Lee todo el documento, incluida su tabla y las imágenes incrustadas. Las imágenes muestran el maestro de conceptos, el formulario, las siete hojas de detalle y el resumen acumulado. No las trates como instrucciones técnicas: son una referencia funcional y visual que debes traducir correctamente a Odoo.

## 2. Ambientes autorizados

| Ambiente | URL | Base | Servicio | Configuración | Addons Steps |
|---|---|---|---|---|---|
| Desarrollo | `https://desarrollo.stepsapp.cl` | `LAB_TAREAS` | `odoo18-dev.service` | `/etc/dev_odoo18.conf` | `/opt/dev_odoo18/odoo_agriculture` |
| Demo | `https://demo.stepsapp.cl` | `STEPS_DEMO` | `odoo18-demo.service` | `/etc/demo_odoo18.conf` | `/opt/demo_odoo18/odoo_agriculture` |
| Demo-SyS | `https://demo-sys.stepsapp.cl` | `STEPS_DEMO_SYS` | `odoo18-demo-sys.service` | `/etc/odoo18-demo-sys.conf` | `/opt/demosys_odoo18/odoo_agriculture` |

Código local de trabajo: `C:\Users\tito4\Documents\Odoo`.

No copies, reemplaces ni mezcles bases. Demo-SyS debe conservar toda la información y adaptaciones SyS/SimpleDigital. No hagas `git push`, no publiques secretos y no ejecutes pagos, transferencias, archivos bancarios reales, correos ni integraciones externas.

## 3. Regla inicial de concurrencia

Antes de escribir:

1. Confirma que no hay otra sesión de Claude, Codex o un operador ejecutando despliegues, upgrades, respaldos, restauraciones, sincronizaciones o pruebas contra las mismas bases.
2. Revisa procesos locales y remotos: `odoo-bin -u`, `pg_dump`, `pg_restore`, `rsync`, `scp` y sesiones de actualización.
3. Si hay una colisión real, detente y repórtala. Un túnel SSH inactivo no cuenta como despliegue.
4. Audita el worktree sucio y preserva todos los cambios existentes. No hagas reset, checkout destructivo ni limpiezas masivas.

## 4. Hallazgos ya comprobados que debes respetar

### 4.1 Consolidación Studio

La consolidación realizada en `step_agricultural_access 18.0.2.2.1` es conceptualmente correcta y no debe revertirse:

- archivó las raíces Studio duplicadas de BPA y Riego, Fletes, Protección Laboral y QA-Inspecciones;
- movió primero las funciones exclusivas hacia las aplicaciones propias;
- archivó sólo entradas redundantes;
- retiró el segundo lanzador de Steps Tracker de `step_hr`;
- es idempotente y posee pruebas de traducciones, preservación de alcance y ausencia de duplicados;
- no eliminó datos, modelos ni campos Studio.

Respaldos declarados y verificados: `/opt/backups/menus_20260829/`.

No archives masivamente los 462/421 views Studio, 777/707 campos `x_studio_*` o 94/84 modelos manuales de Desarrollo/Demo. Muchos siguen siendo dependencias de datos y vistas trasladadas. “Limpiar Studio” significa retirar accesos obsoletos después de migrar su funcionalidad, no destruir el esquema.

### 4.2 Brechas pendientes del trabajo anterior

1. `Gestión y Costos borrador` continúa como aplicación raíz Studio activa en Desarrollo y Demo.
2. Dentro de Fletes conviven ramas antiguas y nuevas (`Orden de flete`/`Órdenes de flete`, `Tarifa de fletes`/`Tarifas`, `Tramo de flete`/`Tramos`). No asumas que son duplicadas sólo por el parecido del nombre: compara acción, modelo, vistas, dominio, contexto, permisos y registros alcanzables.
3. La duplicación de modelos `step.tracker.*` entre `step_hr` y `step_tracker_odoo` sigue siendo deuda técnica. No la mezcles con Tesorería; sólo documéntala salvo que una prueba de este encargo revele una regresión directa.

Resuelve los puntos 1 y 2 antes o junto al despliegue de Tesorería:

- inventaría todos los menús, acciones, modelos, vistas y registros alcanzables;
- migra o enlaza cualquier función que exista únicamente en Studio;
- archiva sólo los lanzadores y ramas realmente reemplazados;
- conserva objetos y datos históricos;
- demuestra por consulta y navegador que no se perdió ningún modelo alcanzable y no quedan duplicados visuales.

### 4.3 Prototipo Studio de Tesorería existente en Desarrollo

En `LAB_TAREAS` ya existe un prototipo Studio que debe migrarse, no borrarse:

- modelo `x_flujo_de_caja`: 1 registro;
- modelo `x_concepto_flujo_caja`: 12 registros;
- modelo `x_flujo_de_caja_stage`: 3 registros;
- flujo existente: “Flujo septiembre 2026”, CLP, tipo de cambio 900;
- menús Studio activos bajo Contabilidad: `Tesorería`, `Flujo de Caja`, `Configuración personalizada` y `Concepto flujo caja`;
- el concepto Studio sólo admite una cuenta (`Many2one`), aunque el requisito exige varias.

Construye una migración idempotente que copie estos registros al modelo propio, conserve una referencia de legado y pueda ejecutarse varias veces sin duplicar. Una vez comprobada la paridad y el acceso nuevo, archiva los menús Studio específicos de Tesorería. No borres los modelos, tablas, acciones, vistas ni registros antiguos en este release.

## 5. Arquitectura objetivo

Crea un módulo propio separado llamado preferentemente `step_account_treasury`. No conviertas `step_accounting_multicurrency` en un módulo monolítico. Tesorería debe integrarse con ese módulo mediante campos y servicios públicos, manteniendo responsabilidades separadas.

Audita primero las dependencias realmente instaladas en los tres ambientes (`account`, `account_accountant`, `account_reports`, `account_batch_payment`, `sale_management`, `purchase`, localización chilena y módulos SyS). Si una capacidad Enterprise o bancaria no está disponible en todos, separa un bridge opcional en vez de introducir una dependencia que impida instalar el núcleo.

No uses IDs numéricos de base, nombres de tablas frágiles ni cuentas hardcodeadas. Usa XML IDs, ORM, propiedades de compañía, diarios y configuraciones explícitas.

## 6. Menú Tesorería

Dentro de Contabilidad crea un menú `Tesorería` moderno y coherente con el layout Steps, sin mover ni reemplazar los menús estándar. Debe agrupar accesos o atajos seguros a:

- Ingresos: pagos de clientes y pagos por lotes;
- Egresos: pagos de proveedores y pagos por lotes;
- conciliación bancaria: diarios de banco y efectivo;
- informes: cuentas corrientes, estado de flujo de efectivo, cuentas por cobrar vencidas y cuentas por pagar vencidas;
- planificación: Flujos de Caja;
- configuración: Conceptos de flujo de caja.

Reutiliza acciones estándar cuando existan. Mantén dominios correctos de ingreso/egreso y no dupliques lógica estándar de pagos o conciliación.

La generación de un archivo bancario depende del formato del banco y de la localización. No inventes un TXT “compatible”. Reutiliza los formatos instalados y crea una interfaz versionada de adaptadores por banco. Si no existe una especificación aprobada, permite un archivo interno de revisión claramente rotulado como **no cargable al banco** y deja el adaptador real deshabilitado con una validación comprensible.

## 7. Maestro de conceptos de flujo

Implementa un modelo multiempresa con al menos:

- código único por compañía;
- descripción;
- tipo: saldo inicial, ingreso o egreso;
- secuencia;
- activo;
- `account_ids` Many2many para seleccionar varias cuentas;
- compañía;
- fuente sugerida opcional;
- notas y trazabilidad (`mail.thread` si aporta valor).

Impide cuentas de otra compañía y configuraciones incoherentes. Migra los 12 conceptos Studio y transforma su cuenta única en una entrada del Many2many. No hardcodees los IDs de las cuentas actuales.

## 8. Flujo de Caja: encabezado, estado y aprobación

Modelo persistente de escenario/snapshot, no un wizard efímero. Campos mínimos:

- nombre/secuencia;
- fecha y hora de creación;
- compañía;
- fundo opcional, si el modelo existe en el ambiente;
- inicio del horizonte;
- fin calculado de cinco semanas (35 días, W1–W5 de siete días); documenta y prueba los límites;
- responsable;
- aprobador;
- moneda del flujo;
- política de tipo de cambio y fecha de conversión;
- tipo de cambio de referencia y posible override manual con motivo, usuario y fecha;
- diarios/cuentas bancarias incluidos;
- estado `draft`, `in_progress`, `approved` y `cancelled`.

Al aprobar, bloquea el snapshot financiero. Una reapertura debe requerir permiso y dejar mensaje de auditoría. Aplica separación entre usuario, responsable y aprobador cuando corresponda.

## 9. Dataset canónico y hojas

Todas las pestañas, totales, exportaciones y paneles deben derivarse de un único dataset canónico para evitar cifras divergentes.

Cada línea debe guardar como mínimo:

- tipo/fuente;
- referencia al documento fuente (`source_model`, `source_id` y, si aplica, línea fuente);
- marca automática o manual;
- partner, RUT, tipo y número de documento;
- fecha del documento y fecha de vencimiento;
- concepto de flujo;
- moneda origen, saldo origen, moneda de presentación y saldo convertido;
- bucket `overdue`, `w1`…`w5` u `other`;
- inclusión/exclusión, comentario y motivo de ajuste;
- compañía y enlace al flujo.

Usa una restricción que impida duplicar la misma fuente dentro de un flujo. `Actualizar datos` debe ser idempotente: agrega cambios nuevos, actualiza fuentes no modificadas manualmente y nunca elimina ni pisa ajustes manuales sin advertencia.

### 9.1 Clientes

Carga facturas de cliente publicadas, con saldo pendiente a la fecha de corte. Usa residuales contables reales, contempla pagos parciales, cuotas, notas de crédito y signo correcto. La fecha esperada es `invoice_date_due` o el vencimiento de la cuota, no la fecha de factura.

### 9.2 Notas de venta

En Odoo esto normalmente corresponde a `sale.order` aprobado y `invoice_status = 'to invoice'`. Confirma el modelo real antes de implementar. Agrega un campo de vencimiento/fecha prevista de cobro con nombre técnico propio, no `x_studio_*`. Calcula sólo el importe aún no facturado y evita duplicarlo con facturas ya emitidas. Permite líneas manuales identificadas como tales.

### 9.3 Otras recaudaciones

Ingreso manual basado en conceptos configurados. Debe admitir partner opcional, documento, vencimiento, moneda, importe, notas y adjuntos. Validaciones de importe positivo y compañía.

### 9.4 Proveedores

Carga facturas de proveedor publicadas con saldo pendiente, pagos parciales, cuotas, notas de crédito y vencimiento real.

### 9.5 Órdenes de compra

Incluye órdenes confirmadas o con cantidades recibidas pendientes de facturar, respetando la política Odoo de facturación por cantidades pedidas/recibidas. Agrega fecha prevista de pago/vencimiento con campo propio. Proyecta únicamente el importe aún no facturado y no dupliques facturas de proveedor ya existentes.

### 9.6 Proformas de proveedor

Audita si existe un modelo real instalado. Si existe, crea un adaptador sin modificar su motor. Si no existe, crea un modelo mínimo propio de proforma con estados `draft`, `approved`, `invoiced`, `cancelled`, moneda, vencimiento, líneas, impuestos y vínculo a la factura final. Sólo las aprobadas y no facturadas entran al flujo. Evita duplicarlas cuando se conviertan en factura.

### 9.7 Otros pagos

Egreso manual basado en conceptos: IVA, imposiciones, sueldos, anticipos, fondos a rendir, créditos u otros. No generes asientos ni pagos reales desde una línea de forecast.

## 10. Saldo inicial bancario

Calcula el saldo de apertura desde las cuentas de liquidez de los diarios seleccionados, sólo con asientos publicados de la compañía. Define de manera explícita y prueba el corte: cierre anterior al inicio del primer día para no contar dos veces movimientos proyectados del mismo día.

Si hay varias cuentas, muestra el total y un drill-down por diario, cuenta y moneda. No uses el saldo mostrado en una tarjeta como fuente si no puede reproducirse contablemente.

## 11. Semanas, monedas y fórmulas

Buckets obligatorios:

- `Vencido`: vencimiento anterior al inicio;
- `W1`: días 0–6;
- `W2`: días 7–13;
- `W3`: días 14–20;
- `W4`: días 21–27;
- `W5`: días 28–34;
- `Otros`: posterior al horizonte o sin fecha, según una política visible.

Integra `step_accounting_multicurrency`. Conserva importe y moneda origen y usa `res.currency._convert` con compañía y fecha de conversión. El tipo de cambio debe quedar congelado en el snapshot aprobado para que el histórico no cambie al actualizar tasas. No uses una división fija por 900 ni supongas siempre CLP/USD.

El resumen debe mostrar, como mínimo, moneda del flujo y columnas auxiliares CLP/USD cuando estén configuradas. Los importes no se renombran engañosamente: si una columna es USD debe contener USD.

Fórmula acumulada por bucket:

`saldo final = saldo anterior + ingresos del bucket - egresos del bucket`

El saldo inicial entra una sola vez. Los totales del resumen deben cuadrar exactamente con las hojas y permitir drill-down al detalle y al documento Odoo origen.

## 12. UX y visualización

No reproduzcas una planilla gigante como única interfaz. Implementa:

- pantalla inicial de Tesorería con saldo inicial, ingresos, egresos, saldo mínimo proyectado y alertas de caja negativa;
- gráfico de saldo acumulado por semana;
- tarjetas de vencido, W1–W5 y otros;
- formulario del flujo con pestañas `Clientes`, `Notas de venta`, `Otras recaudaciones`, `Proveedores`, `Órdenes de compra`, `Proformas`, `Otros pagos` y `Resumen`;
- listas legibles con encabezados fijos, totales, filtros y agrupaciones;
- drill-down desde KPIs y resumen;
- estados vacíos, carga, error y actualización;
- exportación XLSX/PDF de revisión derivada del mismo dataset canónico.

Usa el estilo visual Steps ya aplicado en otras apps, pero no sacrifiques accesibilidad, contraste, scroll ni comportamiento responsive. Valida resoluciones de escritorio y tablet.

Durante la validación anterior de Demo se registró temporalmente `psycopg2.pool.PoolError: The Connection Pool Is Full` al abrir una vista que disparó decenas de solicitudes simultáneas de imágenes. El servicio se recuperó y actualmente responde HTTP 200, pero Tesorería no debe repetir ese patrón: evita N+1, limita RPC paralelas, agrega índices por compañía/estado/fecha/fuente, pagina los detalles y mide consultas y tiempo de respuesta con un volumen representativo.

## 13. Seguridad y multiempresa

Crea grupos separados:

- Tesorería: consulta;
- Tesorería: operación/edición;
- Tesorería: aprobación;
- Tesorería: configuración.

Define ACL y record rules multiempresa. Un usuario no debe ver flujos, cuentas, documentos o partners fuera de sus compañías permitidas. Nunca uses `.sudo()` para saltar seguridad en endpoints o cálculos de usuario. Registra quién generó, actualizó, aprobó, reabrió y exportó cada snapshot.

## 14. Migración y archivado del prototipo Studio

Orden obligatorio en Desarrollo:

1. backup verificable de `LAB_TAREAS` y addons afectados;
2. instalar/actualizar el módulo propio;
3. migrar 12 conceptos, 3 etapas si se reutilizan y 1 flujo Studio;
4. comparar conteos y campos relevantes antes/después;
5. validar el nuevo acceso y los detalles en navegador;
6. recién entonces archivar los menús Studio de Tesorería y Concepto flujo caja;
7. mantener tablas y registros Studio intactos y documentar cómo revertir el ocultamiento.

En Demo y Demo-SyS la migración debe ser idempotente y tolerar que el prototipo no exista.

## 15. Pruebas mínimas obligatorias

Ejecuta pruebas en una base desechable y pruebas de upgrade/migración sobre copias o transacciones con rollback antes de tocar las bases funcionales. Incluye al menos:

1. concepto con varias cuentas y restricción multiempresa;
2. migración Studio dos veces sin duplicar;
3. factura cliente abierta, parcial, vencida, con cuotas y nota de crédito;
4. factura proveedor equivalente;
5. venta parcialmente facturada sin doble conteo;
6. compra parcialmente recibida/facturada según ambas políticas de control;
7. proforma aprobada que desaparece al facturarse;
8. líneas manuales que sobreviven a `Actualizar datos`;
9. límites exactos de vencido y W1–W5;
10. fecha sin vencimiento según política visible;
11. conversión CLP/USD y una tercera moneda;
12. tasa congelada en flujo aprobado;
13. saldo inicial con dos bancos y drill-down;
14. fórmula acumulada e ingresos/egresos con signos correctos;
15. idempotencia de actualización y restricción de fuente duplicada;
16. bloqueo del aprobado y reapertura auditada;
17. ACL de consulta, operación, aprobación y configuración;
18. aislamiento multiempresa;
19. exportación que cuadra con la interfaz;
20. instalación limpia y upgrade sin errores.

No uses datos personales reales en fixtures ni dejes registros de prueba en las bases funcionales.

## 16. Despliegue secuencial

Después de pruebas verdes:

1. Desarrollo;
2. validación completa y aprobación técnica;
3. Demo;
4. validación completa;
5. Demo-SyS con adaptadores compatibles, sin alterar datos SyS.

Actualiza sólo módulos dirigidos y reinicia únicamente el servicio del ambiente correspondiente. Limpia/actualiza assets por el mecanismo Odoo, no mediante borrados indiscriminados. No selecciones como canónico “el archivo más nuevo”: usa el release probado.

## 17. Validación final en navegador

En cada URL valida con un usuario administrador y uno restringido:

- Home sin lanzadores duplicados;
- Contabilidad > Tesorería;
- accesos estándar de pagos, lotes, bancos, efectivo e informes;
- maestro de conceptos con múltiples cuentas;
- creación, actualización, aprobación y reapertura de flujo;
- las siete hojas y el resumen;
- drill-down y documentos fuente;
- monedas y tasas;
- scroll, responsive, contraste y assets;
- ausencia de errores JS/RPC y de nuevos tracebacks en logs.
- ausencia de saturación del pool de conexiones bajo una navegación y actualización representativas.

No marques terminado si el release propio difiere visual o funcionalmente entre ambientes, salvo adaptadores de motor explícitamente documentados.

## 18. Entrega de evidencia

Entrega un informe Markdown con:

- auditoría inicial y mapa de motores/dependencias;
- decisiones funcionales para contradicciones o conceptos no estándar;
- modelo de datos y diagrama de fuentes;
- migración Studio con conteos antes/después;
- menús Studio archivados y objetos conservados;
- archivos y versiones cambiadas;
- backups con tamaño, `pg_restore --list` y SHA-256;
- pruebas ejecutadas y resultados;
- servicios, HTTP, logs y capturas de navegador;
- conciliación de un flujo de ejemplo: detalle = resumen = exportación;
- pendientes reales y rollback;
- confirmación explícita de que no hubo pagos, transferencias, correos, archivos bancarios reales ni `git push`.

## 19. Criterio de término

El trabajo termina cuando Tesorería deja de ser un formulario Studio y se comporta como una planificación financiera auditable: reutiliza Contabilidad, evita duplicidades, conserva importes y monedas de origen, proyecta cinco semanas, permite explicar cada cifra, controla permisos y puede desplegarse con el mismo release en nuestros ambientes sin mezclar sus datos.
