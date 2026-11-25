# Maestros originales, permisos y referencia SyS — 30-10-2026

## U13D · Tipo obligatorio de estructura salarial, 25-11-2026

El perfil privado de Cerro recupera la obligatoriedad de
`hr.payroll.structure.type_id` en el ORM y PostgreSQL. Conserva el campo 8275,
el XML ID original de `hr_payroll` y la FK validada con `ON DELETE RESTRICT`
al maestro de tipos. La declaración se incluye en el overlay de adopción. El
perfil genérico de OCA mantiene el campo opcional.

El paquete `950f6932` se ejecutó bajo el bloqueo compartido en dos bases nuevas
del mismo respaldo fresco, con directorios de datos 0700 y dump 0600. La
copia Community oficial con OCA (144 instalados, cero Enterprise) y la
referencia nativa (414 instalados, 140 Enterprise) crearon una estructura
con un tipo original, la cambiaron a otro tipo existente y rechazaron el alta
y la edición con el tipo vacío. Se comprobó el rollback de la estructura de
prueba. La referencia nativa conserva su motor original.

Se repitieron 118 accesos y dos denegaciones con el gerente original, cinco
formularios y cuatro menús. La proyección guardó los 71 pares de estructuras
y reglas y creó cero al repetir. La lectura PostgreSQL posterior confirmó los
71 pares. La revisión conserva 999 de 1.000 proyecciones literales, 197
contadores, 60.686 XML IDs y los históricos y vencimientos originales.
Se observaron siete vínculos sólo en menús nuevos y un adjunto adicional
clasificado como posible icono. Coinciden los cuatro contratos de almacenamiento
y la FK Calendar. Las 32 FK nuevas siguen vacías. Quedan 35 diferencias
físicas, seis también de obligatoriedad ORM. Pasaron 176 pruebas locales.

El inventario readonly vigente coincide módulo por módulo con U12, incluidas
las fuentes privadas y huellas. Cerro tiene 414 instalados / 140 Enterprise /
133 propios, Steps 310 / 123 / 19 y SyS 336 / 142 / 21. De los 170 propios del
repo, 40 están fuera de Cerro. Las matrices conservan 75/9/14 caminos de apps
propias a Enterprise. Los ensayos U13, U13B y U13C se detuvieron antes de
instalar OCA por sellos pendientes del inventario, el observador y el
verificador de menús, respectivamente. U13D actualizó la cadena completa.

Evidencia privada en `~/.codex/local-artifacts/community-resume-20261125/U13` y
`/opt/steps-validation/community-original-handover-20261125U13D`.

- Paquete `1756ab3ba7e98a11f75f9898190d30be4cc66609dbcf6c41209ebb5633b96ffd`.
- Respaldo `6780ccb5a15a8b30ab53d1885810b60164cf9cb4902fc1584ebaf88c1154e0b4`.
- Admisión `1b62c221b737d94dfe1d0a2f15d83dbf962b1372d76d88b6e6bdd2f0e071ce6e`.
- Relaciones `22243c558f041209b9435a9f6274543985c7d3d774fed2701b0d5167acfce365`.
- Inventario `1a1c9ac8e0c0ee2944c7b3986d211188d473e430b3953ebe69d7b091ac8e2861`.

Siguiente bloque: restaurar `hr.salary.rule.struct_id` (8303), verificando
alta, cambio de estructura y rechazo de vacío con maestros existentes. Probar
la relación primaria y su membresía M2M, la herencia de líneas históricas y
la idempotencia de las 71 reglas. Después seguir con categoría y código de
regla, nombre de liquidación y relaciones de entradas y días. T2 sigue como
pareja multifrente. Siguen pendientes la certificación financiera y de HR,
DTE/CAF/SII, Tesorería, Calidad, Studio, Documentos/Firma, los demás productos
y la copia integral restaurable con cero Enterprise.

## U12 · Código obligatorio de categoría salarial, 25-11-2026

El perfil privado de adopción de Cerro declara obligatorio el código de
`hr.salary.rule.category`. Odoo aplica la obligación ORM y PostgreSQL exige
`NOT NULL`. La declaración se carga desde el overlay del adaptador OCA. El
perfil genérico conserva su configuración opcional. El campo y su XML ID
original conservan el destino 8332 y el namespace `hr_payroll`.

El paquete `d3150db5` se probó bajo el bloqueo compartido en dos copias nuevas
del mismo respaldo. Community oficial con OCA y la referencia nativa de Cerro
aceptaron crear y editar una categoría con código y rechazaron las dos
operaciones con el código vacío. Las categorías de prueba se revirtieron.
La revisión física verificó la recuperación de esta única columna. De las 36
diferencias físicas pendientes, siete requieren recuperar también `required`
en el ORM. Se mantienen las 32 FK nuevas vacías.

La adopción repitió 118 accesos, dos denegaciones, cinco formularios y cuatro
menús. PostgreSQL confirmó los 71 vínculos guardados y la segunda ejecución
creó cero. Quedaron exactas 999 de 1.000 proyecciones, 197 contadores y 60.686
XML IDs. Se preservaron los adjuntos originales, históricos y vencimientos.
Se repitieron las adiciones observadas en U11C de siete vínculos en menús nuevos
y un adjunto clasificado como posible icono de menú. Coincidieron los cuatro
contratos de almacenamiento y la FK Calendar. Pasaron 176 pruebas locales.

El inventario de los tres productos coincidió módulo por módulo con U11C,
incluidas fuentes privadas y huellas. Se revisaron 170 módulos propios en el
repo, 40 fuera de Cerro y 75/9/14 apps con caminos declarados a Enterprise.
La aceptación multifrente sigue en T2. La copia nativa es la referencia y la
copia OCA sólo acredita la adopción parcial de Nómina.

Evidencia privada en `~/.codex/local-artifacts/community-resume-20261125/U12` y
`/opt/steps-validation/community-original-handover-20261125U12`.

- Paquete `be1b6d810d9a8a66c5e7f965631019b3d56a978493887413859e404efc8db088`.
- Respaldo `fb0fead68177b0dace2a8cacfc153a50826c35971522f1204a144c4a5aaf5f19`.
- Relaciones `2e6b48a67b00acda231295e1ace37cd5744cf328fe8260dc2b443d91d06a8bbc`.
- Admisión `dcd36d2202a096275e5c6ed3bebdaa9c2eb6fb4a8053213ec46552772d7cd94f`.

