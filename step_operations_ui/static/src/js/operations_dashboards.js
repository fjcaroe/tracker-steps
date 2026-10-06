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

    async safeReadGroup(model, domain, fields, groupby, options = {}) {
        try {
            return await this.orm.readGroup(model, domain, fields, groupby, options);
        } catch {
            return [];
        }
    }

    formatCurrency(value) {
        return new Intl.NumberFormat("es-CL", { style: "currency", currency: "CLP", maximumFractionDigits: 0 })
            .format(value || 0);
    }

    /** Lunes (00:00) de la semana que contiene `date`. */
    startOfWeek(date) {
        const d = new Date(date);
        const day = (d.getDay() + 6) % 7; // 0 = lunes
        d.setDate(d.getDate() - day);
        d.setHours(0, 0, 0, 0);
        return d;
    }

    toDateString(date) {
        return date.toISOString().slice(0, 10);
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

    setup() {
        super.setup();
        this.weekState = useState({ offset: 0 });
    }

    async loadDashboard() {
        this.state.loading = true;
        try {
            const orders = await this.safeCount("step.freight.order");
            const accounting = await this.safeCount("step.freight.accounting");
            const tariffs = await this.safeCount("step.freight.tariff", [["active", "=", true]]);
            const tracking = await this.safeCount("step.freight.tracking");
            const routes = await this.safeCount("step.freight.route", [["active", "=", true]]);
            const coldModes = await this.safeCount("step.freight.cold.mode", [["active", "=", true]]);
            const recent = await this.safeRead(
                "step.freight.order",
                [],
                ["name", "date", "freight_state", "fundo_id", "freight_carrier_id", "responsible_id", "route_id"],
                { limit: 6, order: "date desc, id desc" }
            );
            // El valor real del flete se carga en la hoja "Detalles" de Studio
            // (step.freight.order.line), no en el campo "amount" del código.
            if (recent.length) {
                const sums = await this.safeReadGroup(
                    "step.freight.order.line",
                    [["order_id", "in", recent.map((r) => r.id)]],
                    ["freight_value:sum"],
                    ["order_id"]
                );
                const byOrder = {};
                for (const row of sums) {
                    const orderId = Array.isArray(row.order_id)
                        ? row.order_id[0]
                        : row.order_id;
                    byOrder[orderId] = row.freight_value;
                }
                for (const row of recent) {
                    row.freight_value = byOrder[row.id] || 0;
                }
            }
            await this.loadWeekComparison();
            this.state.data = { orders, accounting, tariffs, tracking, routes, coldModes, recent };
        } catch {
            this.state.error = "No fue posible cargar el resumen de Fletes.";
        } finally {
            this.state.loading = false;
        }
    }

    async loadWeekComparison() {
        const monday = this.startOfWeek(new Date());
        monday.setDate(monday.getDate() + this.weekState.offset * 7);
        const sunday = new Date(monday);
        sunday.setDate(sunday.getDate() + 6);
        this.weekState.label = `${this.formatDate(this.toDateString(monday))} — ${this.formatDate(this.toDateString(sunday))}`;
        const rows = await this.safeReadGroup(
            "step.freight.plan.vs.actual",
            [["week_start", "=", this.toDateString(monday)]],
            ["planned_amount:sum", "real_amount:sum"],
            []
        );
        const totals = rows[0] || {};
        this.weekState.planned = totals.planned_amount || 0;
        this.weekState.real = totals.real_amount || 0;
        this.weekState.diff = this.weekState.real - this.weekState.planned;
    }

    async changeWeek(delta) {
        this.weekState.offset += delta;
        await this.loadWeekComparison();
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
