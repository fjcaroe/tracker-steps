/** @odoo-module **/

// The Helpdesk app uses several routes, including /odoo/all-tickets. Its menu
// XML IDs identify the active app more reliably than the URL or translated name.
function refreshHelpdeskScope() {
    const helpdeskRoutes = [
        '/odoo/helpdesk', '/odoo/all-tickets', '/odoo/my-tickets',
        '/odoo/tickets-analysis', '/odoo/sla-status-analysis',
        '/odoo/helpdesk-teams', '/odoo/sla-policies',
    ];
    const path = window.location.pathname;
    const routeMatch = helpdeskRoutes.some((route) => path === route || path.startsWith(`${route}/`));
    const active = routeMatch || Boolean(document.querySelector('.o_main_navbar [data-menu-xmlid^="helpdesk."]'));
    document.body.classList.toggle('o_steps_helpdesk', active);
}

function start() {
    let queued = false;
    const observer = new MutationObserver(() => {
        if (queued) return;
        queued = true;
        requestAnimationFrame(() => {
            queued = false;
            refreshHelpdeskScope();
        });
    });
    observer.observe(document.body, {childList: true, subtree: true});
    refreshHelpdeskScope();
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', start, {once: true});
} else {
    start();
}
