# Diagnóstico SII — Karo Consultorías

**Actualización a las 12:58 de Santiago:** se confirmó la carga del CAF nuevo
11–18 y se corrigió el entorno Python del servicio. La autenticación y una
consulta al SII se validaron correctamente. FAC 000011 sigue pendiente de envío,
sin modificaciones ni reenvíos durante las pruebas. Ver seguimiento al final.

Revisión: 31 de agosto de 2026, aproximadamente 11:50–12:05 hora de Santiago.

## Resultado

La integración no se puede declarar reparada. Se confirmaron tres bloqueos diferentes:

1. La factura FAC 000010 fue recibida por el SII el 20 de agosto y posteriormente rechazada por CAF vencido.
2. El CAF cargado para factura electrónica solo autoriza los folios 1–10. No existe un CAF que permita emitir el folio 11.
3. Durante esta revisión, el servicio de semilla del SII respondió HTTP 503 desde el servidor. Por ello no se logró verificar la autenticación actual ni consultar nuevamente el estado remoto del envío.

Adicionalmente, el buzón entrante denominado DTE presenta errores de credenciales IMAP.

## Instancia verificada

- IP y puerto de la foto: `35.222.25.110:8069`.
- Servidor SSH: `odoo-new`.
- Servicio: `odoo18.service`, activo antes y después del diagnóstico.
- Base: `karo_consultorias`.
- Configuración: `/etc/odoo18.conf`.
- Intérprete del servicio: `/opt/odoo18/venv/bin/python`, Python 3.10.
- Proveedor DTE configurado: `SII` (producción).
- Módulo `l10n_cl_edi`: instalado, versión `18.0.1.2`.

## Evidencias

### Factura de la foto

Registro `account.move` 61, `FAC 000010`, contabilizada, estado DTE `rejected`.

| Fecha UTC | Evidencia en el historial |
|---|---|
| 18 de agosto | Error al importar `Mapping`, seguido de errores de semilla/token y «No autenticado». |
| 19 de agosto | «No autenticado». |
| 20 de agosto, 22:00:12 | «Subida exitosa». Track ID `12372297812`. |
| 20 de agosto, 22:04:17 | Respuesta entrante: envío procesado, DTE rechazado; código `CAF-3-517`, CAF vencido. La firma del DTE es del 12 de agosto y el CAF del 2 de febrero. |
| 20 de agosto, 22:43:40 | Consulta registrada: `EPR`, envío procesado. Esto no equivale a aceptación del documento. |

La evidencia de rechazo procede del historial persistido de Odoo, no de una consulta remota exitosa hoy.

### Folios

| Tipo de documento | CAF ID | Fecha de autorización | Rango | Estado registrado |
|---|---:|---|---|---|
| 33 — Factura electrónica | 4 | 2026-02-02 | 1–10 | En uso |
| 56 — Nota de débito electrónica | 2 | 2026-02-02 | 1–4 | En uso |
| 61 — Nota de crédito electrónica | 3 | 2026-02-02 | 1–4 | En uso |

