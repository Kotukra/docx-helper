"""Regression tests for Markdown-to-DOCX generation.

Run from the application root with: python -m unittest discover -s tests -v
"""
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile
import unittest

from docx import Document
from lxml import etree

from document_profile_manager import get_profile, resolve_profile_settings
from processor.doc_creator import create_word_document

W = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}


class ProfileTests(unittest.TestCase):
    def test_builtin_profiles_exist(self):
        self.assertIsNotNone(get_profile('jasmine'))
        self.assertIsNotNone(get_profile('legacy_gost'))

    def test_profile_save_delete_and_validation(self):
        from unittest.mock import patch
        from document_profile_manager import save_profile, delete_profile
        profile = dict(get_profile('jasmine'))
        with TemporaryDirectory() as tmp:
            with patch('document_profile_manager.PROFILE_DIR', Path(tmp)):
                profile['profile_id'] = 'qa_custom'
                profile['profile_name'] = 'QA custom'
                saved = save_profile(profile, overwrite=False)
                self.assertTrue(saved.exists())
                self.assertEqual(get_profile('qa_custom')['profile_name'], 'QA custom')
                self.assertTrue(delete_profile('qa_custom'))
                self.assertFalse(saved.exists())
                with self.assertRaises(ValueError):
                    delete_profile('../outside')
                profile['profile_id'] = 'bad_custom'
                profile['font_size'] = 200
                with self.assertRaises(ValueError):
                    save_profile(profile)

    def test_profile_margins_are_resolved(self):
        jasmine = resolve_profile_settings({'document_profile': 'jasmine'})
        legacy = resolve_profile_settings({'document_profile': 'legacy_gost'})
        self.assertEqual(jasmine['margins'], {'top': 2.0, 'bottom': 2.0, 'left': 2.5, 'right': 1.1})
        self.assertEqual(legacy['margins'], {'top': 2.0, 'bottom': 2.0, 'left': 3.0, 'right': 1.5})


