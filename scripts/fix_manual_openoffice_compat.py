from pathlib import Path

from docx import Document
from docx.enum.style import WD_STYLE_TYPE
from docx.shared import Pt, RGBColor


MANUAL = Path("docs/Manual_Steps_Tracker.docx")
SECTION_STYLE = "Section Title Manual"


doc = Document(MANUAL)

# OpenOffice assigns its own outline numbering to Word's built-in Heading 1
# style. The manual already carries explicit chapter numbers, so that produced
# duplicated titles such as "3. 3. Resumen de jornada". A custom style keeps
# the same visual hierarchy without triggering the automatic numbering.
if SECTION_STYLE in [style.name for style in doc.styles]:
    section_style = doc.styles[SECTION_STYLE]
else:
    section_style = doc.styles.add_style(SECTION_STYLE, WD_STYLE_TYPE.PARAGRAPH)

section_style.base_style = doc.styles["Normal"]
section_style.font.name = "Calibri"
section_style.font.size = Pt(16)
section_style.font.bold = True
section_style.font.color.rgb = RGBColor(0x2E, 0x74, 0xB5)
section_style.paragraph_format.keep_with_next = True
section_style.paragraph_format.keep_together = True
section_style.paragraph_format.space_before = Pt(18)
section_style.paragraph_format.space_after = Pt(10)

updated = 0
for paragraph in doc.paragraphs:
    if paragraph.style.name == "Heading 1":
        paragraph.style = section_style
        updated += 1

if updated != 18:
    raise RuntimeError(f"Se esperaban 18 títulos de sección y se encontraron {updated}.")

doc.save(MANUAL)
print(f"Compatibilidad de OpenOffice aplicada a {updated} títulos: {MANUAL}")