Siguiente bloque: recuperar `hr.payroll.structure.type_id` en el perfil
original y probar altas y ediciones con tipos de estructura existentes. Al
seguir con reglas y líneas, verificar la relación primaria y M2M, las guardas
de históricos y la compatibilidad del OCA general. Mantener abiertas las
puertas financieras, HR, DTE, Tesorería, Calidad, Studio, Documentos, Firma y
la recuperación integral de todos los productos con cero Enterprise.


## U11C — adopción funcional de la configuración original, 25-11-2026

En dos bases privadas nuevas restauradas del mismo respaldo fresco, el paquete
`168bb264` cargó OCA sobre Community oficial (144 módulos, cero Enterprise)
y observó en solo lectura la referencia nativa (414 módulos, 140 Enterprise).
Con el gerente original UID7 reprodujo los 118 accesos y dos denegaciones,
abrió cinco formularios y comprobó la paridad de cuatro menús, con Categorías
oculto. Conservó 120 maestros, el modelo 600 y la ruta del reporte 462.
La API OCA materializó 71 relaciones de reglas y creó cero en el reintento.
Una lectura PostgreSQL posterior confirmó los 71 pares exactos ya guardados.
La referencia conservó su motor y el destino ensayó la adopción parcial de la
configuración con otros productos en cuarentena.

La revisión física conservó 999 de 1.000 proyecciones literales, 197 contadores
y 60.686 XML IDs, sin pérdida de IDs de modelo o campo. Se conservaron las
membresías originales y se añadieron siete vínculos en menús nuevos.
La comparación literal de historia y vencimiento difiere por un adjunto nuevo
clasificado como candidato a icono de menú. Todos los adjuntos e históricos
originales y los parámetros de vencimiento quedaron iguales. Coincidieron los
cuatro contratos de almacenamiento, la FK Calendar SET NULL y los cinco XML IDs
originales de esos campos. Hubo siete aliases nuevos previstos.

La puerta de relaciones constató 32 FK nuevas vacías y 37 columnas que perdieron
NOT NULL sin presentar nulos. Ocho perdieron también la marca ORM persistida.
Respecto de U2 aparecen siete pérdidas nuevas, en Gastos, Cosecha y permisos de
maestros de usuarios. Las dos columnas de tarifa de U2 ya no figuran en esta
lista. La obligatoriedad de las 37 sigue pendiente de validación y restauración
por proveedor, empezando por las ocho de Nómina con altas y ediciones reales.

El inventario vigente conserva Cerro 414/140 Enterprise/133 propias, Steps
310/123/19 y SyS 336/142/21. Hay 170 propias en repo, 40 fuera de Cerro y
75/9/14 con caminos Enterprise. Cambiaron los módulos activos de Cosecha
`step_cosecha_operations` y `step_harvest_launcher`. Siguen las fuentes privadas,
el proveedor AGPL y `steps_transport` recuperable fuera de la ruta activa.

Evidencia privada en `~/.codex/local-artifacts/community-resume-20261125/U11` y
`/opt/steps-validation/community-original-handover-20261125U11C`. El primer U11
se detuvo después de restaurar porque el sello de inventario seguía en U9.
U11C verificó ambos sellos, 176 pruebas locales y 98 en canónica. El respaldo
se creó con modo 0600 y se verificó que un usuario ajeno no podía leerlo.

- Paquete `b672c88bc7e7940a79b712e60bcceda3f5bc23be04a86b2c51e0655da1b1c69c`.
- Respaldo `5bdd534050b7133f525fad7b6967c038b6718ecf16ebfdae00dc3d4b93d90898`.
- Admisión funcional `7bc91ca9d3611f7109155c36a415c1915210e2c40f182442c838fd175b8e62b7`.
- Revisión física `daaaf879b5594171f46f3a4e3341b40ad529d362cbb838a305c6afca5aaa4457`.
- Relaciones y obligatoriedad `828ef5495eacfb00a81493626b50c4dfb10e589603db3030e3b14dfd061c2b5c`.

La rama del hilo conserva el coordinador completo del ensayo. T2 mantiene la
aceptación multifrente. Siguen días, redondeos, YTD, contabilización, Previred,
libro y consumidores HR, DTE/CAF/SII, Tesorería, Calidad, Studio/Documentos/Firma
y la restauración y aceptación integral de los productos con cero Enterprise.
Continúa la ejecución horaria y el corte de producción permanece fuera.

## U10 — procedencia de las columnas obligatorias, 25-11-2026

La puerta física ahora une las columnas revisadas con sus campos almacenados y
XML IDs en las dos bases privadas. En U2 ejecutó 196 consultas de solo lectura.
Los 32 campos conservan sus IDs y namespaces originales. Las 32 columnas siguen
sin `NOT NULL` y sin nulos. De ellas, 24 mantienen `required=True` en los
metadatos persistidos del destino. Las otras ocho pertenecen a `hr_payroll`:
tipo de estructura, nombre de liquidación, tipo de entrada, tipo de día, categoría,
código y estructura de regla, y código de categoría. La revisión también
reconfirmó las 32 FK nuevas y vacías. El catálogo persistido no sustituye
comprobar el registro ORM activo y las altas y ediciones reales.

Evidencia privada en `~/.codex/local-artifacts/community-resume-20261125/U10`.
Recibo de catálogo `a2d74a552d79a56146e7f83459dd78347356f3b1398858f74e1bd907b8c91cd6`.
Pasaron 176 pruebas locales. El consumidor actualizado admitió los dos recibos
reales de U9 y rechazó tanto una pareja distinta como un sello incorrecto.

El inventario completo conserva Cerro 414/140 Enterprise/133 propias, Steps
310/123/19 y SyS 336/142/21. El repositorio conserva 170 módulos propios y 40
fuera de Cerro. La matriz candidata sube de 74 a 75 caminos en Cerro por
`step_harvest_launcher`; Steps y SyS conservan nueve y 14. La fuente activa de
`step_packing_ticket_revision` cambió en Cerro. Siguen las tres fuentes propias
privadas de Cerro, el proveedor AGPL y la recuperación de `steps_transport`
fuera de la ruta activa. Huella del inventario
`8f3c7a809d9a18a5d5a4473f982e8a5fe26dcb0521e61ae19397afaf4aca6a8a`.

