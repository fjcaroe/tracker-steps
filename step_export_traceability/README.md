# Trazabilidad por pallet T94

Reemplaza Exportaciones / Recibidor / Trazabilidad por una lista de tarjas E y un
panel con siete etapas. Usa paquetes, OT, repaletizajes validados, recepciones,
controles de calidad, inspecciones SAG, guías, embarques y reclamos existentes.
No crea un libro paralelo ni modifica sus resultados. La lista permite exportar
los resúmenes de todas las etapas con la herramienta estándar de Odoo.

La genealogía recorre las entradas de las OT y las líneas de repaletizado
validadas, evitando ciclos. Muestra todos los orígenes vinculados, sin adjudicar
cantidades de una recepción completa a una tarja concreta. Las cajas y kilos
pertenecen al folio consultado. Los controles de recepción se identifican como
controles de la recepción; no certifican resultados individuales de cada tarja.
Solo se muestran reclamos que identifican expresamente la tarja.

Las relaciones y permisos nativos siguen vigentes; no se usa sudo. Un dato sin
evidencia vinculada disponible aparece como “Sin registro”. El cuartel histórico
procede del dato ya registrado en recepción, no de una relación inventada. No se
deducen orígenes por coincidencia de nombre o por la ubicación actual del stock.
Se conservan también los vínculos nativos de guías y de tarjas de origen del
detalle. Las guías del embarque sin asignación individual se muestran aparte;
no se atribuyen automáticamente a todos sus pallets.

La calidad de llegada usa el catálogo de calidad existente mediante el nuevo
campo opcional `arrival_quality_id` en el embarque. Las fechas de arribo son las
registradas por el usuario y no una confirmación AIS. Datos anteriores intactos.
