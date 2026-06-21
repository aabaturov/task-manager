"""SPEC-003: визуальный редизайн панели «Дела на день» (DayPanel).

Это чисто визуальная доработка фронтенда (React + CSS-переменные), а в окружении
нет Node/npm. Поэтому проверки выполнены как статические утверждения над исходными
файлами фронтенда: они фиксируют ключевые маркеры приёмки из спецификации, чтобы
регресс редизайна ловился существующим раннером pytest.

Поведение модели/API/слотов тесты НЕ трогают — спека запрещает их менять.
"""

import re
from pathlib import Path

import pytest

FRONTEND = Path(__file__).resolve().parents[2] / "frontend" / "src"
CSS = (FRONTEND / "styles.css").read_text(encoding="utf-8")
DAYPANEL = (FRONTEND / "DayPanel.jsx").read_text(encoding="utf-8")


def _block(css: str, selector: str) -> str:
    """Вернуть тело первого CSS-правила для точного селектора `selector {...}`."""
    pattern = re.compile(
        r"(?:^|\})\s*" + re.escape(selector) + r"\s*\{([^}]*)\}",
        re.MULTILINE,
    )
    m = pattern.search(css)
    assert m, f"CSS-правило для селектора '{selector}' не найдено"
    return m.group(1)


# --------------------------------------------------------------------------- #
# Фича 1: контейнер панели — светлая приподнятая карточка                      #
# --------------------------------------------------------------------------- #

def test_root_has_day_panel_variables():
    """Цвета/радиусы/тени панели вынесены в CSS-переменные :root (без хардкода)."""
    root = _block(CSS, ":root")
    for var in ("--day-bg", "--day-radius", "--day-shadow", "--day-accent"):
        assert var in root, f"В :root отсутствует переменная {var}"


def test_day_panel_uses_variables_not_hardcode():
    body = _block(CSS, ".day-panel")
    assert "var(--day-bg)" in body
    assert "var(--day-radius)" in body
    assert "var(--day-shadow)" in body
    # Никаких сырых rgba()/#hex прямо в правиле — всё через переменные.
    assert "rgba(" not in body, "тень/цвет панели должны идти из переменной"
    assert "#" not in body, "цвет панели должен идти из переменной, не из hex"


def test_day_panel_no_dark_header_no_hard_border():
    body = _block(CSS, ".day-panel")
    # Жёсткой рамки нет: либо border:none, либо вовсе нет border-объявления.
    if "border:" in body.replace(" ", "") or re.search(r"\bborder\s*:", body):
        assert re.search(r"border\s*:\s*none", body), (
            "у панели не должно быть жёсткой рамки"
        )
    # Толстой чёрной обводки 2px solid var(--ink) быть не должно.
    assert "2px solid var(--ink)" not in body


def test_day_panel_radius_larger_than_project_card():
    """Скругление панели крупнее, чем у проектных карточек (--r = 12px)."""
    root = _block(CSS, ":root")

    def px(var):
        m = re.search(re.escape(var) + r"\s*:\s*(\d+)px", root)
        assert m, f"{var} не задан в px"
        return int(m.group(1))

    assert px("--day-radius") > px("--r"), "радиус панели должен быть крупнее проекта"


def test_day_panel_height_fits_content():
    """Панель не растягивается на пустую высоту закреплённой зоны."""
    body = _block(CSS, ".day-panel")
    assert "fit-content" in body


# --------------------------------------------------------------------------- #
# Фича 2: заголовок панели — лёгкий лейбл + иконка-пин                         #
# --------------------------------------------------------------------------- #

def test_day_title_has_no_dark_plaque():
    body = _block(CSS, ".day-title")
    assert "background: transparent" in body, "заголовок без тёмной плашки-фона"
    assert "var(--ink)" not in body.split("color")[0] or "background: var(--ink)" not in body
    assert "background: var(--ink)" not in body, "у заголовка нет чёрной плашки"


def test_day_title_is_uppercase_letterspaced():
    body = _block(CSS, ".day-title")
    assert "uppercase" in body
    assert "letter-spacing" in body


def test_daypanel_renders_pin_icon():
    assert 'name="pin"' in DAYPANEL, "иконка-пин у заголовка должна присутствовать"
    assert "day-pin" in DAYPANEL