El candidato anclado `34854458` queda en `codex/community-resume-20261123`.
Prepara una observación nativa y un destino Community oficial/OCA a partir del
mismo dump. U10B se empaquetó en
`/opt/steps-validation/community-original-handover-20261125U10B`, SHA256
`9bb2af25b6e522a0933054eb1e21b26286ffd482129645e53e24318e1446429f`.
La revisión concurrente de Cosecha mantuvo el bloqueo compartido. La espera
se canceló antes de crear bases o tomar el respaldo. U10 no añade una
aceptación de conversión. T2, U7 y U9 conservan sus alcances.

Retomar desde la canónica actualizada integrando el candidato pendiente en el
worktree del hilo. Ejecutar la pareja nueva bajo el bloqueo y comprobar
118 accesos, dos denegaciones, 71 vínculos y su idempotencia, cinco formularios
y cuatro menús. Ejecutar la revisión física y priorizar las ocho pérdidas ORM
de Nómina: conservar los contratos válidos del OCA genérico y probar el
proveedor original con altas y ediciones. Revisar por separado los 24 campos
con metadatos obligatorios y pérdida de restricción física. Siguen Nómina
financiera, HR, DTE/CAF/SII, Tesorería, Calidad, Studio/Documentos/Firma y la
restauración y aceptación integral de los productos con cero Enterprise.


## U9 — cuatro menús originales de Nómina, 24-11-2026

El candidato `b0c8ffd9` recupera el observador de menús nativos y
el verificador que consume su recibo. Los ejecuta antes del upgrade en el mismo
proceso de solo lectura que el testigo de maestros. Cada ruta conserva XML IDs,
modelo, acción con modo formulario y cadena de menús y grupos del respaldo. El gerente
original UID7 vio Estructuras, Reglas y Tipos de entrada. Categorías quedó oculto.
Se volvieron a observar 118 accesos, dos denegaciones, las 71 reglas y las cuatro
estructuras, con modelo 600, reporte 462, políticas y contadores conservados.
La verificación local del recibo real rechazó atribuirlo a otra copia.

El inventario fresco preserva los conteos de Cerro, Steps y SyS. En Cerro
cambió la versión de `step_cosecha_operations` y las huellas de ese módulo y
`step_harvest_launcher`, con dependencias declaradas iguales. El observador
contrasta el grafo instalado completo (414 módulos, 140 Enterprise) y la
versión vigente de cada módulo. Cerro conserva 74 propios con caminos
Enterprise, Steps nueve y SyS 14. El repo suma 170 propios, 40 fuera de Cerro.
Se conservan las tres fuentes privadas de Cerro y el caso de ruta de
`steps_transport` en Steps.

Las bases privadas nuevas se ejecutaron en serie bajo el bloqueo compartido.
Pasaron 13 pruebas en Community oficial (68 módulos, cero Enterprise), cinco en
la referencia nativa (417 módulos tras el upgrade, 140 Enterprise) y 34 locales.
Coincidieron 164 archivos de addons, los cuatro contratos de almacenamiento y
la FK Calendar. La referencia preservó 1.168 contratos de negocio y contadores
y 60.654 XML IDs originales. El respaldo y filestore quedan en
`/opt/steps-validation/community-multifront-parallel-20261124U9`. Evidencia
local en `~/.codex/local-artifacts/community-resume-20261124/U9`.

- Paquete SHA256 `bd310e7543209c9bc37fe99b806eee14a387946ccd5ed0f0de585d29c7b808a2`.
- Recibo de menús `afd3c69bf1acf7a2b5993993eec35a1869d92502b90187b43c2ac000104c4905`.
- Recibo de maestros `b9ff0c8f1cbf0d0e3d83e4439461251b9bf71e473ca15f72acd517f6562a0e8c`.
- Comparación de almacenamiento `535d7a84533a1c6c301ec7716416c2b456f6531704337a4715f587da2e0b441a`.

U9 certifica la referencia de identidad y permisos de menús. La adopción OCA
anclada sigue pendiente. Recuperar el lanzador y el consumidor de `2802bcde`
en una pareja nueva, usando el mismo respaldo para referencia y destino y
capturando ambos recibos nativos antes de ejecutar el candidato. Repetir las 71
relaciones idempotentes, cinco formularios y cuatro menús F/G, después aplicar
`review_original_anchor.py` y la puerta física U7. Restaurar las obligaciones
por proveedor con altas y ediciones reales sin defaults inventados. T2 conserva
la aceptación multifrente. Siguen pendientes Nómina financiera y consumidores
HR, DTE/CAF/SII, Tesorería, Calidad, Studio/Documentos/Firma, los demás
productos y la restauración integral cero Enterprise.

## U8 — permisos originales en el inventario actual, 24-11-2026

El observador recuperado de `2802bcde` se actualizó al inventario completo de
Cerro. `validate_payroll_api.py --original-source-inventory` comprueba cada
nombre, versión, licencia y estado instalado de la copia fresca antes del
upgrade. La captura se ejecuta bajo el bloqueo compartido, con el motor
nativo, cursor Odoo de solo lectura y las rutas originales de addons. Se exige
la cápsula sellada y el inventario completo de 414 módulos, 140 Enterprise.
La captura de los tres productos coincidió módulo por módulo con U7. La
canónica incluye cambios de Cosecha con las mismas dependencias declaradas.

El gerente original UID7 obtuvo 118 accesos y dos denegaciones sobre los
120 maestros. Pudo consultar las 71 reglas y las cuatro estructuras. Se
conservaron modelo 600, reporte 462, proyección de maestros, política de
seguridad y contadores durante la observación. Huella del recibo privado
`1efa33b6799109ddf580fd737b379c33e622882e144267a9fe47b9fb64fa967d`.
La evidencia está en `~/.codex/local-artifacts/community-resume-20261124/U8`
y `/opt/steps-validation/community-multifront-parallel-20261124U8`.

