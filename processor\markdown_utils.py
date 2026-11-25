"""Markdown -> DOCX parser. Keeps source markup intact until rendering."""
import re
from pathlib import Path
from docx import Document
from docx.shared import Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from .footnotes import add_text_with_footnotes
from .gost_builder import add_gost_table, insert_image_placeholder
from caption_numbering import CaptionNumberer
from markdown_editors import parse_image_marker_options

INLINE = re.compile(r'(\[\^[^\]]+\]|\*\*.+?\*\*|__.+?__|(?<!\*)\*[^*\n]+\*(?!\*)|(?<!_)_[^_\n]+_(?!_)|~~.+?~~|`[^`]+`)')
IMAGE_MD = re.compile(r'^!\[([^\]]*)\]\((.+?)(?:\s+"([^"]*)")?\)$')
IMAGE_MARKER = re.compile(r'^\[IMAGE:\s*(.*?)\]$', re.I)


def _font(run, name, size):
    run.font.name = name
    run.font.size = size


def _inline(p, text, font_name, font_size, fnmgr=None):
    pos = 0
    for m in INLINE.finditer(text):
        if m.start() > pos:
            r = p.add_run(text[pos:m.start()]); _font(r, font_name, font_size)
        token = m.group(0)
        if token.startswith('[^'):
            if fnmgr is not None:
                add_text_with_footnotes(p, token, fnmgr)
            else:
                r = p.add_run(token); _font(r, font_name, font_size)
        elif token.startswith(('**', '__')):
            r = p.add_run(token[2:-2]); r.bold = True; _font(r, font_name, font_size)
        elif token.startswith('~~'):
            r = p.add_run(token[2:-2]); r.font.strike = True; _font(r, font_name, font_size)
        elif token.startswith('`'):
            r = p.add_run(token[1:-1]); _font(r, 'Courier New', font_size)
        else:
            r = p.add_run(token[1:-1]); r.italic = True; _font(r, font_name, font_size)
        pos = m.end()
    if pos < len(text):
        r = p.add_run(text[pos:]); _font(r, font_name, font_size)


def _split_row(line):
    line = line.strip()
    if line.startswith('|'): line = line[1:]
    if line.endswith('|') and not line.endswith(r'\\|'): line = line[:-1]
    cells, buf, escaped = [], [], False
    for ch in line:
        if escaped: buf.append(ch); escaped = False
        elif ch == '\\': escaped = True
        elif ch == '|': cells.append(''.join(buf).strip()); buf = []
        else: buf.append(ch)
    if escaped: buf.append('\\')
    cells.append(''.join(buf).strip())
    return cells


def _separator(line):
    cells = _split_row(line)
    return bool(cells) and all(re.fullmatch(r':?-{3,}:?', c.replace(' ', '')) for c in cells)


def _image_path(path, base_dir=None):
    p = Path(path.strip().strip('<>').strip('"\'' )).expanduser()
    candidates = [p] if p.is_absolute() else ([Path(base_dir)/p] if base_dir else []) + [Path.cwd()/p]
    for candidate in candidates:
        try:
            if candidate.is_file(): return str(candidate.resolve())
        except OSError: pass
    return None


def _add_image(doc, path, caption, base_dir=None, width_cm=15, alignment="center"):
    resolved = _image_path(path, base_dir)
    if not resolved:
        insert_image_placeholder(doc, f'[Файл изображения не найден: {caption or path}]', width_cm)
        return False
    p = doc.add_paragraph(); p.alignment = {
        "left": WD_ALIGN_PARAGRAPH.LEFT, "center": WD_ALIGN_PARAGRAPH.CENTER,
        "right": WD_ALIGN_PARAGRAPH.RIGHT}.get(alignment, WD_ALIGN_PARAGRAPH.CENTER)
    p.paragraph_format.first_line_indent = Cm(0)
    p.paragraph_format.keep_with_next = bool(caption)
    try: p.add_run().add_picture(resolved, width=Cm(width_cm))
    except Exception:
        p.add_run(f'[Не удалось вставить изображение: {path}]'); return False
    if caption:
        cap = doc.add_paragraph(); cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
        cap.paragraph_format.first_line_indent = Cm(0); cap.paragraph_format.keep_together = True
        r = cap.add_run(caption); _font(r, 'Times New Roman', Pt(14))
    return True


