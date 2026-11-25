"""Merge DOCX body content while retaining images and external hyperlinks."""
from __future__ import annotations

from copy import deepcopy
from io import BytesIO
from pathlib import Path

from docx import Document
from docx.oxml.ns import qn


REL_ATTRS = {qn("r:id"), qn("r:embed"), qn("r:link")}


def merge_docx_files(paths, output_path) -> str:
    paths = [Path(path) for path in paths]
    if len(paths) < 2:
        raise ValueError("Для объединения выберите не менее двух DOCX-файлов")
    for path in paths:
        if not path.is_file() or path.suffix.lower() != ".docx":
            raise FileNotFoundError(f"Файл DOCX не найден: {path}")
    target = Document(str(paths[0]))
    target_body = target._element.body
    target_sect = target_body.sectPr

    for source_path in paths[1:]:
        source = Document(str(source_path))
        if source._element.body.xpath(".//w:footnoteReference | .//w:endnoteReference"):
            raise ValueError(
                f"В {source_path.name} есть сноски. Их перенос между файлами не поддерживается; "
                "сначала сохраните отдельную копию без сносок."
            )
        target.add_page_break()
        rid_map = {}
        for child in source._element.body:
            if child.tag == qn("w:sectPr"):
                continue
            copied = deepcopy(child)
            for element in copied.iter():
                for attr in REL_ATTRS.intersection(element.attrib):
                    old_rid = element.get(attr)
                    if old_rid not in rid_map:
                        relation = source.part.rels.get(old_rid)
                        if relation is None:
                            raise ValueError(f"Не найдена связь DOCX {old_rid} в файле {source_path.name}")
                        if relation.is_external:
                            rid_map[old_rid] = target.part.relate_to(
                                relation.target_ref, relation.reltype, is_external=True)
                        elif relation.reltype.endswith("/image"):
                            rid_map[old_rid], _ = target.part.get_or_add_image(BytesIO(relation.target_part.blob))
                        else:
                            raise ValueError(
                                f"В {source_path.name} есть встроенный объект, который нельзя безопасно объединить: "
                                f"{relation.reltype.rsplit('/', 1)[-1]}"
                            )
                    element.set(attr, rid_map[old_rid])
            target_body.insert(len(target_body) - (1 if target_sect is not None else 0), copied)

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    target.save(output_path)
    return str(output_path)
