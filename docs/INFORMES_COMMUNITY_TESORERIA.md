# Informes de Tesorería sobre Community

`step_treasury_community_reports` depende solo de Tesorería y su núcleo
contable Community. No consulta `account.report`, no usa SQL con privilegios
ni crea libros o maestros paralelos. El único modelo nuevo es un asistente
transitorio privado de cada usuario, con regla por empresas autorizadas.

## Contratos de las cinco alternativas

| Menú existente | Alternativa y conciliación |
| --- | --- |
| Cuentas corrientes | Apuntes publicados de cuentas por cobrar y pagar, resumen por ID de socio, saldo previo, movimiento y saldo final. El saldo final coincide con la suma del libro nativo al corte. |
| Cuentas por cobrar vencidas | Saldo firmado por documento al corte, vencimiento y bandas no vencido, 1–30, 31–60, 61–90, 91–120 y más de 120 días. |
| Cuentas por pagar vencidas | Mismo contrato para cuentas por pagar; créditos de proveedores permanecen negativos, sin ocultar notas de crédito ni saldos deudores. |
| Estado de flujo de efectivo | Efectivo realizado sobre cuentas nativas `asset_cash`, con apertura, detalle publicado, resumen por cuenta y cierre. Las transferencias internas netean al incluir ambos bancos. No incorpora todavía una taxonomía normativa de actividades operacionales, inversión y financiación; esa presentación requiere una definición adicional, no una clasificación automática por nombre. |
| Conciliación bancaria | Control del libro de efectivo, extractos con moneda y estado actual, partidas conciliables pendientes al corte y comparación de libro con saldo declarado del último extracto completo, a su propia fecha. Los documentos nativos quedan enlazados para revisar y conciliar; consultar el informe no publica ni concilia movimientos. |

Las fechas del mayor y efectivo limitan movimientos; su apertura incluye el
histórico anterior al inicio. La antigüedad usa solo la fecha de corte y
reconstruye conciliaciones parciales por las fechas contables de ambos extremos.
Una factura pagada después sigue abierta en una consulta anterior. No se usa
el residual actual como sustituto de un saldo histórico.

El indicador de conciliación de un extracto es su estado **actual**, rotulado
como tal; el modelo nativo no conserva un historial temporal de ese indicador.
Las partidas pendientes sí se reconstruyen al corte. Un filtro parcial por
socio no se compara con el saldo global de un extracto. No se comparan ni suman
monedas distintas. Los extractos incompletos a la fecha consultada no se usan
como puntos de comparación.

La moneda principal conserva el signo e importes del libro. Las columnas
operacionales muestran importes almacenados por moneda, sin reconvertir usando
tasas actuales. El residual operacional se valora proporcionalmente a la tasa
histórica del apunte; no representa diferencias de cambio realizadas. Las
monedas de documento y operacional se identifican en cada fila y no se suman
entre monedas. Pantalla, CSV y PDF usan el mismo dataset. El PDF horizontal es
autocontenido y no requiere recursos externos, manteniendo el aislamiento de QA.

## Identidad y permisos

La instalación adopta los cinco menús sin recrearlos. Conserva sus IDs, padres,
grupos, secuencias y estado activo. Solo modifica el destino de la acción y la
fecha de esa modificación. Conserva los XMLIDs anteriores como alias y añade
el namespace del módulo nuevo. Una acción personalizada desconocida bloquea
la conversión en lugar de reemplazarla silenciosamente.

Las cinco acciones globales de Enterprise y sus IDs permanecen intactos; otros
accesos a ellas no cambian. Los destinos nuevos son acciones propias de ventana,
con IDs estables a partir de su instalación. No se desinstala el puente anterior,
`account_reports` ni ningún módulo Enterprise. No se afirma conversión integral
de Cerro: quedan lotes, maestros, Nómina, DTE y otros dependientes.

Se requiere lectura contable nativa o administración contable, además de las
restricciones existentes de los menús. El perfil de Tesorería por sí solo no
otorga lectura de contabilidad. No se asignan grupos nuevos a usuarios. Las
consultas respetan ACL y reglas de los modelos nativos; no usan `sudo`.

## Evaluación OCA y alcance

Se revisó el [manifiesto oficial OCA Financial Reports 18.0](https://github.com/OCA/account-financial-reporting/blob/18.0/account_financial_report/__manifest__.py):
AGPL-3, dependencias `account`, `date_range` y `report_xlsx`; incluye mayor,
antigüedad, balance de comprobación y partidas abiertas. No enumera los controles
de banco y efectivo de este paquete. No se presumió equivalencia de su moneda
operacional con los campos históricos Steps. Para esta entrega se implementó
el conjunto acotado directamente sobre el libro nativo; OCA sigue siendo
candidato para ampliar estados financieros, con adaptación y pruebas propias.

## Ensayo y publicación

`validate_community_reports.py` instala con fuentes oficiales Community o restaura
una copia fresca de Cerro, Desarrollo o QA-Cerro. Conserva dump y filestore,
neutraliza correo/cron solo en la copia, compara tablas previas, IDs, permisos y
acciones globales; permite exclusivamente la redirección documentada de menús.
Comprueba formularios, las cinco rutas con un usuario contable existente sin
superusuario y los totales contra agregaciones independientes del libro nativo.
Las pruebas de fixtures se revierten. La copia QA exige permiso temporal por
socket a esa única base y lo retira al terminar; no amplía la red ni cambia claves.

`manage_community_reports.py` solo admite Desarrollo y QA-Cerro. Requiere el
mismo SHA256 por archivo probado en Community, Cerro y el destino; compara
configuración, fuentes, versiones y datos con el origen de la prueba. Detiene
el servicio bajo bloqueo, toma dump/configuración/filestore recuperables y usa
un overlay privado de los cinco módulos. Rechaza downgrade y cambios concurrentes.
No restaura datos automáticamente ante un fallo. Verifica registros, saldos,
formularios y flujo real antes de registrar la entrega. QA conserva sus ejercicios,
correo neutralizado, cron detenido y las reglas de aislamiento.
