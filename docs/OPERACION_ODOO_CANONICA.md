# Operación y publicación de Odoo

T210 actualiza `step_export_document_revision` con `document-design` en
Desarrollo, Cerro y QA-Cerro. La nota usa la modalidad del maestro de la
empresa, su matriz o compartida, y los embalajes de venta del producto que
pertenecen a la empresa de la nota o son compartidos. En cálculo por cajas,
un único embalaje con peso configurado se propone sin redondear las cajas.
Probar la selección desde la nota, el cálculo de 100 cajas de 1,5 kg y las
restricciones de empresa en copias. Conservar maestros y notas existentes.

T209 actualiza `step_packing_interplant` a 18.0.1.0.3 con el mismo paquete
`reception-excel --with-interplant`. El almacén de destino se consulta con
el contexto de la planta destinataria autorizada, aunque solo esté activa
la sucursal de origen. Un único almacén se propone automáticamente; varios
requieren selección. Las guías existentes sin selección resuelven el almacén
único al confirmar. No modificar las membresías del usuario ni su compañía
activa y conservar la recepción pendiente de validación en destino.
Reutilizar lotes nativos de igual código, producto y empresa al retornar o
recibir fruta nuevamente; conservar los vínculos de origen de cada movimiento
y el origen inicial del lote, sin sobrescribirlo. La migración conserva la compañía nativa de las tarjas anteriores al campo de compañía persistente, sin alterar stock ni maestros. Exigir 24 pruebas por copia, selector visual con una sola sucursal activa y
reproducción de la guía reportada mediante `run_interplant_draft_probe.py`
en una copia certificada de Cerro, siempre revertida. No confirmar una guía
real del cliente como prueba. Publicar y verificar el mismo paquete en
Desarrollo, Cerro y QA-Cerro, con respaldo y aislamiento intactos.
Si QA-Cerro aún no tiene el tipo nativo de traslado, usar
`configure_interplant_qa_type.py` con las dos plantas autorizadas: exige
prueba revertida en su copia, respaldo nuevo y conservación de guías y stock.
La revisión visual de guías nuevas espera cada respuesta de cálculo antes
de continuar y comprueba la propuesta automática del almacén único.


T207–T208 se entregan con `reception-excel --with-interplant` en Desarrollo,
Cerro y QA-Cerro. El paquete incluye `step_packing_interplant` 18.0.1.0.0 y
`step_packing_ticket_revision` 18.0.1.2.5. Tipo despacho precede al destinatario
y selecciona clientes, productores o empresas y sucursales del mismo grupo.
En Folio Pallet se eligen tarjas C, E y N con stock libre; usar Traer detalle
de pallets antes de confirmar. Se conservan instructivos de exportación y
traslados de materiales mediante movimientos nativos.

El traslado interplanta deja una recepción pendiente en Packing / Recepciones /
Recepciones interplanta. La planta receptora debe validar la llegada; hasta
entonces no tiene stock disponible. Preservar folio, lote, propietario,
cantidades y vínculos originales. No ampliar asignaciones de maestros ni
permisos de otras empresas para efectuar el traslado. Probar con un operador
que tenga acceso solo al destino y rechazar reservas, duplicados o cambios
en el origen, lote y cantidades de una recepción pendiente.

Las recepciones con devolución realizada se excluyen de los listados vigentes
y los informes dinámicos, conservando originales y devoluciones en Inventario.
Verificar filtros guardados, ambos tipos de recepción, totales y trazabilidad.
Cada copia del destino exige 19 pruebas, además del flujo real revertido en
la copia de Cerro. Revisar las pantallas con `check_interplant_dispatch_ui.cjs`
y retirar las sesiones privadas. `collect_interplant_delivery.py` comprueba
paquete idéntico, versiones, fuentes, respaldos legibles y aislamiento de QA.
El cierre interno requiere esas evidencias, revisión visual y ausencia de
respuestas nuevas. QA-Cerro conserva sus datos; no se refresca desde producción.

T204–T206 se entregan con `reception-excel --with-receipt-dispatch` en
Desarrollo, Cerro y QA-Cerro. Los tipos de despacho reutilizan el maestro
nativo, conservan las guías existentes y pueden compartirse entre empresas.
En recepciones, la unicidad aplica a folios vigentes y la guía se comprueba
por fundo. La corrección de una recepción a proceso realizada devuelve el
stock intacto mediante movimientos nativos y abre un borrador vinculado.
Verificar el Excel del folio 42 en copia y ensayar devolución y revalidación
sin modificar una recepción realizada del cliente.

T203 se entrega junto con T202 mediante `reception-excel --with-master-access`
en Desarrollo, Cerro y QA-Cerro. El paquete contiene el importador y los
perfiles de aplicación. Verificar en copia la pestaña Maestros Steps del
usuario, los menús elegidos, la consulta y edición de fundos, la revocación
sin reiniciar y el rechazo de cambios en empresas ajenas. La personalización
es optativa, conserva los selectores de lectura y no modifica las asignaciones
existentes de usuarios, grupos y empresas.

T202 amplía `reception-excel` en Desarrollo, Cerro y QA-Cerro. Verificar en
copia el consumo por cajas y kilos proporcionales, la reutilización del saldo
C y la consolidación de pallets E de un mismo productor con distintas
variedades. La importación conserva la OT abierta. La validación aplica la
división C nativa y el cierre registra las contribuciones E por repaletizado
con sus lotes y OT originales. Comprobar que una reimportación, una tarja
reservada o un exceso de capacidad se rechacen sin afectar stock.

T201 usa `packing-dashboard` para ampliar el panel nativo en Desarrollo,
Cerro y QA-Cerro. El paquete contiene solo `step_packing_dashboard`, sin
modificar operaciones, existencias ni documentos. Validar los siete
indicadores, períodos, rango manual, especie y empresa activa; comprobar
repaletizado, consumo real y despacho en copia. Los flujos usan la fecha
de recepción, proceso o salida. El stock muestra las tarjas actualmente
validadas originadas en el período. No duplicar ingresos por repaletizado.
Incluir las tarjas históricas vacías sin empresa solo cuando una recepción,
OT o repaletizado de la empresa activa acredite su origen; no reasignarlas
ni incluir paquetes sin trazabilidad.
Verificar además el panel servido, título blanco, siete tarjetas, filtros,
lista y formulario de detalle. Conservar el comparativo independiente.
Publicar el mismo paquete con respaldo, bloqueo y paridad.

T200 amplía `agriculture-multicompany` en Desarrollo, Cerro y QA-Cerro.
Los calibres del catálogo de Inventario permiten asignar varias empresas,
conservando su origen, identificadores y relaciones. Su grupo se habilita
para las empresas agregadas con los permisos del editor. Migrar únicamente
las asignaciones originales, sin fusionar calibres ni reasignar documentos.
Probar el formulario, el selector de Excel y el guardado de una tarja desde
otra sucursal, además de permisos y conservación de asignaciones utilizadas.
El caso privado de recepción de T194 se exige para su versión 18.0.1.0.4;
T200 mantiene sus pruebas de regresión sin repetir aquel documento real.
Publicar el mismo paquete con respaldo, bloqueo y paridad.

