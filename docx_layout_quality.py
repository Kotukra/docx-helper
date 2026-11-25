"""Post-generation diagnostics for page-break-sensitive DOCX structures."""
from docx import Document
from docx.oxml.ns import qn


def inspect_docx_layout(path) -> dict:
    document = Document(str(path))
    findings = []
    pending_page_break = False
    blank_page_reported = False
    for index, paragraph in enumerate(document.paragraphs, start=1):
        style_name = paragraph.style.name if paragraph.style else ""
        if style_name.startswith("Heading") and not paragraph.paragraph_format.keep_with_next:
            findings.append({"code": "orphan_heading", "message":
                             f"Заголовок в абзаце {index} не закреплён со следующим абзацем."})
        inline_breaks = paragraph._p.xpath('.//w:br[@w:type="page"]')
        breaks_before = bool(paragraph.paragraph_format.page_break_before)
        has_manual_break = bool(inline_breaks) or breaks_before
        has_text = bool(paragraph.text.strip())
        if has_manual_break:
            if pending_page_break and not has_text and not blank_page_reported:
                findings.append({"code": "consecutive_page_breaks", "message":
                                 "Подряд расположены ручные разрывы страниц; возможно, в Word появится пустая страница."})
                blank_page_reported = True
            pending_page_break = not has_text and not breaks_before
        elif has_text:
            pending_page_break = False
            blank_page_reported = False
    for table_index, table in enumerate(document.tables, start=1):
        for row_index, row in enumerate(table.rows, start=1):
            tr_pr = row._tr.get_or_add_trPr()
            if tr_pr.find(qn("w:cantSplit")) is None:
                findings.append({"code": "split_table_row", "message":
                                 f"Строка {row_index} таблицы {table_index} может разорваться между страницами."})
    return {"findings": findings,
            "warnings": len(findings),
            "orphan_headings": sum(item["code"] == "orphan_heading" for item in findings),
            "splittable_rows": sum(item["code"] == "split_table_row" for item in findings)}


def format_layout_report(report: dict) -> str:
    if not report["findings"]:
        return "Проверка разрывов страниц: висячих заголовков и разрываемых строк таблиц не найдено."
    return f"Проверка разрывов страниц: замечаний {report['warnings']}.\n" + "\n".join(
        item["message"] for item in report["findings"][:12])
