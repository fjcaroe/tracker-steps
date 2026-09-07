/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class StepTaskDashboard extends Component {
    static template = "step_task.Dashboard";

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.state = useState({ loading: true, days: 30, data: null, error: null });
        onWillStart(() => this.load());
    }

    async load(days = this.state.days) {
        this.state.loading = true;
        this.state.days = Number(days);
        this.state.error = null;
        try {
            this.state.data = await this.orm.call("step.tarja", "get_task_dashboard_data", [], {
                days: this.state.days,
            });
        } catch {
            this.state.error = "No se pudo cargar el panel de Steps Task.";
            this.notification.add(this.state.error, { type: "danger" });
        } finally {
            this.state.loading = false;
        }
    }

    openAction(xmlId, extraContext) {
        return this.action.doAction(xmlId, extraContext ? { additionalContext: extraContext } : {});
    }

    openOrder(id) {
        return this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "step.tarja",
            res_id: id,
            views: [[false, "form"]],
            target: "current",
        });
    }

    num(value) {
        return new Intl.NumberFormat("es-CL").format(value || 0);
    }

    fmtDate(value) {
        if (!value) return "Sin fecha";
        return new Intl.DateTimeFormat("es-CL", { day: "2-digit", month: "short" }).format(
            new Date(`${value}T00:00:00`)
        );
    }
}

registry.category("actions").add("step_task.dashboard", StepTaskDashboard);