T199 usa `packing-output-lots` para publicar en Desarrollo, Cerro y
QA-Cerro el menú de calibres de Packing. El acceso abre la acción del
catálogo que ya usan las tarjas de proceso. Verificar el menú, el listado
y la selección de un calibre existente en una tarja de prueba. Conservar
los calibres y las relaciones de contratos e historial. Publicar el mismo
paquete con respaldo y bloqueo, sin plan de reparación de lotes.

Para T199, la comparación de Desarrollo conserva la suite amplia y
contrasta el paquete con la versión instalada. Si ambas ejecuciones
reproducen los mismos seis fallos contables, el certificador verifica
que el único cambio funcional sea el enlace del menú y ejecuta la
comprobación del catálogo antes de autorizar la publicación.

T198 amplía `producer-advances` en Desarrollo, Cerro y QA-Cerro. El
asistente omite los productos valorizados que se excluyan en cada
preparación, antes de buscar tarifas y reservar kilos. Conservar las
proformas existentes y evitar que preparaciones con distintas exclusiones
agreguen líneas al mismo borrador. Probar ambos modos de cálculo y el
flujo de factura en copia. Publicar el mismo paquete con respaldo y bloqueo.

T197 amplía `reception-excel` en Desarrollo, Cerro y QA-Cerro. El listado
nativo de Fruta a proceso muestra producto, embalaje, envases, kilos netos
y kilos por envase. Totaliza los envases y kilos visibles. Usar las tarjas
registradas y consultar las operaciones cuando falte el dato. Verificar el
menú y la lectura de recepciones existentes en copias antes de publicar.

T196 amplía `reception-lots` en Desarrollo, Cerro y QA-Cerro. Inventario
puede corregir el producto de tarjas C íntegras, sin reservas, procesos o
documentos asociados, mediante dos movimientos nativos trazables. Mantener
la recepción realizada, sus movimientos originales, los kilos, los envases
y el propietario. El solicitante autorizó habilitar inventario y lotes en
el AR11 existente y corregir solo las dos tarjas identificadas en Cerro.
Ensayar ese mismo plan en una copia fresca antes de aplicarlo con respaldo
y bloqueo. QA-Cerro conserva sus datos de capacitación.

El solicitante autorizó cancelar el anticipo en borrador que pasó a incluir
las tarjas durante la intervención y corregir ambas tarjas en Cerro. Usar
la cancelación nativa y conservar el historial de la proforma. Ensayar y
aplicar el mismo plan privado con el ejecutor versionado
`tools/ops/apply_receipt_product_case.py`, con respaldo y bloqueo compartido.

T195 amplía `producer-advances` en Desarrollo, Cerro y QA-Cerro. El
asistente selecciona kilos procesados o los kilos netos de tarjas C y E de
recepciones validadas. La fecha de corte aplica al cálculo procesado. Usar
precios explícitos para los productos de cada modalidad en la lista nativa.
Conservar los documentos históricos y evitar el doble uso de tarjas y del
origen entre modalidades, incluso cuando la tarja C se dividió. Verificar el
flujo 33/46, ambos informes, los permisos y la compra mensual en copias.
Publicar el mismo paquete con respaldo, bloqueo y paridad.

T194 amplía `agriculture-multicompany` en Desarrollo, Cerro y QA-Cerro. Un
usuario de Inventario con acceso al contacto de origen puede validar fruta de
un fundo asignado a la sucursal receptora, sin activar la otra sucursal. La
excepción de Inventario se limita al productor del mismo grupo de empresas y a
su recepción y tarjas; conserva el contacto, el dueño de la fruta y las reglas
de escritura. Probar en copia el caso reportado y el rechazo en transferencias
ordinarias. Publicar con respaldo, bloqueo y paridad, sin validar documentos
reales ni refrescar QA-Cerro.

T192 solicita un refresco explícito de QA-Cerro desde Cerro El Plomo. Preparar
una copia privada con el script `tools/ops/refresh_cerro_qa.py`, conservar las
versiones vigentes de Tesorería y Multimoneda en QA, y validar formularios,
informes y adjuntos. Antes de publicar, respaldar y archivar la base de
capacitación anterior, su configuración y su filestore. Mantener la
neutralización y el aislamiento de QA-Cerro. Desarrollo conserva el QA general.

T193 amplía `reception-excel` en Desarrollo y Cerro. Verificar la carga de
recepciones desde Fruta a proceso, la reutilización de plantillas y la carga
de una OT desde las secciones Fruta procesada y Fruta embalada. Las tarjas C
provienen de recepciones validadas. El Excel deja la OT abierta y no mueve
existencias. Probar los adjuntos en copia antes de publicar.

T191 autoriza `activities-accounting-list` en Desarrollo, Cerro y QA-Cerro.
La acción nativa de Contabilización Personal Propio conserva sus vistas y
limita los asientos a la empresa activa. Probar el cambio de empresa con
ambas seleccionadas en Desarrollo y verificar menú, listado y formulario en
copias frescas de los destinos. Publicar con respaldo, bloqueo y paridad.

T190 autoriza recuperar el ciclo nativo de Compras en Desarrollo, Cerro y
QA-Cerro, manteniendo proformas mensuales y anticipos como ciclos adicionales.
El formulario primario de anticipos no debe ser predeterminado de purchase.order.
Corregir prioridades y accesos en código, conservar los registros y probar
solicitud, confirmación, recepción y factura en copia, junto a la regresión de
proformas 33/46. Mismo paquete producer-advances, respaldo, bloqueo y paridad;
no validar compras, stock ni facturas reales ni refrescar QA-Cerro.

T189 autoriza `reception-excel` en Desarrollo, Cerro y QA-Cerro. Probar
la primera hoja del Excel externo y el guardado en borrador de una recepción
por folio. El usuario confirma los maestros cuando sus nombres difieren del
archivo. Mantener fecha efectiva y stock bajo el flujo de validación nativo.
Probar el adjunto en copia sin cargar registros del caso en producción.

T187 autoriza `activities-dashboard` en Desarrollo, Cerro y QA-Cerro.
Validar el panel nativo, los cuatro períodos y los indicadores de costo
con datos de la empresa activa. Publicar el mismo paquete con respaldo y
bloqueo, conservando la versión instalada de Actividades por empresa.

T188 amplía `reception-lots` en Desarrollo, Cerro y QA-Cerro. La pestaña
Fruta incorpora las condiciones de recepción y la clasificación. Validar los
dos menús de recepción y el guardado en copias frescas. Las selecciones
históricas quedan sin valor predeterminado. Publicar el mismo paquete con
respaldo y bloqueo, sin ejecutar el plan de reparación de lotes de T165.

T186 amplía `producer-advances` en Desarrollo, Cerro y QA-Cerro. Las dos
acciones de tarifas de Actividades abren su formulario agrícola y la acción
de Productores abre su formulario de anticipos. Verificar guardado de labor,
producto y unidad con ambas tarifas de Actividades y conservar el flujo de
precios de fruta. Mismo paquete en copias frescas, respaldo y bloqueo.

T185 autoriza `packing-company` en Desarrollo, Cerro y QA-Cerro. Al guardar
una tarja nueva se conserva la compañía de origen aunque esté sin existencias.
En Cerro, anular solo los tres borradores auditados sin stock, movimientos ni
referencias externas y enlazarlos con sus tarjas vigentes. Preservar sus
detalles y excluirlos de los listados de tarjas. Repetir el plan privado
validado en copia con el mismo paquete, respaldo y bloqueo.

