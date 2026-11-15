{
    "name": "Steps - Control de envases de cosecha",
    "version": "18.0.1.0.0",
    "license": "LGPL-3",
    "depends": ["step_packing_operations", "step_packing_interplant", "step_cosecha_planning",
                "step_packing_analytics", "step_machinery", "step_hr", "step_task"],
    "data": ["security/ir.model.access.csv", "security/rules.xml", "views/control.xml", "views/work_order.xml"],
    "installable": True,
}
