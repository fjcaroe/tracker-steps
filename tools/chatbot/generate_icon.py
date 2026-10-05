"""Generate the PNG menu icon required by Odoo from simple vector-like shapes."""
from pathlib import Path
from PIL import Image, ImageDraw

root = Path(__file__).resolve().parents[2]
image = Image.new("RGBA", (512, 512), (0, 0, 0, 0))
draw = ImageDraw.Draw(image)
draw.rounded_rectangle((0, 0, 511, 511), radius=112, fill="#123c33")
draw.polygon([(128, 120), (384, 120), (384, 320), (248, 320), (168, 392), (168, 320), (128, 320)], fill="#d8ff62")
for endpoint, y in [(328, 188), (288, 244)]:
    draw.line([(184, y), (endpoint, y)], fill="#123c33", width=28)
    draw.ellipse((170, y - 14, 198, y + 14), fill="#123c33")
    draw.ellipse((endpoint - 14, y - 14, endpoint + 14, y + 14), fill="#123c33")
image.resize((128, 128), Image.Resampling.LANCZOS).save(root / "step_support_assistant/static/description/icon.png")
