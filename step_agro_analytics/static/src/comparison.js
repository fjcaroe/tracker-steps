/** @odoo-module **/
import { Component, onWillStart, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { patch } from "@web/core/utils/patch";
import { ProducerDashboard } from "@step_producers/js/dashboard";
import { StepPackingDashboard } from "@step_packing_operations/js/packing_dashboard";

export class AgroComparison extends Component {
    static template = "step_agro_analytics.Comparison";
    static props = { kind: String };
    setup() {
        this.orm = useService("orm");
        this.state = useState({ data: null, loading: true, error: "",
            filters: { season_id: "", month: "", week: "", species_id: "" } });
        this.request = 0;
        onWillStart(() => this.load());
    }
    async load() {
        const request = ++this.request;
        this.state.loading = true;
        this.state.error = "";
        try {
            const data = await this.orm.call("step.packing.order", "operational_comparison", [], {
                kind: this.props.kind, filters: { ...this.state.filters },
            });
            if (request === this.request) this.state.data = data;
        } catch (error) {
            if (request === this.request) {
                this.state.data = null;
                this.state.error = "No se pudo cargar el comparativo. Revisa tus permisos o vuelve a intentar.";
            }
        } finally {
            if (request === this.request) this.state.loading = false;
        }
    }
    changeFilter(key, event) {
        this.state.filters[key] = event.target.value;
        if (key === "month") this.state.filters.week = "";
        return this.load();
    }
    format(value, kind) {
        if (kind === "text") return value || "";
        if (value === null || value === undefined) return "—";
        return new Intl.NumberFormat("es-CL", { maximumFractionDigits: 1 }).format(value)
            + (kind === "percent" ? "%" : "");
    }
}
patch(ProducerDashboard, { components: { ...ProducerDashboard.components, AgroComparison } });
patch(StepPackingDashboard, { components: { ...StepPackingDashboard.components, AgroComparison } });