T184 amplía `activities-company` en Desarrollo para el caso de EcoPlantas.
El selector de trabajadores de una cuadrilla contratista usa la empresa y el
contratista del registro, conserva las reglas de acceso y valida las líneas al
guardar. Verificar el formulario y el guardado en copia con la cuadrilla
reportada y trabajadores locales. Usar el paquete probado con respaldo y bloqueo.

T183 amplía `activities-company` en Desarrollo, Cerro y QA-Cerro. En el
registro de tareas, verificar que Contabilizar informe los maestros pendientes
antes de crear el asiento. Probar en copia una tarja inválida y la OT00068 de
EcoPlantas con sus maestros completos hasta generar un asiento cuadrado en
borrador. Publicar el mismo paquete con respaldo y bloqueo compartido.

T182 amplía `activities-company` en Desarrollo (incluida la empresa EcoPlantas),
Cerro y QA-Cerro. El detalle de la tarja sin lista de precios permite seleccionar
centros activos del plan de costos de la empresa. Con lista se mantiene su
selección de centros. Verificar la búsqueda nativa, el registro de labores
y la conservación de las reglas de T179 en copias frescas. Mismo paquete,
respaldo, bloqueo y paridad sin refrescar QA-Cerro.

T180 autoriza `payroll-steps-layout` solo en Desarrollo y para la empresa
seleccionada en el plan privado del caso. Conservar la acción nativa de
Nómina y los importes almacenados de Simple Digital. Verificar el formulario,
el menú Imprimir, el formato alternativo y el PDF real en una copia fresca.
Revisar visualmente el PDF y publicar el mismo paquete con respaldo y bloqueo.

T181 autoriza `payroll-simpledigital-base` en Desarrollo para la empresa
indicada en el plan privado. Usar la categoría imponible de la estructura
nativa cuando la regla GROSS conserva la fórmula anterior BASIC + ALW.
Verificar imponible, cotizaciones y líquido al calcular copias en borrador
del lote reportado. Preservar los originales y sus asientos al instalar.
La autorización posterior permite corregir los tres recibos de demostración
del lote indicado. Repetir el mismo flujo nativo en copia y conservar IDs,
referencias y el respaldo de los borradores previos. Los asientos regenerados
deben quedar cuadrados y en borrador. Sin pagos ni notificaciones.

T179 (adjunto 3544 y confirmación del usuario) autoriza `activities-company`
en Desarrollo, Cerro y QA-Cerro. Cuadrillas, registro de tareas y costeo
usan la empresa actual para personal propio y contratistas, incluso al tener
varias empresas habilitadas. Aplicar las reglas sobre los modelos existentes
y sus detalles. Conservar sus datos, permisos de grupo, menús y referencias.
Probar los seis menús, el acceso directo y los detalles en copias frescas.
Publicar el mismo paquete con respaldo, bloqueo y paridad. Mantener el
aislamiento y los ejercicios de QA-Cerro.

T175 (mensaje 10205, adjuntos 3536/3537) autoriza `producer-advances` en
Desarrollo, Cerro y QA-Cerro. Listas de anticipos sobre product.pricelist e
items nativos, compañías autorizadas, mercado y embalaje relacionados con los
maestros existentes. Proformas sobre purchase.order y factura nativa tras
validación, con fechas separadas de pago neto e IVA. El período usa la fecha
local programada de recepción, igual al informe de recepciones del productor;
el corte de proceso permite incluir OT posteriores. Distribuir la exportación
por los kilos consumidos de cada recepción y reservar cada parte una sola vez,
conservando tarjas, OT y guías. Impedir otra compra mensual sobre esos kilos.
La retención se toma de la política de especie y su impuesto seleccionado.
No cargar los precios ilustrativos del anexo en producción, modificar impuestos,
emitir DTE ni contabilizar documentos reales al instalar. La adaptación del
alias de labor obligatorio de tarifas conserva la exigencia para las tarifas
ordinarias y permite categorías de fruta sin inventar una labor. Probar también
la regresión de proformas mensuales, formularios, menús, cuotas nativas y PDF.
Mismo paquete en copias frescas, revisión visual, respaldo, bloqueo y paridad.

T175 revisión 1 (mensaje 10210): seleccionar la fecha local más antigua de
recepción prevista y efectiva; usar esa misma fecha para la vigencia de precios.
El corte utiliza la fecha nativa de la OT que se muestra como Date Packing,
independiente de su registro en el ERP. En recepciones históricas sin fundo,
admitir el productor nativo de la recepción si coincide con la tarja de origen.
Si una tarja histórica no indica embalaje, usar únicamente el único embalaje
nativo disponible de su producto exacto y alcance de compañía, si existe.
Preservar fundos, tarjas, órdenes, precios guardados y documentos existentes.
Verificar el caso real en copia fresca y promover el mismo paquete únicamente
en Desarrollo, Cerro y QA-Cerro.

T171 revisión 1 (mensaje 10199, adjunto 3535) autoriza `packing-proforma-policy`
en Desarrollo, Cerro y QA-Cerro. Actualizar explícitamente los impuestos de
proformas en borrador tras cambiar la política de su especie; el asistente
mensual también actualiza los borradores que reutiliza. Impedir aprobar un
borrador fiscalmente desactualizado. Conservar netos, cantidades, precios,
tarjas, OT y referencias anteriores si cambia la numeración interna 33/46.
Las proformas aprobadas o facturadas conservan su configuración aprobada.
El plan privado identifica el único borrador reportado y sus impuestos ya
configurados por el cliente; comprobarlo en copia fresca antes de actualizarlo
en Cerro. No aprobarlo, facturarlo ni modificar maestros o tasas al publicar.
Mismo paquete, respaldo, bloqueo, PDF revisado y paridad Cerro/QA-Cerro.

T174 (mensaje 10192, adjunto 3531) autoriza `previred-movement-dates` en
Desarrollo y SyS. Contratación a plazo indefinido (1) y cambio a indefinido (8)
admiten fecha Hasta vacía. Corregir únicamente el requisito falso de cierre
del validador instalado; conservar Desde obligatorio, los controles de otros
movimientos y todas las fechas e importes almacenados y emitidos. Probar
anexas mixtas y la descarga nativa, formularios y casos reales en copia fresca.
Mismo paquete, respaldo, bloqueo y ninguna declaración o cambio de nómina real.

T173 (mensaje 10187, adjunto 3530) amplía `previred-simpledigital` en Desarrollo
y SyS. Clasificar explícitamente la regla salarial nativa que paga la asignación
familiar retroactiva y llevar su total guardado al campo 23, únicamente en la
línea principal y para empleadores con CCAF. No inferir por nombre o por un
código dinámico ni sumar al campo 22. La clasificación de reglas existentes se
identifica en un plan privado certificado en copia; conserva IDs, fórmulas,
auditoría, recibos e importes. No recalcular nómina ni enviar declaraciones.
Mismo paquete, copias frescas, respaldo, bloqueo y prueba del caso reportado.

El paquete `previred-revision` certifica T173 y T174 juntos, únicamente en
Desarrollo y SyS. Incluye las dos extensiones y prueba en el mismo registro
sus quince casos, los archivos descargados y la clasificación privada de la
regla existente. T172 conserva además su entrega independiente en Demo-SYS.

