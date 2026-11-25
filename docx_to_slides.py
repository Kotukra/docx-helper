"""Convert DOCX text, headings, tables and embedded pictures into slide markup."""
import hashlib
import os
from docx import Document
from docx.oxml.ns import qn
from docx.text.paragraph import Paragraph


def _default_asset_dir() -> str:
    root = os.environ.get("APPDATA", os.path.expanduser("~"))
    return os.path.join(root, "GostDocumentGenerator", "imported_assets")


def _extract_images(document, asset_dir: str) -> list[tuple[str, str, str]]:
    os.makedirs(asset_dir, exist_ok=True)
    images = []
    current_title = "Иллюстрация"
    # Walk the document body in XML order so paragraphs inside table cells
    # are included as well as top-level paragraphs.
    for paragraph_xml in document.element.body.xpath(".//w:p"):
        paragraph = Paragraph(paragraph_xml, document)
        style = paragraph.style.name if paragraph.style else "Normal"
        if style.startswith(("Heading 1", "Заголовок 1")) and paragraph.text.strip():
            current_title = paragraph.text.strip()
        for blip in paragraph._p.xpath(".//a:blip"):
            rid = blip.get(qn("r:embed"))
            relation = document.part.rels.get(rid) if rid else None
            # An image relationship may point to an external URL. Such links
            # have no target_part/blob to extract and must not abort import.
            if (relation is None or relation.is_external
                    or not relation.reltype.endswith("/image")):
                continue
            image_part = relation.target_part
            data = image_part.blob
            extension = str(image_part.partname).rsplit(".", 1)[-1].lower()
            if not extension.isalnum():
                extension = "png"
            filename = hashlib.sha256(data).hexdigest() + "." + extension
            destination = os.path.join(asset_dir, filename)
            if not os.path.isfile(destination):
                with open(destination, "wb") as image_file:
                    image_file.write(data)
            descriptions = paragraph._p.xpath(".//wp:docPr/@descr")
            caption = descriptions[0].strip() if descriptions and descriptions[0].strip() else "Иллюстрация"
            images.append((current_title, caption, destination))
    return images


def docx_to_presentation_markup(path, max_items: int = 6, asset_dir: str | None = None) -> str:
    document = Document(str(path))
    paragraphs = [(paragraph.style.name if paragraph.style else "Normal", paragraph.text.strip())
                  for paragraph in document.paragraphs if paragraph.text.strip()]
    extracted_images = _extract_images(document, asset_dir or _default_asset_dir())
    if not paragraphs and not document.tables and not extracted_images:
        raise ValueError("В DOCX не найдено текста или таблиц для переноса")
    max_items = max(1, int(max_items))
    lines = []
    if paragraphs:
        title = paragraphs[0][1]
        lines.extend(["[SLIDE: title]", f"# {title}"])
        if len(paragraphs) > 1:
            lines.append(f"[SUB: {paragraphs[1][1][:180]}]")

    groups = []
    current_title = "Основные положения"
    current_items = []
    for style, text in paragraphs[1:] if paragraphs else []:
        if style.startswith("Heading 1") or style.startswith("Заголовок 1"):
            if current_items:
                groups.append((current_title, current_items))
                current_items = []
            current_title = text
        elif style.startswith(("Heading", "Заголовок")):
            current_items.append(f"{text}")
        else:
            current_items.append(text)
    if current_items:
        groups.append((current_title, current_items))

    for title, items in groups:
        for start in range(0, len(items), max_items):
            chunk = items[start:start + max_items]
            lines.extend(["---", "[SLIDE: bullets]", f"# {title}"])
            lines.extend(f"- {item[:180]}" for item in chunk)

    for table_index, table in enumerate(document.tables, start=1):
        rows = []
        for row in table.rows:
            values = [cell.text.strip().replace("|", "／").replace("\n", " ") for cell in row.cells]
            if any(values):
                rows.append("| " + " | ".join(values) + " |")
        if rows:
            lines.extend(["---", "[SLIDE: table]", f"# Таблица {table_index}", "[TABLE]", *rows, "[/TABLE]"])

    for title, caption, image_path in extracted_images:
        lines.extend(["---", "[SLIDE: image_full]", f"# {title}", f"[IMAGE: {image_path} | {caption}]"])
    return "\n".join(lines)
