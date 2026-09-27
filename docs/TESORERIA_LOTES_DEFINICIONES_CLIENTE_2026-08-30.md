# Pagos por lotes — información que necesitamos del cliente

Módulo 2.3.1 Tesorería · 30 de agosto de 2026 · Steps Consulting

## 1. Para qué es este documento

El requerimiento «2.3.1 Módulo Tesorería, pagos por lotes» pide tres cosas.
Una ya está construida; las otras dos no se pueden construir sin información
que sólo tiene el cliente o su banco.

| # | Requerimiento | Estado | Qué falta |
|---|---|---|---|
| 1 | TXT de nómina para subir al banco (Estado, Chile, Santander, Itaú, Scotiabank, BICE) | Pendiente | La especificación del archivo de cada banco (sección 3) |
| 2 | Integración directa con la API del banco | Pendiente | Banco piloto, credenciales y ambiente de pruebas (sección 5) |
| 3 | Crear lotes desde el flujo de caja, con selección de los documentos a pagar | **Implementado** | Confirmar las reglas de operación (sección 6) |

Odoo estándar trae los formatos SEPA (Europa), NACHA (EE. UU.) e ISO 20022.
**No trae ningún formato de banco chileno.** Cada banco en Chile define su
propio archivo de nómina, y ese diseño no es público: se entrega al cliente
junto con el convenio de pago que firma con el banco. Por eso lo pedimos.

Mientras no exista esa especificación aprobada, el sistema entrega sólo un
archivo de revisión interna, marcado «NO CARGABLE AL BANCO», para control
humano. No lo presentamos nunca como archivo bancario, para no arriesgar una
carga rechazada o —peor— mal interpretada por el banco.

## 2. Qué ya puede hacer el sistema hoy

- Agrupar pagos de proveedores o de clientes en un lote (funcionalidad
  estándar de Odoo).
- **Generar el lote desde la Planificación / Flujo de caja de Tesorería**: el
  proceso propone los egresos vencidos y los de la semana 1 del horizonte,
  permite marcar y desmarcar qué documentos se pagan, crea un pago por
  factura y los agrupa en un único lote saliente. El lote queda anotado en la
  línea del flujo, de modo que un documento no se paga dos veces.
- Conciliar el lote contra el movimiento único del extracto bancario.
- Descargar un CSV de revisión interna del lote (no bancario).

## 3. Especificación del archivo por banco

**Complete una ficha por cada banco con el que la empresa paga.** Si un banco
tiene más de un convenio o producto (por ejemplo, pago a proveedores y pago de
remuneraciones), complete una ficha por cada uno.

Lo ideal es que el cliente nos entregue el **manual del convenio** y un
**archivo de ejemplo real aprobado por el banco**: con esos dos documentos la
ficha se completa sola y el riesgo de error baja a casi cero.

### Ficha de formato bancario

| Dato | Respuesta |
|---|---|
| Banco | |
| Nombre del convenio o producto | |
| Versión del formato y fecha de vigencia | |
| ¿Adjunta el manual del banco? (sí/no, nombre del archivo) | |
| ¿Adjunta un archivo de ejemplo aprobado? (sí/no, nombre del archivo) | |
| Tipo de archivo (largo fijo / delimitado / Excel / otro) | |
| Si es delimitado: separador de campos | |
| Codificación (UTF-8, ISO-8859-1, ASCII) | |
| Fin de línea (Windows CRLF / Unix LF) | |
| ¿Lleva registro de cabecera? ¿Qué contiene? | |
| ¿Lleva registro de tráiler o totales? ¿Qué contiene? | |
| Formato del nombre del archivo (ejemplo real) | |
| Formato de fecha dentro del archivo (AAAAMMDD, DDMMAAAA…) | |
| Formato de montos (¿con decimales?, ¿con separador?, ¿centavos incluidos?) | |
| Moneda admitida (¿sólo CLP? ¿USD? ¿UF?) | |
| Máximo de registros por archivo | |
| Máximo de monto por registro y por archivo | |
| Identificación de la empresa en el archivo (RUT, número de convenio, código de cliente) | |
| ¿Cómo se carga el archivo? (portal web, host to host, SFTP, otro) | |
| Horario de corte para que el pago se curse el mismo día | |
| ¿El banco devuelve un archivo de respuesta o de rechazos? ¿En qué formato? | |
| Contacto del ejecutivo del banco (nombre, correo, teléfono) | |

### Campos de cada línea de pago

Enumere los campos que exige el banco por cada beneficiario, en el orden del
archivo. Si nos entrega el manual del convenio, esta tabla la completamos
nosotros y sólo pedimos que la revisen.

