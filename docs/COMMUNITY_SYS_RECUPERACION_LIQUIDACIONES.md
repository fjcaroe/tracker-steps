# Recuperación de SyS con la ficha de liquidación .6.2

El directorio privado `U48/recovery-kit` contiene los 52 archivos necesarios para partir del respaldo íntegro de SyS, recuperar los 193 proveedores y actualizar la ficha de liquidaciones al paquete aceptado. El índice exterior `release.json` tiene SHA-256 `9631b6cf47ac43a798622da746bdd044e8921cbaed356f753af161cc81ea7cfe`. Se entrega el directorio entero. Los enlaces físicos de la copia en NTFS ahorran espacio y sus archivos siguen siendo independientes de las rutas de origen al transportar el directorio.

| Directorio | Contenido |
| --- | --- |
| `fg/` | Respaldo base con SQL, código efectivo, documentos, archivos adicionales y sus índices de integridad. |
| `base193/` | Diferencia comprimida del SQL, sellos, tres archivos del módulo de colores y las diferencias del almacén documental. |
| `operator/` | TAR exacto del módulo .6.2 y cuatro recibos de la prueba de formularios, cálculo, confirmación y preservación. |
| `tools/` | Recuperador de la entrega y sus dependencias de código. El actualizador consume directamente el TAR firmado. |

La comprobación independiente en Windows reconstruyó completamente los 27.699.785 bytes del volcado PostgreSQL en memoria, con SHA-256 `06596b017042ac3d2ee43c61d7a1ae2f081805c1949f2c7d915c120628c83389`. El actualizador incluido descomprimió las nueve piezas y cotejó cada una con el TAR `e1f3d645ce6ca3b1c967114c72efb6db8c33c8e70c391d258caf6eb58ec27642`. Con esos mismos bytes se había ejecutado la actualización oficial en la restauración independiente U48D. [Resultados de los operadores](COMMUNITY_SYS_ALTA_LIQUIDACION.md)

## Repetición

Desde cualquier equipo con Python 3.12 o posterior puede verificarse el directorio sin abrir la base. Para reconstruir el SQL también en Windows se puede ejecutar `verify_sys_recovery_on_windows.py` con la ruta del directorio y `--libzstd` apuntando a la biblioteca local instalada.

```bash
python -B "$KIT/tools/package_sys_operator_release.py" verify "$KIT"
```

La restauración usa la estación WSL de QA con el entorno Focal, PostgreSQL 12, Python 3.10 para Odoo y Python 3.14 para la reconstrucción Zstandard. Requiere una instancia RAM nueva o restituida a su situación inicial. El destino fijado en el recuperador es la derivada privada U48D. La base U46R restaurada conserva el respaldo anterior como control.

```bash
export PYTHONDONTWRITEBYTECODE=1
python3 -B "$KIT/tools/package_sys_operator_release.py" restore "$KIT"
```

El comando verifica los componentes, reconstruye el volcado y el almacén, comprueba el esquema y las filas antes de actualizar y entrega a Odoo el TAR probado de .6.2. El verificador por nombre y huella comprueba las columnas originales requeridas durante la actualización. El entorno del sistema operativo y las fuentes tipográficas corresponden al perfil validado en la recuperación de U46R. [Entorno de la entrega de 193 módulos](COMMUNITY_SYS_ENTREGA_193.md)
