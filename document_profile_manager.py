"""Менеджер профилей оформления DOCX.

Профили хранятся отдельно от общих настроек приложения в ./profiles/*.json.
Поддерживает текущую плоскую схему и вложенную схему из раннего прототипа.
"""
from __future__ import annotations
import json
import re
from pathlib import Path
from copy import deepcopy

PROFILE_DIR = Path(__file__).resolve().parent / 'profiles'
DEFAULT_PROFILE = 'jasmine'


def _normalize(data: dict, path: Path | None = None) -> dict:
    p = deepcopy(data)
    if 'profile_id' not in p and 'id' in p:
        p['profile_id'] = p['id']
    if 'profile_name' not in p and 'name' in p:
        p['profile_name'] = p['name']
    # Совместимость с ранней вложенной схемой.
    page, body = p.get('page', {}), p.get('body', {})
    h1, h2, code = p.get('heading1', {}), p.get('heading2', {}), p.get('code', {})
    if page:
        p.setdefault('page_width', page.get('width_cm', 21.0))
        p.setdefault('page_height', page.get('height_cm', 29.7))
        p.setdefault('margins', page.get('margins_cm', {}))
    if body:
        mapping = {'font':'font_name','size_pt':'font_size','alignment':'alignment',
                   'line_spacing':'line_spacing_multiple','first_line_indent_cm':'first_line_indent',
                   'space_before_pt':'space_before','space_after_pt':'space_after'}
        for src, dst in mapping.items():
            if src in body: p.setdefault(dst, body[src])
    for src, dst in ((h1, 'heading_1'), (h2, 'heading_2')):
        if src:
            p.setdefault(dst, {})
            for key, value in src.items():
                p[dst].setdefault({'font':'font_name','size_pt':'font_size','alignment':'alignment',
                                   'space_before_pt':'space_before','space_after_pt':'space_after'}.get(key,key), value)
    if code:
        mapping = {'font':'code_font_name','size_pt':'code_font_size','left_indent_cm':'code_left_indent',
                   'first_line_indent_cm':'code_first_line_indent','line_spacing':'code_line_spacing',
                   'space_before_pt':'code_space_before','space_after_pt':'code_space_after'}
        for src, dst in mapping.items():
            if src in code: p.setdefault(dst, code[src])
    p.setdefault('profile_id', path.stem if path else 'custom')
    p.setdefault('profile_name', p['profile_id'])
    return p



def _validate_profile(data: dict) -> None:
    """Проверяет ключевые числовые и перечислимые параметры профиля."""
    def number(key, default, low, high):
        try:
            value = float(data.get(key, default))
        except (TypeError, ValueError):
            raise ValueError(f"Параметр {key}: требуется число")
        if not low <= value <= high:
            raise ValueError(f"Параметр {key}: допустимый диапазон {low}–{high}")
        return value

    width = number('page_width', 21.0, 10.0, 100.0)
    height = number('page_height', 29.7, 10.0, 100.0)
    margins = data.get('margins', {})
    if not isinstance(margins, dict):
        raise ValueError('Параметр margins должен быть JSON-объектом')
    vals = {}
    for side in ('top', 'bottom', 'left', 'right'):
        try:
            vals[side] = float(margins.get(side, 0))
        except (TypeError, ValueError):
            raise ValueError(f'Поле margins.{side}: требуется число')
        if not 0 <= vals[side] <= 10:
            raise ValueError(f'Поле margins.{side}: допустимый диапазон 0–10 см')
    if vals['left'] + vals['right'] >= width or vals['top'] + vals['bottom'] >= height:
        raise ValueError('Сумма полей страницы должна быть меньше размера листа')

    number('font_size', 14, 6, 72)
    number('line_spacing_multiple', 1.5, 0.5, 4)
    for key in ('code_font_size',):
        if key in data:
            number(key, 11, 6, 72)
    for key in ('alignment', 'code_alignment'):
        if key in data and data[key] not in ('left', 'center', 'right', 'justify'):
            raise ValueError(f'Недопустимое значение {key}: {data[key]}')
    for section in ('heading_1', 'heading_2', 'heading_3'):
        conf = data.get(section, {})
        if not isinstance(conf, dict):
            raise ValueError(f'Параметр {section} должен быть JSON-объектом')
        if 'font_size' in conf and not 6 <= float(conf['font_size']) <= 72:
            raise ValueError(f'{section}.font_size: допустимый диапазон 6–72 пт')
        if 'alignment' in conf and conf['alignment'] not in ('left', 'center', 'right', 'justify'):
            raise ValueError(f'Недопустимое значение {section}.alignment')


def list_profiles() -> list[dict]:
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    result = []
    for path in sorted(PROFILE_DIR.glob('*.json')):
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
            if isinstance(data, dict):
                result.append(_normalize(data, path))
        except (OSError, json.JSONDecodeError):
            continue
    return result


def get_profile(profile_id: str | None) -> dict | None:
    for profile in list_profiles():
        if profile.get('profile_id') == profile_id:
            return profile
    return None


def save_profile(profile: dict, overwrite: bool = True) -> Path:
    if not isinstance(profile, dict):
        raise ValueError('Профиль должен быть JSON-объектом')
    data = _normalize(profile)
    profile_id = str(data.get('profile_id', '')).strip()
    if not re.fullmatch(r'[a-zA-Z0-9_-]{2,48}', profile_id):
        raise ValueError('ID профиля: 2–48 символов, только латиница, цифры, _ и -')
    if not str(data.get('profile_name', '')).strip():
        raise ValueError('Укажите название профиля')
    _validate_profile(data)
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    path = PROFILE_DIR / f'{profile_id}.json'
    if path.exists() and not overwrite:
        raise FileExistsError(path)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    return path


def delete_profile(profile_id: str) -> bool:
    if not isinstance(profile_id, str) or not re.fullmatch(r'[a-zA-Z0-9_-]{2,48}', profile_id):
        raise ValueError('Некорректный ID профиля')
    if profile_id in ('jasmine', 'legacy_gost'):
        raise ValueError('Встроенные профили нельзя удалять')
    path = PROFILE_DIR / f'{profile_id}.json'
    if not path.exists():
        return False
    path.unlink()
    return True


def resolve_profile_settings(settings: dict | None) -> dict:
    merged = deepcopy(settings or {})
    profile_id = merged.get('document_profile', DEFAULT_PROFILE)
    profile = get_profile(profile_id) or get_profile(DEFAULT_PROFILE)
    if not profile:
        return merged
    merged['_document_style_profile'] = profile
    merged['page_width'] = profile.get('page_width', merged.get('page_width', 21.0))
    merged['page_height'] = profile.get('page_height', merged.get('page_height', 29.7))
    if isinstance(profile.get('margins'), dict):
        merged['margins'] = deepcopy(profile['margins'])
    # Перекрываем только параметры, реально определённые профилем.
    keys = ('font_name','font_size','alignment','line_spacing_multiple','first_line_indent',
            'left_indent','right_indent','space_before','space_after','code_font_name',
            'code_font_size','code_alignment','code_left_indent','code_first_line_indent',
            'code_line_spacing','code_space_before','code_space_after',
            'page_numbers_skip_first','page_numbers_start',
            'page_numbers_position','page_numbers_align')
    for key in keys:
        if key in profile: merged[key] = profile[key]
    return merged
