// Read-only visual inspection of the native Odoo export; no workbook rewrite.
import fs from 'node:fs/promises';
import path from 'node:path';
import {FileBlob, SpreadsheetFile} from '@oai/artifact-tool';

const input = process.argv[2];
if (!input) throw new Error('Provide the generated Packing List XLSX path');
const book = await SpreadsheetFile.importXlsx(await FileBlob.load(input));
console.log((await book.inspect({kind:'workbook,sheet,table', maxChars:2000, tableMaxRows:3, tableMaxCols:10})).ndjson);
const sheet = book.worksheets.getItemAt(0);
const preview = await book.render({sheetName:sheet.name, range:'A1:J18', scale:1.3, format:'png'});
const output = path.join(path.dirname(input),'packing-excel-preview.png');
await fs.writeFile(output,new Uint8Array(await preview.arrayBuffer()));
console.log('PACKING_EXCEL_PREVIEW_OK ' + output);
