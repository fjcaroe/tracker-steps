# Empresa adicional y cuentas de productos de Cerro El Plomo

El paquete conserva el campo `mrp.bom.x_studio_compaia`, su identificador
original 30516, la relación con `res.company` y los registros que lo usan.
El módulo de productos adopta las dos listas originales de cuentas de gastos
y de plantillas de producto con sus padres, columnas opcionales y permisos.
Sus dependencias declaradas son `mrp`, `account` y `hr_expense`.

En U42B, una restauración privada de Cerro con 161 módulos instalados y todos
registrados con licencia libre, el operador de fabricación 6 creó una lista
de materiales, asignó la empresa adicional, copió la lista y vació la empresa
adicional conservando la principal. El usuario público recibió una denegación
al intentar escribir. Tras revertir la prueba coincidieron las siete listas
originales, las reglas de acceso y las columnas de ambas vistas.

El orden de la restauración permitió adoptar el campo antes de crear la
guarda de campos. El cambio de manual a base fue la única diferencia entre
las 27.963 filas de campos. Se conservaron los 62.099 identificadores
anteriores y las 23 guardas originales, incluida la que rechazó volver a
manual. Las 21 vistas Studio ajenas a las dos listas mantuvieron las mismas
filas. Los recibos privados se conservan en el ensayo U42B como
`adopted-receipt.json` y `qualified-bom.json`. El ejecutor de la restauración
con ese orden se encuentra en el commit `245a9518` del ensayo integrado.
