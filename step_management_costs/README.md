# Steps - Gestión y Costos

Aplicación nativa y portable para Odoo 18. Reemplaza el conjunto de pantallas
Studio de gestión, planificación y presupuesto operacional.

## Alcance

- centro de gestión con indicadores y accesos rápidos;
- centros de costo con superficie en hectáreas;
- grupos e indicadores presupuestarios;
- plantillas versionables expresadas por hectárea;
- creación de un presupuesto para uno o varios centros de costo;
- extrapolación automática por las hectáreas asignadas a cada centro;
- distribución mensual, aprobación y cierre del presupuesto;
- planificación operacional y control presupuesto versus costo real;
- vistas lista, kanban, gráfico y tabla dinámica.

Las opciones **Cultivos** e **Informes** del menú anterior no están incluidas.

## Instalación

Copie `step_management_costs` a una ruta de addons, actualice la lista de
aplicaciones e instale **Steps - Gestión y Costos**. Sólo utiliza dependencias
estándar: Base, Conversaciones, Web, Contabilidad y Productos.

La migración demostrativa de `steps_qa` es opcional y está separada del addon:

```python
exec(open('/ruta/step_management_costs/scripts/migrate_steps_qa_data.py').read())
migrate(env)
```

La prueba repetible del cálculo multi-centro se ejecuta desde un shell de Odoo:

```python
exec(open('/ruta/step_management_costs/scripts/validate_template_budget.py').read())
validate(env)
```
