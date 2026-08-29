/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

class StepsOperationsDashboard extends Component {
    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.state = useState({ loading: true, error: null, data: {} });
        onWillStart(() => this.loadDashboard());
    }

    async safeCount(model, domain = []) {
        try {
            return await this.orm.searchCount(model, domain);
        } catch {
            return 0;
        }
    }

    async safeRead(model, domain, fields, options = {}) {
        try {
            return await this.orm.searchRead(model, domain, fields, options);
        } catch {
            return [];
        }
    }

    openAction(xmlId) {
        return this.action.doAction(xmlId);
    }

    openRecord(model, id) {
        return this.action.doAction({
            type: "ir.actions.act_window",
            res_model: model,
            res_id: id,
            views: [[false, "form"]],
            target: "current",
        });
    }

    formatNumber(value) {
        return new Intl.NumberFormat("es-CL").format(value || 0);
    }

    formatDate(value) {
        if (!value) return "Sin fecha";
        return new Intl.DateTimeFormat("es-CL", { day: "2-digit", month: "short", year: "numeric" })
            .format(new Date(`${value}T12:00:00`));
    }

    many2oneName(value, fallback = "Sin asignar") {
        return Array.isArray(value) ? value[1] : fallback;
    }
}

export class MachineryDashboard extends StepsOperationsDashboard {
    static template = "step_operations_ui.MachineryDashboard";

    async loadDashboard() {
        this.state.loading = true;
        try {
            // Keep requests sequential: development instances commonly use a
            // small PostgreSQL connection pool and the dashboard must remain light.
            const total = await this.safeCount("step.hrs.machinery");
            const draft = await this.safeCount("step.hrs.machinery", [["state", "=", "draft"]]);
            const progress = await this.safeCount("step.hrs.machinery", [["state", "=", "progress"]]);
            const done = await this.safeCount("step.hrs.machinery", [["state", "in", ["done", "costed", "accounted"]]]);
            const lines = await this.safeCount("step.hrs.machinery.line");
            const vehicles = await this.safeCount("fleet.vehicle", [["es_maquina", "=", true]]);
            const realCosts = await this.safeCount("real.cost.machinery");
            const recent = await this.safeRead(
                "step.hrs.machinery",
                [],
                ["name", "date", "state", "responsable_id", "fundo_id", "temp_id"],
                { limit: 6, order: "date desc, id desc" }
            );
            this.state.data = { total, draft, progress, done, lines, vehicles, realCosts, recent };
        } catch {
            this.state.error = "No fue posible cargar el resumen de Maquinaria.";
        } finally {
            this.state.loading = false;
        }
    }

    stateLabel(state) {
        return { draft: "Nuevo", progress: "En progreso", done: "Listo" }[state] || state || "Sin estado";
    }
}

export class FreightDashboard extends StepsOperationsDashboard {
    static template = "step_operations_ui.FreightDashboard";

    async loadDashboard() {
        this.state.loading = true;
        try {
            const orders = await this.safeCount("x_orden_de_flete");
            const accounting = await this.safeCount("x_contabilizacion_de_f");
            const tariffs = await this.safeCount("x_tarifa_de_fletes", [["x_active", "=", true]]);
            const tracking = await this.safeCount("x_rastreo_camiones");
            const routes = await this.safeCount("x_tramo_de_flete", [["x_active", "=", true]]);
            const coldModes = await this.safeCount("x_modalidad_de_frio", [["x_active", "=", true]]);
            const recent = await this.safeRead(
                "x_orden_de_flete",
                [],
                ["x_name", "x_studio_fecha", "x_studio_selection_field_4ag_1jhk4c7s5", "x_studio_fundo", "x_studio_transportista", "x_studio_responsable"],
                { limit: 6, order: "x_studio_fecha desc, id desc" }
            );
            this.state.data = { orders, accounting, tariffs, tracking, routes, coldModes, recent };
        } catch {
            this.state.error = "No fue posible cargar el resumen de Fletes.";
        } finally {
            this.state.loading = false;
        }
    }

    stateLabel(state) {
        return {
            status1: "Ingresado",
            status2: "Autorizado",
            status3: "Contabilizado",
        }[state] || "Sin estado";
    }
}

registry.category("actions").add("step_operations_ui.machinery_dashboard", MachineryDashboard);
registry.category("actions").add("step_operations_ui.freight_dashboard", FreightDashboard);
