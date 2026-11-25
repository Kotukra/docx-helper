# utils/debug_decorator.py
import functools
import time
from logger import get_debug_logger

def debug_log(level='DEBUG', enabled_attr='debug_mode'):
    """
    Декоратор для логирования вызовов функций в отладочном режиме.
    Проверяет наличие атрибута 'debug_mode' в первом аргументе (self или settings-словарь).
    Если режим включён, логирует входные параметры, результат и время выполнения.
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Проверяем, включён ли отладочный режим
            debug_enabled = False
            # Ищем в args или kwargs объект с атрибутом debug_mode
            for arg in args:
                if isinstance(arg, dict) and arg.get(enabled_attr, False):
                    debug_enabled = True
                    break
                if hasattr(arg, 'get') and callable(getattr(arg, 'get')):
                    if arg.get(enabled_attr, False):
                        debug_enabled = True
                        break
            if not debug_enabled:
                # Проверяем kwargs
                if kwargs.get(enabled_attr, False):
                    debug_enabled = True
            if not debug_enabled:
                return func(*args, **kwargs)

            logger = get_debug_logger()
            # Логируем вызов
            arg_str = ", ".join([repr(a) for a in args])
            kwarg_str = ", ".join([f"{k}={repr(v)}" for k, v in kwargs.items()])
            all_args = arg_str
            if kwarg_str:
                all_args += (", " if all_args else "") + kwarg_str
            logger.debug(f"Вызов {func.__name__}({all_args})")
            start = time.time()
            try:
                result = func(*args, **kwargs)
                elapsed = time.time() - start
                logger.debug(f"{func.__name__} вернул {repr(result)} за {elapsed:.3f} сек")
                return result
            except Exception as e:
                logger.exception(f"Исключение в {func.__name__}: {e}")
                raise
        return wrapper
    return decorator