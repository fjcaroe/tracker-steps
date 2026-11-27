# SyS · Factura y nota de crédito en color

El 27 de noviembre de 2026 se restauró en la estación una copia independiente de la entrega FG de Nómina, Finanzas y Documentos. El complemento `step_report_print_colors` 18.0.1.0.0 utiliza dos variables del paquete de impresión de Odoo Community. Se instaló el mismo TAR de tres archivos aprobado para Steps, SHA-256 `db1f4c20809563d81e759b2d03c76b1ed57f547d02e4b320eca7901f4cc19dc9`. El código del complemento está en el repositorio. Los PDF privados y los datos de cliente están en la custodia de la estación.

Los dos operadores originales imprimieron cada uno una factura contabilizada y una nota de crédito por la acción `account.account_invoices`. El texto HTML y PDF completo, las referencias originales, los permisos de cada operador, los 141 tramos de texto y los 140 trazados coincidieron con la referencia nativa. La geometría, la tipografía y el color coincidieron en las cuatro páginas. También coincidió cada píxel RGB en dos renderizaciones independientes por resolución.

| Comparación con la referencia nativa | Factura A | Nota A | Factura B | Nota B |
| --- | ---: | ---: | ---: | ---: |
| Píxeles distintos del control FG anterior, gris a 72 ppp | 8.567 | 13.746 | 8.589 | 13.746 |
| Píxeles distintos con el complemento, RGB a 96 ppp | 0 | 0 | 0 | 0 |
| Píxeles distintos con el complemento, RGB a 144 ppp | 0 | 0 | 0 | 0 |

Las cuatro páginas del control anterior también difirieron en RGB a 96 y 144 ppp. Los tonos nativos de los tramos afectados eran `#111827` y `#5f636f`. El comparador coteja medidas y píxeles de los originales, sin extraer sus hojas de estilo. El renderizador wkhtmltopdf 0.12.6 con Qt parcheado y Ghostscript 9.50 tienen las mismas huellas que en la aplicación nativa. El recibo del nuevo PDF es `ecfa49faa076a7e1c6861c7c47d66b84592102fe9da673a56d88c8e8f0aaef44`, el del cotejo independiente es `1426b8f44f29da25094e469cef43dc97518564dd4d1647a9ad4ba8b70a987cbb`. [Comparador](../tools/community/compare_sys_fiscal_print_colors.py)

## Datos de la restauración

La copia arrancó con los 192 proveedores, las 609.133 filas, las 1.141 tablas y las 861 secuencias de FG. Se comprobaron 22.258 archivos de código y 2.702 objetos o marcas físicas. PostgreSQL conservó las reglas de ordenación y clasificación de caracteres así como los permisos del rol secundario. En la estación ese rol no admite conexiones. La instalación del proveedor 193 conservó todas las columnas, restricciones, vistas, índices y propietarios del catálogo inicial, con huella `a2535d3213a101a03297564d282b0aa2a2f6940f2fbc5073a2b707c3797b2e4d`. Las 3.184 columnas obligatorias se protegieron durante la inicialización. Las 21 columnas históricas de SyS se comprobaron además por identificador, propietario y tipo.

Se cotejaron todas las tablas. Los únicos cambios quedaron en seis tablas técnicas. El instalador añadió una fila de módulo, una dependencia, un alias y una solicitud de tarea. Actualizó sólo la fecha de escritura en 76 fichas de módulo y una vista. Al imprimir, Odoo sustituyó los dos registros de CSS compilado de los informes. Los 5.439 adjuntos restantes conservaron todos sus valores. Se registraron seis avances de secuencias de la copia. Los 2.702 archivos físicos del control siguen íntegros. El nuevo árbol contiene 2.708 entradas. Se añadió un estilo referenciado, dos estilos del primer intento y tres marcas del almacén. El otro estilo referenciado reutiliza contenido que ya existía. El primer intento detectó que faltaban el compilador y el enlace a los perfiles ICC. Se corrigió el entorno y se invalidaron exclusivamente los dos estilos de error creados por ese intento en la copia. El recibo posterior es `9f3558a64664a1a3653c3341bfb44f3c4bd051d361a90d3349907ebc5f5d96fb`. [Control de filas](../tools/community/audit_local_print_rows.py) · [Control físico](../tools/community/finish_local_fiscal_print.py)

## Repetición en una estación Windows con WSL Ubuntu

El entorno de QA usa bibliotecas públicas de Ubuntu Focal, Python 3.10.18, PostgreSQL 12.22 y las fuentes del renderizador original. Las herramientas verifican la transferencia y sólo escriben bajo `/var/tmp/steps-community-qa-focal` en WSL. Los comandos de Odoo se ejecutan con una identidad propia dentro de un espacio de red privado. La impresión habilita su interfaz local. El directorio de SQL de SyS y el socket 55441 son independientes de los de Cerro.

Desde PowerShell y el worktree, cada etapa de la siguiente orden transfiere sólo los archivos del sistema seleccionados. La captura de FG, su índice y la referencia nativa proceden de la custodia original. Compruebe el espacio físico del volumen Windows antes de iniciar la restauración.

```powershell
foreach ($stage in 'pg','odoo','extras','print') {
    python tools/community/transfer_focal_print_userspace.py $stage --qa-host odoo-new
    if ($LASTEXITCODE) { throw "Transferencia interrumpida en $stage" }
}
```

En WSL, como administrador local, ejecute desde `tools/community` con `FG` apuntando al directorio que contiene `verified-local-members.json` y `OUT` a la nueva carpeta privada de recibos. El esquema, las filas y el almacén se comparan contra la captura original. Cada paso debe completarse para pasar al siguiente.

```bash
set -e
python3 restore_local_fiscal_print.py "$FG" cluster
python3 restore_local_fiscal_print.py "$FG" sources
python3 restore_local_fiscal_print.py "$FG" sql
python3 prepare_local_fiscal_print.py "$FG"
python3 execute_local_fiscal_print.py restored
python3 execute_local_fiscal_print.py install
python3 read_local_print_rows.py "$FG/source.dump" installed
python3 execute_local_fiscal_print.py installed
python3 execute_local_fiscal_print.py pdf
python3 read_local_print_rows.py "$FG/source.dump" rendered
python3 execute_local_fiscal_print.py rendered
python3 finish_local_fiscal_print.py "$FG" "$OUT"
```

En la estación, `compare_sys_fiscal_print_colors.py` recibe los tres juegos de cuatro PDF y sus recibos mediante `--native`, `--previous`, `--candidate` y sus opciones `--*-directory`. El resultado verifica el control FG anterior además de la copia con el estilo corregido. Al cerrar el ensayo se puede detener únicamente el clúster de SyS con `run_focal_print_command.py --user postgres -- pg_ctl -D /work/sys-print-pg/cluster -m fast stop`. La entrega anterior de FG conserva su estado de control.
