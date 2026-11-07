/** Browser check of the native demo walkthrough. Credentials arrive on stdin. */
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { chromium } = require("playwright");

async function main() {
    const request = JSON.parse(fs.readFileSync(0, "utf8"));
    const [executablePath, output, origin, sha256] = process.argv.slice(2);
    assert(path.isAbsolute(output));
    assert(["https://ecoplantas.stepsapp.cl", "http://127.0.0.1:41476"].includes(origin));
    assert(/^[a-f0-9]{64}$/.test(sha256));
    fs.mkdirSync(output, { recursive: true });
    const browser = await chromium.launch({ executablePath, headless: true });
    const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
    page.setDefaultTimeout(25000);
    const failures = [];
    page.on("pageerror", error => failures.push(error.message));
    const save = name => page.screenshot({ path: path.join(output, name + ".png") });
    const board = () => page.locator(".o_ecoplantas_dashboard");
    const screenshot = async name => {
        await board().waitFor();
        await page.waitForFunction(() => document.querySelector(".eco-hero-visual img")?.naturalWidth > 0);
        await save(name);
    };
    const contains = text => page.waitForFunction(value =>
        document.body.innerText.includes(value) ||
        Array.from(document.querySelectorAll(".o_form_view input")).some(input => input.value.includes(value)), text);
    const openBoard = async () => {
        await page.goto(origin + "/odoo/invernadero", { waitUntil: "domcontentloaded" });
        await board().waitFor();
    };
    const destinations = [];
    const visit = async (button, selector, expected, capture) => {
        await board().getByRole("button", { name: button, exact: true }).click();
        await page.locator(selector).first().waitFor();
        await contains(expected);
        if (capture) await save(capture);
        destinations.push(expected);
        await openBoard();
    };

    try {
        await page.goto(origin + "/web/login?redirect=%2Fodoo", { waitUntil: "domcontentloaded" });
        await page.locator('input[name="login"]').fill(request.login);
        await page.locator('input[name="password"]').fill(request.password);
        await page.locator('form.oe_login_form button[type="submit"]').click();
        await screenshot("portada");
        assert.equal(await board().locator(".eco-stages article").count(), 4);
        assert.deepEqual((await board().locator(".eco-metrics strong").allTextContents()).slice(0, 2), ["100", "2"]);
        assert.equal(await page.locator(".o_main_navbar").evaluate(el => getComputedStyle(el).backgroundColor), "rgb(23, 63, 51)");
        assert(await board().locator(".eco-stage-link").first().isVisible());

        const form = ".o_ecoplantas_native_form";
        await visit("Abrir recepción", form, "[DEMO] Semillas y sustrato");
        await visit("Abrir orden", form, "Plantín de tomate [DEMO]", "manufactura");
        await visit("Abrir control", form, "Revisión visual del lote de plantines [DEMO]");
        await visit("Abrir despacho", form, "[DEMO] Despacho de plantines", "despacho");
        await visit(/^Labores de cultivo/, ".o_kanban_view",
            "Registrar riego y condición de bandejas [DEMO]", "labores");
        await visit(/^Mantenimiento de riego/, form, "Revisar bomba y goteros [DEMO]");
        await visit(/^Trazabilidad de plantines/, ".o_list_view", "Lotes de plantines");

        await page.setViewportSize({ width: 390, height: 844 });
        await openBoard();
        await screenshot("portada-movil");
        assert(await board().evaluate(node => node.scrollWidth <= node.clientWidth + 1));
        await board().getByRole("heading", { name: "El lote, paso a paso" }).scrollIntoViewIfNeeded();
        await save("recorrido-movil");
        assert.deepEqual(failures, []);
        const proof = { sha256, origin, home: true, desktop: true, mobile: true, destinations };
        fs.writeFileSync(path.join(output, "browser-proof.json"), JSON.stringify(proof, null, 2));
        console.log("ECOPLANTAS_LAYOUT_BROWSER_OK", JSON.stringify(proof));
    } catch (error) {
        await save("diagnostic").catch(() => {});
        const sanitize = value => value.replaceAll(request.login, "[usuario]").replaceAll(request.password, "[clave]");
        process.stderr.write(JSON.stringify({ path: new URL(page.url()).pathname,
            failures: failures.map(sanitize), error: sanitize(error.message) }) + "\n");
        process.exitCode = 1;
    } finally {
        await browser.close();
    }
}

main().catch(error => { console.error(error.message); process.exitCode = 1; });
