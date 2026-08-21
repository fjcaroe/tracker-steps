/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class StepCosechaDashboard extends Component {
    static template = "step_cosecha.Dashboard";

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.state = useState({ loading: true, days: 30, data: null, error: null });
        onWillStart(() => this.loadDashboard());
    }

    async loadDashboard(days = this.state.days) {
        this.state.loading = true;
        this.state.days = Number(days);
        this.state.error = null;
        try {
            this.state.data = await this.orm.call(
                "step.cosecha.registry",
                "get_dashboard_data",
                [],
                { days: this.state.days }
            );
        } catch (error) {
            this.state.error = "No fue posible cargar el resumen de Cosecha.";
            this.notification.add(this.state.error, { type: "danger" });
        } finally {
            this.state.loading = false;
        }
    }

    openAction(xmlId) {
        return this.action.doAction(xmlId);
    }

    openRegistry(id) {
        return this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "step.cosecha.registry",
            res_id: id,
            views: [[false, "form"]],
            target: "current",
        });
    }

    formatNumber(value, digits = 0) {
        return new Intl.NumberFormat("es-CL", {
            minimumFractionDigits: digits,
            maximumFractionDigits: digits,
        }).format(value || 0);
    }

    formatDate(value) {
        if (!value) return "Sin fecha";
        return new Intl.DateTimeFormat("es-CL", { day: "2-digit", month: "short", year: "numeric" })
            .format(new Date(`${value.replace(" ", "T")}Z`));
    }
}

registry.category("actions").add("step_cosecha.dashboard", StepCosechaDashboard);
