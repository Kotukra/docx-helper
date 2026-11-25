# processor/worker.py
import sys
import traceback
from .doc_creator import create_word_document, get_title_for_part
from docx_image_quality import inspect_docx_images, format_image_report
from docx_layout_quality import inspect_docx_layout, format_layout_report
from logger import logger, get_debug_logger

def create_document_worker(text, output_path, settings, part_index, markdown_mode, pipe_conn, debug_mode=False):
    """
    Функция, запускаемая в отдельном процессе.
    Создаёт один документ и отправляет результат через pipe.
    """
    if debug_mode:
        debug_logger = get_debug_logger()
        debug_logger.debug(f"=== Worker для части {part_index} начал работу ===")
        debug_logger.debug(f"Выходной путь: {output_path}")
        debug_logger.debug(f"Настройки: {settings}")
        debug_logger.debug(f"Текст (первые 200 символов): {text[:200]}...")
    try:
        title_doc = None
        if settings.get("title_enabled", False):
            logger.info(f"Попытка загрузить титульный лист для части {part_index}")
            if debug_mode:
                debug_logger.debug(f"Загрузка титульного листа для части {part_index}")
            title_doc = get_title_for_part(settings, part_index)
            if title_doc is None:
                logger.error(f"Не удалось загрузить титульный лист для части {part_index}")
                if debug_mode:
                    debug_logger.error(f"Титульный лист для части {part_index} не найден")
            else:
                logger.info(f"Титульный лист для части {part_index} успешно загружен")
                if debug_mode:
                    debug_logger.debug(f"Титульный лист загружен для части {part_index}")
        else:
            logger.debug(f"Титульные листы отключены для части {part_index}")

        final_path = create_word_document(
            text, output_path, settings=settings,
            title_doc=title_doc, markdown_mode=markdown_mode,
            progress_callback=None, cancel_check=None
        )
        image_report = format_image_report(inspect_docx_images(final_path))
        layout_report = format_layout_report(inspect_docx_layout(final_path))
        pipe_conn.send((True, f"Документ создан: {final_path}\n{image_report}\n{layout_report}"))
        if debug_mode:
            debug_logger.debug(f"Часть {part_index} успешно создана")
    except Exception as e:
        exc_info = traceback.format_exc()
        logger.error(f"Ошибка в worker для части {part_index}: {str(e)}\n{exc_info}")
        if debug_mode:
            debug_logger.error(f"Ошибка в worker для части {part_index}: {str(e)}\n{exc_info}")
        pipe_conn.send((False, f"Ошибка: {str(e)}\n{exc_info}"))
    finally:
        pipe_conn.close()
        if debug_mode:
            debug_logger.debug(f"=== Worker для части {part_index} завершён ===")