El paquete exacto `7b9fbaeb` pasó 13 pruebas en Community oficial
(68 instalados, cero Enterprise) y cinco en la referencia fresca de Cerro
(417 instalados después del upgrade de ensayo, 140 Enterprise). Las dos
ejecuciones usaron bases nuevas en serie bajo el bloqueo compartido. Se
verificaron 164 archivos de addons idénticos, los cuatro contratos de
almacenamiento, la FK Calendar y 1.168 contratos de negocio y contadores en
la referencia. La comparación de almacenamiento tiene huella
`9bf221cf224de6769a02547e7281fdbfaa5adf0d4f759ecec5a5f3031f2033ea`.
El archivo de entrada tiene huella
`47fad5990bd5c92eac0648295cc43ca4f47648aa11e41fa769fc9ae5927a5607`.
El primer lanzamiento se detuvo antes de crear bases porque el enlace del
checkout OCA requería lectura con el usuario autorizado. El reintento usó
ese checkout fijado y completó las dos pruebas. Pasaron 24 pruebas locales.

La siguiente puerta es consumir la observación actualizada en el perfil
anclado, usando una referencia del mismo respaldo que su copia OCA. Comparar
la partición 118/2, los formularios y menús de F/G, y proyectar las 71 reglas de
forma idempotente. Ejecutar la revisión física y restaurar las obligaciones
por proveedor, con casos de creación y edición que no introduzcan defaults.
Las 32 diferencias de obligatoriedad siguen abiertas. T2 conserva la
aceptación multifrente. Siguen abiertas la certificación financiera y de HR,
DTE/CAF/SII, Tesorería, Calidad, Studio/Documentos/Firma, los demás productos
y la restauración integral cero Enterprise.

## U7 — admisión física de relaciones nuevas, 24-11-2026

`tools/community/check_original_anchor_relations.py` incorpora una puerta
ejecutable para la revisión de una pareja anclada privada. Contrasta el catálogo
real de PostgreSQL con la revisión de esa pareja. Comprueba los extremos,
la validación, las acciones de borrado y la ausencia física de la columna en
el origen. Rechaza cambios de restricciones originales y exige una prueba
específica cuando una relación nueva ya tiene referencias pobladas.
Ejecutar la puerta bajo el bloqueo compartido tras `review_original_anchor.py`,
con `--stage`, `--review` y un `--output` privado nuevo. Conservar el recibo
junto al plan y la revisión de la misma pareja.

Sobre la pareja retenida U2, 194 consultas de solo lectura demostraron que
las 32 FK revisadas viven sobre columnas nuevas y carecen de referencias
pobladas. Once pertenecen a tablas con filas previas. Las 26 políticas
`SET NULL` y seis `RESTRICT` coinciden con el catálogo revisado. Los dos
`register_id` son adiciones vacías y siguen pendientes de una prueba de
uso. La huella del recibo privado es
`6ab9a01788d74c3154140908c4c3cac219740ef563dffb9083f646b1425cedff`.
Tres pruebas negativas contra los catálogos reales rechazaron una definición
alterada, una restricción ausente y una revisión atribuida a otra pareja.

El candidato `b665caa7` pasó 13 pruebas en Community oficial y cinco en
una copia fresca de Cerro con el motor nativo. El paquete se ensayó en bases
nuevas en serie bajo el bloqueo compartido. La verificación de la puerta
anclada usó U2, con el respaldo y el control nativo de ese ensayo.
Los 164 archivos de addons coincidieron y la comparación de los cuatro
contratos de almacenamiento y la FK Calendar pasó. La referencia fresca
conservó 971 tablas/proyecciones, 197 contadores y 60.638 XML IDs.
La huella de la comparación física es
`561701108a0b0c2a253cda6c21dcfd06f6b801c71e3699e61a2600c3e6aa5370`.
El lanzador SSH falló al interpretar su argumento de salida después de
emitirse ambos recibos. Se verificaron los recibos y las huellas por separado.
Evidencia privada en `~/.codex/local-artifacts/community-resume-20261124/U7`
y en la raíz del servidor
`/opt/steps-validation/community-multifront-parallel-20261124U7`.

Las 32 columnas originales que perdieron `NOT NULL` carecen de nulos en U2.
En ocho casos la tabla está vacía. El resultado permite usar los valores
existentes como testigos al restaurar los contratos campo a campo. Sigue
pendiente la obligatoriedad de nuevas escrituras para esos campos y la
adopción en una copia actual. Los cinco campos de configuración con
admisión explícita OCA mantienen ese control y la evidencia F/G.

El inventario PostgreSQL de los tres productos coincidió módulo por módulo
con el del 24-11. Conserva las fuentes privadas y la excepción de
`steps_transport`. Sigue la certificación del motor y de los consumidores
HR, días, YTD, redondeos, contabilización, Previred/libro, DTE/CAF/SII,
Tesorería, Calidad, Studio/Documentos/Firma y la restauración integral.

## U6 — almacenamiento original de Nómina, 24-11-2026

Se cerró el ensayo enfocado del candidato `c363608a`. El mismo inventario de
164 archivos de cinco addons propios y Simple Digital AGPL se verificó en
Community oficial (68 instalados, 0 Enterprise, 13 pruebas) y en una copia
fresca privada de Cerro con el motor nativo (417 instalados, 140 Enterprise,
5 pruebas). Ambos terminaron con cero fallos y errores. El paquete conserva el
nombre literal de línea, el nombre traducible de regla, el nombre nullable de
días trabajados y el calendario nullable de contrato con FK `SET NULL`.
El catálogo físico y los campos de los dos registros de Odoo se verificaron
con conexiones de solo lectura. En Community también se probó el borrado
atómico de borradores y el rechazo al intentar borrar históricos protegidos.

La copia nativa conservó 970 tablas/proyecciones, 198 contadores, 60.638
XML IDs y la evidencia de históricos antes y después. El preflight de ambas
bases, las restauraciones y las pruebas se ejecutaron en serie con el bloqueo
compartido. U5 había aprobado Community, pero el calendario sin horas del
fixture provocó una división por cero en el costo horario del RR. HH. nativo.
U6 añadió un turno al calendario de prueba y repitió ambas ejecuciones en
bases nuevas. Se conservaron el respaldo privado y la evidencia de U5.

Huella del inventario idéntico:
`72f053b06900c7a3725c624b2fca733fb21f18f81c3d9f87903803855269e4ae`.
Comparación física:
`9bc18fb4bc88108ee5dc3d1b01e9a91a582e99754b87319778f2f514e8b0093a`.
Evidencia privada en `~/.codex/local-artifacts/community-resume-20261124/U6`
y respaldo en la raíz privada U6 del servidor. Pasaron además 74 pruebas locales.