T172 (mensaje 10183, adjunto 3529) autoriza `previred-simpledigital` en
Desarrollo, SyS y Demo-SYS. Corregir únicamente los campos CCAF 84/90
omitidos por la puerta de cero días del proveedor, después de recuperar la
asistencia nativa del recibo. Usar la renta Fonasa ya emitida y el indicador
del período; no modificar contratos, tasas, recibos ni asientos. Mantener
las cotizaciones existentes y no repetir importes en anexas. Exigir copias
frescas, prueba del caso privado de SyS, mismo paquete, respaldo, bloqueo,
verificación de menú/formulario/flujo y alcance instalado de SyS para Demo-SYS.

T171 (comentarios 10173/10174 y adjunto 3528) autoriza `packing-fruit-proforma`
en Desarrollo, Cerro y QA-Cerro. La compra mensual prepara proformas nativas
de Compras, separadas de Contabilidad y sin movimientos de stock; solo tras
aprobación se prepara la factura de proveedor en borrador. La especie permite
seleccionar el impuesto de retención existente: no inferir factores por nombre
ni modificar impuestos, contratos, cuentas o configuración fiscal al instalar.
El traslado de borradores mensuales anteriores nunca es automático: requiere
revisión explícita, conserva el original cancelado y rechaza diferencias de
importes o documentos ya contabilizados. El plan privado de Cerro identifica
el borrador real y los importes, tarjas y OT que deben conservarse en la copia.
Validar el ciclo 33/46, formularios, menús, PDF y anexo de mil filas, reintentos,
permisos y preservación de maestros y stock. Publicar el mismo paquete con
respaldo, bloqueo y paridad; no emitir DTE, consumir folios ni enviar al SII.

Entrega T171 verificada con `step_packing_fruit_proforma` 18.0.1.0.1 y el mismo
paquete en los tres destinos: 23 pruebas por copia, ciclo 33/46, caso original,
PDF y anexo de mil tarjas. Se conservaron maestros, stock y el borrador real.
Con esta ampliación instalada, la compra mensual se verifica mediante
`packing-fruit-proforma`; el antiguo plan T170 sin facturación previa ya no
representa el flujo de proformas. El usuario selecciona Cambio sujeto IVA y
Retención en Packing / Configuraciones / Fruta / Especie para la empresa activa,
y confirma explícitamente cualquier traslado de borradores anteriores.

T170 autoriza `packing-holding-contract` en Desarrollo, Cerro y QA-Cerro.
La compra mensual utiliza las cuentas nativas del producto/categoría en la
sucursal, con prioridad de la cuenta contractual específica y posición fiscal;
los impuestos y los diarios compatibles respetan la jerarquía nativa de empresas.
No revalorizar stock ni modificar contratos o cuentas al publicar. Para Cerro,
`--monthly-fruit-plan` identifica privadamente el caso real sin facturación
previa, con OT, período, cantidades, moneda, cuentas, impuestos y totales esperados.
La copia fresca debe completar la preparación del borrador y su reintento con
los mismos maestros, preservando stock e históricos. No sustituir ese caso por
un contrato/cuenta ficticios. La promoción exige el mismo plan certificado,
paquete, respaldo y bloqueo; conservar paridad e aislamiento de QA-Cerro.
No contabilizar facturas ni modificar maestros reales como parte de la prueba.

T166 autoriza `packing-output-lots` en Desarrollo, Cerro y QA-Cerro.
Agregar LOTE a la OT, con el número de OT por defecto y valor editable antes
del cierre. Propagar el nombre a stock.lot por producto y empresa en las
tarjas resultantes E/N. El plan privado del adjunto 3517 autoriza reemplazar
los lotes de las siete OT indicadas de Cool & Go en Cerro. Probar el plan en
copia fresca, conservar estados, cantidades, materiales, movimientos, permisos
y registros previos. Publicar el mismo paquete con respaldo, bloqueo y paridad.

T165 autoriza `reception-lots` en Desarrollo, Cerro y QA-Cerro. El lote de la
hoja Fruta crea o reutiliza stock.lot por producto y empresa y se conserva en
las tarjas C, sus existencias y el detalle consultado desde la OT.
El plan privado del adjunto 3516 autoriza reparar seis recepciones reales de
Cool & Go únicamente en Cerro, incluidos sus vínculos de división de tarjas.
Probar ese mismo plan y herramienta en copia fresca. Comparar cantidades,
reservas, propietarios, ubicaciones, estados, registros y contabilidad antes
y después. Publicar con respaldo y bloqueo, preservando datos de capacitación.

T162 y T163 autorizan `packing-tag-folio` en Desarrollo, Cerro y QA-Cerro.
Conservar los registros históricos y omitir del informe únicamente duplicados
de borrador desvinculados, sin stock, movimientos ni uso documental.
Revertir el cierre de la OT mediante movimientos nativos con referencia a los
originales. Solo Inventario, con stock íntegro y sin asientos, movimientos
posteriores, reservas, embarques, inspecciones ni documentos de costeo.
Validar reapertura y segundo cierre en copia. No revertir una OT real al publicar.

T161 autoriza `packing-material-consumption` en Desarrollo, Cerro y QA-Cerro.
Preparar materiales solo para tarjas E de exportación, sin alterar el producto
ni los kilos históricos. Copias frescas, mismo paquete, respaldo y bloqueo.

Las respuestas 10078 de T158, 10086 de T159 y 10076 de T160 autorizan
`packing-document-corrections`
para Desarrollo, Cerro y QA-Cerro. Actualizar únicamente los documentos de
Packing, con copias frescas, mismo paquete, respaldo y bloqueo compartido.

La respuesta 10082 de T157 incorpora ambos campos al formulario de Packing.
Validar su menú efectivo junto con el alcance de compañías.

T157–T160 autorizan `packing-producer-documents` en Desarrollo, Cerro y QA-Cerro.
Aplicar alcance explícito a listas de materiales nativas y agregar PDF y Excel
de OP, recepciones y proceso por productor. El correo se encola al confirmar
desde el asistente; las pruebas no envían correo real. Mismo paquete, copias
frescas, respaldo, bloqueo y paridad.

T156 y su respuesta 10102 autorizan `packing-process-report` en Desarrollo, Cerro y QA-Cerro.
Conservar la acción PDF de la OT y agregar Excel con resumen y anexo de tarjas.
Probar el mismo paquete en copias frescas, revisar ambos formatos y publicar
con respaldo y bloqueo compartido. Mantener la paridad de Cerro y QA-Cerro.

T152 autoriza `reception-variety` en Cerro, Desarrollo y QA-Cerro. La instrucción
expresa del usuario del 02-11-2026 cambia únicamente el orden de publicación:
primero Cerro producción y luego homologar Desarrollo y QA-Cerro. Antes de Cerro
se mantiene certificación en copia privada de Desarrollo y compatibilidad en
copia fresca de Cerro. Mismo paquete, respaldo y bloqueo compartido; migrar
Variedad del encabezado a cada línea conservando encabezados, tarjas e históricos.
Esta excepción no modifica el alcance de otros tickets ni autoriza SAG en producción.


