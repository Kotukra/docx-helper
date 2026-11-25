# processing/processing_thread.py
import os
import multiprocessing
from PySide6.QtCore import QThread, Signal

from processor import (
    split_text_by_marker,
    generate_filename_adaptive,
    generate_custom_filename,
    sanitize_filename,
)
from processor.worker import create_document_worker
from processor.ppt_worker import create_presentation_worker
from logger import logger, get_debug_logger


class ProcessingThread(QThread):
    progress = Signal(str)
    finished = Signal(bool, str)
    document_created = Signal(str, str)

    def __init__(self, app, text, settings_dict, split_enabled, split_marker,
                 ask_name, debug_mode=False, mode="docx", parent=None):
        super().__init__(parent)
        self.app = app
        self.text = text
        self.settings = settings_dict
        self.split_enabled = split_enabled
        self.split_marker = split_marker
        self.ask_name = ask_name
        self.debug_mode = debug_mode
        self.mode = mode
        self.cancel_flag = False

    def run(self):
        if self.mode == "pptx":
            self._run_pptx()
        else:
            self._run_docx()

    # ===================== DOCX =====================
    def _run_docx(self):
        debug_logger = get_debug_logger() if self.debug_mode else None

        if debug_logger:
            debug_logger.debug("=== НАЧАЛО ОБРАБОТКИ (DOCX) ===")
            debug_logger.debug(f"Длина текста: {len(self.text)}")
            debug_logger.debug(f"Настройки: {self.settings}")

        try:
            if not self.text.strip():
                self.finished.emit(False, "Пустой текст")
                return

            output_folder = self.settings.get("output_folder", "")
            if not output_folder or not os.path.isdir(output_folder):
                output_folder = os.getcwd()
                logger.warning(f"Папка не задана, используется {output_folder}")

            parts = split_text_by_marker(self.text, self.split_marker, enabled=self.split_enabled)
            if len(parts) > 1:
                text_parts = parts
                self.progress.emit(f"Разделено на {len(text_parts)} частей (автоматически)")
                logger.info(f"Автоматическое разделение на {len(text_parts)} частей по маркеру '{self.split_marker}'")
            else:
                text_parts = [self.text]
                self.progress.emit("Разделение не требуется (маркер не найден)")
                logger.info("Маркер не найден, обработка одного документа")

            top_n = self.settings.get("naming_top_n", 4)
            markdown_mode = self.settings.get("markdown_mode", False)
            template = self.settings.get("filename_template", "{keywords}")

            total = len(text_parts)
            quality_reports = []
            logger.info(f"Всего частей для обработки: {total}")

            for idx, part in enumerate(text_parts, start=1):
                if self.cancel_flag:
                    self.progress.emit("❌ Операция отменена")
                    break

                try:
                    keywords = generate_filename_adaptive(part, top_n=top_n)
                except Exception:
                    logger.exception(f"Ошибка извлечения ключевых слов для части {idx}")
                    keywords = "output"
                if not keywords or keywords == "output":
                    keywords = "output"

                try:
                    base_name = generate_custom_filename(template, keywords, idx)
                    base_name = sanitize_filename(base_name)
                except Exception:
                    logger.exception(f"Ошибка формирования имени для части {idx}")
                    base_name = f"output_part{idx}"

                filename = f"{base_name}_part{idx}.docx" if total > 1 else f"{base_name}.docx"
                full_path = os.path.join(output_folder, filename)
                logger.info(f"Полный путь для части {idx}: {full_path}")

                parent_conn, child_conn = multiprocessing.Pipe()
                process = multiprocessing.Process(
                    target=create_document_worker,
                    args=(part, full_path, self.settings, idx, markdown_mode, child_conn, self.debug_mode),
                )
                process.start()
                process.join()
                if parent_conn.poll():
                    success, message = parent_conn.recv()
                else:
                    success, message = False, "Процесс завершился без ответа"
                parent_conn.close()

                if not success:
                    logger.error(f"Ошибка при создании документа для части {idx}: {message}")
                    self.finished.emit(False, f"Ошибка при создании части {idx}: {message}")
                    return

                created_path = message.partition(": ")[2].splitlines()[0]
                if created_path:
                    self.document_created.emit(created_path, "docx")
                details = "\n".join(message.splitlines()[1:]).strip()
                if details:
                    quality_reports.append(details)

                logger.info(f"Документ для части {idx} успешно создан: {full_path}")
                self.progress.emit(f"Создан: {full_path}")

            if not self.cancel_flag:
                self.progress.emit(f"✅ Готово! Создано {total} документов")
                report_text = "\n\n".join(quality_reports)
                self.finished.emit(True, f"Создано {total} документов" +
                                   (f"\n\n{report_text}" if report_text else ""))
            else:
                self.finished.emit(False, "Операция отменена")

        except Exception as e:
            logger.exception("Необработанная ошибка в ProcessingThread (docx)")
            self.progress.emit(f"Ошибка: {e}")
            self.finished.emit(False, str(e))

    # ===================== PPTX =====================
    def _run_pptx(self):
        debug_logger = get_debug_logger() if self.debug_mode else None

        if debug_logger:
            debug_logger.debug("=== НАЧАЛО ОБРАБОТКИ (PPTX) ===")
            debug_logger.debug(f"Длина текста: {len(self.text)}")

        try:
            if not self.text.strip():
                self.finished.emit(False, "Пустой текст")
                return

            output_folder = self.settings.get("output_folder", "")
            if not output_folder or not os.path.isdir(output_folder):
                output_folder = os.getcwd()
                logger.warning(f"Папка не задана, используется {output_folder}")

            template_path = self.settings.get("ppt_template_path", "")
            if not template_path or not os.path.exists(template_path):
                self.finished.emit(
                    False,
                    "Не выбран шаблон .pptx. Откройте вкладку «Презентация» → "
                    "«Создать шаблон-заготовку» или выберите свой .pptx"
                )
                return

            try:
                keywords = generate_filename_adaptive(self.text, top_n=4)
            except Exception:
                keywords = "presentation"
            if not keywords or keywords == "output":
                keywords = "presentation"

            base_name = sanitize_filename(keywords, max_len=60) or "presentation"
            out_path = os.path.join(output_folder, f"{base_name}.pptx")

            self.progress.emit(f"Создание презентации: {base_name}.pptx")

            parent_conn, child_conn = multiprocessing.Pipe()
            process = multiprocessing.Process(
                target=create_presentation_worker,
                args=(
                    self.text,
                    out_path,
                    template_path,
                    self.settings,
                    child_conn,
                    self.debug_mode,
                ),
            )
            process.start()
            process.join()

            if parent_conn.poll():
                success, message = parent_conn.recv()
            else:
                success, message = False, "Процесс завершился без ответа"
            parent_conn.close()

            if self.cancel_flag:
                self.finished.emit(False, "Операция отменена")
                return

            if success:
                created_path = message.partition(": ")[2].splitlines()[0]
                if created_path:
                    self.document_created.emit(created_path, "pptx")
                self.progress.emit(f"✅ {message}")
                self.finished.emit(True, message)
            else:
                self.finished.emit(False, message)

        except Exception as e:
            logger.exception("Необработанная ошибка в ProcessingThread (pptx)")
            self.progress.emit(f"Ошибка: {e}")
            self.finished.emit(False, str(e))