class DocxGenerationTests(unittest.TestCase):
    def test_docx_text_import_includes_tables_in_document_order(self):
        from processor.file_io import extract_text_from_docx

        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "table_import.docx"
            doc = Document()
            doc.add_paragraph("До таблицы")
            table = doc.add_table(rows=1, cols=2)
            table.cell(0, 0).text = "Поле"
            table.cell(0, 1).text = "Значение"
            doc.add_paragraph("После таблицы")
            doc.save(path)
            imported = extract_text_from_docx(str(path))

        self.assertEqual(imported.splitlines(), ["До таблицы", "Поле | Значение", "После таблицы"])

    def test_pptx_shape_iterator_reads_text_nested_in_groups(self):
        from types import SimpleNamespace
        from processor.file_io import _iter_pptx_shapes

        text_shape = SimpleNamespace(shape_type=1, text="Текст внутри группы")
        image_shape = SimpleNamespace(shape_type=13)
        nested_group = SimpleNamespace(shape_type=6, shapes=[text_shape])
        group = SimpleNamespace(shape_type=6, shapes=[image_shape, nested_group])
        self.assertEqual(list(_iter_pptx_shapes([group])), [image_shape, text_shape])

    def test_docx_to_slides_skips_external_image_relationships(self):
        from types import SimpleNamespace
        from unittest.mock import patch
        from docx_to_slides import _extract_images

        class ExternalImageRelationship:
            is_external = True
            reltype = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/image"

            @property
            def target_part(self):
                raise AssertionError("external relationship must not access target_part")

        class Blip:
            def get(self, key):
                return "rIdExternal" if key.endswith("}embed") else None

        paragraph_xml = SimpleNamespace(xpath=lambda query: [Blip()] if query == ".//a:blip" else [])
        paragraph = SimpleNamespace(style=SimpleNamespace(name="Normal"), _p=paragraph_xml)
        body = SimpleNamespace(xpath=lambda query: [object()] if query == ".//w:p" else [])
        document = SimpleNamespace(element=SimpleNamespace(body=body), part=SimpleNamespace(
            rels={"rIdExternal": ExternalImageRelationship()}))

        with TemporaryDirectory() as tmp:
            with patch("docx_to_slides.Paragraph", return_value=paragraph):
                self.assertEqual(_extract_images(document, tmp), [])

    def test_layout_check_reports_unattached_heading_and_splittable_row(self):
        from docx_layout_quality import inspect_docx_layout
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / 'layout.docx'
            doc = Document()
            doc.add_paragraph('Заголовок', style='Heading 1')
            doc.add_table(rows=1, cols=1).cell(0, 0).text = 'Строка таблицы'
            doc.save(path)
            codes = {item['code'] for item in inspect_docx_layout(path)['findings']}
            self.assertEqual(codes, {'orphan_heading', 'split_table_row'})

    def test_layout_check_warns_about_consecutive_page_breaks(self):
        from docx_layout_quality import inspect_docx_layout
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / 'empty_page.docx'
            doc = Document()
            doc.add_paragraph('Текст до разрыва')
            doc.add_page_break()
            doc.add_page_break()
            doc.add_paragraph('Текст после разрыва')
            doc.save(path)
            codes = {item['code'] for item in inspect_docx_layout(path)['findings']}
            self.assertIn('consecutive_page_breaks', codes)

    def test_merge_docx_keeps_text_and_images(self):
        from PIL import Image
        from docx_merge import merge_docx_files
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            image = root / 'image.png'
            Image.new('RGB', (40, 30), 'white').save(image)
            first_path, second_path, output = root / 'first.docx', root / 'second.docx', root / 'merged.docx'
            first = Document()
            first.add_paragraph('Первый документ')
            first.save(first_path)
            second = Document()
            second.add_paragraph('Второй документ')
            second.add_picture(str(image))
            second.save(second_path)
            merge_docx_files([first_path, second_path], output)
            result = Document(output)
            self.assertIn('Первый документ', '\n'.join(p.text for p in result.paragraphs))
            self.assertIn('Второй документ', '\n'.join(p.text for p in result.paragraphs))
            self.assertEqual(len(result.inline_shapes), 1)

    def test_docx_image_quality_reports_tiny_and_overwide_images(self):
        from PIL import Image
        from docx.shared import Cm
        from docx_image_quality import inspect_docx_images
        with TemporaryDirectory() as tmp:
            tiny = Path(tmp) / 'tiny.png'
            wide = Path(tmp) / 'wide.png'
            Image.new('RGB', (20, 20), 'white').save(tiny)
            Image.new('RGB', (200, 80), 'white').save(wide)
            path = Path(tmp) / 'images.docx'
            doc = Document()
            doc.add_picture(str(tiny), width=Cm(1))
            doc.add_picture(str(wide), width=Cm(20))
            doc.save(path)
            codes = {item['code'] for item in inspect_docx_images(path)['findings']}
            self.assertEqual(codes, {'image_too_small', 'image_too_large', 'image_low_resolution'})

    def test_docx_to_presentation_markup_keeps_headings_tables_and_images(self):
        from PIL import Image
        from docx_to_slides import docx_to_presentation_markup
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / 'source.docx'
            image = Path(tmp) / 'source.png'
            Image.new('RGB', (40, 30), 'white').save(image)
            doc = Document()
            doc.add_paragraph('Название работы')
            doc.add_paragraph('Краткое описание')
            doc.add_paragraph('Введение', style='Heading 1')
            doc.add_paragraph('Цель исследования.', style='Normal')
            table = doc.add_table(rows=2, cols=2)
            table.cell(0, 0).text = 'Параметр'
            table.cell(0, 1).text = 'Значение'
            table.cell(1, 0).text = 'Срок'
            table.cell(1, 1).text = '2026'
            table.cell(1, 1).paragraphs[0].add_run().add_picture(str(image))
            doc.add_picture(str(image))
            doc.save(path)
            asset_dir = Path(tmp) / 'assets'
            markup = docx_to_presentation_markup(path, max_items=2, asset_dir=str(asset_dir))
            self.assertIn('[SLIDE: title]', markup)
            self.assertIn('# Введение', markup)
            self.assertIn('- Цель исследования.', markup)
            self.assertIn('[SLIDE: table]', markup)
            self.assertIn('| Срок | 2026 |', markup)
            self.assertEqual(markup.count('[SLIDE: image_full]'), 2)
            self.assertTrue(list(asset_dir.glob('*')))
            from processor.ppt_creator import parse_presentation
            image_slide = next(slide for slide in parse_presentation(markup) if slide['type'] == 'image_full')
            self.assertTrue(Path(image_slide['images'][0]).is_file())

    def test_docx_comparison_reports_layout_differences(self):
        from docx_comparison import compare_docx
        with TemporaryDirectory() as tmp:
            reference_path = Path(tmp) / 'reference.docx'
            candidate_path = Path(tmp) / 'candidate.docx'
            reference = Document()
            reference.styles['Normal'].paragraph_format.line_spacing = 1.0
            reference.add_paragraph('Текст образца для сравнения.')
            reference.add_table(rows=1, cols=2)
            reference.sections[0].header.paragraphs[0].text = 'Организация'
            reference.sections[0].footer.paragraphs[0].text = 'Лист'
            reference.save(reference_path)
            candidate = Document()
            candidate.sections[0].left_margin = __import__('docx').shared.Cm(4.0)
            candidate.styles['Normal'].paragraph_format.line_spacing = 1.5
            candidate.add_paragraph('Текст проверяемого документа.')
            candidate.add_table(rows=2, cols=2)
            candidate.sections[0].header.paragraphs[0].text = 'Другая организация'
            candidate.save(candidate_path)
            report = compare_docx(reference_path, candidate_path)
            properties = {item['property'] for item in report['findings']}
            self.assertIn('left_margin', properties)
            self.assertIn('table_dimensions', properties)
            self.assertIn('Normal.line_spacing', properties)
            self.assertIn('header_content', properties)
            self.assertIn('footer_content', properties)

    SAMPLE = '''# ВВЕДЕНИЕ

Текст с **жирным** и *курсивом*, а также сноской[^Иванов И. И. Книга. — 2024. — С. 10.].

## 1.1 Подраздел

### 1.1.1 Третий уровень

| Поле | Значение |
|---|---:|
| А | 1 |
| Б | 2 |

```python
print("Тест")
```

# ЗАКЛЮЧЕНИЕ

Итог.
'''

    def _generate(self, profile='jasmine', footnotes=True):
        tmp = TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = Path(tmp.name) / 'result.docx'
        settings = {
            'document_profile': profile,
            'markdown_mode': True,
            'page_numbers': True,
            'page_numbers_skip_first': True,
            'footnotes_enabled': footnotes,
            'detect_issues': False,
        }
        created_path = create_word_document(self.SAMPLE, str(path), settings=settings, markdown_mode=True)
        self.assertEqual(created_path, str(path))
        return path

    def test_docx_contains_headings_table_code_and_page_field(self):
        path = self._generate()
        doc = Document(path)
        self.assertEqual([p.style.name for p in doc.paragraphs if p.style.name.startswith('Heading')],
                         ['Heading 1', 'Heading 2', 'Heading 3', 'Heading 1'])
        self.assertEqual(len(doc.tables), 1)
        code_runs = [r for p in doc.paragraphs for r in p.runs if 'print(' in r.text]
        self.assertTrue(code_runs)
        self.assertEqual(code_runs[0].font.name, 'Times New Roman')
        self.assertEqual(code_runs[0].font.size.pt, 11)
        with ZipFile(path) as archive:
            xml = etree.fromstring(archive.read('word/document.xml'))
            footer_parts = [name for name in archive.namelist() if name.startswith('word/footer') and name.endswith('.xml')]
            self.assertTrue(footer_parts)
            footer_xmls = [etree.fromstring(archive.read(name)) for name in footer_parts]
            self.assertTrue(any(x.xpath('.//w:instrText[contains(., "PAGE")]', namespaces=W) for x in footer_xmls))
            self.assertEqual(len(xml.xpath('.//w:footnoteReference', namespaces=W)), 1)
            rows = xml.xpath('.//w:tbl/w:tr', namespaces=W)
            self.assertTrue(rows[0].xpath('./w:trPr/w:tblHeader', namespaces=W))
            self.assertTrue(all(r.xpath('./w:trPr/w:cantSplit', namespaces=W) for r in rows))
            foot = etree.fromstring(archive.read('word/footnotes.xml'))
            self.assertEqual(len(foot.xpath('./w:footnote[@w:id > 0]', namespaces=W)), 1)

    def test_disabled_footnotes_keep_marker_as_text(self):
        path = self._generate(footnotes=False)
        doc = Document(path)
        content = '\n'.join(p.text for p in doc.paragraphs)
        self.assertIn('[^Иванов И. И. Книга.', content)
        with ZipFile(path) as archive:
            xml = etree.fromstring(archive.read('word/document.xml'))
            self.assertEqual(len(xml.xpath('.//w:footnoteReference', namespaces=W)), 0)


    def test_title_template_keeps_tables_images_and_direct_formatting(self):
        from PIL import Image
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            image_path = tmp_path / 'title_image.png'
            Image.new('RGB', (120, 60), 'white').save(image_path)
            template_path = tmp_path / 'title.docx'
            title = Document()
            p = title.add_paragraph()
            run = p.add_run('ТИТУЛЬНЫЙ ЛИСТ')
            run.bold = True
            run.font.size = __import__('docx').shared.Pt(18)
            title.add_picture(str(image_path))
            title.add_table(rows=1, cols=2).cell(0, 0).text = 'Титульная таблица'
            title.save(template_path)

            output = tmp_path / 'with_title.docx'
            settings = {'document_profile': 'jasmine', 'markdown_mode': True,
                        'page_numbers': True, 'footnotes_enabled': True,
                        'detect_issues': False}
            create_word_document('# ВВЕДЕНИЕ\n\nТекст основной части.', str(output),
                                 settings=settings, title_doc=Document(template_path),
                                 markdown_mode=True)
            result = Document(output)
            self.assertEqual(len(result.tables), 1)
            self.assertEqual(len(result.inline_shapes), 1)
            self.assertIn('ТИТУЛЬНЫЙ ЛИСТ', '\n'.join(p.text for p in result.paragraphs))
            title_run = next(r for p in result.paragraphs for r in p.runs if 'ТИТУЛЬНЫЙ ЛИСТ' in r.text)
            self.assertTrue(title_run.bold)
            self.assertEqual(title_run.font.size.pt, 18)

    def test_legacy_profile_page_geometry(self):
        path = self._generate(profile='legacy_gost')
        section = Document(path).sections[0]
        self.assertAlmostEqual(section.left_margin.cm, 3.0, places=2)
        self.assertAlmostEqual(section.right_margin.cm, 1.5, places=2)

    def test_marked_table_receives_gost_caption(self):
        with TemporaryDirectory() as tmp:
            output = Path(tmp) / 'captioned.docx'
            source = '[TABLE: Сравнение вариантов]\n| Поле | Значение |\n|---|---|\n| А | 1 |'
            create_word_document(source, str(output),
                                 settings={'document_profile': 'jasmine', 'markdown_mode': True,
                                           'auto_number_captions': True, 'detect_issues': False},
                                 markdown_mode=True)
            doc = Document(output)
            self.assertEqual(len(doc.tables), 1)
            self.assertEqual(doc.paragraphs[0].text, 'Таблица 1 — Сравнение вариантов')

    def test_appendix_marker_is_numbered_and_starts_new_page(self):
        with TemporaryDirectory() as tmp:
            output = Path(tmp) / 'appendix.docx'
            create_word_document('[APPENDIX: Анкета]', str(output),
                                 settings={'document_profile': 'jasmine', 'markdown_mode': True,
                                           'auto_number_captions': True, 'detect_issues': False},
                                 markdown_mode=True)
            appendix = next(p for p in Document(output).paragraphs if p.text.startswith('Приложение'))
            self.assertEqual(appendix.text, 'Приложение А — Анкета')
            self.assertTrue(appendix.paragraph_format.page_break_before)

    def test_image_marker_applies_individual_width_and_alignment(self):
        from PIL import Image
        from docx.enum.text import WD_ALIGN_PARAGRAPH
        with TemporaryDirectory() as tmp:
            image = Path(tmp) / 'plot.png'
            Image.new('RGB', (100, 60), 'white').save(image)
            output = Path(tmp) / 'positioned.docx'
            source = f'[IMAGE: {image} | График | width=8 | align=left]'
            create_word_document(source, str(output),
                                 settings={'document_profile': 'jasmine', 'markdown_mode': True,
                                           'detect_issues': False}, markdown_mode=True)
            doc = Document(output)
            self.assertAlmostEqual(doc.inline_shapes[0].width.cm, 8.0, places=1)
            self.assertEqual(doc.paragraphs[0].alignment, WD_ALIGN_PARAGRAPH.LEFT)