La auditoría de solo lectura del 24-11 confirmó los inventarios instalados
de la tabla siguiente. Cambiaron las huellas de dos módulos de Cosecha en
Cerro, sin altas ni bajas. Las tres matrices de dependencias, las rutas de
fuentes privadas y el caso `steps_transport` están en el directorio privado
de la ejecución.

El próximo bloque es una adopción anclada nueva que compruebe las 32
diferencias de obligatoriedad y las 32 FK adicionales, antes de ampliar
consumidores o dependencias. Sigue vigente el alcance de F/G para las 71
reglas y la interfaz. U6 certifica almacenamiento y borrado de borradores
con fixtures. La preservación de identidad al convertir, la nómina
financiera, DTE/CAF/SII, Tesorería, Calidad, Studio/Documentos/Firma, los
demás productos y la restauración integral cero Enterprise siguen abiertos.
La pareja multifrente T2 conserva su alcance.

## Reanudación e inventario — 23-11-2026

La automatización reanudó la migración en un worktree propio desde la canónica
actualizada. T2 sigue siendo la última pareja multifrente aceptada. Se recuperó
el candidato de almacenamiento de Nómina que había quedado en pausa en
`4312b0f7`. U3 había ejecutado 684 pruebas Community; la referencia nativa
quedó interrumpida y su objetivo de 467 casos sigue sin certificar.

| Producto | Instalados | Enterprise | Propios instalados | Propios con caminos Enterprise en el código candidato |
| --- | ---: | ---: | ---: | ---: |
| Cerro | 414 | 140 | 133 | 74 |
| Steps | 310 | 123 | 19 | 9 |
| SyS | 336 | 142 | 21 | 14 |

Se inventariaron los módulos instalados con PostgreSQL en solo lectura y se
contrastaron sus manifiestos efectivos con los del repositorio. El repositorio
contiene 170 módulos propios con manifiesto. 40 quedan fuera de Cerro y tres
propios instalados en Cerro existen sólo en fuentes privadas. Se verificó el
origen activo de Simple Digital AGPL en los tres productos. Para Steps,
`steps_transport` tiene una fuente identificada fuera de las rutas activas y
queda pendiente reconciliar su ruta efectiva antes de migrarlo. Studio conserva
su registro en el inventario. Los grafos de manifiestos quedan pendientes de
contraste funcional de imports, vistas, assets, datos y permisos.

La auditoría y las matrices completas por producto quedan en
`~/.codex/local-artifacts/community-resume-20261123`. El inventario nuevo
corresponde a los servicios vigentes. Los conteos de T2, S7 y la matriz de
octubre corresponden a sus respaldos y paquetes respectivos.

### Almacenamiento histórico y custodia de U2

Se completó la clasificación pendiente sobre las dos bases privadas U2 de
octubre, con 17 consultas verificadas en solo lectura. Permanecen exactos los
3.965 registros originales de mensajería, seguimiento, seguidores, actividades
y adjuntos. El único adjunto agregado es un candidato a icono técnico de menú.
Los 552 vínculos de grupos de menús originales quedaron iguales. Los siete
vínculos adicionales pertenecen a menús nuevos. Los valores de vencimiento
comparados quedaron iguales. La clasificación conserva el estado sin aceptar
la conversión. SHA256: `b7263606cf4e2cb01a966349e9cbd8ca8fc5ca618fd5faf79c37c4109a619ff6`.

El catálogo de la referencia nativa U2 (382 instalados) y el de su copia
anclada con OCA (144 instalados, cero Enterprise) coinciden en los cuatro
contratos de columna y en la FK Calendar con SET NULL. Se conservaron los IDs
y la metadata de los cuatro campos y sus modelos, y los cinco XML IDs de
campo originales con `noupdate` íntegro. Los siete alias adicionales del
motor y el puente apuntan a esos mismos campos. Comparación privada:
`1d333ddef8fdd82bf22cb62764d309ded692664d6df1c4235c054fd0106452ff`.
Siguen pendientes 32 diferencias de obligatoriedad y la revisión de las
32 FK adicionales. Esta revisión de catálogos no certifica escrituras sobre
históricos pagados ni la operación de los demás productos.

Se preparó U4 en una raíz privada con cinco addons propios y el proveedor
AGPL. El perfil de almacenamiento deja fuera actualizaciones independientes,
incluida la migración T155 que envuelve dos fórmulas de asignaciones. Los dos
modos adquirieron el bloqueo compartido y detuvieron antes de crear una base:
`SHOW data_directory` apuntó al volumen con 1,90 GiB disponibles frente a la
reserva de 5 GiB. Artefactos tenía 12,0 GiB. El inventario posterior encontró
30 ensayos con prefijo de Nómina en ese volumen y un total de 2,33 GiB contando
incluso T2 y casos a preservar. Esa limpieza por sí sola no cubre el déficit.
No se retiraron copias ni respaldos. Se conservaron ambos recibos de capacidad.
Pasaron 63 pruebas locales de herramientas y contratos de evidencia. El
paquete de ejecución queda en `origin/codex/community-resume-20261123` a la
espera de la pareja funcional nueva, completada después en U6.

La [limpieza posterior](LIMPIEZA_DISCO_2026-11-23.md) restituyó la reserva.
Al cierre dejó 34,64 GiB libres en el volumen de PostgreSQL y 32,66 GiB en
raíz. La siguiente ejecución debe verificarla bajo bloqueo, crear raíz y
bases privadas nuevas, y repetir el paquete de almacenamiento exacto en
Community y la referencia fresca de Cerro. Después corresponde
revisar las 32 columnas y 32 FK pendientes en una adopción anclada nueva.
Conservar F/G y el testigo de 71 reglas. Mantener abiertos días, redondeos,
YTD, asientos, Previred/libro, consumidores, DTE/CAF/SII, Tesorería, Calidad,
Studio/Documentos/Firma, demás productos y recuperación integral cero Enterprise.

La pareja normal vigente es **T2**, congelada en `10278323`: **671 casos
Community y 462 nativos, cero fallos y errores**. Foundation **1.16.0** corrige
la FK de seguridad detectada después de S7 mediante la API original de Odoo.
El paquete exacto y el postflight físico pasaron en ambos entornos. S7 queda
conservado como evidencia histórica, con su regresión diagnosticada.

