# Liquidación PDF Community desde líneas almacenadas

Aceptación vigente: [COMMUNITY_CONFIGURACION_NOMINA.md](COMMUNITY_CONFIGURACION_NOMINA.md).
D valida HTML, dos PDF reales y cuatro páginas revisadas; también la guarda
contable descrita como propuesta en esta auditoría inicial. La acción 462 y la
configuración original todavía no están adoptadas. El contenido inferior
conserva el contrato y las propuestas del bloque inicial.

Bloque preparado desde `db398fba`, sin cambio de motor, importación de maestros,
publicación ni recálculo de originales. La aceptación del paquete y su PDF real
corresponde al coordinador; esta hoja no la presume.

## Proveedor y representación

Se reutilizan la acción `payroll.action_report_payslip`, la plantilla LGPL-3
de OCA Payroll 18.0.1.4.0 y su extensión Simple Digital AGPL-3, fuente fijada
por `simpledigital_runtime_source.json`. No se lee ni copia QWeb OEEL.
El renderer real conserva el nombre Community
`step_simpledigital_oca_base.report_payslip`. No se crea un renderer ficticio
llamado `hr_payroll.report_payslip_lang` ni un alias que lo finja.

El builder transforma expresiones concretas del archivo AGPL fijado, conservando
autoría, licencia y procedencia. Las cifras vienen de las líneas almacenadas,
tras admitir con el actor normal las cabeceras, todas las líneas/días de sus
relaciones inversas, compañía y acceso a cada campo. No se acepta un subconjunto
oculto. La lectura SQL acotada conserva NULL físicos; no evalúa reglas, salarios
actuales, `paid_amount`, `net_wage` ni horas extra calculadas al imprimir.

El payload sólo obtiene metadata de presentación estrictamente enlazada a los
documentos ya autorizados. El empleado conserva sus ACL: imprimir lo propio no
le concede acceso global a estructuras, categorías, fórmulas ni salarios ajenos.
No hay `sudo` de importes ni concesiones ACL nuevas. Las estructuras archivadas
y sus liquidaciones cerradas se pueden imprimir sin invocar guardas de cálculo.
El entrypoint elimina explícitamente `env.su` conservando el UID del entorno;
no acepta UID/autoridad de `data` o del contexto. También se prueba una llamada
interna con `.with_user(empleado).sudo()`: sólo su liquidación sigue accesible.
La metadata G no tiene campo `report_sudo` en `ir.actions.report`; esa ausencia
no sustituye la guarda, porque Odoo resuelve metadata de acciones con elevación
y un caller interno puede entregar un entorno elevado.
Los grupos de campo de título, bandera BASIC y código de categoría también se
comprueban antes de la proyección SQL, sin conceder ACL de modelo de configuración.

NULL se imprime como importe ausente; cero y negativos conservan su valor. NET
se toma de las líneas de código NET: varias líneas de la misma regla original
se suman; reglas distintas o una identidad ausente se rechazan. No se elige la
primera ni se convierte ausencia de NET en cero. No se asignan importes al leer.
No existe una instantánea certificada de las horas extra no pactadas: se omite
esa sección calculada en lugar de usar asistencia o contratos actuales.

`hide_basic_on_pdf` oculta únicamente la fila BASIC, sin alterar NET ni los
subtotales almacenados. `payslip_name` es un título literal, con escape HTML y
sin evaluación. El nombre y correlativo del documento original se conservan.
Estos campos eran NULL en las cuatro estructuras del origen; no se afirma una
equivalencia nativa de modalidades no observadas.

La clasificación de columnas usa el código actual de la categoría enlazada:
no existe una instantánea histórica de ese código. No acredita clasificación
legal histórica ni una liquidación completa. Los conceptos imprimibles que no
entran en las columnas conocidas aparecen en una tabla adicional, conservando
sus importes. NET no se deriva de esa clasificación ni de salarios actuales.

## Identidad del reporte 462

La referencia nativa G conserva la acción original 462 y el XML ID
`hr_payroll.action_report_payslip`: `hr.payslip`, `qweb-pdf`, binding `list,form`,
sin grupos propios y sin reutilización de adjuntos. Su renderer sigue siendo
Enterprise en esa referencia. La acción OCA Community real tiene su identidad
propia; en G es 515. La acción 462 del CE limpio es una ventana ajena, «All
Allocations». Sobrescribirla sería pérdida de identidad ajena.

`tools/community/payslip_report_adoption_preflight.py` exporta sólo metadata,
referencias y colisiones, en transacción de sólo lectura y sin arquitectura
QWeb. Rechaza como equivalencia un alias que retargetee 462 a otra acción.
El espacio de IDs deberá provenir de una copia nativa integral admitida o de
una reserva previamente comprobada; no se borran acciones del CE limpio.
La adopción fría debe conservar el registro/ID original, filas de XML IDs,
traducciones, binding y los cuatro vínculos de estructuras, y cambiar su
renderer explícitamente al proveedor Community probado. Sigue pendiente.

## Diario: auditoría, sin activación nueva

OCA `payroll_account` 18.0.1.0.6, LGPL-3, define `hr.payslip.journal_id` como
related almacenado de `contract_id.journal_id`. No consulta el JSON por empresa
de la estructura original. Su confirmación llama primero al motor base, que
puede recalcular/cerrar, y después crea y publica el asiento con las cuentas
del contexto de compañía del recordset. Eso no cierra por sí solo la ruta
multicompañía original.

Propuesta pendiente de pruebas: guarda `operation='account'` antes de cualquier
mutación, savepoint completo y contexto de cada compañía de la liquidación.
Una propiedad estructural poblada debe resolver su clave exacta de compañía a
un diario real compatible; no se usa el primer diario ni un default. El fallback
al contrato sólo sería admisible ante NULL físico de la propiedad original y
un diario del contrato validado en esa compañía. Deben conservarse todos los
objetos JSON, NULL y valores históricos de `journal_id` de liquidaciones cerradas.
No se ha activado esa selección ni flags de contabilidad aún no certificados.

## Comprobación prevista

Ocho casos transaccionales prueban HTML real, archivo/cierre, importes NULL/cero/
negativos, nombre literal, ocultación BASIC, NET repetido/ambiguo, empleado propio,
ajeno, hijos ocultos, field ACL e identidad de la acción. Un HttpCase imprime dos
PDF reales por la ruta autenticada y wkhtmltopdf: estructura activa/BASIC visible
y archivada/BASIC oculto. Sirve únicamente assets del runtime privado por loopback,
sin sustituir el PDF o el generador; guarda PDF y hashes fuera del checkout.
Los registros originales y correlativos no se consumen: los fixtures usan sus
maestros privados y un número explícito. El PDF debe revisarse visualmente antes
de declarar esta puerta aceptada. No sustituye la conversión de identidad ni
la certificación de 71 reglas, Previred/libro o la puerta integral cero Enterprise.
La verificación offline del PDF usa PyMuPDF local mediante
`tools/community/verify_stored_payslip_pdf.py`: PyPDF2 1.26 del servidor devuelve
texto vacío para estos PDFs wkhtml. No se instalan dependencias en el servidor
ni se cambia Python de producción. El helper comprueba los hashes del export,
nombre/referencia, conceptos y BASIC en el PDF real, valores 0/-25/75 y las
filas cuando su geometría es verificable; renderiza todas las páginas a PNG
fuera del checkout y emite una prueba separada. Sigue faltando la revisión
visual humana/agente de esas páginas para aceptar la presentación.