T147–T151 autorizan `agriculture-holding` en Desarrollo, Cerro y QA-Cerro:
OP y OT en la sucursal elegida desde la matriz; panel de Productores con
selección de compañías autorizadas del holding; guías e instructivos de una
sucursal vinculados a sus embarques o los de su matriz; mercado, recibidor
genérico y contactos Notify/Consignatario; sobrepeso total firmado en kilos y
porcentajes de cuadratura. Reutilizar compañías, mercados, contactos y
documentos existentes. No asignar permisos, trasladar stock, validar documentos
reales ni cambiar pesos estándar al publicar. Copias frescas, mismo paquete,
respaldo, bloqueo, conservación de históricos y paridad Cerro/QA-Cerro.

Este procedimiento aplica a todos los agentes que trabajen en este repositorio.
Las instrucciones específicas de un producto se conservan, pero no reemplazan
la identificación y comprobación del ambiente real.

## Identificar antes de intervenir

Definición vigente del cliente, 06-10-2026:

- **Desarrollo es el único QA** y destino de revisión funcional.
- **Demo-SYS replica exclusivamente el alcance actual de SyS**, incluida Nómina
  Simple Digital y soporte de Luis. No es una copia de Desarrollo ni de Steps;
  no instalar allí aplicaciones para igualar todos los ambientes.
- Producción: **SyS (Luis), Steps / karo_consultorias y Cerro El Plomo**.
- Demo, Admin Studio y Everfruit son instalaciones legadas, fuera de QA y
  promoción. Conservar datos y respaldos; no eliminarlas ni distribuir mejoras
  allí. Su retiro de infraestructura requiere inventario y conservación previa.

Primero instalar y probar en Desarrollo. Las copias privadas de una producción
pueden validar compatibilidad, pero no son otros QA públicos. Promover el mismo
paquete revisado. Nómina oficial: Simple Digital; no instalar el motor anterior
ni recalcular liquidaciones pagadas al cambiar de motor. El retiro de un motor
requiere migración comprobada de estructuras/reglas e históricos antes de
desinstalar dependencias que puedan borrar registros.

La fuente de puertos, bases, servicios y dominios es
[`tools/ops/environments.json`](../tools/ops/environments.json). Por ejemplo,
`http://35.222.25.110:8075/odoo` es Desarrollo / `LAB_TAREAS`, y `8070` es
SyS. `8069` es Steps; no es SyS. Admin es una referencia Studio multi-base,
no una base para copiar ciegamente a los demás ambientes.

1. Leer descripción, adjuntos y comentarios recientes del ticket. Si el cliente
   respondió una decisión, incorporarla aunque haya una nota de análisis anterior.
2. Resolver URL, puerto y nombre del ambiente con el registro; verificar por SSH
   la configuración, base, servicio y rutas efectivas de addons. Una API sin
   acceso no demuestra que el servidor sea inaccesible: SSH sigue disponible.
3. Inventariar versión instalada, versión de manifiesto y hash del código que
   realmente carga cada servicio. `audit_runtime.py` no imprime contraseñas.
4. Consultar el manifiesto de la última entrega instalada, no elegir por la fecha
   de una rama ni por el checkout abierto. Gestión y sus puentes se consolidan
   en `origin/codex/ambientes-canonicos-reparacion`; el stack agrícola previo
   está integrado en esa base. Steps Móvil y Web Tracker conservan sus bases
   propias documentadas. Crear worktree propio y preservar cambios ajenos.

## Excepción específica T115, 24-10-2026

El usuario autorizó crear **QA-CERROELPLOMO** desde la producción de Cerro para
pruebas de implementación y capacitación del cliente. Es una copia aislada,
neutralizada y con fuentes/filestore propios. Desarrollo conserva el QA general
y la revisión previa del circuito de ingeniería. La copia del cliente no cambia
los destinos de publicación genéricos ni autoriza producción, accesos adicionales
entre empresas, envíos reales o una actualización automática de sus datos.
Un refresco futuro requiere conservar primero los ejercicios de capacitación;
no sobrescribir la copia por una ejecución recurrente.

El registro `qa-cerro` documenta esta excepción con `deploy_enabled=false`;
`tools/ops/provision_cerro_qa.py` implementa su creación explícita. Su servicio
no tiene tareas programadas ni salida a Internet, con excepción del acceso a
su propio HTTP local para informes. Los demás ambientes legados y SAG T92/T93
conservan sus restricciones.

## Actualizaciones explícitas T117/T118/T119/T120 de QA-CERROELPLOMO

T118, T119 y T120 solicitan aplicar sus cambios de recepciones de Packing a Desarrollo,
Cerro El Plomo y QA-CERROELPLOMO. La respuesta humana 9692 de T117 solicita
además actualizar la copia QA con las taras ya entregadas en Desarrollo y Cerro.
Los tipos de paquete `reception-revision` y `packing-tare` permiten únicamente
esos destinos dentro de estas autorizaciones explícitas. El registro de la copia conserva `deploy_enabled=false`
y no se habilitan promociones genéricas ni refrescos de datos. Se exige copia
fresca de cada destino, paquete idéntico, respaldo y bloqueo antes de publicar.
La capacitación existente, la neutralización, el correo y la red aislada se
conservan. Para probar la copia del cliente, un contexto temporal autoriza a su
rol únicamente la base clonada por socket local; retira la regla al terminar,
sin modificar claves ni dar acceso a producción.

## Contrato funcional

T141 autoriza `reception-report` en Desarrollo, Cerro y QA-Cerro: adaptar el
recibo de entrega nativo para recepciones entrantes de fruta según el adjunto.
Conservar acción, logo, direcciones y documentos de stock ajenos a Packing.
Guía, tipo/clase, lote, operaciones, tarjas con pesos y totales y transporte
proceden de los registros existentes. El recibo conserva formato numérico y
fechas de español de Chile sin cambiar el idioma del usuario. No validar recepciones reales ni cambiar
pesos o existencias. Mismo paquete en copias frescas, PDF nativo corto y largo,
revisión visual, respaldo, bloqueo, paridad e aislamiento de QA-Cerro.


T139/T140 autorizan `agriculture-multicompany` en Desarrollo, Cerro y QA-Cerro:
selección explícita de empresas y sucursales para Fundos de productores,
categoría, clase, calidad y color de fruta. Reutilizar los maestros y conservar
IDs, datos, empresa de origen y relaciones. No compartir documentos contables
ni inventario, ni asignar automáticamente otras empresas. Incorporar Fundos
a Packing / Maestros. La lectura de los operadores no debe requerir acceso
a fichas de compañías ajenas. Copias frescas, mismo paquete, respaldo, bloqueo y
paridad del módulo afectado; no refrescar capacitación ni retirar aislamiento.


### Paridad de las entregas de Cerro y QA-Cerro — 30-10-2026

El usuario indicó mantener QA-Cerro incluido en los cambios aplicables que se
entreguen a Cerro producción, para evitar versiones dispares y promociones
erróneas. Para cada módulo afectado, comprobar versión y código efectivo de
ambos antes de registrar la entrega. Usar el mismo paquete certificado en
Desarrollo, con prueba fresca de cada destino, respaldo y bloqueo. La copia
del cliente conserva capacitación, aislamiento y datos propios; no se refresca.
No promover código, configuraciones de ejercicio o datos desde QA-Cerro hacia
producción por coincidencia de versiones. Las restricciones de prototipos SAG
y de la migración Community se conservan; esta regla no publica prototipos.