La copia original S7 completó además la proyección real de sus 71 reglas bajo
UID7: **71 relaciones creadas y cero en la segunda ejecución**, con commit.
Los 120 maestros originales, sus datos, IDs, ACL, reporte 462/modelo 600 y
contadores permanecen. Esto cierra la proyección de relaciones; no certifica
sus importes ni la adopción completa de metadatos, interfaz legada e históricos.
G validó por separado cinco formularios y cuatro menús de configuración contra
el testigo nativo real, conservando la categoría oculta y los otros tres visibles.
Ninguna de estas puertas convierte integralmente Cerro ni resuelve el 31.
Este bloque no publicó cambios en producción ni en QA-Cerro.

## Pareja T2 y proyección original aceptada por alcance

T2 conserva **33 addons propios / 461 archivos propios + 52 AGPL = 513**,
API **18.0.1.16.0** y Foundation **18.0.1.16.0**. El archivo Git seleccionado
coincide con el paquete probado y su evidencia fue reproducida offline desde
el worktree de integración. Pasaron 212/168 métodos críticos y 31/27 versiones
exactas. Grafos medidos independientemente: **120/0 EE Community y 398/140 EE
en referencia nativa**. La referencia sigue usando Enterprise.

Se preservaron **925 tablas/proyecciones, 147 contadores y 59.113 XML IDs**
del respaldo fresco posterior a T139/T140. Son 1.072 contratos: 1.071 literales
y el único cambio tipado `base_weight` ID1 `15.00`→`15`, sin Float ni redondeo.
El testigo T2 se reconstruyó desde su propio dump; SHA256
`0632c34720d3b9edb32ddc82826085f027c8d8eca0a876bd636afb205e175314`.
Los históricos, vencimientos e identidades originales se compararon antes y
después; no se reutilizan los snapshots anteriores para afirmar esta conservación.

Las pruebas de borrado reales verificaron RESTRICT con actor Settings normal
en ambos motores. El postflight T exige además la FK validada, no diferida,
sus columnas/extremos, modelos y campos originales. En nativa contrastó antes
del upgrade, después del upgrade, tras las pruebas y desde otra lectura final;
en CE frío no se inventó un baseline nativo. El OID queda informativo. T1 pasó
671 pruebas CE pero falló al leer OID como JSON; nativa T1 detuvo antes del
upgrade. Se conservan esos intentos y se repitió T2 con `oid::bigint`, sin
relajar la política de borrado ni fabricar un recibo T1 de aceptación.

Evidencia privada T2: `/opt/steps-validation/community-multifront-parallel-20261030T2`
y `~/.codex/local-artifacts/community-adoption-20261030S/accepted-normal-T2`.
Archivo 1.106 miembros: `11c01c60ba0263a1f87becaca404140af08350ff8b8be15f656883da139d5b57`.
Sello offline 1.108 miembros, 11.512.292 bytes:
`aafb9c8b073fe04ef90822b50bdabe41c0e217d7fd999a7b6eb1218481dbe55d`.
Resumen: `8bdd1318b54c00c4d5d9f54b73a89e43444743775a987c6630bc36e9aa74bb81`.

El intento anclado **F** usó sólo los contratos de datos/seguridad y la API
real de proyección. No saltó una excepción de menú: el alcance `projection-only`
es explícito y el alcance `full` permanece estricto. El Source nativo real es
obligatorio, con actor/contexto y partición 118 permitidos/dos denegados exactos.
Se observaron las 71 inserciones y la segunda llamada idempotente, con todas las
columnas originales, auditoría de maestros, políticas y contadores intactos.
Se conservaron 88 aliases de origen; los tres de referencia no se adoptaron.
Sólo los dos modelos OCA nuevos, vacíos y ausentes en origen recibieron lectura
del gerente existente. No se agregaron grants sobre los modelos originales.

F: `/opt/steps-validation/community-original-handover-20261030S7/anchor/probe-source-projection-F`.
Probe: `a21e327512a1ba4bc349793a64f8770d6288b9c412c1e751b405bcbca4ecd480`.
Recibo después del commit: `f926c064d3494dd7a97cc507f4bdd37f7e9aa98da8d6a11add952a59dc0d9b73`.
Mantiene `ui_admission=False`, metadatos/refs opacas no admitidos, certificación
financiera e integral falsas. El runtime anclado S7 permanece congelado en 1.15;
la corrección 1.16 probada en T2 debe adoptarse en un overlay nuevo, sin pisarlo.

El observador nativo readonly de menús confirmó, bajo el mismo UID7, tres menús
visibles y categorías ocultas con `debug=False`. No se infiere permiso desde
el nombre ni se añade el grupo técnico. Kernel y todas las conexiones PG fueron
readonly, sin ejecutar acciones ni leer nómina histórica. Source de menús:
`c5a81c31ba8242207920d301e5ee1baeb07813285f9d93157168c8485497e289`.
**G terminó con commit y los tres flags verdaderos**:
`source_menu_witness_validated`, `source_menu_visibility_parity`,
`core_ui_admitted`. Validó cinco formularios por la API real y los cuatro menús,
sus lecturas/ACL, acciones/modelos y visibilidad normal contra aquel Source.
El renderer original conservó su ruta/configuración bajo el actor normal;
no se imprimió una liquidación histórica ni se certificó su validez legal.
G observó **cero/cero inserciones** sobre las 71 membresías ya creadas por F.
Maestros, alias, auditoría, política original y contadores permanecieron exactos.
No hay excepción por país o grupo técnico: la categoría se conserva oculta
porque esa denegación fue observada realmente en ambos motores.

G: `/opt/steps-validation/community-original-handover-20261030S7/anchor/probe-source-full-G`.
Probe `511e52c07e1bb368fe51d7cb39e85014290748e27cc54accab8fbf44164701d4`;
recibo después del commit `1c101c590ecc180abf23d8b3c72ef03f00731e849be030cec42d1b7728a46c3d`.
Las copias locales se verificaron por hash y como datos inertes. `full` designa
el alcance del probe de configuración, **no la conversión completa**:
`all_legacy_flows_certified`, `original_metadata_semantics_admitted`,
`financial_certified` e `integral_conversion` siguen falsos.

