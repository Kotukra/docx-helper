"""Merge DOCX body content while retaining images and external hyperlinks."""
from __future__ import annotations

from copy import deepcopy
from io import BytesIO
from pathlib import Path

from docx import Document
from docx.opc.constants import CONTENT_TYPE, RELATIONSHIP_TYPE
from docx.opc.packuri import PackURI
from docx.opc.part import Part
from docx.oxml.ns import qn
from lxml import etree


REL_ATTRS = {qn("r:id"), qn("r:embed"), qn("r:link")}
W_NS = qn("w:footnote").split("}")[0][1:]
NOTE_TYPES = {
    "footnote": ("footnoteReference", "footnotes", CONTENT_TYPE.WML_FOOTNOTES,
                 RELATIONSHIP_TYPE.FOOTNOTES, "/word/footnotes.xml"),
    "endnote": ("endnoteReference", "endnotes", CONTENT_TYPE.WML_ENDNOTES,
                RELATIONSHIP_TYPE.ENDNOTES, "/word/endnotes.xml"),
}


def _related_part(part, reltype):
    for relation in part.rels.values():
        if relation.reltype == reltype and not relation.is_external:
            return relation.target_part
    return None


def _copy_relationships(source_part, target_part, element, source_path):
    rid_map = {}
    for node in element.iter():
        for attr in REL_ATTRS.intersection(node.attrib):
            old_rid = node.get(attr)
            if old_rid not in rid_map:
                relation = source_part.rels.get(old_rid)
                if relation is None:
                    raise ValueError(f"Не найдена связь DOCX {old_rid} в файле {source_path.name}")
                if relation.is_external:
                    rid_map[old_rid] = target_part.relate_to(
                        relation.target_ref, relation.reltype, is_external=True)
                elif relation.reltype.endswith("/image"):
                    image_part = target_part.package.image_parts.get_or_add_image_part(
                        BytesIO(relation.target_part.blob))
                    rid_map[old_rid] = target_part.relate_to(image_part, relation.reltype)
                else:
                    raise ValueError(
                        f"В {source_path.name} есть встроенный объект, который нельзя безопасно объединить: "
                        f"{relation.reltype.rsplit('/', 1)[-1]}"
                    )
            node.set(attr, rid_map[old_rid])


def _ensure_target_notes(target, source_part, note_kind, source_path):
    ref_name, part_name, content_type, reltype, package_name = NOTE_TYPES[note_kind]
    source_notes = _related_part(source_part, reltype)
    if source_notes is None:
        return None
    target_notes = _related_part(target.part, reltype)
    if target_notes is not None:
        return target_notes

    root = etree.fromstring(source_notes.blob)
    for child in list(root):
        raw_id = child.get(qn(f"w:id"))
        if raw_id is not None and int(raw_id) >= 0:
            root.remove(child)
    target_notes = Part(PackURI(package_name), content_type,
                        etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True),
                        target.part.package)
    target.part.relate_to(target_notes, reltype)
    return target_notes


def _merge_notes(target, source, copied_body, source_path, note_kind):
    ref_name, part_name, _content_type, reltype, _package_name = NOTE_TYPES[note_kind]
    source_notes = _related_part(source.part, reltype)
    refs = copied_body.xpath(f".//w:{ref_name}", namespaces={"w": W_NS})
    if not refs:
        return
    if source_notes is None:
        raise ValueError(f"В {source_path.name} есть ссылки на {note_kind}, но часть со сносками отсутствует")

    target_notes = _ensure_target_notes(target, source.part, note_kind, source_path)
    target_root = etree.fromstring(target_notes.blob)
    source_root = etree.fromstring(source_notes.blob)
    current_ids = [int(node.get(qn("w:id"))) for node in target_root
                   if node.get(qn("w:id")) is not None and int(node.get(qn("w:id"))) >= 0]
    next_id = max(current_ids, default=0) + 1
    note_map = {}

    for reference in refs:
        old_id = reference.get(qn("w:id"))
        if old_id not in note_map:
            old_note = source_root.xpath(
                f"./w:{part_name}[@w:id='{old_id}']",
                namespaces={"w": W_NS})
            if not old_note:
                raise ValueError(f"В {source_path.name} не найдена запись {note_kind} {old_id}")
            copied_note = deepcopy(old_note[0])
            new_id = str(next_id)
            next_id += 1
            copied_note.set(qn("w:id"), new_id)
            _copy_relationships(source_notes, target_notes, copied_note, source_path)
            target_root.append(copied_note)
            note_map[old_id] = new_id
        reference.set(qn("w:id"), note_map[old_id])

    target_notes._blob = etree.tostring(target_root, xml_declaration=True,
                                        encoding="UTF-8", standalone=True)


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
        target.add_page_break()
        copy_container = etree.Element(qn("w:body"), nsmap=source._element.body.nsmap)
        for child in source._element.body:
            if child.tag == qn("w:sectPr"):
                continue
            copied = deepcopy(child)
            copy_container.append(copied)
        for note_kind in NOTE_TYPES:
            _merge_notes(target, source, copy_container, source_path, note_kind)
        _copy_relationships(source.part, target.part, copy_container, source_path)
        for copied in list(copy_container):
            target_body.insert(len(target_body) - (1 if target_sect is not None else 0), copied)

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    target.save(output_path)
    return str(output_path)

