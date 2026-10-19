// Read-only visual QA of the XLSX produced by Odoo. Run a copy of this file
// beside a node_modules junction to the bundled workspace dependency runtime.
import fs from 'node:fs/promises';
import {FileBlob, SpreadsheetFile} from '@oai/artifact-tool';

const [input, output] = process.argv.slice(2);
if (!input || !output) throw new Error('Usage: node render_sag_annex.mjs input.xlsx output.png');
const workbook = await SpreadsheetFile.importXlsx(await FileBlob.load(input));
const preview = await workbook.render({sheetName:'Anexo despacho', range:'A1:I12', scale:1, format:'png'});
await fs.writeFile(output, new Uint8Array(await preview.arrayBuffer()));
console.log('SAG_XLSX_PREVIEW_OK');
