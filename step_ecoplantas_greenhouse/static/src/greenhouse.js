/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";

class Greenhouse extends Component {
    static template = "step_ecoplantas_greenhouse.Dashboard";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.actions = useService("action");
        this.data = useState({});
        onWillStart(async () => {
            Object.assign(this.data, await this.orm.call("res.company", "get_steps_greenhouse_dashboard", []));
        });
    }

    get stages() {
        return [
            { key: "receipt", number: "01", icon: "fa-inbox", area: _t("Inventario"), title: _t("Recibir insumos"),
                detail: _t("Registra las semillas por lote y recibe el sustrato."), button: _t("Abrir recepción") },
            { key: "batch", number: "02", icon: "fa-leaf", area: _t("Manufactura"), title: _t("Producir plantines"),
                detail: _t("Sigue la siembra y el trasplante en la orden del lote."), button: _t("Abrir orden") },
            { key: "inspection", number: "03", icon: "fa-check-square-o", area: _t("Calidad"), title: _t("Revisar el lote"),
                detail: _t("Comprueba la identificación, la sanidad y la uniformidad."), button: _t("Abrir control") },
            { key: "dispatch", number: "04", icon: "fa-truck", area: _t("Inventario"), title: _t("Preparar despacho"),
                detail: _t("Selecciona el lote de plantines y prepara su salida."), button: _t("Abrir despacho") },
        ];
    }

    openRecord(key) {
        const record = this.data[key];
        return this.actions.doAction({
            type: "ir.actions.act_window",
            name: record.name,
            res_model: record.model,
            res_id: record.id,
            views: [[false, "form"]],
            target: "current",
        });
    }

    openTasks() {
        const project = this.data.project;
        return this.actions.doAction({
            type: "ir.actions.act_window",
            name: project.name,
            res_model: "project.task",
            domain: [["project_id", "=", project.id]],
            context: { default_project_id: project.id },
            views: [[false, "kanban"], [false, "list"], [false, "form"]],
            target: "current",
        });
    }

    openLots() {
        const plant = this.data.plant;
        return this.actions.doAction({
            type: "ir.actions.act_window",
            name: _t("Lotes de plantines"),
            res_model: "stock.lot",
            domain: [["product_id", "=", plant.id]],
            context: { default_product_id: plant.id },
            views: [[false, "list"], [false, "form"]],
            target: "current",
        });
    }
}

registry.category("actions").add("step_ecoplantas_greenhouse.dashboard", Greenhouse);
