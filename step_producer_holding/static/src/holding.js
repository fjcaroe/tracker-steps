/** @odoo-module **/
import { patch } from "@web/core/utils/patch";
import { useBus } from "@web/core/utils/hooks";
import { ProducerDashboard } from "@step_producers/js/dashboard";
import { AgroComparison } from "@step_agro_analytics/comparison";

patch(ProducerDashboard.prototype, {
    setup() {
        super.setup(...arguments);
        this.state.holdingError = "";
        useBus(this.env.bus, "step-producer-holding-scope", (event) => this.loadCounts(event.detail));
    },
    async loadCounts(companyIds = null) {
        const request = this.holdingCountRequest = (this.holdingCountRequest || 0) + 1;
        this.state.loading = true;
        this.state.holdingError = "";
        try {
            const counts = await this.orm.call("step.packing.order", "producer_holding_counts", [], { company_ids: companyIds });
            if (request === this.holdingCountRequest) this.state.counts = counts;
        } catch (error) {
            if (request === this.holdingCountRequest) {
                this.state.counts = {};
                this.state.holdingError = "No se pudieron cargar los indicadores del holding.";
            }
        } finally {
            if (request === this.holdingCountRequest) this.state.loading = false;
        }
    },
});

patch(AgroComparison.prototype, {
    async load() {
        await super.load(...arguments);
        if (this.props.kind === "producers" && !this.state.error && this.state.data?.selected_company_ids) {
            const ids = this.state.data.selected_company_ids;
            const key = JSON.stringify([...ids].sort((a, b) => a - b));
            if (this.holdingScopeKey !== key) {
                this.holdingScopeKey = key;
                this.env.bus.trigger("step-producer-holding-scope", ids);
            }
        }
    },
    async changeHoldingCompany(companyId, event) {
        const selected = new Set(this.state.data.selected_company_ids);
        if (event.target.checked) selected.add(companyId);
        else selected.delete(companyId);
        if (!selected.size) {
            event.target.checked = true;
            return;
        }
        this.state.filters.company_ids = [...selected];
        await this.load();
    },
    async selectAllHolding() {
        this.state.filters.company_ids = this.state.data.companies.map((company) => company.id);
        await this.load();
    },
});
