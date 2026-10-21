# T97–T99: informes operacionales agrícolas

Módulo `step_agro_analytics`, rama canónica `codex/ambientes-canonicos-reparacion`.
Alcance: Desarrollo y Cerro El Plomo; sin cambios SAG.

## T97: informe de embarques

El menú existente Informe embarques abre un informe nativo pivot/gráfico/lista.
Usa las cargas reales de embarques despachados, embarcados, facturados y liquidados.
Permite filtrar número explícito, temporada, fecha, tipo, programa, recibidor,
modalidad, nave, país, puerto, producto, variedad, calibre, calidad y marca.
Se desactivan solo Orden de Despacho y Reserva de Stock dentro de Embarques;
se conservan los registros, acciones y accesos equivalentes de Packing.

Venta neta = facturas y débitos contabilizados menos créditos, sin impuestos.
USD utiliza la tasa de cada documento. La moneda de empresa conserva el neto
contable. La venta de cada embarque se distribuye según kilos de cada línea,
conforme a la decisión humana. Los contenedores usan la misma proporción.
Precio total = USD total / kilos totales; cantidad de embarques = distintos,
sin multiplicarlos por las líneas. Un embarque sin kilos conserva su venta en
una fila identificada sin kilos distribuibles. Requiere lectura contable.
El informe es una vista SQL sobre documentos existentes, sin datos maestros paralelos.

## T98: comparativo de estimaciones

Panel Productores, tablas por especie y especie/variedad. Estimado: semanas de
la versión vigente de estimación; no suma nuevamente sus subdivisiones diarias.
Real: kilos exportación de OT terminadas más recepciones embaladas de exportación
confirmadas. Deduplica tarjas y excluye las ya contadas como salida de OT.
Filtros: temporada, mes, semana lunes y especie. Período por inicio de semana
estimada, fecha del proceso o fecha efectiva de recepción respectivamente.
Diferencia = real − estimado; variación = diferencia / estimado.

## T99: procesos y maquinaria

Panel Packing, resultados por especie y rendimiento por especie/línea.
Considera OT cerradas, costeadas y contabilizadas. Los totales usan sumas de
kilos y horas efectivas; no promedian porcentajes ni velocidades por fila.
OT sin horas permanecen en resultados; maquinaria muestra cuántas faltan y
calcula rendimiento solo con los kilos y horas de los procesos medidos.

Configuración: Líneas de proceso → Estándares por especie (kg/h).
Cada combinación línea/especie admite un estándar positivo. No convierte
envases/h a kilos/h. Se propone el estándar en nuevas OT y se conserva en el
campo histórico de la OT. Cambiar el catálogo no altera procesos anteriores.
Un grupo con estándares incompletos muestra referencia y variación sin definir.
No se inventan valores iniciales ni se rellenan históricos sin información.

## Verificación y entrega

Las pruebas ejecutan contabilización de documentos y conversión de monedas,
reparto 100/300 kg, agregados ponderados y embarque sin kilos; cierre real de OT,
estándar histórico, filtros y ausencia de horas; recepción embalada real y
reemplazo de versión de estimación. Los probes verifican versión/ruta efectiva,
formularios, menús, agregados, perfiles y compilación de assets en copias privadas.

La revisión visual interactiva permanece pendiente: la herramienta de navegador
falla al inicializar con `failed to write kernel assets` (Windows os error 3).
No se presenta esa compilación como revisión visual. Los tickets permanecen
abiertos para revisión del usuario hasta comprobar la interfaz real.

### Desarrollo verificado

Paquete `a9db6e6ab4ade2df214f18d226386013b6bec828`, módulo 18.0.1.0.1.
SHA-256 `4168061afe7177c64d8d0e979130dc841636d4e59fc50054a4b3af3131ee65d7`.
Copia fresca `MANAGEMENT_QA_DEVELOPMENT_t9799qa3`: cuatro pruebas sin fallos ni errores;
probes efectivos y perfiles contable/Packing correctos, datos originales preservados.
Publicación Desarrollo: respaldo `management_development_20261021T012910Z`,
servicio y verificación posterior correctos.

El primer intento de publicación detectó una importación de tests fuera de modo
prueba. Se conservó el respaldo `management_development_20261021T012459Z`,
se corrigió la raíz del módulo y se volvió a acreditar desde una copia fresca.
No se reutilizó como prueba aprobada la copia con fallos.

### Cerro El Plomo verificado

Mismo paquete y SHA-256 de Desarrollo. Copia fresca
`MANAGEMENT_QA_CERRO_t9799ce1`: cuatro pruebas sin fallos ni errores, probes de
formularios/menús/perfiles/paneles y preservación de datos aprobados.
Publicación: respaldo `management_cerro_20261021T013224Z`, servicio y verificación
posterior correctos. El bloqueo compartido y la comparación de baseline se
aplicaron en ambas publicaciones; no se modificaron raíces de addons compartidas.

Notas internas de entrega: T97/9560, T98/9561, T99/9562. Se comprobó cero
notificaciones y cero correos para esas notas. Los tickets permanecen abiertos
para revisión visual. No se recibieron nuevas respuestas antes de registrar la entrega.