Inventario vigente después de T139/T140: Cerro **382/140 EE/101 propias**;
Steps **310/123/19** y SyS **332/142/17**. Repo **134 propias / 37 fuera de Cerro**,
**55 apps instaladas con caminos EE**. La nueva app multiempresa explica el
aumento de alcance; no se atribuye a una regresión o retiro Enterprise de esta
migración. Ver la matriz y su fuente readonly `9358e34e…7240e`.

## Histórico S7: código y aceptación funcional

- Foundation `step_payroll_contracts` **18.0.1.15.0** conserva la familia nativa
  de beneficios como datos, sin fingir su API. Sus observadores contrastan
  14 tablas/58 filas y relaciones originales en el ensayo anclado. Dos aliases
  OCA reutilizan los grupos originales; no crean grupos ni membresías.
- El adaptador de `res.groups` resuelve esos dos pares mediante las interfaces
  públicas `get_id`/`parse` de las definiciones reales de Odoo. Odoo sólo registra
  un nombre externo por grupo: `env.ref` por sí solo no prueba `has_group` ni
  expresiones de campos/vistas. Se conservan IDs, evaluador, implicaciones y
  restricciones. Un alias en conflicto falla también al negarlo; el nombre
  nativo válido mantiene su comportamiento. Ocho casos nativos enfocados pasaron
  antes de repetir la pareja completa.
- API **18.0.1.16.0** añade formulario, lista, acción y menú Community reales de
  tipos de entrada. Tres casos comprueban actor normal, país oculto, campos y
  caché caliente. Los indicadores sin semántica certificada permanecen de sólo
  lectura en el formulario; no se introducen maestros.
- Paquete exacto: **33 addons propios / 461 archivos propios + 52 del proveedor
  AGPL = 513**. El archivo Git reproducido en el worktree de integración coincide
  byte a byte con los 461 archivos propios probados. Se verificaron 212/168
  métodos críticos y 31/27 versiones por modo, incluidos 26 módulos requeridos.
- Grafos medidos: Community **120 instalados / 0 EE**; copia nativa de Cerro
  **397 / 140 EE**. La segunda conserva Enterprise y es una referencia.
- Preservación normal: **921 tablas/proyecciones + 140 contadores**, 59.079
  aliases originales y sus noupdate, modelos, relaciones, ACL, históricos y
  saldos. El único cambio de representación permitido sigue siendo
  `stock_package_type.base_weight` ID 1 `15.00`→`15`; un testigo nuevo, desde el
  respaldo S7, prueba equivalencia sin Float ni redondeo. R3 permanece separado.

Evidencia privada: `/opt/steps-validation/community-multifront-parallel-20261030S7`
y `~/.codex/local-artifacts/community-adoption-20261030S`. Cápsula normal:
`8efe41690d0f7b5451455b0a9d7b9f0dc610d9674b832fd4759f29de642b9939`.
Reproducción offline con código Git confiable y sello de 1.104 miembros,
11.501.675 bytes: **`ad84c0302d4f46f39411f4f5c5fc49c468cf2cb37a394d5793f4e900c924aae0`**.
Resumen: `d9925da02991a4e55638be96151097ef651feb373b6694547202362737491e2a`.
El sello y su recibo se conservaron también en el servidor con modo 0600;
los bytes se releyeron allí y sus hashes coinciden con los verificados localmente.
El replay independiente desde el worktree de integración y 38 pruebas puras
de aliases, captura, custodia y verificador pasaron. Estas pruebas puras no
sustituyen los 1.133 casos funcionales de la pareja S7.

## Ensayo original anclado: avance y bloqueos

Las herramientas experimentales quedan preservadas en
`origin/codex/community-original-adoption-20261030`; no se presentan como una
conversión aceptada. S1 detuvo antes de ORM por Git; S3 detectó que el motor no
se había cargado. S2/S4 originales sólo se materializaron. S5/S7 cargaron OCA
real en copia fresca: **modelo 600, reporte 462, 144 instalados/0 EE** en S7,
con los demás productos explícitamente fuera de operación.

El perfil privado conserva los 120 registros y omite semillas y políticas
aditivas. Mantiene sus datos, maestros y permisos originales; dos modelos OCA
nuevos vacíos sólo admiten lectura del gerente existente. Usa cuatro columnas
nuevas nulas sin inferir propietario/padre y derivaciones LGPL mínimas para
preservar propiedades JSONB desde el primer arranque. La instalación oficial
por estados evita que `-i` propague init y recargue datos noupdate del proveedor.
La limpieza LGPL se delega completa, reteniendo sólo dos aliases originales
comprobados; 23 guardas SQL preceden ORM y sus tres negativas se ejecutaron.

El observador nativo readonly real confirmó **118 maestros permitidos y dos
tipos denegados** al UID7, sin ser superusuario ni cambiar sus cuatro compañías.
Los tipos 3/4 de Bélgica no son usados por las cuatro estructuras. Las reglas
de país originales deben conservar su denegación; no se concede acceso para
hacer pasar el ensayo. Todas las estructuras y las 71 reglas sí son visibles.
Sourceproof S7B: `6577c8c2d004778ce825e6427e3f4081080ccf15db8391febb18538082b42773`.
La primera comprobación Target S7 con ese Sourceproof pasó la política, actor,
contexto y partición de los 120 maestros. Se detuvo en el primer formulario
por el observador que prohíbe SQL fuera de la proyección. No alcanzó a escribir
las 71 membresías; el intento y su rechazo quedan conservados, sin ampliar
permisos ni aceptar una escritura por inferencia.

La revisión readonly S5 preserva 944/945 proyecciones literales, 59.079 aliases
y 140 contadores, sin columnas originales perdidas. El delta de filas es de
menús nuevos; historia/adjuntos necesitan separación técnica demostrada. Hay
36 diferencias de columnas: 33 caídas NOT NULL, dos aumentos y
`hr_payslip_line.name` VARCHAR→JSONB. Tres FK cambiaron sólo ON DELETE:
calendario SET NULL→RESTRICT, compañía RESTRICT→SET NULL y lote CASCADE→SET NULL.
Antes de restaurar CASCADE hay que cerrar `run.unlink` sobre todos sus hijos y
la protección de historias; no confiar en `unlink` de hijos ante cascada SQL.
Hay otras 32 restricciones nuevas que requieren revisión. **No hay aceptación
de conversión por esta revisión**, ni por cero EE en una cohorte aislada.

