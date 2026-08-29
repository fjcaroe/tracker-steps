/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class StepMobilizationDashboard extends Component {
    static template = "step_mobilization.Dashboard";

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
            this.state.data = await this.orm.call("step.movi.registry", "get_dashboard_data", []);
        } catch (error) {
            this.state.error = "No fue posible cargar la portada de Movilización.";
            this.notification.add(this.state.error, { type: "danger" });
        } finally {
            this.state.loading = false;
        }
    }

    openAction(xmlId, extraContext) {
        return this.action.doAction(xmlId, { additionalContext: extraContext || {} });
    }

    formatNumber(value) {
        return new Intl.NumberFormat("es-CL").format(value || 0);
    }

    formatCurrency(value) {
        return new Intl.NumberFormat("es-CL", { style: "currency", currency: "CLP" }).format(value || 0);
    }
}

registry.category("actions").add("step_mobilization_dashboard", StepMobilizationDashboard);
