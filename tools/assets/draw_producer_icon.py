from PIL import Image, ImageDraw

scale = 4
image = Image.new("RGBA", (256 * scale, 256 * scale), (0, 0, 0, 0))
draw = ImageDraw.Draw(image)
def box(coords):
    return tuple(round(value * scale) for value in coords)

draw.rounded_rectangle(box((4, 4, 252, 252)), radius=54 * scale, fill="#0b5d48")
draw.arc(box((51, 165, 205, 248)), 200, 340, fill="white", width=12 * scale)
draw.line(box((73, 170, 73, 205)), fill="white", width=10 * scale)
draw.line(box((183, 170, 183, 205)), fill="white", width=10 * scale)
draw.ellipse(box((103, 108, 153, 158)), outline="white", width=11 * scale)
draw.polygon([(128*scale, 99*scale), (89*scale, 61*scale), (81*scale, 65*scale),
              (87*scale, 87*scale), (105*scale, 98*scale)], fill="#bedf71")
draw.polygon([(128*scale, 99*scale), (167*scale, 61*scale), (175*scale, 65*scale),
              (169*scale, 87*scale), (151*scale, 98*scale)], fill="#bedf71")
draw.line(box((128, 65, 128, 104)), fill="white", width=6 * scale)
image.resize((256, 256), Image.Resampling.LANCZOS).save(
    "step_producers/static/description/icon.png")