def test_pin_icon_is_thin_line_style():
    """Пин рисуется тем же инлайн-SVG набором, что и прочие иконки."""
    icon = (FRONTEND / "Icon.jsx").read_text(encoding="utf-8")
    assert "pin:" in icon, "путь иконки 'pin' должен быть в общем наборе PATHS"


# --------------------------------------------------------------------------- #
# Фича 3: пустые слоты — компактный плейсхолдер в одну строку                  #
# --------------------------------------------------------------------------- #

def test_empty_slot_is_clickable_and_opens_editor():
    """Клик/тап по плейсхолдеру открывает тот же редактор слота."""
    assert "slot-empty-add" in DAYPANEL
    # Кнопка плейсхолдера должна вызывать setEditingIndex (как «Изменить»).
    block = DAYPANEL.split("slot-empty-add")[1]
    assert "setEditingIndex(slot.index)" in block


def test_empty_slot_compact_one_line_height():
    body = _block(CSS, ".slot-empty-add")
    assert "var(--day-empty-h)" in body, "высота пустого слота — из переменной"
    root = _block(CSS, ":root")
    m = re.search(r"--day-empty-h\s*:\s*(\d+)px", root)
    assert m and int(m.group(1)) <= 40, "пустой слот не выше одной строки (~36-40px)"


def test_empty_slot_has_dashed_outline_and_muted_text():
    body = _block(CSS, ".slot-empty-add")
    assert "dashed" in body, "у плейсхолдера лёгкий пунктирный контур"
    assert "var(--muted)" in body, "приглушённый текст плейсхолдера"


def test_no_full_height_gray_placeholder_block():
    """Старого блока «пусто» в полную высоту больше нет."""
    assert ">пусто<" not in DAYPANEL


# --------------------------------------------------------------------------- #
# Фича 4: заполненный слот и задачи — компактные чекбоксы                      #
# --------------------------------------------------------------------------- #

def test_slot_checkbox_uses_unified_size_variable():
    body = _block(CSS, ".check.sm")
    assert "var(--check-sm)" in body, "чекбокс слота берёт размер из переменной"


def test_slot_checkbox_small():
    root = _block(CSS, ":root")
    m = re.search(r"--check-sm\s*:\s*(\d+)px", root)
    assert m and 16 <= int(m.group(1)) <= 20, "чекбокс слота мельче (~18-20px)"


def test_slot_name_is_muted_letterspaced_label():
    body = _block(CSS, ".slot-name")
    assert "var(--muted)" in body
    assert "letter-spacing" in body
    assert "uppercase" in body


def test_long_task_text_clamped_to_two_lines():
    body = _block(CSS, ".slot-task-text")
    assert "-webkit-line-clamp: 2" in body or "line-clamp: 2" in body
    assert "overflow: hidden" in body


def test_long_project_label_single_line_ellipsis():
    body = _block(CSS, ".slot-task-project")
    assert "text-overflow: ellipsis" in body
    assert "white-space: nowrap" in body


def test_slot_separators_are_light_not_bold():
    """Разделители слотов — тонкие/светлые (var(--line)), без жирных линий."""
    body = _block(CSS, ".slot")
    assert "var(--line)" in body
    assert "var(--line-2)" not in body  # --line-2 темнее — не для разделителей


def test_edit_button_is_hover_reveal_ghost():
    """Кнопка «Изменить» призрачная: скрыта под hover, видна на тач."""
    assert "@media (hover: hover)" in CSS
    hover_section = CSS.split("@media (hover: hover)")[1]
    assert ".slot-head .ghost" in hover_section
    assert "opacity: 0" in hover_section


def test_slot_state_uses_single_done_flag():
    """Регресс: отметка в слоте идёт через единое поле done (без новой модели)."""
    assert "{ done: !task.done }" in DAYPANEL
    assert "onUpdateTask(task.id" in DAYPANEL


def test_no_api_or_model_changes_in_daypanel():
    """Спека запрещает трогать API/модель: DayPanel остаётся представлением."""
    # Никаких прямых fetch/api-вызовов внутри компонента — только через пропсы.
    assert "fetch(" not in DAYPANEL
    assert "api." not in DAYPANEL


# --------------------------------------------------------------------------- #
# Граничные случаи (компактность во всех состояниях)                           #
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("selector", [".day-panel", ".day-title", ".slot-empty-add"])
def test_visual_blocks_present(selector):
    """Базовая защита: ключевые правила редизайна существуют в CSS."""
    assert _block(CSS, selector)