Aunque Odoo conserva el estado «En uso», las fechas requieren renovación/revisión de vigencia antes de emitir. El SII informa una vigencia de seis meses para los CAF autorizados desde el 1 de julio de 2018: [pregunta frecuente oficial](https://www.sii.cl/preguntas_frecuentes/factura_electronica/001_003_6968.htm).

El registro del servidor del 31 de agosto a las 15:02:18 UTC muestra un intento de contabilización bloqueado porque no hay CAF para el folio 11. Existe una nueva factura en borrador, registro 66; no fue modificada durante esta revisión.

### Certificado y autenticación

- Certificado activo seleccionado por Odoo: ID 2, compartido con los usuarios de la compañía, con clave privada presente.
- Vigencia registrada: 3 de julio de 2025 a 3 de julio de 2028.
- Se cargó el mismo entorno Python que usa producción: Zeep 4.1.0 y requests-toolbelt 1.0.0.
- No se reprodujo el error `cannot import name 'Mapping'`. La rama Python 3 de requests-toolbelt importa desde `collections.abc`.
- La carga WSDL de `https://palena.sii.cl/DTEWS/CrSeed.jws?WSDL` funciona.
- La operación SOAP `getSeed` devolvió HTTP 503 en una prueba inicial y en tres reintentos posteriores. La respuesta era HTML de servicio no disponible, no XML SOAP.
- No se obtuvo semilla/token. La vigencia local del certificado no demuestra que el SII lo acepte actualmente.
- El 503 fue observado desde esta instancia; no se ha demostrado una caída general del SII ni un problema permanente.

### Recepción de correo

El servicio de consulta IMAP del buzón `DTE` registra `Invalid credentials (Failure)`. Otro buzón, `Contacto`, logró consultar correo en el mismo ciclo. No se imprimieron ni modificaron contraseñas, tokens o claves.

## Acciones pendientes para resolver

1. Obtener del responsable autorizado un CAF XML vigente para factura electrónica, de esta empresa y ambiente productivo. Validar RUT, tipo 33, fecha y rango antes de cargarlo. El rango debe cubrir la numeración que se vaya a utilizar; no se debe forzar un número fuera del rango autorizado.
2. Revisar por separado la regularización de FAC 000010 con el responsable tributario y el procedimiento aplicable en el SII. Un CAF para folios posteriores no autoriza por sí mismo el folio 10. No alterar fechas, folios ni XML firmado para ocultar el vencimiento.
3. Repetir semilla, token y consulta del Track ID cuando el servicio responda. Verificar el resultado antes de cualquier reenvío para evitar duplicidades.
4. Reautorizar el buzón DTE en Odoo con su titular mediante el mecanismo de autenticación del proveedor. No compartir contraseñas por chat.
5. Revisar también los CAF de notas de crédito y débito antes de usarlos.

Referencia de configuración: [localización chilena de Odoo 18](https://www.odoo.com/documentation/18.0/es_419/applications/finance/fiscal_localizations/chile.html).

## Alcance y seguridad

Solo se realizaron lecturas de configuración, código, registros y datos específicos, y solicitudes de semilla al SII. La prueba Odoo se ejecutó con transacción de solo lectura y `rollback` final. No se enviaron facturas, correos, aceptaciones, reclamos ni anulaciones. No se modificaron datos, certificados, CAF, código del servidor, tareas programadas ni servicios. No hubo reinicios ni despliegues. Los ambientes Demo y Desarrollo no se modificaron.

El script local `tmp/sii_diagnostic_20260831.py` permite reproducir las consultas sin imprimir material criptográfico ni persistir cambios. Si el servicio vuelve a responder, está preparado para solicitar un token y consultar el envío existente, sin transmitir un DTE.

## Seguimiento: CAF actualizado y corrección aplicada

### CAF y factura 11

El usuario cargó a las 15:47 UTC el CAF ID 5, tipo 33, emitido el 31 de agosto
de 2026, rango 11–18. Se comprobó que corresponde al RUT de la compañía. La
FAC 000011 (registro 66) quedó contabilizada y su XML firmado contiene el
folio 11 y el CAF nuevo, fechado el 31 de agosto. El bloqueo por falta de CAF
quedó resuelto por esa carga.

El intento de envío posterior, a las 15:47:59 UTC, volvió a registrar
`cannot import name 'Mapping' from 'collections'`, seguido de fallos de semilla,
token y «No autenticado». Esto demostró que el error Python no era solamente
histórico: la primera prueba se había hecho con el intérprete configurado en
systemd, pero el proceso activo había perdido ese entorno.

### Causa reproducida

La unidad systemd inicia `/opt/odoo18/venv/bin/python`, pero Odoo, en
`odoo/service/server.py::_reexec`, vuelve a ejecutarse usando `argv[0]=python`.
El `PATH` del servicio no incluía el entorno virtual. Se reprodujo aisladamente
ese mecanismo y Python pasó a `/usr/bin/python`, cargando una versión antigua
de requests-toolbelt desde `/usr/lib/python3/dist-packages` que falla con
Python 3.10. El proceso activo anterior tenía precisamente esa línea de comando
y ese `PATH`.

Con `/opt/odoo18/venv/bin` al inicio de `PATH`, la misma prueba conservó
`sys.prefix=/opt/odoo18/venv` y la importación funcionó. El papel de PATH en la
selección del entorno está documentado en la [guía oficial de entornos
virtuales de Python](https://packaging.python.org/en/latest/guides/installing-using-pip-and-virtual-environments/).

### Cambio desplegado

Se añadió exclusivamente:

`/etc/systemd/system/odoo18.service.d/20-python-venv-path.conf`

```ini
[Service]
# Odoo _reexec uses argv[0]=python; preserve the venv across internal restarts.
Environment="PATH=/opt/odoo18/venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/snap/bin"
```

Se respaldaron la unidad, la configuración de Odoo y la unidad efectiva previa
en `/opt/steps_backups/karo-sii-python-path-20260831T155625Z`, con directorio
de acceso exclusivo de root (0700). Se recargó systemd y reinició únicamente
`odoo18.service`, a las 15:56:31 UTC. No se actualizaron paquetes, addons ni
datos contables, y no se modificó el código compartido con otros ambientes.

### Validación final

- Proceso nuevo: PID 1490096, intérprete y bibliotecas del entorno virtual.
- Página de acceso de Karo: HTTP 200; registro cargado y servicio activo.
- Demo, Desarrollo y Demo-SyS continuaban activos y no fueron reiniciados.
- Prueba aislada de reinicio interno: falla reproducida antes, importación
  correcta con el nuevo PATH.
- Prueba con los métodos reales de Odoo `_get_seed_ws`, `_get_token_ws` y
  `_get_send_status_ws`: semilla obtenida, token aceptado con estado `00`,
  consulta de envío completada.
- Consulta del Track ID de FAC 000010: un documento rechazado y cero aceptados,
  coincidente con el rechazo previo. No se modificó su estado.
- FAC 000011: `posted`, DTE `not_sent`, sin Track ID, al finalizar la prueba.
- Todas las pruebas de datos terminaron con `rollback`. No se transmitieron
  DTEs, anulaciones, aceptaciones ni correos.

El SII respondió 503 en varios intentos y luego respondió correctamente con
el cliente estándar y sus reintentos. Una respuesta exitosa durante una prueba
de cabeceras no demostró que User-Agent fuera la causa: Zeep sobrescribe esa
cabecera al crear su transporte. Por tanto **no se cambió el cliente HTTP ni
el User-Agent**. La solución aplicada es únicamente la del entorno Python.

### Pendientes operativos

Se puede reintentar el envío de la FAC 000011 existente y comprobar su resultado
en el SII. La prueba confirma autenticación y consulta, no aceptación de una
factura que no se envió durante el diagnóstico. No crear una factura adicional
para sustituirla: se observó también una FAC 000012, que debe revisar el
responsable antes de enviar si corresponde a la misma operación.

El rechazo por CAF vencido de FAC 000010 y las credenciales del buzón DTE
siguen siendo asuntos separados, no resueltos por este cambio.
