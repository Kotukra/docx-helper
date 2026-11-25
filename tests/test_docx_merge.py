import tempfile
import unittest
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from docx import Document

from docx_merge import merge_docx_files


W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG_REL = "http://schemas.openxmlformats.org/package/2006/relationships"
CT = "http://schemas.openxmlformats.org/package/2006/content-types"
NOTE_SETTINGS = {
    "footnote": ("footnotes", "footnoteReference", "http://schemas.openxmlformats.org/officeDocument/2006/relationships/footnotes",
                 "application/vnd.openxmlformats-officedocument.wordprocessingml.footnotes+xml"),
    "endnote": ("endnotes", "endnoteReference", "http://schemas.openxmlformats.org/officeDocument/2006/relationships/endnotes",
                "application/vnd.openxmlformats-officedocument.wordprocessingml.endnotes+xml"),
}


def _add_note(path, note_kind, text, note_id="1"):
    part_name, ref_name, rel_type, content_type = NOTE_SETTINGS[note_kind]
    with zipfile.ZipFile(path, "r") as source:
        files = {name: source.read(name) for name in source.namelist()}

    document = ET.fromstring(files["word/document.xml"])
    paragraph = document.find(f".//{{{W}}}p")
    run = ET.SubElement(paragraph, f"{{{W}}}r")
    ET.SubElement(run, f"{{{W}}}{ref_name}", {f"{{{W}}}id": note_id})
    files["word/document.xml"] = ET.tostring(document, encoding="utf-8", xml_declaration=True)

    rels = ET.fromstring(files["word/_rels/document.xml.rels"])
    rel_id = f"rIdTest{part_name.capitalize()}"
    ET.SubElement(rels, f"{{{PKG_REL}}}Relationship", {
        "Id": rel_id, "Type": rel_type, "Target": f"{part_name}.xml"})
    files["word/_rels/document.xml.rels"] = ET.tostring(rels, encoding="utf-8", xml_declaration=True)

    types = ET.fromstring(files["[Content_Types].xml"])
    ET.SubElement(types, f"{{{CT}}}Override", {
        "PartName": f"/word/{part_name}.xml", "ContentType": content_type})
    files["[Content_Types].xml"] = ET.tostring(types, encoding="utf-8", xml_declaration=True)

    root = ET.Element(f"{{{W}}}{part_name}")
    for special_id, special_type in (("-1", "separator"), ("-2", "continuationSeparator")):
        special = ET.SubElement(root, f"{{{W}}}{part_name}", {
            f"{{{W}}}type": special_type, f"{{{W}}}id": special_id})
        ET.SubElement(ET.SubElement(special, f"{{{W}}}p"), f"{{{W}}}r")
    note = ET.SubElement(root, f"{{{W}}}{part_name}", {f"{{{W}}}id": note_id})
    note_paragraph = ET.SubElement(note, f"{{{W}}}p")
    note_run = ET.SubElement(note_paragraph, f"{{{W}}}r")
    ET.SubElement(note_run, f"{{{W}}}t").text = text
    files[f"word/{part_name}.xml"] = ET.tostring(root, encoding="utf-8", xml_declaration=True)

    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as output:
        for name, data in files.items():
            output.writestr(name, data)


def _add_broken_note_reference(path, note_kind):
    _part_name, ref_name, _rel_type, _content_type = NOTE_SETTINGS[note_kind]
    with zipfile.ZipFile(path, "r") as source:
        files = {name: source.read(name) for name in source.namelist()}
    document = ET.fromstring(files["word/document.xml"])
    run = ET.SubElement(document.find(f".//{{{W}}}p"), f"{{{W}}}r")
    ET.SubElement(run, f"{{{W}}}{ref_name}", {f"{{{W}}}id": "1"})
    files["word/document.xml"] = ET.tostring(document, encoding="utf-8", xml_declaration=True)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as output:
        for name, data in files.items():
            output.writestr(name, data)


class DocxMergeTests(unittest.TestCase):
    def test_merge_preserves_and_renumbers_footnotes_and_endnotes(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            paths = []
            for index in range(2):
                path = temp / f"source{index}.docx"
                document = Document()
                document.add_paragraph(f"Документ {index + 1}")
                document.save(path)
                _add_note(path, "footnote", f"Сноска {index + 1}")
                _add_note(path, "endnote", f"Концевая сноска {index + 1}")
                paths.append(path)

            output = temp / "merged.docx"
            merge_docx_files(paths, output)
            merged = Document(output)
            self.assertIn("Документ 1", "\n".join(p.text for p in merged.paragraphs))
            self.assertIn("Документ 2", "\n".join(p.text for p in merged.paragraphs))

            with zipfile.ZipFile(output) as package:
                body = ET.fromstring(package.read("word/document.xml"))
                for note_kind, (part_name, ref_name, _rel_type, _content_type) in NOTE_SETTINGS.items():
                    references = [node.get(f"{{{W}}}id") for node in body.iter(f"{{{W}}}{ref_name}")]
                    self.assertEqual(references, ["1", "2"])
                    notes = ET.fromstring(package.read(f"word/{part_name}.xml"))
                    actual = [node for node in notes if int(node.get(f"{{{W}}}id")) >= 0]
                    self.assertEqual([node.get(f"{{{W}}}id") for node in actual], ["1", "2"])
                    note_text = ["".join(node.itertext()) for node in actual]
                    self.assertTrue(any("1" in value for value in note_text))
                    self.assertTrue(any("2" in value for value in note_text))
                    self.assertTrue(any(node.get(f"{{{W}}}id") == "-1" for node in notes))

    def test_broken_note_reference_is_rejected_with_a_clear_error(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            first = temp / "first.docx"
            second = temp / "broken.docx"
            Document().save(first)
            broken = Document()
            broken.add_paragraph("Есть ссылка на отсутствующую сноску")
            broken.save(second)
            _add_broken_note_reference(second, "footnote")
            with self.assertRaisesRegex(ValueError, "часть со сносками отсутствует"):
                merge_docx_files([first, second], temp / "merged.docx")


if __name__ == "__main__":
    unittest.main()

