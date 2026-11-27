# Recuperación del perfil SyS de Nómina para integrar Documentos

El punto de partida de U43C es la copia privada U42L de SyS. Contiene 765 liquidaciones y 1.430 documentos. El respaldo congela las 1.138 tablas públicas, sus 608.867 filas y las 858 secuencias con sus valores. La segunda lectura de U42L coincidió con las tablas, el esquema y los contadores de la primera.

| Componente verificado fuera del servidor | Resultado |
| --- | --- |
| SQL | `0c4e970e29579c6de38d71397a987682e97ff9a90027baad8c9e9b77f84bf606` |
| Almacén de objetos referenciados | 2.679 objetos, `d694d99ca0e8670922caefc5eb98d47249cd09b675057824e09ad6b1dbd88b2a` |
| Árbol físico completo | 2.698 entradas, incluidos nueve objetos sueltos y diez marcas de recolección, `71c9add47cf4265ee31555f42c02c8a819b8683154e53858490b22c6c11f8d1c` |
| Motor y módulos efectivos | 22.238 archivos y 190 proveedores, 189 LGPL-3 y uno AGPL-3, `46b1bc9d66abd42ab9c066eacc468a7553aee6a59b54c2c70b8393b4d9782a1a` |
| Paquete de Nómina | Siete módulos y 133 archivos iguales a los del motor congelado, `547c89989b796475cbb46075992f4008c10d23f7a50bbf450f0941192e81fc07` |
| Manifiesto local del respaldo | 11 componentes comprobados por tamaño y SHA-256, `370bf3255b9c82e1f028858fbaf89c1c0135706647a6072b65961b98ac878d40` |

La nómina usa `step_payroll_oca_sys_history` 18.0.1.6.1. La recuperación mantiene los valores de secuencia vigentes al tomar el respaldo. También conserva seis diferencias previas entre la versión registrada y el manifiesto efectivo.

| Módulo | Versión registrada | Manifiesto | Origen |
| --- | --- | --- | --- |
| hr_timesheet | 18.0.1.0 | 18.0.1.1 | Odoo Community |
| l10n_latam_invoice_document | 18.0.1.0 | 18.0.1.1 | Odoo Community |
| project_sms | 18.0.1.0 | 18.0.1.1 | Odoo Community |
| l10n_cl_simpledigital_payroll | 18.0.1.0.0 | 18.0.1.1.0 | Cohorte SyS |
| step_hr_previred | 18.0.3.8.7 | 18.0.3.8.8 | Cohorte SyS |
| step_hr_previred_simpledigital | 18.0.2.4.1 | 18.0.2.4.2 | Cohorte SyS |
