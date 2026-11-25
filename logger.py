# logger.py
import logging
import logging.handlers
import multiprocessing
import os
import atexit
from datetime import datetime

LOG_DIR = "logs"
_logger = None
_listener = None
_debug_logger = None

def shutdown_logger():
    """Корректно завершает QueueListener и закрывает очередь логирования."""
    global _listener
    listener = _listener
    _listener = None
    if listener is not None:
        try:
            listener.stop()
        except Exception:
            pass


def setup_logger():
    global _logger, _listener
    if _listener is not None:
        shutdown_logger()
    if not os.path.exists(LOG_DIR):
        os.makedirs(LOG_DIR)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_filename = f"app_{timestamp}.log"
    log_path = os.path.join(LOG_DIR, log_filename)

    logger = logging.getLogger('DocProcessor')
    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()

    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    queue = multiprocessing.Queue()
    queue_handler = logging.handlers.QueueHandler(queue)
    queue_handler.setLevel(logging.DEBUG)
    logger.addHandler(queue_handler)

    file_handler = logging.FileHandler(log_path, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)

    listener = logging.handlers.QueueListener(queue, file_handler, console_handler)
    listener.start()

    _logger = logger
    _listener = listener
    return logger

def get_logger():
    global _logger
    if _logger is None:
        _logger = setup_logger()
    return _logger

def get_debug_logger():
    """Возвращает отдельный логгер для отладочной информации (уровень DEBUG)."""
    global _debug_logger
    if _debug_logger is None:
        _debug_logger = logging.getLogger('DebugLogger')
        _debug_logger.setLevel(logging.DEBUG)
        # Создаём папку для отладочных логов, если её нет
        debug_dir = "debug_logs"
        if not os.path.exists(debug_dir):
            os.makedirs(debug_dir)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        debug_filename = f"debug_{timestamp}.log"
        debug_path = os.path.join(debug_dir, debug_filename)
        fh = logging.FileHandler(debug_path, encoding='utf-8')
        fh.setLevel(logging.DEBUG)
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        fh.setFormatter(formatter)
        _debug_logger.addHandler(fh)
        # Также дублируем в консоль (можно убрать, если не нужно)
        ch = logging.StreamHandler()
        ch.setLevel(logging.DEBUG)
        ch.setFormatter(formatter)
        _debug_logger.addHandler(ch)
    return _debug_logger

# Глобальный логгер для основного процесса
logger = setup_logger()
atexit.register(shutdown_logger)