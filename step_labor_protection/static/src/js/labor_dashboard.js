/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class StepLaborDashboard extends Component {
    static template = "step_labor_protection.Dashboard";

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.state = useState({ loading: true, days: 0, data: null, error: null });
        onWillStart(() => this.loadDashboard());
    }

    async loadDashboard(days = this.state.days) {
        this.state.loading = true;
        this.state.days = Number(days);
        this.state.error = null;
        try {
            this.state.data = await this.orm.call("res.users", "get_step_labor_dashboard", [], { days: this.state.days });
        } catch (error) {
            this.state.error = "No fue posible cargar Protección Laboral.";
            this.notification.add(this.state.error, { type: "danger" });
        } finally {
            this.state.loading = false;
        }
    }

    openAction(xmlId) { return this.action.doAction(xmlId); }
    formatNumber(value) { return new Intl.NumberFormat("es-CL").format(value || 0); }
}

registry.category("actions").add("step_labor_protection.dashboard", StepLaborDashboard);

