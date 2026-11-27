# Descarga de liquidaciones de SyS

Dos operadores abrieron la ficha original y usaron su botón de impresión para cinco liquidaciones cerradas y una liquidación recién confirmada cada uno. En Community el botón abrió la misma acción de informe 1431 y el cliente descargó el PDF mediante la ruta estándar de Odoo Web. La prueba comparó el archivo descargado con el informe generado por la acción. El sistema nativo entrega el suyo mediante `/print/payslips`. Ambas rutas sirvieron a los operadores identificados en la prueba.

Las doce descargas quedaron en una página de 612 × 1008 puntos, con Lato normal y negrita. El ajuste de espaciado corrigió la paginación de la liquidación que antes ocupaba dos páginas en Community. La comparación conservó las 172 líneas de los diez recibos históricos y sus montos. Coincidieron los conceptos, días, líquidos y las líneas de las dos liquidaciones nuevas. Las transacciones de alta recibieron números de documento propios.

La cabecera muestra «Salario del contrato» con el valor vigente del contrato vinculado, igual que la referencia nativa. Se comprobó el importe impreso en las doce descargas. La lectura requiere acceso normal al contrato y al campo salario, dentro de la empresa de la liquidación. Las bases y líquidos reflejan las líneas guardadas del recibo. El ensayo verificó cuatro denegaciones de lectura entre una empresa ajena y el usuario público.

Se cotejaron los ocho PDF archivados byte por byte y los 2.708 archivos del respaldo. Las 1.141 tablas coincidieron antes y después de imprimir. Las dos altas contables de ensayo se revirtieron y avanzaron cinco contadores de la base privada.

El proveedor `step_sys_payslip_print` 18.0.1.0.0 se instaló y actualizó sobre la derivada U49E de .6.3. La copia quedó con 194 módulos y conservó el catálogo PostgreSQL. El TAR de cuatro piezas tiene SHA-256 `21e2a31caf6e6a82497bbf003af485e524121838782c0a8873156aa14d11fa08`. El índice del complemento privado tiene SHA-256 `b9cd49e92efb966a01b9051f4647b8de7ebe2bf067089782b4b999e73074741e` y referencia el respaldo comprobado de .6.3.

El respaldo privado de la derivada con impresión conserva 609.178 filas, 1.141 tablas y 861 contadores. Su índice tiene SHA-256 `a171f16a6254ecf4f6392823b8d536bc5e7d06e36d77f96a07662fd1a574ec32`. Se restauró en una base independiente y se abrieron diez descargas en cada uno de dos arranques de Odoo. El catálogo, las tablas, los contadores y los 2.708 archivos coincidieron después de cada arranque. `restore_local_sys_role_payslip.py` generó el recibo `53900262b5c92b1be968e643dd91bba7861d6bcad599b6c2ee4652ac890e5961`.

`tools/community/admit_sys_role_payslip_print.py` reconstruye ese archivo e instala la extensión en la copia aislada. `tools/community/probe_sys_role_payslip_pdf.py` comprueba el botón, la descarga y los permisos. `tools/community/verify_sys_role_payslip_pdf.py` coteja los PDF privados y el recibo de preservación. [Recuperación de SyS 18.0.1.6.3](COMMUNITY_SYS_ARRASTRE_NETOS.md)
