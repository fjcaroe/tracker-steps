/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class StepBpaDashboard extends Component {
    static template = "step_bpa_irrigation.Dashboard";

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.state = useState({ loading: true, days: 90, data: null, error: null });
        onWillStart(() => this.loadDashboard());
    }

    async loadDashboard(days = this.state.days) {
        this.state.loading = true;
        this.state.days = Number(days);
        this.state.error = null;
        try {
            this.state.data = await this.orm.call(
                "x_riego_y_fertilizacio", "get_step_bpa_dashboard", [], { days: this.state.days }
            );
        } catch (error) {
            this.state.error = "No fue posible cargar el centro BPA y Riego.";
            this.notification.add(this.state.error, { type: "danger" });
        } finally {
            this.state.loading = false;
        }
    }

    openAction(xmlId) { return this.action.doAction(xmlId); }
    openRecord(model, id) {
        return this.action.doAction({
            type: "ir.actions.act_window", res_model: model, res_id: id,
            views: [[false, "form"]], target: "current",
        });
    }
    formatNumber(value, digits = 0) {
        return new Intl.NumberFormat("es-CL", {
            minimumFractionDigits: digits, maximumFractionDigits: digits,
        }).format(value || 0);
    }
    formatCurrency(value) {
        return new Intl.NumberFormat("es-CL", {
            style: "currency", currency: "CLP", maximumFractionDigits: 0,
        }).format(value || 0);
    }
    formatDate(value) {
        if (!value) return "Sin fecha";
        return new Intl.DateTimeFormat("es-CL", { day: "2-digit", month: "short", year: "numeric" })
            .format(new Date(`${value}T12:00:00`));
    }
}

registry.category("actions").add("step_bpa_irrigation.dashboard", StepBpaDashboard);
