# processor/ppt_worker.py
import traceback
from .ppt_creator import create_presentation
from ppt_quality import inspect_presentation, format_presentation_report
from logger import logger, get_debug_logger


def create_presentation_worker(markup, output_path, template_path,
                               settings, pipe_conn, debug_mode=False):
    debug_logger = None
    try:
        if debug_mode:
            dbg = get_debug_logger()
            dbg.debug("=== PPTX worker ===")
            dbg.debug(f"output={output_path}")
            dbg.debug(f"template={template_path}")
            dbg.debug(f"markup_len={len(markup)}")
        final = create_presentation(markup, output_path, template_path, settings)
        report = inspect_presentation(final, settings.get("ppt_min_font_size", 10.0))
        details = format_presentation_report(report)
        pipe_conn.send((True, f"Презентация создана: {final}\n{details}"))
    except Exception as e:
        tb = traceback.format_exc()
        logger.error(f"PPTX worker error: {e}\n{tb}")
        if debug_mode:
            get_debug_logger().error(tb)
        pipe_conn.send((False, f"Ошибка: {e}"))
    finally:
        try:
            pipe_conn.close()
        except Exception:
            pass
