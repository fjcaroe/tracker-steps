// Progressive enhancement: the complete catalog and native details work without JS.
(function () {
    "use strict";
    function initStepsHomepage() {
        var root = document.querySelector(".step-demo-home");
        if (!root || root.dataset.stepsReady) return;
        root.dataset.stepsReady = "true";
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
                if (status) status.textContent = visible + " soluciones: " + button.textContent.trim().replace(/\s+12$/, "") + ".";
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
