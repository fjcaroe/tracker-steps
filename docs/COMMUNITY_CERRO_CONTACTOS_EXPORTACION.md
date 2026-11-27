# Cerro El Plomo · contactos de exportación

El directorio conserva las 229 filas originales de contactos, los cuatro mercados y los cuatro permisos de esos mercados. En el respaldo hay 15 contactos marcados como recibidor y seis como recibidor genérico. Hay una referencia de contacto de notificación predeterminado y una de consignatario predeterminado con valor. Los datos, sus relaciones y los campos conservan sus identidades originales.

La extensión usa las declaraciones y validaciones de los proveedores libres de exportaciones, perfiles de recibidores y mercados. La vista 5192 conserva su identidad de Studio, su padre y su acción original. El código propio de las vistas de Cerro asocia el identificador del paquete al registro histórico existente.

## Prueba del operador

El conjunto restaurado de Cerro quedó en 187 módulos instalados, todos libres y sin transiciones pendientes. Se instaló y se volvió a actualizar el directorio después de Presupuestos y Fletes. Las 23 filas de Studio, los 62.030 identificadores protegidos, las 229 filas de contactos, los cuatro mercados y sus permisos conservaron su contenido. Se cotejaron completas las 32 filas de definición de campos de contacto, usuario y mercado.

El usuario 6 leyó en el cliente web los roles y vínculos de 225 contactos activos con todas sus empresas. Los mismos valores y registros se obtuvieron en nueve contextos del control nativo y de Community. Para las empresas 1, 2, 3, 4, 29, 30, 31 y 41 por separado pudo leer 214, 221, 213, 214, 222, 221, 223 y 221 contactos, respectivamente. Las lecturas de los cuatro mercados también coincidieron. La huella conjunta de estas pruebas fue `546fc023bd3c2c7782ffbfc76bb7587bfca5c25bb9c4f3e5a2bee8f5be685cce`.

Con las operaciones de guardado del cliente web, el usuario creó un contacto de notificación y le asignó ese contacto a un recibidor genérico con mercado. La aplicación activó el rol exportador. Ambas copias rechazaron un recibidor genérico sin mercado, un consignatario sin su rol y la lectura de mercados con el usuario público. Se revirtieron los registros de prueba. El recibo de la instalación y el alcance de la vista es `U43Z/qualified-export-contacts.json`, SHA-256 `e0e940c8e3d1292216c23bc6b1263e146fb05d8169eb11f4bd5b4628ade96865`. El recibo del cotejo nativo y Community es `U43Z/qualified-compared-export-contacts.json`, SHA-256 `51be7a3ca58a525de8ae3293d25d9a4c5d61ac26af1222d65502f3d87e186f71`.

## Alcance de la lista de contactos

En el combinado de Fletes y Presupuestos, la incorporación del directorio añade una lectura de Studio idéntica al control. El usuario operativo alcanza 20 de las 23 rutas, obtiene 19 lecturas coincidentes de los registros y campos de Studio y conserva las 15 lecturas completas del cliente web. La lista genérica de contactos incluye otra herencia, la vista 3925 de seguimiento de cobros. En el control nativo ese proveedor tiene licencia OEEL-1. La cohorte Community lo registra como desinstalado.

La vista de cobros solicita el responsable, el tipo de recordatorio, el estado, la fecha de la próxima acción, la etapa de seguimiento, el saldo a pagar y el saldo vencido. Las siete columnas aparecen como opcionales en la definición nativa. El cotejo de la fila completa las incluye, por lo que la vista 5192 sigue fuera de las 15 filas completas acreditadas.

## Paquete

El archivo del proveedor contiene cinco archivos y tiene SHA-256 `576fba5fa799deb6fa6e60c770c00d63ba2e4b1fe39ea591ab89734ec6402240`. Se reconstruye desde la raíz del repositorio con `tools/community/build_cerro_verified_172.py --profile contacts --source . --output <archivo-nuevo>`. La extensión corresponde al perfil Community restaurado de Cerro con sus maestros, referencias y permisos históricos.