La revisión S7 independiente confirmó 944/945 entradas literales, 59.079 aliases
y **146 contadores** exactos. Sus 552 vínculos de menús originales permanecen:
hay siete vínculos adicionales sólo en menús nuevos. Se conservaron todos los
1.431 mensajes, 747 seguimientos, 620 seguidores, una actividad y 1.166 adjuntos
originales; sólo se añadió un candidato a icono técnico de menú. Los dos
parámetros de vencimiento comparados también son exactos. Estas observaciones
clasifican la diferencia sin otorgar aceptación productiva ni legal.

S7 añade una cuarta FK alterada: `rule_group_rel.group_id` RESTRICT→CASCADE al
reinicializar únicamente `res.groups`. La corrección mínima delega el updater
original del campo propietario `ir.rule.groups` después del inverso; no escribe
DDL manual ni cambia grupos, membresías o reglas. La prueba real de borrado debe
rechazar por la FK original, bajo actor Settings normal, y conservar su vínculo.
T exige además catálogo readonly antes del upgrade nativo, inmediatamente después
y tras las pruebas, con semántica y metadatos originales idénticos. Conserva
inmutables los contratos R3 y S. Candidato congelado T1: `ab9e7685`.

Las otras 32 FK nuevas están todas sobre columnas nuevas (26 SET NULL y seis
RESTRICT, once tablas). Dos `register_id` apuntan al maestro OCA nuevo, sin
materialización histórica acreditada. No sustituyen una FK anterior ni cierran
la adopción por existir. Las 36 diferencias de columnas y las tres políticas
de borrado de Nómina siguen pendientes; no hay exención para históricos vacíos.

Revisión S7: `12f26677c10e6602e7f0c3e0ab4e9e2a27813d0ee697a2c274b22f79d0a432d8`.
Clasificación readonly: `0e16916aa1c86a271998a69a8327e22cfa99096b00504f01dccff1091da14a77`.
Copias privadas verificadas localmente, sin ejecutar código de los artefactos.

## Referencia real SyS

Una única transacción RR/READ ONLY, sin ORM ni recálculo, capturó 622 cerradas
previas al mes actual, 9.710 líneas con componentes, 753 días y dos entradas.
Las 87.880 work entries son candidatas por contrato: no prueban vínculo directo
al recibo ni aprobación del período. La fuente tenía 727 cerradas; 105 actuales
quedaron fuera del corte. D registraba 627 en otro instante; no se atribuye el
cambio de población a este migrador.

La matriz reproducida liga 39 de las 71 reglas por XML ID original; 23 tienen
líneas históricas en esa cohorte. Sólo 14 coinciden en los campos/expresiones
actuales comparados; 25 difieren y 32 carecen de binding probado. SyS tiene
92 reglas: no se copia su configuración sobre Cerro por código coincidente.
La cronología de maestros sigue sin acreditar en las 71.

Se recontrastaron íntegros el positivo D, el cero F, los cuatro componentes
BASIC y la ambigüedad NET 8/32, conservada sin escoger una regla. La captura
liga 52 archivos listados del proveedor; no certifica archivos extra ni clausura
de ejecución. Artefacto privado A: `488437ac9e936279bf891c6a9c6c7ba053360fb098dd95c786f7921e50ccce77`;
replay independiente exacto: `297c761304a1badea7b23101161ff54793f360b6debbbd612e98f94a4ffd9aa8`.

## Siguiente puerta

Adoptar Foundation 1.16.0 en un overlay anclado nuevo y cerrar las diferencias
de almacenamiento/constraints. Conservar la proyección F y sus dos denegaciones;
conservar la paridad G de menús con el Source nativo real, sin conceder acceso técnico.
Cerrar menús legados y
referencias opacas, y certificar reglas, Previred/libro con casos equivalentes
probados. DTE/CAF/folios/firma/respuestas SII, demás productos y copia integral
restaurable con cero Enterprise continúan en el camino crítico. Quedan 55 apps
instaladas con caminos EE en código; producción conserva 140 EE.

El 31 sigue en riesgo. Esta migración no intervino producción, QA-Cerro,
vencimientos ni saldos. No hubo emisión SII, mensajes externos ni recálculo
de pagadas. T139/T140 es una entrega concurrente de otro frente autorizada
por sus propios tickets; sus cambios fueron conservados e inventariados.

## Prompt de continuación

```text
Haz fetch de origin/codex/ambientes-canonicos-reparacion y usa el worktree propio.
Lee AGENTS.md, el registro de ambientes, la operación canónica, el workflow, el
plan, COMMUNITY_CONTINUACION.md, COMMUNITY_AUTONOMIA.md y los documentos de
aceptación. Revisa el inventario integral y las fuentes privadas antes de editar.

Usa U13D como referencia de adopción parcial y T2 para la pareja multifrente.
Recupera `hr.salary.rule.struct_id` con maestros existentes. Comprueba altas,
ediciones, ACL y membresía M2M sin propagar obligaciones a líneas históricas.
Quedan seis obligaciones ORM y 29 diferencias exclusivamente físicas.
Comprueba que las 71 relaciones sigan exactas e idempotentes y que el perfil
genérico conserve su contrato. Mantén la cadena de sellos del inventario,
el observador nativo y el verificador de menús al actualizar los recibos.

Certifica reglas, días, entradas, redondeos, YTD, asientos, Previred, libro y
consumidores HR. Usa la referencia SyS y conserva las reglas de Cerro. Prosigue
con DTE, CAF, folios, firma, respuestas SII, Tesorería, Calidad, Studio,
Documentos, Firma y el resto de productos. Conserva Calendar, el Boolean bancario
legado, 210233 descontinuada, IDs, maestros, ACL, saldos y correlativos.

Prueba el paquete exacto en Community oficial y una referencia fresca de Cerro
con overlays y bases privadas, respaldo e inclusión bajo el lock compartido.
Preserva históricos, vencimientos y datos de producción y QA-Cerro. Evita
recalcular pagadas o validadas y emitir al SII real. Conserva la evidencia privada,
publica los commits validados y ejecuta verify_handoff.py --require-pushed.
Mantén el horario hasta verificar la copia integral restaurable con cero
Enterprise y la aceptación. El corte productivo queda fuera de la automatización.
```