def _add_code(doc, code_lines, settings):
    for line in code_lines:
        p = doc.add_paragraph(); pf = p.paragraph_format
        p.alignment = WD_ALIGN_PARAGRAPH.LEFT
        pf.left_indent = Cm(float(settings.get('code_left_indent', 1.27)))
        pf.right_indent = Cm(float(settings.get('code_right_indent', 0)))
        pf.first_line_indent = Cm(float(settings.get('code_first_line_indent', 0)))
        pf.line_spacing = float(settings.get('code_line_spacing', 1.0))
        pf.space_before = Pt(float(settings.get('code_space_before', 0)))
        pf.space_after = Pt(float(settings.get('code_space_after', 0)))
        pf.keep_together = True
        code_align = settings.get('code_alignment', 'left')
        p.alignment = {'left': WD_ALIGN_PARAGRAPH.LEFT, 'center': WD_ALIGN_PARAGRAPH.CENTER,
                       'right': WD_ALIGN_PARAGRAPH.RIGHT, 'justify': WD_ALIGN_PARAGRAPH.JUSTIFY}.get(
                           code_align, WD_ALIGN_PARAGRAPH.LEFT)
        r = p.add_run(line.expandtabs(4))
        _font(r, settings.get('code_font_name', 'Times New Roman'), Pt(float(settings.get('code_font_size', 11))))
        r.font.color.rgb = RGBColor(0, 0, 0)
        r._element.get_or_add_rPr().rFonts.set('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}eastAsia', settings.get('code_font_name', 'Times New Roman'))


