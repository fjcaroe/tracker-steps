# Accesos originales de Tesorería sobre Community

`18.0.2.0.0` conserva el namespace original y conecta sus cinco menús al
proveedor real `step_treasury_community_reports`. El bridge deja de requerir
`account_reports` y `step_accounting_multicurrency`. No define sustitutos de
`account.report`, no altera ni elimina acciones globales Enterprise y no retira
módulos instalados. La actualización debe incluir los tres addons financieros.

Los cinco menús conservan su fila, XML IDs, padres, grupos, secuencia y estado.
Sólo se admite cambiar una acción que sea exactamente la antigua acción conocida
o la acción Community correspondiente. Un destino personalizado se rechaza; el
savepoint impide una conversión parcial. Las filas XML ID existentes conservan
también `noupdate=False` o `True` exactamente. Los aliases nuevos apuntan al
mismo menú, sin crear tablas de negocio ni maestros.

El núcleo Community `step_account_treasury` valida únicamente esos cinco nombres,
el modelo `ir.ui.menu`, la existencia y la coincidencia entre propietarios; los
registra mediante `_load_xmlid`. Su integración estrecha con `_process_end`
conserva los aliases durante actualizaciones posteriores sin cambiar flags. La
desinstalación nativa conserva los menús que tienen un propietario independiente;
no se sustituye el mecanismo de uninstall ni se protege metadata ajena.

El flujo abre los formularios reales y consulta los apuntes nativos publicados:
control bancario, cuentas corrientes, efectivo realizado, antigüedad por cobrar y
por pagar. CSV, pantalla y PDF utilizan el mismo dataset. Consulta e impresión
validan al UID real aunque el despachador llegue con `sudo`; no se conceden roles
contables por instalar el bridge. Un actor no puede usar el transient de otro.
El PDF directo vuelve a consultar con las reglas actuales antes de presentar
el resultado. No se postean pagos, concilian partidas ni alteran saldos.

El control bancario sigue siendo un informe: la conciliación operativa, el motor
integral de lotes y los handlers multimoneda `account.report` siguen pendientes.
Esta extracción no acredita conversión integral ni resuelve el vencimiento.

Pruebas del bridge: dos casos de launchers, tres de identidad/ciclo/atomicidad y
dos de flujo por actor, incluidos los cinco formularios, CSV y PDF real. Deben
ejecutarse con los casos existentes de Tesorería y del proveedor de informes en
Community oficial y copia nativa fresca del mismo paquete. El coordinador realiza
esas pruebas; sintaxis o commit no equivalen a aceptación.