La ampliación actual de T138 incluye expresamente QA-Cerro con `payroll-days`,
mismo paquete y versión 18.0.1.2.0 que ya se verificó en Cerro. Se conserva
deploy_enabled=false para promociones genéricas; los gestores incorporan cada
tipo de paquete conforme a su alcance, sin habilitar instalaciones arbitrarias.
Comprobar los módulos de la entrega con
`python tools/ops/verify_cerro_release_pair.py --module nombre_del_modulo` en
el servidor; compara estado instalado, versión y hash del código efectivo.
No anunciar paridad de todos los addons por haber comprobado solo un módulo.

T138 autoriza `payroll-days` en Desarrollo, SyS, Demo-SYS, Cerro y QA-Cerro:
inasistencias injustificadas de contratos mensuales que cubren el mes completo,
base de 30 días menos faltas. Conservar licencias, contratos parciales, atrasos
y liquidaciones almacenadas. Probar los casos reportados por cálculo nativo en
copia de SyS; no recalcular recibos reales ni históricos al publicar. Demo-SYS
exige el alcance instalado de SyS, sin addons adicionales. Mismo paquete en
copias frescas de cada destino, respaldo, bloqueo y overlays privados.

T137 amplía `packing-stock` en Desarrollo, Cerro y QA-Cerro para admitir las
tarjas E/N ya validadas de la misma OT que aún no tienen existencias ni
movimientos. La validación de la tarja no genera inventario. Conservar las
validaciones de origen, empresa, productor, variedad, balance, reservas y
materiales; impedir reutilizar tarjas con stock o historial de movimiento.
Prueba en copias frescas, mismo paquete, respaldo y bloqueo. No validar ni cerrar
la OT real del cliente durante el despliegue ni cambiar la definición de sus
productos sin resolver el dato pendiente. QA mantiene ejercicios y aislamiento.

T132/T133/T134 amplían `reception-revision` en Desarrollo, Cerro y QA-Cerro:
envases físicos independientes del peso, detalle de tarjas, selector de Packing,
informes que consultan stock/recepciones nativos y encabezado de proceso.
Convertir los cuatro campos de los prototipos de QA en el sitio, con IDs y datos
conservados y vistas originales archivadas. No refrescar capacitación ni crear
maestros paralelos. La divergencia de fecha nativa/prototipo de una OT requiere
la decisión humana solicitada antes de cambiar el valor nativo. Se pueden
adoptar ambos campos conservando los dos valores mientras se espera. Copias frescas, mismo
paquete, respaldo y bloqueo compartido; no simular una entrega con Studio.


T128 y T135 autorizan `payroll-review` exclusivamente en Desarrollo y SyS:
mensajes con trabajadores y contratos pendientes, y validación de entradas del
período local del lote. No confirmar parámetros, corregir asistencias ni calcular
nómina real durante la publicación. Probar el asistente en copias frescas,
conservar las liquidaciones históricas y publicar el mismo paquete con respaldo
y bloqueo compartido. SyS continúa con Simple Digital.


T131 amplía `company-form` en Desarrollo, Cerro y QA-Cerro para corregir la
validación del contacto generado al crear sucursales nativas. La respuesta
humana 9790 y el adjunto 3432 permiten reproducir la validación del cliente web.
No modificar la obligatoriedad ORM del contacto ni crear sucursales reales
durante la verificación. Exigir copias frescas, mismo paquete, respaldo, bloqueo
y preservación de la capacitación y aislamiento de QA-Cerro.

T130 autoriza `company-form` en Desarrollo, Cerro y QA-Cerro para recuperar
el formulario completo de Ajustes / Empresas. Se conservan los formularios
específicos de Folios y Bodega Packing, los datos y los permisos. Copia fresca
de cada destino, paquete idéntico, respaldo y bloqueo; no refrescar QA-Cerro.

El 28-10-2026 el usuario autorizó `manual-contact` en Cerro y QA-Cerro para
crear proveedores sin el aviso de créditos del autocompletado IAP. Se revisa
primero en Desarrollo y se exige copia fresca de cada destino, paquete idéntico,
respaldo y bloqueo. Se conserva la búsqueda local, permisos, contactos y datos
de capacitación; no se compran créditos ni se refresca QA-Cerro.

T127 autoriza `product-bpa` en Desarrollo, Cerro y QA-CERROELPLOMO. El
28-10-2026 el usuario confirmó implementar como producto Community los campos
y el maestro BPA heredados de Studio. El núcleo depende solo de Product y Mail;
el puente reutiliza los maestros agrícolas actuales. Migrar en el sitio, con
IDs, relaciones, textos, fechas e historial conservados. QA-Cerro mantiene sus
ejercicios y aislamiento; no se refrescan datos ni se retira Enterprise.
Exigir copias frescas, paquete idéntico, respaldo y bloqueo compartido.

El 27-10-2026 el usuario autorizó reemplazar las cinco acciones de informes de
Tesorería por alternativas Community y desplegar el paquete en QA-Cerro para
probar, sin modificar producción. Esta autorización es específica de
`step_treasury_community_reports` y la extracción contable que necesita.
`tools/community/manage_community_reports.py` solo publica en Desarrollo y
QA-Cerro, exige pruebas del mismo paquete en Community, copia fresca de Cerro
y copia fresca del destino, ausencia de cambios concurrentes, respaldo y bloqueo.
No refresca QA-Cerro, no retira Enterprise, no asigna perfiles ni altera
vencimientos. La revisión inicial continúa en Desarrollo. El registro conserva
`deploy_enabled=false` para promociones genéricas de QA-Cerro.

T123 usa `invoice-payments` en Desarrollo, Cerro y QA-CERROELPLOMO, según
confirmación explícita del usuario en este chat el 26-10-2026. El adjunto pide
seleccionar facturas pendientes y distribuir el pago/cobro total o parcial,
con una contrapartida contable por factura y conciliación nativa. QA-Cerro
conserva sus ejercicios, red y correo neutralizados; no se refresca su base.
La instalación no cambia pagos ni facturas históricos. Las pruebas contables
se ejecutan en copia, publicando el mismo paquete con respaldo y bloqueo.

T114 y T122 autorizan `packing-controls` en Desarrollo, Cerro y QA-CERROELPLOMO:
perfiles por aplicación y analítica de consumos de Packing. Los perfiles no se
asignan automáticamente ni alteran membresías existentes; la contabilidad
conserva sus grupos nativos. El plan nativo OT Packing y las reglas por empresa
se configuran sin generar asientos o movimientos. Las cuentas de OT se crean
al preparar el comprobante. Las correcciones de cargos de asientos anteriores
se presentan como reclasificaciones en borrador, conservando los publicados.
Se exige copia fresca del destino, paquete idéntico, respaldo y bloqueo; QA
conserva sus ejercicios y aislamiento. El stock en kg y cajas separadas de T121
fue confirmado en la respuesta humana 9720, que informa el ciclo probado.

T121 autoriza además el paquete `packing-stock` en Desarrollo, Cerro y
QA-CERROELPLOMO: configurar una bodega nativa Packing, el origen de materiales y
el traslado de tarjas C al proceso. Se reutiliza la bodega existente cuando es
única y compatible. La configuración inicial solo crea registros logísticos
nativos; no inventa existencias ni mueve fruta o materiales de los ambientes
activos. Las tarjas se trasladan cuando el operador valida o cierra la OT.
La prueba en copias permite altas de configuración de la empresa autorizada,
manteniendo huellas de todos los registros previos y de todas las cantidades,
movimientos, reservas, documentos y registros contables. QA conserva su
aislamiento, sin refresco de datos ni autorización genérica de publicación.

