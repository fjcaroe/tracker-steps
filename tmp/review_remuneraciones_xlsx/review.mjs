import fs from "node:fs/promises";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const inputPath = "C:/Users/tito4/Downloads/LIBRO DT EMCA junio 2026.xlsx";
const outputDir = "C:/Users/tito4/Documents/Odoo/tmp/review_remuneraciones_xlsx";

const input = await FileBlob.load(inputPath);
const workbook = await SpreadsheetFile.importXlsx(input);
const overview = await workbook.inspect({
  kind: "workbook,sheet,table,formula,definedName,drawing",
  maxChars: 12000,
  tableMaxRows: 8,
  tableMaxCols: 24,
  tableMaxCellChars: 80,
});
await fs.writeFile(`${outputDir}/overview.ndjson`, overview.ndjson, "utf8");

const preview = await workbook.render({
  sheetName: "Libro impreso2",
  range: "A1:X92",
  scale: 1.5,
  format: "png",
});
await fs.writeFile(`${outputDir}/libro-impreso2.png`, new Uint8Array(await preview.arrayBuffer()));

process.stdout.write(overview.ndjson.slice(0, 12000));