if __name__ == '__main__':
    unittest.main()

class PresentationTests(unittest.TestCase):
    def test_pptx_file_import_extracts_slide_text_and_tables(self):
        from pptx import Presentation
        from processor.file_io import read_file_content
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / 'source.pptx'
            prs = Presentation()
            slide = prs.slides.add_slide(prs.slide_layouts[1])
            slide.shapes.title.text = 'Результаты'
            slide.placeholders[1].text = 'Основной вывод'
            table = slide.shapes.add_table(2, 2, 100000, 2000000, 4000000, 1500000).table
            table.cell(0, 0).text = 'Критерий'
            table.cell(0, 1).text = 'Оценка'
            prs.save(path)
            extracted = read_file_content(str(path))
            self.assertIn('Результаты', extracted)
            self.assertIn('Основной вывод', extracted)
            self.assertIn('Критерий | Оценка', extracted)

    def test_slide_markup_round_trip_keeps_notes_images_chart_and_table(self):
        from processor.ppt_creator import parse_presentation
        from slide_editor import serialize_presentation
        markup = ('[SLIDE: chart]\n# Динамика\n- Вывод\n[IMAGE: график.png]\n'
                  '[CHART: line]\n2024: 5\n2025: 8\n[/CHART]\n'
                  '[TABLE]\n| Год | Значение |\n|---|---|\n| 2025 | 8 |\n[/TABLE]\n'
                  '[NOTES: Подробное объяснение]')
        parsed = parse_presentation(markup)
        round_trip = parse_presentation(serialize_presentation(parsed))
        self.assertEqual(round_trip[0]['notes'], 'Подробное объяснение')
        self.assertEqual(round_trip[0]['images'], ['график.png'])
        self.assertEqual(round_trip[0]['chart'], parsed[0]['chart'])
        self.assertEqual(round_trip[0]['table'], parsed[0]['table'])

    def test_slide_quality_check_reports_bounds_overlap_and_small_text(self):
        from pptx import Presentation
        from pptx.util import Inches, Pt
        from PIL import Image
        from ppt_quality import inspect_presentation
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / 'quality.pptx'
            prs = Presentation()
            slide = prs.slides.add_slide(prs.slide_layouts[6])
            first = slide.shapes.add_textbox(Inches(1), Inches(1), Inches(3), Inches(1))
            first.text_frame.text = 'Первый блок'
            first.text_frame.paragraphs[0].runs[0].font.size = Pt(8)
            second = slide.shapes.add_textbox(Inches(2), Inches(1), Inches(3), Inches(1))
            second.text_frame.text = 'Второй блок'
            slide.shapes.add_textbox(Inches(12), Inches(7), Inches(2), Inches(1)).text_frame.text = 'За краем'
            tiny_image = Path(tmp) / 'tiny.png'
            Image.new('RGB', (20, 20), 'white').save(tiny_image)
            slide.shapes.add_picture(str(tiny_image), Inches(6), Inches(1), width=Inches(0.3), height=Inches(0.3))
            prs.save(path)
            codes = {item['code'] for item in inspect_presentation(path)['findings']}
            self.assertTrue({'out_of_bounds', 'small_font', 'text_overlap', 'small_image'}.issubset(codes))

    def test_slide_numbers_are_optional_and_sequential(self):
        from processor.ppt_creator import create_presentation
        from pptx import Presentation
        template = Path(__file__).resolve().parents[1] / 'templates_ppt' / 'starter.pptx'
        markup = '[SLIDE: title]\n# Первый\n---\n[SLIDE: bullets]\n# Второй\n- пункт'
        with TemporaryDirectory() as tmp:
            output = Path(tmp) / 'numbered.pptx'
            create_presentation(markup, str(output), str(template), {'ppt_slide_numbers': True})
            slides = Presentation(output).slides
            numbered = [shape.text for slide in slides for shape in slide.shapes
                        if shape.name == 'GOST slide number']
            self.assertEqual(numbered, ['1', '2'])

    def test_table_stays_inside_slide(self):
        from processor.ppt_creator import create_presentation
        template = Path(__file__).resolve().parents[1] / 'templates_ppt' / 'starter.pptx'
        with TemporaryDirectory() as tmp:
            output = Path(tmp) / 'table.pptx'
            rows = '\n'.join(f'| Строка {i} | Значение {i} |' for i in range(1, 18))
            markup = ('[SLIDE:table]\n# Проверка таблицы\n[TABLE]\n'
                      '| Поле | Значение |\n|---|---|\n' + rows + '\n[/TABLE]')
            create_presentation(markup, str(output), str(template), {})
            from pptx import Presentation
            prs = Presentation(output)
            table_shape = next(shape for shape in prs.slides[0].shapes if shape.has_table)
            self.assertLessEqual(table_shape.top + table_shape.height, prs.slide_height)
            self.assertGreaterEqual(table_shape.top, 0)

    def test_full_image_is_fitted_without_overflow(self):
        from processor.ppt_builder import add_full_image
        from pptx import Presentation
        from PIL import Image
        with TemporaryDirectory() as tmp:
            image_path = Path(tmp) / 'portrait.png'
            Image.new('RGB', (500, 1400), 'white').save(image_path)
            prs = Presentation()
            slide = prs.slides.add_slide(prs.slide_layouts[6])
            add_full_image(slide, [str(image_path)], prs)
            picture = next(shape for shape in slide.shapes if shape.shape_type == 13)
            self.assertLessEqual(picture.left + picture.width, prs.slide_width)
            self.assertLessEqual(picture.top + picture.height, prs.slide_height)
