/** @odoo-module **/
import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class StepManagementDashboard extends Component {
    static template = "step_management_costs.Dashboard";
    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.request = 0;
        this.state = useState({loading: true, days: 0, data: null, error: null,
            seasonId: 0, speciesId: 0, currencyId: 0});
        onWillStart(() => this.loadDashboard());
    }
    async loadDashboard(days = this.state.days) {
        const request = ++this.request;
        this.state.loading = true;
        this.state.days = Number(days);
        this.state.error = null;
        try {
            const data = await this.orm.call("step.management.operational.budget", "get_management_dashboard", [], {
                days: this.state.days, season_id: this.state.seasonId,
                species_id: this.state.speciesId, currency_id: this.state.currencyId,
            });
            if (request !== this.request) return;
            this.state.data = data;
            this.state.seasonId = data.filters.season_id || 0;
            this.state.speciesId = data.filters.species_id || 0;
            this.state.currencyId = data.filters.currency_id;
        } catch (error) {
            if (request !== this.request) return;
            this.state.error = "No fue posible cargar Gestión y Costos. Revise los filtros e intente nuevamente.";
            this.notification.add(this.state.error, {type: "danger"});
        } finally {
            if (request === this.request) this.state.loading = false;
        }
    }
    changeFilter(field, event) {
        this.state[field] = Number(event.target.value);
        return this.loadDashboard();
    }
    openAction(xmlId) { return this.action.doAction(xmlId); }
    openRecord(id) {
        return this.action.doAction({type: "ir.actions.act_window",
            res_model: "step.management.operational.budget", res_id: id,
            views: [[false, "form"]], target: "current"});
    }
    openCenter(id) {
        return this.action.doAction({type: "ir.actions.act_window",
            res_model: "account.analytic.account", res_id: id,
            views: [[false, "form"]], target: "current"});
    }
    number(value, digits = 0) {
        if (value === null || value === undefined) return "—";
        return new Intl.NumberFormat("es-CL", {minimumFractionDigits: digits, maximumFractionDigits: digits}).format(value);
    }
    money(value, digits) {
        if (value === null || value === undefined) return "—";
        const currency = this.state.data.currencies.selected;
        const precision = digits ?? (currency === "CLP" ? 0 : 2);
        return new Intl.NumberFormat("es-CL", {style: "currency", currency,
            minimumFractionDigits: precision, maximumFractionDigits: precision}).format(value);
    }
    percentage(value) {
        if (value === null || value === undefined) return "—";
        return new Intl.NumberFormat("es-CL", {style: "percent", minimumFractionDigits: 2,
            maximumFractionDigits: 2}).format(value);
    }
    varianceClass(value) {
        if (value === null || value === undefined) return "";
        return value > 0 ? "o_mgmt_variance_positive" : "o_mgmt_variance_nonpositive";
    }
    stateLabel(state) {
        return ({draft: "Borrador", calculated: "Calculado", approved: "Aprobado",
            closed: "Cerrado", cancelled: "Cancelado"})[state] || state;
    }
}
registry.category("actions").add("step_management_costs.dashboard", StepManagementDashboard);
