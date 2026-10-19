# T92–T93 · Inspecciones y lotes SAG

Solo Desarrollo para QA. Extiende la inspección nativa `step.packing.inspection`;
reutiliza tarjas, inventario, OT, productores, especies, variedades, países,
fundos, comunas e instructivos existentes. Conserva registros históricos.

## Preparar un lote

Packing / Inspecciones / Inspección SAG: elegir servicio, establecimiento, especie,
tipo de fruta y país. Se puede agregar recibidor, instructivo y filtro de variedades.
El instructivo propone recibidor, destino, especie y tipo de fruta del programa.

Seleccione tarjas o escriba/escanee su código impreso en «Leer código / ingresar
folios», confirmando con Tab. Admite varios folios separados por coma, punto y
coma o salto de línea y no duplica una tarja ya seleccionada. Deben ser tarjas E
validadas con stock interno, de la misma empresa, especie y tipo de fruta; deben
cumplir las variedades y carga del instructivo, si se indicaron. Para una nueva
inspección no se reutilizan tarjas asignadas a otra inspección SAG. Reinspección
y tratamientos admiten historia anterior, pero no otra evaluación pendiente.

Un lote puede reunir varias OT y productores. El encabezado no identifica un
productor único: la pestaña Tarjas y trazabilidad conserva las OT y el detalle
original por tarja. La revisión exige que las OT relacionadas estén cerradas.
Los borradores históricos se adaptan al nuevo control cuando el usuario edita
los filtros o la composición; los resultados revisados permanecen inalterables.

Guardar antes de adjuntar evidencias. Documentar requisitos y fecha de consulta,
verificar controles, resolver tratamientos, registrar solicitud y horario externos,
muestreo y laboratorio. Un administrador de Inventario registra el resultado
comunicado por SAG con SIF y respaldo propio. Pendiente bloquea el despacho y no
puede borrarse ni restablecerse como preparación para eludir el resultado. Una
reevaluación no hereda archivos ni solicitud. El rechazo exige causal.

## Archivos del Anexo 5

El maestro Tipos de servicio SAG asocia cada servicio con INS, INT, REP, DET o DES.
Los servicios sin formato especificado en el anexo permanecen sin archivo;
no se inventa un formato para frío o recepción de camiones con sello.

- INS: inspección, reinspección o fumigación. Usa el número SIF del registro.
  Exportar los datos del lote no cambia su resultado ni lo marca aprobado.
- INT: recepción interplanta o devolución, con resultado de origen por tarja.
- REP: operación A/M/E y SIF de origen por tarja; E usa operación, SIF y folio.
- DET: anulación, con los folios seleccionados.
- DES: despacho, con fecha, destino, folios, especie y envases.

Configurar el número del establecimiento sin región en el contacto de la planta,
el código SAG en la especie y el código numérico SAG en el país. No se convierten
códigos ISO ni se asignan identificadores ficticios. Para los otros formatos usar
el correlativo de cinco posiciones de la pestaña Archivos y anexo de despacho.
Si la referencia de tarja no representa el folio oficial, completar «Folio numérico
SAG sin verificador» en la tarja. Solo se elimina un verificador reconocido como
`1234567890-K`. Se aplican letras por ceros, relleno a izquierda, campos sin
delimitadores, `&&` y línea final en blanco. Se rechazan faltantes, desbordamientos
y colisiones de folios normalizados.

INT, REP, DET, DES y el anexo requieren que el último resultado fitosanitario del
folio esté aprobado para el destino. Estas operaciones no se confunden con
nuevas inspecciones al verificar el despacho. Exportar no envía datos a SAG,
ejecuta repaletizados ni anula inventario.

## Anexo Excel y PDF

Indicar Nº de planilla. Ambos formatos comparten folios, especies, variedades,
provincia/comuna, envases, fecha de inspección, destino y productores; total al
final. Cada página de impresión repite número de planilla y columnas. El PDF usa
estilos propios sin solicitudes HTTP de recursos. La contingencia manual incluye
la leyenda correspondiente y lugar para firma.

El origen se obtiene del fundo explícito de la tarja o de los fundos de su OT y
entradas. Elegir comuna en el fundo o usar la relación existente sector/comuna.
No se resuelven nombres de fundos o comunas ambiguos por texto. El inventario no
encontró un maestro de provincias: su nombre se registra como atributo geográfico
de la comuna nativa, sin una tabla paralela ni confundirlo con la región. El menú
Comunas de origen SAG permite revisar esos atributos. Si falta un origen requerido,
el reporte exige completarlo, sin inventar el dato.

Referencia: Manual para Externos Programa Origen SAG v04, 10-07-2024, adjunto T92,
§§6.3–6.5, 6.8.4.2 y 6.10, anexos 2, 5 y 7; modificaciones DOCX de T93.
La planilla oficial se emite y regulariza en Multipuerto. El módulo no agenda
servicios, firma SIF, identifica plagas, prescribe tratamientos ni emite certificados.
Cada registro conserva un país; los requisitos vigentes se verifican ante SAG.
