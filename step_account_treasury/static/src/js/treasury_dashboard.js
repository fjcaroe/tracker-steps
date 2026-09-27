/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class StepsTreasuryDashboard extends Component {
    static template = "step_account_treasury.Dashboard";

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
            this.state.data = await this.orm.call(
                "step.cashflow", "get_treasury_dashboard_data", []
            );
        } catch (error) {
            this.state.error = "No fue posible cargar el resumen de Tesorería.";
            this.notification.add(this.state.error, { type: "danger" });
        } finally {
            this.state.loading = false;
        }
    }

    openAction(xmlId) {
        return this.action.doAction(xmlId);
    }

    openFlow(id) {
        return this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "step.cashflow",
            res_id: id,
            views: [[false, "form"]],
            target: "current",
        });
    }
}

registry.category("actions").add(
    "step_account_treasury.dashboard", StepsTreasuryDashboard
);
