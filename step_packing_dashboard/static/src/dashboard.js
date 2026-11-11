/** @odoo-module **/
import { patch } from "@web/core/utils/patch";
import { StepPackingDashboard } from "@step_packing_operations/js/packing_dashboard";

patch(StepPackingDashboard.prototype, {
    setup() {
        super.setup(...arguments);
        this.state.filters = { period: "season", date_from: "", date_to: "", species_id: "" };
        this.dashboardKpis = [
            ["open_productions", "Órdenes de trabajo abiertas", "Creadas o validadas · fecha de proceso"],
            ["received_kg", "Kilos a proceso recibidos", "Tarjas C · fecha de recepción"],
            ["processed_kg", "Kilos procesados", "Tarjas C consumidas · fecha de proceso"],
            ["stock_input_kg", "Stock kilos a proceso", "Tarjas C validadas · ingresadas en el período"],
            ["export_kg", "Kilos exportación", "Tarjas E · fecha de producción o recepción"],
            ["shipped_kg", "Kilos embarcados", "Tarjas E despachadas · fecha de salida"],
            ["stock_export_kg", "Stock kilos exportación", "Tarjas E validadas · producidas en el período"],
        ];
    },
    async loadDashboard() {
        const request = this.dashboardRequest = (this.dashboardRequest || 0) + 1;
        this.state.loading = true;
        this.state.error = null;
        try {
            const data = await this.orm.call("step.packing.order", "get_dashboard_data", [], { ...this.state.filters });
            if (request === this.dashboardRequest) {
                this.state.data = data;
                Object.assign(this.state.filters, data.filters);
            }
        } catch {
            if (request === this.dashboardRequest) {
                this.state.error = "No fue posible cargar el panel. Comprueba las fechas y vuelve a intentar.";
            }
        } finally {
            if (request === this.dashboardRequest) this.state.loading = false;
        }
    },
    selectPeriod(period) {
        this.state.filters.period = period;
        return this.loadDashboard();
    },
    changeDate(key, event) {
        this.state.filters[key] = event.target.value;
        this.state.filters.period = "custom";
    },
    changeSpecies(event) {
        this.state.filters.species_id = event.target.value;
        return this.loadDashboard();
    },
    openKpi(key) {
        const action = this.state.data?.actions[key];
        if (action) return this.action.doAction(action);
    },
});
