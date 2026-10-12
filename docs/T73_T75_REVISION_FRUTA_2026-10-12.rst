T73 T74 T75 Revisión de maestros y estimaciones de fruta
======================================================

Atención de tickets
------------------

Se leyeron los tickets 73, 74 y 75, sus comentarios humanos 9365, 9369 y
9374 y los tres documentos Word adjuntos el 12 de octubre de 2026.
Todos solicitan Desarrollo y Cerro El Plomo.

T74 y T75 están publicados, verificados y en Solved. Notas internas 9375 y
9376, sin destinatarios ni notificaciones. Se comprobó la etapa y el HTML
almacenado. Se revisaron comentarios y cambios recientes antes del cierre.

T73 solicita reemplazar el maestro de Packing por Categoría de fruta de
Gestión, adaptar sus relaciones y agregar Clase de fruta de Gestión en las
configuraciones de Exportaciones, Packing y Productores. Hay una decisión
pendiente: una recepción de Cerro usa la clase antigua A proceso de una
empresa cuya categoría homónima pertenece a otra empresa. Se consultó si
corresponde migrar a una categoría A proceso de la misma empresa o asociarla
a Materia Prima. No se debe suponer la equivalencia ni asignar la relación
entre empresas. T73 queda en En Espera, con nota interna 9377 y sin
notificaciones. Sus relaciones, menús y registros no se modificaron.

Implementación T74 y T75
-----------------------

step_producer_estimate_revision extiende modelos existentes sin tablas nuevas.
stock.package.type conserva su identidad y recibe Grupo paquete (Bins, Pallet,
A piso) y Pallet por avión. Cajas por pallet cambia de etiqueta a Cajas por
pallet/bins. Packing / Maestros / Tipos de pallets y Productores / Maestros /
Tipos de pallet abren la misma acción de Exportaciones. Se extienden tanto
su formulario como el formulario estándar de Inventario usado al abrir el
envase desde una estimación. Las capacidades negativas se rechazan al editar.
No se asignaron grupos ni capacidades históricas por el nombre del envase.

Las fórmulas pedidas en T75 se aplican literalmente:

* Bins = Kilos a proceso / Cajas por pallet/bins, solo grupo Bins.
* Pallets proceso = Kilos a proceso / Cajas por pallet/bins, solo grupo Pallet.
* Cajas exportación = Kilos exportación / Kg Caja Base de Especie.
* Pallets exportación = Kilos exportación / Caja Base x pallet de Especie.

Los resultados son cero si falta un divisor positivo o el grupo no corresponde.
No se añade una multiplicación implícita por los kg de una caja. Cajas cosecha
conserva Kilos a proceso / Kg por caja de la línea. Las cantidades se recalculan
al cambiar capacidad o grupo del envase y los valores de Especie. Pallets
proceso queda calculado y de solo lectura.

El informe semanal usa las mismas fórmulas y conserva filas, IDs, valores FOB,
precios, semanas, filtros, reglas y origen de cantidades. Añade Pallets proceso
como columna y medida. La instalación recalcula las cantidades derivadas
existentes; no cambia los kilos originales, las semanas ni sus documentos.

Pruebas y preservación
----------------------

t7475a y t7475b detectaron redondeo de Pallets proceso respecto al informe SQL.
Se desactivó explícitamente la precisión heredada para conservar la misma
precisión que las demás cantidades calculadas. t7475d aprobó ocho pruebas,
pero el comparador detectó cambios de auditoría y conversión de algunas marcas
de entrega nulas a falso durante la inicialización. La migración conserva esos
valores y los restaura exactamente después del recálculo, mediante una tabla
temporal de la conexión que se elimina al terminar. No se publicaron esos
paquetes. Cada ensayo partió de una copia nueva.

Paquete final b92bcc820a11c9e24679f854c3cf48da7d1c937d.
SHA256 ed79affae82895bea86cd2aa10faf827cb698ae60eeed5d9be8ba3988feb148e.
Módulo step_producer_estimate_revision versión 18.0.1.0.0.

MANAGEMENT_QA_DEVELOPMENT_t7475e y MANAGEMENT_QA_CERRO_t7475e aprobaron ocho
pruebas cada una, cero fallos y cero errores. Conservación exacta de todas las
columnas originales salvo las cuatro cantidades derivadas cuya corrección
solicita T75. Se verificaron las fórmulas de todas las líneas existentes, las
dos entradas de menú, formularios compartido y estándar, lista/pivot semanal
y validación, activación y reemplazo mediante una nueva versión de estimación.
Todas las muestras se revirtieron.

Ejemplo sintético: 100000 kg de exportación, porcentaje .8, envase con capacidad
35 y Especie con 5 kg por caja base y 200 cajas base por pallet producen 20000
cajas exportación, 500 pallets exportación y 125000/35 bins o pallets proceso,
según el grupo. A piso produce cero bins y pallets proceso. No son valores
históricos ni capacidades configuradas en los registros del cliente.

Publicación
-----------

El mismo paquete se publicó y verificó en Desarrollo y Cerro El Plomo. Se
repitieron versión, origen del código, menús, formularios, fórmulas de líneas
existentes, informe semanal y flujo real de versiones. Las muestras se
revirtieron y no se enviaron correos. Ambos servicios activos y acceso HTTPS
comprobados. Conservación exacta durante ambas instalaciones públicas.

Respaldos completos de base, configuración y filestore:

* /opt/steps_backups/management_development_20261012T191705Z
* /opt/steps_backups/management_cerro_20261012T191806Z

Se usaron overlays privados, sin sustituir raíces compartidas, con control de
downgrade, cambios concurrentes y exclusión /run/lock/steps-environments.lock.
Superposiciones:

* /opt/steps-managed/releases/development/b92bcc820a11c9e24679f854c3cf48da7d1c937d
* /opt/steps-managed/releases/cerro/b92bcc820a11c9e24679f854c3cf48da7d1c937d

La acción de Envases es 2029 en Desarrollo y 1444 en Cerro. Evidencia privada
fuera del repositorio: ~/.codex/local-artifacts/t74-t75/live/. No se versionan
adjuntos del cliente, dumps, configuraciones privadas ni registros reales.

Cambios guardados y subidos a codex/t73-t75-fruta y a la rama canónica
codex/ambientes-canonicos-reparacion. verify_handoff.py --require-pushed
aprobado en el worktree propio. Se preservaron los cambios ajenos.
