// Run with the bundled @oai/artifact-tool, with NODE_PATH resolved by a
// workspace dependency junction beside a private copy of this builder.
import fs from 'node:fs/promises';
import path from 'node:path';
import { Workbook, SpreadsheetFile } from '@oai/artifact-tool';

const output = process.argv[2];
if (!output) throw new Error('Pass a private output directory');
await fs.mkdir(output, {recursive: true});
for (const [file, headers] of [
  ['sustancias_activas', ['Sustancias activas', 'Código', 'Observación', 'Activo', 'ID externo']],
  ['aptitudes_plaguicidas', ['Aptitud plaguicida', 'Código aptitud', 'Observación', 'ID externo']],
]) {
  const book = Workbook.create();
  const sheet = book.worksheets.add('Importar');
  const last = String.fromCharCode(64 + headers.length);
  sheet.getRange(`A1:${last}1`).values = [headers];
  sheet.getRange(`A1:${last}2`).format.font = {name: 'Arial', size: 11};
  sheet.getRange(`A1:${last}1`).format = {
    fill: '#E7EDF2', font: {name: 'Arial', bold: true, color: '#172B40'}, rowHeight: 26,
  };
  sheet.getRange(`A1:${last}2`).format.columnWidth = 26;
  sheet.getRange('C1:C2').format.columnWidth = 42;
  sheet.getRange(`A2:${last}2000`).setNumberFormat('@');
  sheet.freezePanes.freezeRows(1);
  book.recalculate();
  console.log((await book.inspect({kind: 'table', range: `Importar!A1:${last}2`, tableMaxRows: 2, tableMaxCols: 5})).ndjson);
  const preview = await book.render({sheetName: 'Importar', range: `A1:${last}3`, scale: 1, format: 'png'});
  await fs.writeFile(path.join(output, file + '.png'), new Uint8Array(await preview.arrayBuffer()));
  await (await SpreadsheetFile.exportXlsx(book)).save(path.join(output, file + '.xlsx'));
}
