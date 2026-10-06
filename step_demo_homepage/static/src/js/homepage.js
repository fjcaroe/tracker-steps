// Progressive enhancement: the complete catalog and native details work without JS.
(function () {
    "use strict";
    function initStepsHomepage() {
        var root = document.querySelector(".step-demo-home");
        if (!root || root.dataset.stepsReady) return;
        root.dataset.stepsReady = "true";
        var interest = root.querySelector("#steps-interest");
        var team = root.querySelector("#steps-team");
        var season = root.querySelector("#steps-season");
        var brief = root.querySelector("[data-brief-summary]");
        var send = root.querySelector("[data-brief-send]");
        var note = root.querySelector("[data-brief-note]");
        if (interest && team && season && brief && send) {
            var names = { campo: "Campo", personas: "Campo + Personas", integral: "Gestión integral" };
            function updateBrief() {
                var name = names[interest.value] || names.campo;
                brief.textContent = name + " · " + team.value + " · " + season.value;
                var body = "Hola, equipo Steps:\n\nQuiero una demo para evaluar " + name + ".\n" +
                    "Personas en la operación: " + team.value + ".\n" +
                    "Temporada: " + season.value + ".\n\n" +
                    "Me gustaría revisar el proceso, la carga inicial, la capacitación y el soporte, " +
                    "y recibir una cotización con licencias, implementación e integraciones detalladas.\n\n" +
                    "Empresa:\nNombre y teléfono de contacto:\n";
                send.href = "mailto:contacto@stepsapp.cl?subject=" + encodeURIComponent("Demo Steps · " + name) + "&body=" + encodeURIComponent(body);
                send.setAttribute("aria-label", "Preparar correo para solicitar una demo de " + name);
            }
            [interest, team, season].forEach(function (field) { field.addEventListener("change", updateBrief); });
            root.querySelectorAll("[data-plan]").forEach(function (link) {
                link.addEventListener("click", function () {
                    if (names[link.dataset.plan]) interest.value = link.dataset.plan;
                    updateBrief();
                });
            });
            if (note) note.textContent = "Abre tu aplicación de correo con el resumen. Revisa y envía cuando quieras; esta página no envía tus datos.";
            updateBrief();
        }
        var filters = root.querySelector(".steps-filters");
        var products = Array.from(root.querySelectorAll(".steps-product"));
        var status = root.querySelector("[data-filter-status]");
        if (filters && products.length) {
            filters.hidden = false;
            filters.addEventListener("click", function (event) {
                var button = event.target.closest("button[data-filter]");
                if (!button || !filters.contains(button)) return;
                filters.querySelectorAll("button").forEach(function (item) {
                    item.setAttribute("aria-pressed", String(item === button));
                });
                var visible = 0;
                products.forEach(function (product) {
                    product.hidden = button.dataset.filter !== "all" && product.dataset.category !== button.dataset.filter;
                    if (!product.hidden) visible += 1;
                });
                if (status) status.textContent = visible + " soluciones: " + button.textContent.trim().replace(/\s+\d+$/, "") + ".";
            });
        }
        var menu = root.querySelector(".steps-mobile-nav");
        if (menu) {
            menu.addEventListener("click", function (event) {
                if (event.target.closest("a")) menu.open = false;
            });
            document.addEventListener("keydown", function (event) {
                if (event.key === "Escape" && menu.open) {
                    menu.open = false;
                    menu.querySelector("summary").focus();
                }
            });
            document.addEventListener("click", function (event) {
                if (menu.open && !menu.contains(event.target)) menu.open = false;
            });
        }
    }
    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", initStepsHomepage, { once: true });
    } else {
        initStepsHomepage();
    }
})();
