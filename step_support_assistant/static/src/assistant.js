/** @odoo-module **/
import { Component, onWillStart, onPatched, reactive, useRef, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class StepsAssistant extends Component {
    static template = "step_support_assistant.Chat";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.transcript = useRef("transcript");
        this.composer = useRef("composer");
        this.state = useState({ loading: true, busy: false, ready: false, guideProfile: "general", error: "", question: "", messages: [], articles: [], notice: "", catalog: [], dataOpen: false, app: "", reference: "", dateFrom: "", dateTo: "" });
        onWillStart(async () => {
            try {
                const data = await this.orm.call("step.support.assistant", "get_bootstrap", []);
                Object.assign(this.state, { ready: data.ready, articles: data.articles, notice: data.notice, guideProfile: data.guide_profile });
                this.state.catalog = await this.orm.call("step.support.assistant", "get_business_catalog", []);
                this.state.app = this.state.catalog[0]?.key || "";
            } catch {
                this.state.error = "No fue posible cargar la ayuda. Reintenta o contacta a soporte.";
            } finally {
                this.state.loading = false;
            }
        });
        this.lastLength = 0;
        onPatched(() => {
            if (this.state.messages.length !== this.lastLength || this.state.busy) {
                this.transcript.el?.scrollTo({ top: this.transcript.el.scrollHeight, behavior: "smooth" });
                this.lastLength = this.state.messages.length;
            }
        });
    }

    async submit() {
        const question = this.state.question.trim();
        if (!question || question.length > 2000 || this.state.busy || this.state.loading) return;
        const previousQuestions = this.state.messages.filter(message => message.role === "user").slice(-4).map(message => message.text);
        this.state.messages.push({ id: this.state.messages.length, role: "user", text: question, sources: [] });
        this.state.question = "";
        this.state.busy = true;
        this.state.error = "";
        try {
            const result = await this.orm.call("step.support.assistant", "ask", [], { question, previous_questions: previousQuestions });
            this.addResult(result);
        } catch (error) {
            this.state.error = error.data?.message || "No fue posible enviar la consulta. Reintenta o contacta a soporte.";
            this.state.question = question;
            this.state.messages.pop();
        } finally {
            this.state.busy = false;
            this.composer.el?.focus();
        }
    }

    addResult(result) {
        this.state.messages.push({ id: this.state.messages.length, role: "assistant", text: result.answer, sources: result.sources, columns: result.columns || [], records: result.records || [] });
    }

    async queryData() {
        if (this.state.busy || this.state.loading || !this.state.app) return;
        this.state.busy = true;
        this.state.error = "";
        try {
            const result = await this.orm.call("step.support.assistant", "query_business", [], { app: this.state.app, reference: this.state.reference, date_from: this.state.dateFrom, date_to: this.state.dateTo });
            this.addResult(result);
        } catch (error) {
            this.state.error = error.data?.message || "No fue posible consultar los datos con tus permisos.";
        } finally {
            this.state.busy = false;
        }
    }

    openRecord(record) {
        return this.action.doAction({ type: "ir.actions.act_window", res_model: record.model, res_id: record.id, views: [[false, "form"]], target: "new" });
    }

    onKeydown(event) {
        if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
            event.preventDefault();
            this.submit();
        }
    }

    newConversation() {
        if (this.state.busy) return;
        this.state.messages = [];
        this.state.question = "";
        this.state.error = "";
    }

    openArticle(id) {
        return this.action.doAction({ type: "ir.actions.act_window", res_model: id < 0 ? "knowledge.article" : "step.assistant.article", res_id: Math.abs(id),
            views: [[false, "form"]], target: "new" });
    }
}

class AssistantLauncher extends Component {
    static template = "step_support_assistant.Launcher";
    static props = ["*"];
    setup() { this.assistant = useService("steps_assistant"); }
    open() { this.assistant.open(); }
}

class AssistantBubble extends Component {
    static template = "step_support_assistant.Bubble";
    static components = { StepsAssistant };
    static props = ["*"];
    setup() {
        this.assistant = useService("steps_assistant");
        this.state = useState(this.assistant.state);
        this.button = useRef("bubbleButton");
    }
    toggle() { this.state.open ? this.close() : this.assistant.open(); }
    close() { this.state.open = false; this.button.el?.focus(); }
    keydown(event) { if (event.key === "Escape") { event.preventDefault(); this.close(); } }
}

registry.category("services").add("steps_assistant", { start() {
    const state = reactive({ open: false, mounted: false });
    return { state, open() { state.mounted = true; state.open = true; } };
} });

registry.category("actions").add("step_support_assistant.chat", StepsAssistant);
registry.category("systray").add("step_support_assistant.launcher", { Component: AssistantLauncher }, { sequence: 5 });
registry.category("main_components").add("step_support_assistant.bubble", { Component: AssistantBubble });
