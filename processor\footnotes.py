# processor/footnotes.py
"""Реальные сноски Word: внизу страницы, с номерами 1, 2, 3…,
которые Word нумерует и перенумеровывает сам."""
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.opc.part import Part
from docx.opc.packuri import PackURI
from xml.sax.saxutils import escape

FOOTNOTES_CT = ("application/vnd.openxmlformats-officedocument"
                ".wordprocessingml.footnotes+xml")
FOOTNOTES_RT = ("http://schemas.openxmlformats.org/officeDocument/2006/"
                "relationships/footnotes")
W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"

_EMPTY_BODY = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    f'<w:footnotes xmlns:w="{W_NS}">'
    '<w:footnote w:type="separator" w:id="-1"><w:p><w:pPr>'
    '<w:spacing w:after="0" w:line="240" w:lineRule="auto"/>'
    '</w:pPr><w:r><w:separator/></w:r></w:p></w:footnote>'
    '<w:footnote w:type="continuationSeparator" w:id="0"><w:p><w:pPr>'
    '<w:spacing w:after="0" w:line="240" w:lineRule="auto"/>'
    '</w:pPr><w:r><w:continuationSeparator/></w:r></w:p></w:footnote>'
    '</w:footnotes>'
)


class FootnoteManager:
    """Создаёт /word/footnotes.xml и выдаёт ссылки на сноски по id."""

    def __init__(self, doc):
        self.doc = doc
        self._items = []      # [(id, text), ...]
        self._next_id = 1
        self._ensure_styles()
        self._part = self._create_part()

    # ---------------- внутреннее ----------------
    def _ensure_styles(self):
        styles_el = self.doc.styles.element
        ids = {s.get(qn('w:styleId'))
               for s in styles_el.findall(qn('w:style'))}

        if 'FootnoteText' not in ids:
            st = OxmlElement('w:style')
            st.set(qn('w:type'), 'paragraph')
            st.set(qn('w:styleId'), 'FootnoteText')
            name = OxmlElement('w:name')
            name.set(qn('w:val'), 'footnote text')
            st.append(name)
            pPr = OxmlElement('w:pPr')
            sp = OxmlElement('w:spacing')
            sp.set(qn('w:after'), '0')
            sp.set(qn('w:line'), '240')
            sp.set(qn('w:lineRule'), 'auto')
            pPr.append(sp)
            ind = OxmlElement('w:ind')
            ind.set(qn('w:firstLine'), '0')
            pPr.append(ind)
            st.append(pPr)
            rPr = OxmlElement('w:rPr')
            fonts = OxmlElement('w:rFonts')
            fonts.set(qn('w:ascii'), 'Times New Roman')
            fonts.set(qn('w:hAnsi'), 'Times New Roman')
            fonts.set(qn('w:eastAsia'), 'Times New Roman')
            rPr.append(fonts)
            sz = OxmlElement('w:sz'); sz.set(qn('w:val'), '20'); rPr.append(sz)
            szCs = OxmlElement('w:szCs'); szCs.set(qn('w:val'), '20'); rPr.append(szCs)
            st.append(rPr)
            styles_el.append(st)

        if 'FootnoteReference' not in ids:
            st = OxmlElement('w:style')
            st.set(qn('w:type'), 'character')
            st.set(qn('w:styleId'), 'FootnoteReference')
            name = OxmlElement('w:name')
            name.set(qn('w:val'), 'footnote reference')
            st.append(name)
            rPr = OxmlElement('w:rPr')
            va = OxmlElement('w:vertAlign')
            va.set(qn('w:val'), 'superscript')
            rPr.append(va)
            st.append(rPr)
            styles_el.append(st)

    def _create_part(self):
        part = Part(PackURI('/word/footnotes.xml'),
                    FOOTNOTES_CT,
                    _EMPTY_BODY.encode('utf-8'),
                    self.doc.part.package)
        self.doc.part.relate_to(part, FOOTNOTES_RT)
        return part

    # ---------------- публичное ----------------
    def add_reference(self, paragraph, text: str) -> int:
        """Ставит надстрочный номер сноски в конце paragraph.
        Текст сноски запоминается и попадёт в footnotes.xml при finalize()."""
        fid = self._next_id
        self._next_id += 1
        self._items.append((fid, text))

        run = paragraph.add_run()
        rPr = OxmlElement('w:rPr')
        rStyle = OxmlElement('w:rStyle')
        rStyle.set(qn('w:val'), 'FootnoteReference')
        rPr.append(rStyle)
        run._r.append(rPr)
        ref = OxmlElement('w:footnoteReference')
        ref.set(qn('w:id'), str(fid))
        run._r.append(ref)
        return fid

    def finalize(self):
        """Формирует итоговый XML. Вызвать один раз перед doc.save()."""
        chunks = [_EMPTY_BODY.split('</w:footnotes>')[0]]
        for fid, text in self._items:
            chunks.append(
                f'<w:footnote w:id="{fid}"><w:p>'
                '<w:pPr><w:pStyle w:val="FootnoteText"/></w:pPr>'
                '<w:r><w:rPr><w:rStyle w:val="FootnoteReference"/>'
                '<w:vertAlign w:val="superscript"/></w:rPr>'
                '<w:footnoteRef/></w:r>'
                f'<w:r><w:rPr><w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman" w:eastAsia="Times New Roman"/><w:sz w:val="20"/><w:szCs w:val="20"/></w:rPr><w:t xml:space="preserve"> {escape(text)}</w:t></w:r>'
                '</w:p></w:footnote>'
            )
        chunks.append('</w:footnotes>')
        self._part._blob = ''.join(chunks).encode('utf-8')


# ---- helper, который вставит сноски прямо в абзац по маркеру [^...] ----
import re as _re
_FOOTNOTE_RE = _re.compile(r'\[\^([^\]]+)\]')


def add_text_with_footnotes(paragraph, text: str, fnmgr: FootnoteManager):
    """Разбивает text на куски и вставляет сноски на месте [^...]."""
    pos = 0
    for m in _FOOTNOTE_RE.finditer(text):
        if m.start() > pos:
            paragraph.add_run(text[pos:m.start()])
        fnmgr.add_reference(paragraph, m.group(1).strip())
        pos = m.end()
    if pos < len(text):
        paragraph.add_run(text[pos:])