Decisión del usuario, 06-10-2026: no crear ni ampliar desarrollos Studio.
Todo nuevo desarrollo se implementa en código versionado. El inventario de
retiro comprende modelos, campos, vistas, reportes, automatizaciones y permisos;
una portada propia no convierte el modelo manual que todavía consulta.
Para la migración de Fletes, la decisión vigente retira los nombres técnicos
`x_`: usar modelos `step.freight.*` y campos descriptivos propios, renombrando
tablas y referencias mediante migración. Conservar los IDs cuando sea posible,
sin crear maestros paralelos. Esta convención se aplica a nuevos desarrollos.
Los campos dinámicos nativos de
planes analíticos y reportes de nómina no se eliminan por ser `manual`.

- Relacionar temporada, especie, variedad, cuenta, productor, fundo y centro
  con los maestros existentes del ERP cuando el documento pide seleccionarlos.
  No reemplazar una tabla por texto ni crear un segundo maestro para simplificar.
- Un texto histórico o importado puede conservarse como snapshot de solo lectura,
  junto con su relación explícita. No resolver coincidencias ambiguas por nombre.
- Inventariar modelos y menús Studio antes de convertirlos; migrar de forma
  versionada. No crear campos ni parchear vistas manualmente por XML-RPC para
  aparentar una entrega de código. No desactivar Studio fuera del alcance.
- Comparar los campos y las vistas efectivas, no solo el XML del repositorio.
  Probar las acciones de menú y el formulario con el perfil de usuario previsto.
- Los maestros compartidos no autorizan a compartir documentos contables:
  mantener reglas por empresa y comprobar las relaciones en el servidor.

## Pruebas, promoción y evidencia

Una comprobación de sintaxis o HTTP 200 es insuficiente para publicar una
migración o cerrar un ticket. El paquete exacto debe pasar en una copia aislada
del ambiente objetivo; no reutilizar una copia con migraciones fallidas como
si representara el estado inicial.

`build_management_release.py` genera el paquete desde Git y registra commit,
versiones y SHA-256 por archivo. `manage_management.py qa` restaura una copia,
desactiva correo y tareas programadas, ejecuta pruebas del flujo y verifica
formularios y preservación de importes/filas. `deploy` exige la prueba del
mismo paquete y rechaza cambios concurrentes o una versión anterior.

Antes de modificar un servicio, adquirir la exclusión compartida
`/run/lock/steps-environments.lock` y comprobar que no haya otro upgrade activo.
Guardar dump y configuración recuperables. Usar una superposición privada de
addons; no reemplazar una raíz compartida con producción. No copiar bases de
clientes entre ambientes. Actualizar solo los módulos instalados afectados y
las dependencias nuevas justificadas.

Para Demo-SYS, comprobar primero los módulos realmente instalados en SyS con
``tools/ops/demo_sys_scope.py``. Su referencia es ``policy.mirrors`` del registro.
Un paquete para Demo-SYS no puede incluir addons ajenos a esa referencia, aunque
no vaya a instalarlos. El publicador de Nómina hace esa comprobación antes de
copiar addons o intervenir el servicio. Preparar su paquete con
``build_management_release.py --kind payroll --environment demo-sys``; no usar
el paquete agrícola combinado. No restringir la definición a dos aplicaciones:
Contabilidad, Colaciones y las otras aplicaciones que ya estén en SyS también
pertenecen a su alcance, respetando los permisos de cada usuario.

La auditoría del 06-10-2026 encontró 330 módulos instalados en SyS y 356 en
Demo-SYS: 26 adicionales, entre ellos Packing, Productores, Exportaciones,
Maquinaria, Gestión y Calidad. Es una diferencia previa que debe retirarse
con inventario de registros/dependencias y ensayo en copia, preservando datos.
Ocultar menús no equivale a desinstalar esos módulos ni a completar la réplica.
Esta corrección de alcance y publicadores no los desinstala ni cambia las
aplicaciones de SyS.

Verificar después: origen del código, versión instalada, servicio, URL HTTPS,
menús, vistas efectivas y un flujo representativo. Registrar qué se probó y
qué requiere hardware o aceptación del cliente. No decir «resuelto» por haber
hecho un commit o instalado el módulo. Conservar los respaldos ante un fallo;
no restaurar una base descartando datos nuevos sin evaluar la recuperación.

