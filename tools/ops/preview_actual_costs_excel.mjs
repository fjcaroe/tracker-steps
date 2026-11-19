// Read-only visual verification of the exported Excel; never rewrite the input.
import fs from "node:fs/promises";
import path from "node:path";
import {FileBlob, SpreadsheetFile} from "@oai/artifact-tool";

const [input, output] = process.argv.slice(2);
if (!input || !output) throw new Error("Usage: preview_actual_costs_excel.mjs input.xlsx output-directory");
const workbook = await SpreadsheetFile.importXlsx(await FileBlob.load(input));
const sheet = workbook.worksheets.getItemAt(0);
const name = sheet.name;
await fs.mkdir(output, {recursive:true});
const summary = await workbook.inspect({kind:"region",sheetId:name,range:"A2:Q5",
    maxChars:2800,tableMaxRows:4,tableMaxCols:17,tableMaxCellChars:50});
console.log(summary.ndjson);
for (const [label, range] of [["detail","A2:J6"],["amounts","K2:Q6"]]) {
    const rendered = await workbook.render({sheetName:name,range,scale:1.4,format:"png"});
    await fs.writeFile(path.join(output,label+".png"),new Uint8Array(await rendered.arrayBuffer()));
}
console.log("ACTUAL_COSTS_PREVIEW_OK "+JSON.stringify({sheet:name,views:2}));
