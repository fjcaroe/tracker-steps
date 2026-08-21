/** @odoo-module **/
import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class StepManagementDashboard extends Component {
    static template = "step_management_costs.Dashboard";
    setup() {
        this.orm = useService("orm"); this.action = useService("action"); this.notification = useService("notification");
        this.state = useState({ loading: true, days: 0, data: null, error: null });
        onWillStart(() => this.loadDashboard());
    }
    async loadDashboard(days = this.state.days) {
        this.state.loading = true; this.state.days = Number(days); this.state.error = null;
        try { this.state.data = await this.orm.call("step.management.operational.budget", "get_management_dashboard", [], { days: this.state.days }); }
        catch (error) { this.state.error = "No fue posible cargar Gestión y Costos."; this.notification.add(this.state.error, { type: "danger" }); }
        finally { this.state.loading = false; }
    }
    openAction(xmlId) { return this.action.doAction(xmlId); }
    openRecord(id) { return this.action.doAction({ type: "ir.actions.act_window", res_model: "step.management.operational.budget", res_id: id, views: [[false,"form"]], target: "current" }); }
    number(value, digits = 0) { return new Intl.NumberFormat("es-CL", { minimumFractionDigits: digits, maximumFractionDigits: digits }).format(value || 0); }
    money(value) { return new Intl.NumberFormat("es-CL", { style: "currency", currency: "CLP", maximumFractionDigits: 0 }).format(value || 0); }
    stateLabel(state) { return ({draft:"Borrador",calculated:"Calculado",approved:"Aprobado",closed:"Cerrado",cancelled:"Cancelado"})[state] || state; }
}
registry.category("actions").add("step_management_costs.dashboard", StepManagementDashboard);