def markdown_to_docx(md_text: str, doc: Document,
                     font_name: str = 'Times New Roman', font_size: Pt = Pt(14),
                     alignment=WD_ALIGN_PARAGRAPH.JUSTIFY,
                     first_line_indent: Cm = Cm(1.25),
                     left_indent: Cm = Cm(0), right_indent: Cm = Cm(0),
                     debug: bool = False, fnmgr=None, settings=None, base_dir=None,
                     caption_numberer=None) -> None:
    settings = settings or {}
    caption_numberer = caption_numberer or CaptionNumberer(settings.get('auto_number_captions', True))
    lines = md_text.replace('\r\n', '\n').replace('\r', '\n').split('\n')
    i = 0
    while i < len(lines):
        raw, line = lines[i], lines[i].strip()
        if not line: i += 1; continue

        appendix_marker = re.match(r'^\[APPENDIX:\s*(.*?)\s*\]$', line, re.I)
        if appendix_marker:
            title = caption_numberer.format('appendix', appendix_marker.group(1).strip())
            paragraph = doc.add_paragraph(style='Heading 1')
            paragraph.paragraph_format.page_break_before = True
            _inline(paragraph, title, font_name, font_size, fnmgr)
            i += 1; continue

        # Fenced code block; empty lines inside the block are preserved.
        if line.startswith(('```', '~~~')):
            fence = line[:3]; code = []; i += 1
            while i < len(lines) and not lines[i].strip().startswith(fence):
                code.append(lines[i].rstrip()); i += 1
            if i < len(lines): i += 1
            _add_code(doc, code, settings); continue

        # Markdown image syntax ![alt](path "caption").
        im = IMAGE_MD.match(line)
        if im:
            alt, path, title = im.groups()
            caption = caption_numberer.format('figure', title or alt)
            _add_image(doc, path, caption, base_dir, float(settings.get('gost_img_width', 15.0))); i += 1; continue
        # Legacy marker [IMAGE: caption] or extended [IMAGE: path | caption].
        im = IMAGE_MARKER.match(line)
        if im:
            payload = im.group(1).strip()
            if ' | ' in payload:
                path, caption, width, alignment = parse_image_marker_options(line)
                caption = caption_numberer.format('figure', caption)
                width = width or float(settings.get('gost_img_width', 15.0))
                _add_image(doc, path, caption, base_dir, width, alignment)
            else:
                caption = caption_numberer.format('figure', payload)
                insert_image_placeholder(doc, caption, width_cm=float(settings.get('gost_img_width', 15.0)))
            i += 1; continue

        table_caption = None
        table_marker = re.match(r'^\[TABLE:\s*(.*?)\s*\]$', line, re.I)
        if table_marker:
            table_caption = table_marker.group(1).strip()
            i += 1
            while i < len(lines) and not lines[i].strip():
                i += 1
            if i < len(lines):
                raw, line = lines[i], lines[i].strip()

        # GFM table with optional alignment row.
        if i + 1 < len(lines) and '|' in line and _separator(lines[i+1].strip()):
            rows = [_split_row(line)]; alignments = []
            for c in _split_row(lines[i+1].strip()):
                c = c.replace(' ', '')
                alignments.append('center' if c.startswith(':') and c.endswith(':') else 'right' if c.endswith(':') else 'left' if c.startswith(':') else 'center')
            i += 2
            while i < len(lines) and lines[i].strip() and '|' in lines[i]: rows.append(_split_row(lines[i])); i += 1
            width = max(len(r) for r in rows)
            rows = [r + ['']*(width-len(r)) for r in rows]
            caption = caption_numberer.format('table', table_caption) if table_caption is not None else None
            add_gost_table(doc, rows, caption=caption)
            table = doc.tables[-1]
            for row_idx, row in enumerate(table.rows):
                for j, cell in enumerate(row.cells):
                    value = cell.text
                    cell.text = ''
                    p = cell.paragraphs[0]
                    p.alignment = {'left': WD_ALIGN_PARAGRAPH.LEFT, 'right': WD_ALIGN_PARAGRAPH.RIGHT, 'center': WD_ALIGN_PARAGRAPH.CENTER}.get(alignments[j] if j < len(alignments) else 'center', WD_ALIGN_PARAGRAPH.CENTER)
                    p.paragraph_format.first_line_indent = Cm(0)
                    _inline(p, value, font_name, Pt(12), fnmgr)
                    if row_idx == 0:
                        for r in p.runs: r.bold = True
            continue

        # Headings: Markdown plus common academic numbering.
        h = re.match(r'^(#{1,6})\s+(.+)$', line)
        n1 = re.match(r'^\d+\.\s+[А-ЯЁA-Z].*$', line)
        n2 = re.match(r'^\d+\.\d+\s+.+$', line)
        n3 = re.match(r'^\d+\.\d+\.\d+\s+.+$', line)
        named = re.match(r'^(ВВЕДЕНИЕ|ЗАКЛЮЧЕНИЕ|СПИСОК ИСПОЛЬЗОВАННЫХ ИСТОЧНИКОВ|ПРИЛОЖЕНИЯ|ПРИЛОЖЕНИЕ(?:\s+[А-ЯЁA-Z0-9]+)?)$', line, re.I)
        if h or n1 or n2 or n3 or named:
            level = len(h.group(1)) if h else (3 if n3 else (2 if n2 else 1))
            style = 'Heading 1' if level == 1 else ('Heading 2' if level == 2 else 'Heading 3')
            if style not in [s.name for s in doc.styles]: style = 'Heading 2'
            p = doc.add_paragraph(style=style); p.paragraph_format.keep_with_next = True
            _inline(p, h.group(2) if h else line, font_name, font_size, fnmgr); i += 1; continue

        # Nested ordered/unordered lists; indentation is based on source spaces.
        lm = re.match(r'^(\s*)([-*+]|\d+[.)])\s+(.+)$', raw)
        if lm:
            indent, marker, content = lm.groups(); level = min(len(indent.expandtabs(4)) // 2, 8)
            p = doc.add_paragraph(style='List Number' if marker[0].isdigit() else 'List Bullet')
            p.paragraph_format.left_indent = Cm(0.63 * (level + 1))
            p.paragraph_format.first_line_indent = Cm(-0.32)
            p.paragraph_format.keep_together = True
            _inline(p, content, font_name, font_size, fnmgr); i += 1; continue

        # Consecutive blockquote lines become one indented italic paragraph.
        if line.startswith('>'):
            quote = []
            while i < len(lines) and lines[i].strip().startswith('>'):
                quote.append(lines[i].strip()[1:].lstrip()); i += 1
            p = doc.add_paragraph(); p.paragraph_format.left_indent = Cm(1.25)
            p.paragraph_format.first_line_indent = Cm(0); p.paragraph_format.keep_together = True
            _inline(p, ' '.join(quote), font_name, font_size, fnmgr)
            for r in p.runs: r.italic = True
            continue

        if line in ('---', '***', '___'):
            p = doc.add_paragraph('—' * 30); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p.paragraph_format.first_line_indent = Cm(0); i += 1; continue

        # Soft line breaks within a Markdown paragraph are joined with spaces.
        chunks = [line]; i += 1
        while i < len(lines):
            nxt = lines[i].strip()
            if not nxt: break
            if (re.match(r'^#{1,6}\s+', nxt) or nxt.startswith(('```', '~~~', '>', '![', '[IMAGE:'))
                or (i+1 < len(lines) and '|' in nxt and _separator(lines[i+1].strip()))
                or re.match(r'^(\s*)([-*+]|\d+[.)])\s+', lines[i])
                or re.match(r'^\d+\.\d+(?:\.\d+)?\s+', nxt)):
                break
            chunks.append(nxt); i += 1
        p = doc.add_paragraph(); p.alignment = alignment
        pf = p.paragraph_format; pf.first_line_indent = first_line_indent
        pf.left_indent = left_indent; pf.right_indent = right_indent
        pf.line_spacing = float(settings.get('line_spacing_multiple', 1.5))
        pf.space_before = Pt(float(settings.get('space_before', 0)))
        pf.space_after = Pt(float(settings.get('space_after', 0)))
        _inline(p, ' '.join(chunks), font_name, font_size, fnmgr)
