// UI regression for the nursery worker, device outbox, reload and sync.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const http = require("node:http");
const path = require("node:path");
const { chromium } = require("playwright");

const assets = path.join(__dirname, "../../step_nursery_operations/static/src/offline");
const types = {html:"text/html; charset=utf-8", js:"text/javascript; charset=utf-8", css:"text/css; charset=utf-8"};
const recorded = [];
const server = http.createServer((req, res) => {
    const url = new URL(req.url, "http://localhost");
    const send = data => {
        res.writeHead(200, {"Content-Type":"application/json"});
        res.end(JSON.stringify(data));
    };
    if (url.pathname === "/nursery-offline/session") return send({uid:31, csrf:"qa-only", companies:[{id:9,name:"Vivero QA"}]});
    if (url.pathname === "/nursery-offline/orders/9") return send([{id:76,name:"MO-QA-76"}]);
    if (url.pathname === "/nursery-offline/sync" && req.method === "POST") {
        let body = "";
        req.on("data", part => { body += part; });
        req.on("end", () => {
            const match = body.match(/\r\n(\[\{[^\r\n]+\}\])\r\n/);
            assert.ok(match);
            const captures = JSON.parse(match[1]);
            recorded.push(...captures);
            send(captures.map(item => ({id:item.id,ok:true,event_id:71})));
        });
        return;
    }
    const file = url.pathname === "/nursery-offline/" ? "index.html" : path.basename(url.pathname);
    if (!["index.html", "sw.js", "app.js", "offline.css"].includes(file)) {
        res.writeHead(404); return res.end();
    }
    res.writeHead(200, {"Content-Type":types[file.split(".").pop()]});
    return res.end(fs.readFileSync(path.join(assets,file)));
});

(async () => {
    await new Promise(resolve => server.listen(0, "127.0.0.1", resolve));
    const browser = await chromium.launch(process.env.NURSERY_TEST_CHROME ?
        {executablePath:process.env.NURSERY_TEST_CHROME} : {});
    try {
        const ctx = await browser.newContext();
        const page = await ctx.newPage();
        const failures = [];
        page.on("pageerror", error => failures.push(error.message));
        await page.goto("http://127.0.0.1:" + server.address().port + "/nursery-offline/");
        await page.getByRole("button", {name:"Descargar órdenes"}).click();
        await page.getByText("Órdenes descargadas. Puede registrar", {exact:false}).waitFor();
        await page.waitForFunction(() => !!navigator.serviceWorker.controller);
        await ctx.setOffline(true);
        await page.reload();
        await page.getByText("Sin conexión.", {exact:false}).waitFor();
        await page.locator("#order").selectOption("76");
        await page.locator("#sample").fill("50");
        await page.locator("#germinated").fill("42");
        await page.getByRole("button", {name:"Guardar captura"}).click();
        await page.getByText("1 por sincronizar").waitFor();
        await page.reload();
        await page.getByText("1 por sincronizar").waitFor();
        await ctx.setOffline(false);
        await page.getByText("1 sincronizadas. 0 pendientes.").waitFor();
        assert.equal(recorded.length, 1);
        assert.deepEqual([recorded[0].kind, recorded[0].order_id, recorded[0].sample, recorded[0].germinated],
            ["germination", 76, 50, 42]);
        assert.deepEqual(failures, []);
        console.log("Offline UI: cache, offline reload, persisted capture and online sync passed.");
    } finally {
        await browser.close();
    }
})().catch(error => { console.error(error); process.exitCode = 1; }).finally(() => server.close());
