/** @odoo-module **/

import { Component, reactive, useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";
import { Layout } from "@web/search/layout";
import { session } from "@web/session";

export const stages = [
    { key: "receipt", number: "01", short: _t("Insumos"), icon: "fa-inbox", area: _t("Inventario"),
        title: _t("Recibir insumos"), detail: _t("Registra las semillas por lote y recibe el sustrato."), button: _t("Abrir recepción") },
    { key: "batch", number: "02", short: _t("Siembra"), icon: "fa-leaf", area: _t("Manufactura"),
        title: _t("Producir plantines"), detail: _t("Sigue la siembra y el trasplante en la orden del lote."), button: _t("Abrir orden") },
    { key: "inspection", number: "03", short: _t("Calidad"), icon: "fa-check-square-o", area: _t("Calidad"),
        title: _t("Revisar el lote"), detail: _t("Comprueba la identificación, la sanidad y la uniformidad."), button: _t("Abrir control") },
    { key: "dispatch", number: "04", short: _t("Despacho"), icon: "fa-truck", area: _t("Inventario"),
        title: _t("Preparar despacho"), detail: _t("Selecciona el lote de plantines y prepara su salida."), button: _t("Abrir despacho") },
];

const support = [
    { key: "project", short: _t("Labores"), icon: "fa-calendar-check-o", area: _t("Proyecto"),
        title: _t("Labores de cultivo"), detail: _t("Revisa las tareas del lote y organiza el riego, la sanidad y el despacho.") },
    { key: "maintenance", short: _t("Riego"), icon: "fa-wrench", area: _t("Mantenimiento"),
        title: _t("Mantenimiento de riego"), detail: _t("Consulta la solicitud preventiva para la bomba y los goteros.") },
    { key: "lots", short: _t("Lotes"), icon: "fa-barcode", area: _t("Trazabilidad"),
        title: _t("Lotes de plantines"), detail: _t("Abre un lote para consultar sus existencias y movimientos.") },
    { key: "costs", short: _t("Costos"), icon: "fa-sitemap", area: _t("Contabilidad analítica"),
        title: _t("Repartos semanales"), detail: _t("Revisa la vista previa antes de distribuir los costos compartidos."),
        action: "step_nursery_shared_costs.action_cost_run" },
    { key: "centers", short: _t("Centros"), icon: "fa-sitemap", area: _t("Costos compartidos"),
        title: _t("Centros de costo"), detail: _t("Vincula los centros hijos a su centro padre y define el driver de cada labor."),
        action: "step_nursery_shared_costs.action_cost_center" },
    { key: "drivers", short: _t("Drivers"), icon: "fa-sliders", area: _t("Costos compartidos"),
        title: _t("Drivers de costeo"), detail: _t("Consulta la unidad que se usa para distribuir cada costo."),
        action: "step_nursery_shared_costs.action_cost_driver" },
    { key: "measures", short: _t("Carga semanal"), icon: "fa-table", area: _t("Costos compartidos"),
        title: _t("Carga semanal"), detail: _t("Registra las cantidades por semana, centro hijo y driver."),
        action: "step_nursery_shared_costs.action_cost_measure" },
];

const sections = Object.fromEntries([...stages, ...support].map(entry => [entry.key, entry]));

registry.category("services").add("steps_greenhouse_workspace", {
    dependencies: ["action", "company", "orm"],
    start(env, { action, company, orm }) {
        const state = reactive({ key: null, data: {}, refreshing: false });
        const enabled = company.currentCompany.id === session.steps_greenhouse_company;
        let pending;
        async function refresh() {
            if (!pending) {
                state.refreshing = true;
                pending = orm.call("res.company", "get_steps_greenhouse_dashboard", []).then(data => {
                    state.data = data;
                    return data;
                }).finally(() => {
                    state.refreshing = false;
                    pending = null;
                });
            }
            return pending;
        }
        env.bus.addEventListener("ACTION_MANAGER:UPDATE", ({ detail }) => {
            const key = detail.componentProps?.context?.steps_greenhouse_stage;
            state.key = enabled && sections[key] ? key : null;
            document.body.classList.toggle("o_ecoplantas_workspace", Boolean(state.key));
            if (state.key && !Object.keys(state.data).length) {
                refresh().catch(() => {});
            }
        });
        function available(key) {
            if (sections[key]?.action) {
                return Boolean(state.data.shared_costs);
            }
            return Boolean(state.data[key === "lots" ? "plant" : key]);
        }
        async function open(key) {
            const data = await refresh();
            if (!available(key)) {
                return;
            }
            const context = { steps_greenhouse_stage: key };
            if (sections[key].action) {
                return action.doAction(sections[key].action, { additionalContext: context });
            }
            if (key === "project") {
                return action.doAction({
                    type: "ir.actions.act_window", name: data.project.name, res_model: "project.task",
                    domain: [["project_id", "=", data.project.id]],
                    context: { ...context, default_project_id: data.project.id },
                    views: [[false, "kanban"], [false, "list"], [false, "form"]], target: "current",
                });
            }
            if (key === "lots") {
                return action.doAction({
                    type: "ir.actions.act_window", name: sections[key].title, res_model: "stock.lot",
                    domain: [["product_id", "=", data.plant.id], ["company_id", "=", company.currentCompany.id]],
                    context: { ...context, default_product_id: data.plant.id },
                    views: [[false, "list"], [false, "form"]], target: "current",
                });
            }
            const record = data[key];
            return action.doAction({
                type: "ir.actions.act_window", name: record.name, res_model: record.model, res_id: record.id,
                context, views: [[false, "form"]], target: "current",
            });
        }
        return {
            state, available, open, refresh,
            home: () => action.doAction("step_ecoplantas_greenhouse.action_greenhouse", { clearBreadcrumbs: true }),
        };
    },
});

class GreenhouseSubnav extends Component {
    static template = "step_ecoplantas_greenhouse.Subnav";
    static props = {};

    setup() {
        this.workspace = useService("steps_greenhouse_workspace");
        this.state = useState(this.workspace.state);
    }

    get section() {
        return sections[this.state.key];
    }

    get metrics() {
        return this.state.data.subpage_metrics?.[this.state.key] || [];
    }

    get status() {
        return this.state.data[this.state.key]?.status;
    }

    get next() {
        const index = stages.findIndex(section => section.key === this.state.key);
        const entry = index >= 0 && stages[index + 1];
        return entry && this.workspace.available(entry.key) ? entry : null;
    }

    get tabs() {
        if (this.section?.action) {
            return support.filter(section => section.action && this.workspace.available(section.key));
        }
        return stages.filter(section => this.workspace.available(section.key));
    }
}

patch(Layout.prototype, {
    setup() {
        super.setup();
        this.greenhouseWorkspace = useState(useService("steps_greenhouse_workspace").state);
        this.components.GreenhouseSubnav = GreenhouseSubnav;
    },
});
