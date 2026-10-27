# Cerro El Plomo — edición y dependencias

La auditoría de solo lectura confirma que la instalación actual contiene
componentes Enterprise. No es una instalación Community independiente de
Enterprise, aunque los módulos Steps sean desarrollos propios.

## Resultado técnico

- 372 módulos instalados; 140 declaran licencia `OEEL-1`.
- 79 de los 91 módulos con prefijo `step` tienen dependencias declaradas,
  directas o transitivas, hacia componentes Enterprise.
- La base declara motivo de vencimiento `trial` y fecha 31-10-2026.
- No tiene un código de suscripción configurado. Eso no determina si existe
  algún contrato externo: solo describe el registro de esta base.
- `studio_customization` figura instalado sin manifiesto en disco. Existen
  campos manuales heredados que deben inventariarse y preservarse.

Ejemplos de acoplamiento confirmado:

| Área | Dependencia |
| --- | --- |
| Tesorería y contabilidad multimoneda | `account_reports` |
| Exportaciones y módulos de Packing que la usan | `l10n_cl_edi_exports` |
| Recursos humanos y numerosos maestros agrícolas | `hr_payroll`, `hr_holidays_gantt`, `hr_work_entry_contract_enterprise` |
| Calidad y trazabilidad | `quality_control` |
| Algunos formularios e informes propios | `web_gantt` |

El grafo de dependencias instalado relaciona 136 módulos con `web_enterprise`
y 60 con `account_reports`. Son dependencias declaradas que requieren revisión,
no una certificación de que una desinstalación conservaría todos los datos.

También está instalado `step_expire_database`, un componente antiguo cuya
descripción y estilos buscan ocultar el panel de vencimiento. La existencia
de ese componente no convierte la instalación en Community ni sustituye una
suscripción. No se ejecutó su código de prórroga ni se alteraron sus parámetros.
No se encontraron tareas programadas registradas bajo sus identificadores de
módulo durante esta revisión.

## Caminos de resolución

**Mantener Enterprise:** comprobar si existe una suscripción válida y registrar
la base con su código mediante el procedimiento oficial. No se ha contratado,
comprado ni solicitado una licencia durante esta auditoría.

**Migrar realmente a Community:** preparar una copia privada de Cerro dentro
del circuito de revisión de Desarrollo. Inventariar datos, campos, vistas,
reportes y automatizaciones asociados a Enterprise y definir su sustitución.
Separar los maestros agrícolas de las dependencias de Nómina; adaptar los
informes financieros, la facturación electrónica y los puentes de calidad.
Preservar los históricos y las relaciones a maestros existentes. Implementar
los reemplazos mediante componentes Community o código propio independiente.
No copiar código Enterprise para simular una edición Community.

Antes de retirar componentes: demostrar el arranque con fuentes Community,
comprobar integridad de datos y ejecutar flujos de contabilidad, pagos,
facturación, Packing, Productores y las funciones de personal que se conserven.
La publicación necesita un paquete probado, respaldo, bloqueo y comprobación
en el destino. QA-Cerro conserva sus datos y aislamiento; no se refresca.

La elección entre esos dos caminos se consultó al usuario. El aviso permanece
sin alterar mientras se define la solución. Esta auditoría no desinstaló
módulos, no borró datos, no cambió credenciales y no modificó el vencimiento.

## Evidencia y reproducción

Herramienta versionada: `tools/ops/audit_community_readiness.py`.
La ejecución en Cerro confirmó `read_only=true`. El inventario completo,
las rutas efectivas y los recuentos de registros están en artefactos privados,
fuera del repositorio. La herramienta no consulta ni imprime códigos de
suscripción, UUID de la base ni credenciales.

Referencias oficiales:

- [Licencias de Odoo 18](https://www.odoo.com/documentation/18.0/legal/licenses.html).
- [Registro de instalaciones propias](https://www.odoo.com/documentation/18.0/administration/on_premise.html).
