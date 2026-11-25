"""Post-generation diagnostics for page-break-sensitive DOCX structures."""
from docx import Document
from docx.oxml.ns import qn


def inspect_docx_layout(path) -> dict:
    document = Document(str(path))
    findings = []
    for index, paragraph in enumerate(document.paragraphs, start=1):
        style_name = paragraph.style.name if paragraph.style else ""
        if style_name.startswith("Heading") and not paragraph.paragraph_format.keep_with_next:
            findings.append({"code": "orphan_heading", "message":
                             f"Заголовок в абзаце {index} не закреплён со следующим абзацем."})
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
