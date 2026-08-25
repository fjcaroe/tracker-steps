from pathlib import Path
from PIL import Image, ImageOps, ImageDraw

root = Path(r"C:\Users\tito4\Documents\Odoo\tmp\nuevasaplicaciones_review\rendered")
for folder in root.iterdir():
    if not folder.is_dir():
        continue
    pages = sorted(folder.glob("page-*.png"))
    if not pages:
        continue
    thumb_w = 850
    margin = 24
    rendered = []
    for page in pages:
        image = Image.open(page).convert("RGB")
        thumb_h = round(image.height * thumb_w / image.width)
        image = image.resize((thumb_w, thumb_h))
        canvas = Image.new("RGB", (thumb_w + margin * 2, thumb_h + 60), "white")
        canvas.paste(image, (margin, 36))
        ImageDraw.Draw(canvas).text((margin, 10), page.stem, fill="black")
        rendered.append(canvas)
    rows = []
    for idx in range(0, len(rendered), 2):
        pair = rendered[idx:idx+2]
        row_h = max(item.height for item in pair)
        row = Image.new("RGB", (sum(item.width for item in pair), row_h), "#d8d8d8")
        x = 0
        for item in pair:
            row.paste(item, (x, 0))
            x += item.width
        rows.append(row)
    sheet = Image.new("RGB", (max(row.width for row in rows), sum(row.height for row in rows)), "#bdbdbd")
    y = 0
    for row in rows:
        sheet.paste(row, (0, y))
        y += row.height
    sheet.save(folder / "contact-sheet.jpg", quality=88)