Los accesos por puerto redirigen a destinos fijos HTTPS mediante nginx, usando
[`return 308`](https://nginx.org/en/docs/http/ngx_http_rewrite_module.html#return)
y [`listen`](https://nginx.org/en/docs/http/ngx_http_core_module.html#listen) sobre
la dirección privada de la VM. Ruta y query se conservan. Las API deben usar
directamente el dominio canónico porque algunos clientes XML-RPC no siguen
redirecciones. No cambiar claves para resolver esta diferencia de URL.

La etapa y el comentario de un ticket deben describir el ambiente donde se
aplicó y verificó la solución. No cerrar si el ambiente solicitado sigue sin
actualizar. Los comentarios al cliente usan lenguaje de negocio; la evidencia
técnica detallada queda en el acta interna. No enviar mensajes ni notificaciones
externas sin la autorización correspondiente.

Terminar con commits, push y `python tools/git/verify_handoff.py --require-pushed`.


## Ampliación de capacidad autorizada — 28-10-2026

El usuario autorizó explícitamente ampliar odoo-data-balanced-20260923 de 100
a 150 GiB, con respaldo verificado y bloqueo compartido. Se completó en odoo-new
(stepsconsulting/us-central1-c): dumps SyS/CERRO_EL_PLOMO totalmente decodificados,
snapshot odoo-data-pre150-20261028-205103 READY y ext4 ampliado en línea.
Sin DML de negocio, reinicio, cambio de credenciales o particionado.
Prueba privada: /opt/steps-validation/community-payroll-disk-resize-20261028/
proof.json y resize.py, verificables con tools/community/summarize_payroll_api.py.
No repetir la operación ni interpretar esta autorización de infraestructura como
permiso para desplegar cambios de negocio en producción o refrescar QA-Cerro.
Ver COMMUNITY_SYS_REFERENCE.md para paquete F y alcance pendiente.

## Tickets 141 y 144 — 30-10-2026

La respuesta humana 9868 reabre T141 para imprimir el folio nativo en el título
“RECIBO DE RECEPCIÓN N° …”. Mismos destinos y controles de reception-report.

T144 (mensaje 9881, adjunto 3449) autoriza packing-company en Desarrollo, Cerro
y QA-Cerro: conservar la compañía nativa de las tarjas E/N según su OT, incluso
sin existencias. Completar únicamente compañías vacías de tarjas vinculadas;
rechazar contradicciones con stock u origen. Preservar ubicación, cantidades,
estados, IDs y entrenamiento. Mismo paquete, copias frescas, respaldo, bloqueo,
paridad y aislamiento. No crear existencias ni validar OT reales.

T143 (mensaje 9877 y adjunto 3448) autoriza payroll-attendance en Desarrollo,
SyS, Cerro y QA-Cerro. Implementa la alternativa b solicitada: eliminación
manual de asistencia validada si todas sus liquidaciones están en borrador,
sin pago, bloqueo histórico ni asiento publicado. Conservar licencias y otras
ausencias, reglas de acceso y liquidaciones confirmadas. No eliminar registros
reales ni cambiar contratos durante el despliegue. Probar corrección y cambio
de fecha en copia, mismo paquete y controles de publicación.

T142 (mensaje 9873, adjunto 3447) autoriza holding-purchase en Desarrollo, Cerro
y QA-Cerro: Entregar a incorpora operaciones de las sucursales de la misma
raíz legal incluidas en las compañías activas del comprador. Seleccionar antes
de agregar productos; pedido, líneas y recepción pertenecen nativamente a la
sucursal. Mostrar su dirección de entrega. No compartir documentos ni ampliar
permisos. Prueba de compra/recepción en copia, sin compras o movimientos reales
al publicar. Mismo paquete, respaldo, bloqueo y paridad Cerro/QA-Cerro.

T145 (mensaje 9885, adjunto 3450) autoriza export-branches en Desarrollo, Cerro
y QA-Cerro: consolidar guías y tarjas de sucursales de la misma raíz legal en
instructivos y Packing Lists, y mostrar compañía/sucursal en Consultar Tarjas.
Usar únicamente membresías de compañía ya autorizadas al usuario; mantener
propiedad de guías, tarjas, inventario y documentos contables. Las facturas
conservan frontera exacta por compañía. No crear movimientos reales al publicar,
no asignar empresas/perfiles y no refrescar datos. Mismo paquete en copias
frescas, publicación con respaldo, bloqueo y comprobación de paridad.

T146 (mensaje 9916, adjunto 3455) autoriza bpa-masters en Desarrollo, Cerro y
QA-Cerro: Productos BPA bajo Maestros, Configuraciones con los maestros
existentes de sustancias activas y aptitudes plaguicidas y plantillas Excel
para el importador nativo. Conservar IDs, relaciones, maestros y permisos.
No cargar datos ficticios en destinos reales. Copias frescas y mismo paquete,
respaldo, bloqueo, paridad y aislamiento sin refrescar datos de capacitación.


T168 (mensaje 10146, adjunto 3519) autoriza packing-material-rules en Desarrollo,
Cerro y QA-Cerro: E completa consume caja y pallet; E parcial solo caja.
Repaletizado incorpora consumo de pallet preparado, editable y atómico junto
al movimiento nativo de fruta, valoración y gasto con analítica de su OT.
El parámetro por empresa permite materiales sin stock por defecto, como solicita
el adjunto, exige costo positivo y no habilita déficit de fruta ni apropiación
de stock de terceros. No se validan operaciones reales al publicar ni se
reescriben aprobaciones existentes: deben reabrirse y prepararse con la nueva
regla. Copias frescas, mismo paquete, respaldo, bloqueo y paridad de destinos.


T169 (mensaje 10150, adjunto 3520 y confirmación del solicitante en este chat)
autoriza journal-branches en Desarrollo, Cerro y QA-Cerro: mantener disponibilidad
automática nativa de diarios de matriz en todas las sucursales y mostrarla en
formulario y lista. La columna solo calcula descendientes activos con membresía
del usuario existente; no cambia permisos, relaciones legales, diarios, cuentas,
asientos ni configuración fiscal. Probar asiento nativo de sucursal en diario
matriz y rechazo de compañía ajena exclusivamente en copia privada del destino.

T176 y la confirmación del solicitante en este chat autorizan una base nueva e
independiente ECOPLANTAS para demostración comercial. No trasladar la suscripción
de Desarrollo ni copiar su código, UUID, vencimiento, registros de clientes o
personalizaciones Studio. Usar la edición Enterprise nativa disponible, con su
registro propio. El alta comercial de una suscripción se gestiona por separado.
Preparar únicamente los módulos estándar de contactos, CRM, ventas, compras,
inventario y contabilidad chilena. Verificar primero los formularios y un ciclo
de borradores en una copia privada descartable; ningún documento se publica.
La instancia nueva usa usuario, base, puerto 8084, dominio HTTPS y addons privados
propios; impedir el acceso de su rol a las otras bases. No sustituye Desarrollo
como QA ni entra en el circuito de publicación de los productos. El procedimiento
versionado es tools/ops/provision_ecoplantas_demo.py y utiliza el bloqueo común.

La ampliación solicitada para el invernadero autoriza habilitar Fabricación,
Calidad, Mantenimiento y Proyectos exclusivamente en ECOPLANTAS. Reutilizar
sus módulos nativos, lotes, productos, ubicaciones, materiales y tareas.
Agregar ejemplos identificados como DEMO para la recepción de insumos, lote
de plantines, revisión visual, riego y mantenimiento. Conservar los registros
y las credenciales existentes, la licencia independiente y el bloqueo de correo.
Certificar la misma instalación y ejemplos en una copia privada fresca de
ECOPLANTAS antes de publicar con respaldo y bloqueo común. Completar la
recepción y fabricación de prueba únicamente en la copia; en la demo dejar
los documentos de ejemplo en borrador. Verificar el panel y los formularios
con el usuario de revisión existente. Ver `docs/DEMO_ECOPLANTAS_INVERNADERO.md`.

La revisión para la demo del martes autoriza `step_ecoplantas_greenhouse`
únicamente en ECOPLANTAS. Porta el layout agrícola de Steps a la portada y a
los formularios nativos, fija Invernadero como inicio del usuario de revisión y
agrega un despacho de ejemplo en borrador. Mantener el lote, recepción, labores
y maestros previos. Certificar en copia privada fresca la recepción, producción,
calidad, salida parcial por el mismo lote y saldo de inventario. Revisar el
navegador en escritorio y teléfono mediante vista previa privada. Publicar el
mismo paquete con respaldo, bloqueo compartido y comprobación de datos, permisos
y correo. Operación en `tools/ops/manage_ecoplantas_layout.py`.

El vivero ECOPLANTAS autoriza centros analíticos padres, reglas por labor y
carga manual del driver por centro hijo y semana. El catálogo comparte la
tabla existente de Aserradero. Validar su adopción conservando modelo, IDs y
permisos en copia privada. El reparto genera movimientos analíticos compensados
por semana, conserva otras dimensiones y deja los documentos contables
originales intactos. Exigir vista previa, permiso contable, reversa y control
de duplicados. Habilitar el grupo de analítica en el perfil contable de
revisión de la demo. Dejar el ejemplo calculado en borrador. Certificar copia fresca,
formularios, navegador, respaldo y bloqueo; publicar únicamente el módulo de
vivero y su catálogo en ECOPLANTAS. Aserradero conserva su versión instalada en
sus ambientes. Operación en `tools/ops/manage_ecoplantas_costs.py`.

La decisión posterior del usuario traslada la demo activa de ECOPLANTAS a la
empresa EcoPlantas que ya existe en Desarrollo (LAB_TAREAS). Respalda ambas
bases y conserva la anterior como fuente histórica. No reemplaza la base,
empresa, bodega, planes, usuarios, credenciales o suscripción de Desarrollo.
Importa los registros de ejemplo con relaciones nativas, reutiliza el perfil
interno existente y acota el tema a la empresa activa. Instala los módulos
faltantes mediante overlay privado, incluida la adopción del catálogo de
drivers de Aserradero sin pérdida de identidad. Valida los cargos, el reparto,
los borradores y el flujo de lote en una copia privada fresca de Desarrollo.
Operación en `tools/ops/move_ecoplantas_to_development.py`.
