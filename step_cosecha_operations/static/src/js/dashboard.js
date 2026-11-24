/** @odoo-module **/
import { onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { StepCosechaDashboard } from "@step_cosecha/js/cosecha_dashboard";

export class HarvestOperationsDashboard extends StepCosechaDashboard {
    static template = "step_cosecha_operations.Dashboard";

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.sequence = 0;
        this.state = useState({ loading: true, period: "today", days: 1,
            speciesId: 0, farmId: 0, offset: 0, data: null, error: null });
        onWillStart(() => this.loadDashboard());
    }

    async loadDashboard(changes = {}) {
        Object.assign(this.state, changes);
        const request = ++this.sequence;
        this.state.loading = true;
        this.state.error = null;
        try {
            const data = await this.orm.call("step.cosecha.registry", "get_dashboard_data", [], {
                period: this.state.period, species_id: this.state.speciesId,
                farm_id: this.state.farmId, offset: this.state.offset,
            });
            if (request !== this.sequence) return;
            this.state.data = data;
            this.state.days = data.days;
            this.state.offset = data.offset;
        } catch (error) {
            if (request !== this.sequence) return;
            this.state.error = "No fue posible cargar el resumen de Cosecha.";
            this.notification.add(this.state.error, { type: "danger" });
        } finally {
            if (request === this.sequence) this.state.loading = false;
        }
    }

    onPeriod(event) { return this.loadDashboard({ period: event.target.value, offset: 0 }); }
    onSpecies(event) { return this.loadDashboard({ speciesId: Number(event.target.value), offset: 0 }); }
    onFarm(event) { return this.loadDashboard({ farmId: Number(event.target.value), offset: 0 }); }
    previousPage() { return this.loadDashboard({ offset: Math.max(0, this.state.offset - 50) }); }
    nextPage() { return this.loadDashboard({ offset: this.state.offset + 50 }); }
    optionalNumber(value, digits = 2) {
        return value === null || value === false ? "—" : this.formatNumber(value, digits);
    }
}

registry.category("actions").add("step_cosecha.dashboard", HarvestOperationsDashboard, { force: true });
