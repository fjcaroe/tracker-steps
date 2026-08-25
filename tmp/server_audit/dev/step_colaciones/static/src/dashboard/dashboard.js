/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class ColacionesDashboard extends Component {
    static template = "step_colaciones.Dashboard";

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({ loading: true, data: null });
        onWillStart(() => this.loadData());
    }

    async loadData() {
        this.state.loading = true;
        this.state.data = await this.orm.call("step.colacion.registration", "get_dashboard_data", []);
        this.state.loading = false;
    }

    openAction(xmlId, extra = {}) {
        return this.action.doAction(xmlId, extra);
    }

    openRegistration(id) {
        return this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "step.colacion.registration",
            res_id: id,
            views: [[false, "form"]],
            target: "current",
        });
    }
}

registry.category("actions").add("step_colaciones.dashboard", ColacionesDashboard);