| # | Campo | Posición o columna | Largo | Tipo | Obligatorio | Regla o valor fijo |
|---|---|---|---|---|---|---|
| 1 | | | | | | |
| 2 | | | | | | |
| 3 | | | | | | |
| 4 | | | | | | |
| 5 | | | | | | |

## 4. Datos de los beneficiarios

El archivo de nómina identifica a cada proveedor con datos que hoy pueden no
estar cargados en Odoo. Necesitamos saber cómo se van a poblar y quién
responde por ellos.

| Pregunta | Respuesta |
|---|---|
| ¿Qué identifica al beneficiario en el archivo? (RUT, número de cuenta, ambos) | |
| ¿El banco exige el tipo de cuenta? (corriente, vista, ahorro) ¿Con qué código? | |
| ¿El banco exige el código del banco de destino? ¿Con qué tabla de códigos? | |
| ¿Se envía correo de aviso al proveedor? ¿El banco lo manda o lo mandamos nosotros? | |
| ¿Dónde están hoy esos datos? (Odoo, planilla, sistema anterior) | |
| ¿Quién los carga y quién los valida antes del primer pago? | |
| ¿Se acepta pagar a una cuenta de un tercero distinto del proveedor? | |

> Odoo marca toda cuenta bancaria nueva como «no confiable» hasta que alguien
> la valida a mano. Es una defensa contra el fraude de cambio de cuenta
> («estafa de la factura»). Confirmar quién tendrá ese permiso es parte de la
> definición.

## 5. Integración directa con la API del banco (requerimiento 2)

Subir la nómina por API es un proyecto aparte del archivo TXT: exige un
convenio distinto con el banco, credenciales y un ambiente de pruebas.

| Pregunta | Respuesta |
|---|---|
| ¿Con qué banco se parte? | |
| ¿La empresa ya tiene contratado el servicio de API / host to host? | |
| ¿Qué tipo de credencial entrega el banco? (certificado digital, API key, mTLS, OAuth) | |
| ¿Existe ambiente de pruebas del banco? ¿Cómo se solicita? | |
| ¿Quién autoriza y firma la nómina en el banco? ¿Hay doble aprobación? | |
| ¿La autorización se hace desde Odoo o desde el portal del banco? | |
| ¿El banco expone consulta de estado del pago? ¿Y de rechazos? | |
| ¿Con qué IP fija sale la conexión? (el banco suele exigir lista blanca) | |
| Fecha objetivo para tener el ambiente de pruebas disponible | |

## 6. Reglas de operación del lote (requerimiento 3, ya implementado)

Estas preguntas no bloquean la construcción: el proceso ya funciona con las
respuestas por omisión que indicamos. Confirmarlas o corregirlas.

| Pregunta | Por omisión hoy | Respuesta |
|---|---|---|
| ¿Qué se propone pagar? | Egresos vencidos + semana 1 del horizonte | |
| ¿Quién puede armar un lote? | Perfil Tesorería: operación | |
| ¿Quién autoriza el lote antes de enviarlo al banco? | Nadie: el lote queda en borrador hasta que alguien lo valida en Contabilidad | |
| ¿Se permite pagar una cuota parcial de una factura? | Sí, se paga el monto de la cuota seleccionada y la factura queda con saldo | |
| ¿Se pueden pagar órdenes de compra o proformas sin factura? | No: el banco paga documentos, y sólo una factura publicada genera el asiento a pagar | |
| ¿Hay un tope de monto por lote que exija otra aprobación? | No hay tope | |
| ¿Qué pasa con facturas en moneda extranjera? | Se pagan en la moneda del documento | |
| ¿Se descuentan retenciones o notas de crédito antes de pagar? | Se paga el saldo pendiente, que ya considera las notas de crédito aplicadas | |

## 7. Ambientes y validación

La implementación se despliega en los tres ambientes autorizados. Necesitamos
saber quién valida en cada uno.

| Ambiente | Uso | Quién valida | Fecha comprometida |
|---|---|---|---|
| Desarrollo | Construcción y pruebas internas | Steps Consulting | |
| Demo | Validación funcional del cliente | | |
| Demo-SyS | Validación de la empresa SyS | | |

## 8. Cómo devolvernos esto

1. Complete las tablas de las secciones 3 a 7.
2. Adjunte, por cada banco, el manual del convenio y un archivo de ejemplo
   aprobado por el banco.
3. Si un banco todavía no tiene convenio firmado, indíquelo: ese banco queda
   fuera del alcance hasta que exista.

4. No hace falta esperar a tener los seis bancos: con la ficha y el archivo de
   ejemplo de uno solo podemos construir y probar ese adaptador por separado.

> Versión entregable para el cliente:
> `docs/Tesoreria_Pagos_por_Lotes_Formulario_Cliente_2026-08-30.docx`
