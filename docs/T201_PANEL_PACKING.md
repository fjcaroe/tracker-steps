# T201 — Panel de Packing

En **Packing → Inicio**, el panel nativo conserva su menú y sus secciones de
órdenes recientes y atención. El título aparece en blanco y muestra siete
indicadores: OT abiertas, kilos a proceso recibidos, kilos procesados, stock
a proceso, kilos exportación, kilos embarcados y stock de exportación.
Cada tarjeta abre los registros que componen su cifra, en sus listas y
formularios nativos.

Los filtros incluyen Último día, Semana, Mes, Temporada, Desde, Hasta y
Especie. Los períodos se anclan al último día con actividad de la empresa;
Temporada usa sus fechas configuradas. Si faltan, el panel informa que debe
elegirse un rango manual. Las especies provienen de los registros visibles
de esa empresa. No se suman las otras empresas marcadas en el selector.

Los ingresos y la producción usan la fecha de origen; el consumo usa la
fecha de proceso de las OT terminadas y los embarques su salida comprobada.
El stock es el actual de las tarjas originadas en el período, como informa
la pantalla. Los repaletizados conservan el origen sin duplicar los kilos.
Las tarjas históricas vacías sin empresa se incluyen únicamente cuando
una recepción terminada, OT terminada o repaletizado terminado de la empresa
activa acredita su trazabilidad. El panel no modifica las operaciones ni
reasigna esas tarjas. Las salidas sin fecha comprobable se informan y no
se inventa una fecha para incluirlas.

Paquete `packing-dashboard`, módulo `step_packing_dashboard`
**18.0.1.0.3**, commit funcional
`4063702a16b75c958ba95027e21ef0d876ebedff`.
SHA-256 del paquete:
`aa5a1869b2e4c331ac5354c5fb831b5e512c381f1e380d93c4fe6f585e86484c`.

La suite funcional comprende once casos: indicadores y estados, límites de
fechas, empresa activa, atribución de paquetes históricos, zona horaria,
filtros inválidos, períodos y temporadas, especie en órdenes recientes,
repaletizado real, cierre y despacho reales, y salidas sin fecha.
El verificador coteja las siete cifras con los registros de sus acciones,
los menús y formularios, la versión efectiva y los datos de las sucursales.

El control de navegador usa el panel servido, los cuatro períodos, fechas
manuales, opciones de especie y persistencia de selección, siete tarjetas,
título blanco, ancho móvil, listado de detalle y apertura de una tarja real.
El encabezado se compila también con el motor Owl del destino para detectar
expresiones que JavaScript acepta pero el compilador de plantillas no.

Las copias frescas de Desarrollo, Cerro y QA-Cerro pasaron once pruebas cada
una (33 en total), con el mismo paquete. La suite y el verificador posterior
confirmaron la conservación de los registros comerciales. Desarrollo conserva
su advertencia previa sobre el módulo `steps_api`, ajena al alcance de T201.

El 11-11-2026 se publicó y verificó la versión indicada en los tres destinos.
Chrome confirmó en cada uno la selección y restablecimiento de especie,
los cuatro períodos y el rango manual, siete tarjetas, el título blanco,
la ausencia de desbordamiento móvil y la apertura de una tarja existente.
No se registraron errores JavaScript.

Los tres orígenes efectivos coinciden con SHA-256
`9cb517e071aa7f4021fa373e28f86d6c699934aecb3f48f59b6986ed3df53239`.
Se comprobó la lectura de los respaldos de publicación:

- Desarrollo: `management_development_20261111T190103Z`.
- Cerro: `management_cerro_20261111T190937Z`.
- QA-Cerro: `management_qa-cerro_20261111T191105Z`.

Los tres servicios quedaron activos. La comprobación de QA-Cerro confirmó
su flujo nativo, la neutralización de salidas y la denegación de acceso a
la base de producción; se conservaron sus datos de capacitación.

Se retiraron siete copias privadas intermedias ya reemplazadas, con exclusión
mutua y comprobación de que no tenían conexiones. Se conservaron las copias
finales, los registros de prueba y todos los respaldos de publicación.
