/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class StepPackingDashboard extends Component {
    static template = "step_packing_operations.Dashboard";

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.state = useState({ loading: true, data: null, error: null });
        onWillStart(() => this.loadDashboard());
    }

    async loadDashboard() {
        this.state.loading = true;
        this.state.error = null;
        try {
            this.state.data = await this.orm.call("step.packing.order", "get_dashboard_data", []);
        } catch (error) {
            this.state.error = "No fue posible cargar el resumen de Packing.";
            this.notification.add(this.state.error, { type: "danger" });
        } finally {
            this.state.loading = false;
        }
    }

    openAction(xmlId) {
        return this.action.doAction(xmlId);
    }

    openOrder(id) {
        return this.action.doAction({
            type: "ir.actions.act_window", res_model: "step.packing.order",
            res_id: id, views: [[false, "form"]], target: "current",
        });
    }

    openProduction(id) {
        return this.action.doAction({
            type: "ir.actions.act_window", res_model: "step.packing.production",
            res_id: id, views: [[false, "form"]], target: "current",
        });
    }

    formatNumber(value, digits = 0) {
        return new Intl.NumberFormat("es-CL", {
            minimumFractionDigits: digits,
            maximumFractionDigits: digits,
        }).format(value || 0);
    }
}

registry.category("actions").add("step_packing_operations.dashboard", StepPackingDashboard);
