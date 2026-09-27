/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class ExportDashboard extends Component {
    static template = "step_export.Dashboard";

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({ loading: true, counts: null });
        onWillStart(() => this.loadCounts());
    }

    async loadCounts() {
        const queries = [
            ["programs", "step.export.sales.program", [["state", "=", "current"]]],
            ["shipments", "step.export.export", [["state", "not in", ["settled"]]]],
            ["forecasts", "step.export.forecast", []],
            ["settlements", "step.export.receiver.settlement", [["state", "in", ["draft", "validated"]]]],
        ];
        const results = await Promise.allSettled(
            queries.map(([, model, domain]) => this.orm.searchCount(model, domain))
        );
        this.state.counts = Object.fromEntries(
            results.map((result, index) => [queries[index][0], result.status === "fulfilled" ? result.value : null])
        );
        this.state.loading = false;
    }

    count(key) {
        if (this.state.loading) return "…";
        const value = this.state.counts?.[key];
        return value === null || value === undefined ? "—" : new Intl.NumberFormat("es-CL").format(value);
    }

    openAction(xmlId) {
        return this.action.doAction(xmlId);
    }
}

registry.category("actions").add("step_export.dashboard", ExportDashboard);
