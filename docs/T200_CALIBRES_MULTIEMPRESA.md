# T200 — Calibres de Packing por empresas y sucursales

En **Packing → Configuraciones → Fruta → Calibre de fruta**, el catálogo
nativo permite seleccionar varias **Empresas y sucursales** en un calibre.
El editor conserva sus permisos actuales. El calibre queda disponible en
las tarjas y en el importador Excel de las compañías seleccionadas.

El grupo del calibre se habilita para las empresas agregadas con los permisos
del mismo editor. Se conservan los identificadores, la empresa de origen,
el grupo, los vínculos de contratos y las selecciones históricas. La migración
agrega únicamente la asignación a la empresa de origen de cada registro.
No fusiona calibres ni cambia asignaciones comerciales existentes.

Una empresa que ya utiliza el calibre en documentos no puede retirarse de
su asignación. Tampoco se admiten empresas sin acceso del editor ni códigos
duplicados dentro de las empresas asignadas. Si ya existe otro calibre del
mismo código en una empresa, se informa la coincidencia para conservar ambos
historiales y evitar una equivalencia ambigua.

Paquete `agriculture-multicompany`, módulo `step_agriculture_multicompany`
**18.0.1.0.5**, commit funcional `70e98f457cdfb1ec380935f2020e064284e795ea`.
SHA-256 del paquete
`2d5f9bd1e03c2098437f8e5e0b368077fa73fbf1f29498646f2b03beb52e37bb`.

La suite del módulo verifica el guardado desde el formulario, lectura desde
otra sucursal, guardado de una tarja, selección del importador, aislamiento,
códigos repetidos, asignaciones utilizadas y migración idempotente. Incluye
la regresión del acceso a productores y de los otros maestros agrícolas.
El verificador de destino coteja los menús, el listado, el formulario efectivo,
la versión, el origen del código y las relaciones de todos los calibres.

Las copias de Desarrollo, Cerro y QA-Cerro pasaron 23 pruebas cada una. El
11-11-2026 se publicó el mismo paquete en los tres destinos, con comprobación
del menú, listado y formulario efectivos, conservación de registros comerciales
y servicios activos. Se verificó que los tres respaldos son legibles:

- Desarrollo: `management_development_20261111T160743Z`.
- Cerro: `management_cerro_20261111T161548Z`.
- QA-Cerro: `management_qa-cerro_20261111T161713Z`.

Cerro y QA-Cerro ejecutan la misma versión y el mismo contenido del módulo,
con SHA-256 `0d05a18f0e04b4d20d5e9aa9da2675d9422003efb17f3d3108e50d67651ab4de`.
El verificador de QA confirmó la neutralización, el bloqueo de salida y la
denegación de acceso a la base de producción. Sus datos de capacitación
se conservaron y no se copió nuevamente la producción.
