/** @odoo-module **/

// Odoo makes a separate editable copy of the form for each Helpdesk team.
// Translate the visible copy while retaining its input names and submit code.
function prepareSupportForm() {
    const page = document.querySelector('.steps-support-form');
    const form = page?.querySelector('#helpdesk_ticket_form');
    if (!form) return;

    const title = page.querySelector('h2.text-muted');
    if (title) {
        title.textContent = 'Datos de la solicitud';
        title.classList.add('steps-support-form-title');
    }

    const labels = {
        partner_name: 'Nombre completo',
        partner_phone: 'Teléfono',
        partner_email: 'Correo electrónico',
        partner_company_name: 'Empresa',
        name: 'Asunto',
        description: '¿Qué sucedió?',
        Attachment: 'Archivo adjunto',
    };
    for (const [name, translation] of Object.entries(labels)) {
        const input = [...form.querySelectorAll('[name]')].find((field) => field.name === name);
        const label = input?.closest('.s_website_form_field')?.querySelector('.s_website_form_label_content');
        if (label) label.textContent = translation;
    }
    const submit = form.querySelector('.s_website_form_send');
    if (submit) submit.textContent = 'Enviar solicitud';
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', prepareSupportForm, {once: true});
} else {
    prepareSupportForm();
}
