import matplotlib

matplotlib.use('Agg')
import matplotlib.pyplot as plt
from datetime import datetime
import os
import logging
import warnings
from PIL import Image, ImageDraw

from paths import TEMP_DIR, ensure_runtime_dirs, find_lunar_background

warnings.filterwarnings('ignore')
logger = logging.getLogger(__name__)

DEFAULT_BG_SIZE = (800, 600)
FALLBACK_BG_COLOR = (15, 32, 72, 255)


def _load_lunar_background() -> Image.Image:
    bg_path = find_lunar_background()
    if bg_path:
        return Image.open(bg_path).convert("RGBA")

    logger.warning("bg_lunar.png не найден — используется запасной синий фон")
    bg = Image.new("RGBA", DEFAULT_BG_SIZE, FALLBACK_BG_COLOR)
    draw = ImageDraw.Draw(bg)
    for y in range(bg.height):
        shade = int(15 + (y / bg.height) * 25)
        draw.line([(0, y), (bg.width, y)], fill=(shade, shade + 17, shade + 57, 255))
    return bg


def get_chart_url(week_data: list[dict]) -> str | None:
    week_values = [d['energy_percentage'] for d in week_data]
    ensure_runtime_dirs()

    bg = _load_lunar_background()
    bg_w, bg_h = bg.size

    rel_left = 0.30
    rel_right = 0.80
    rel_top = 0.18
    rel_bottom = 0.75

    plot_x = int(bg_w * rel_left)
    plot_y = int(bg_h * rel_top)
    plot_w = int(bg_w * (rel_right - rel_left))
    plot_h = int(bg_h * (rel_bottom - rel_top))

    dpi = 100
    fig = plt.figure(figsize=(plot_w / dpi, plot_h / dpi), dpi=dpi)
    fig.patch.set_alpha(0)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_facecolor('none')

    x_pos = range(len(week_values))
    ax.plot(
        x_pos, week_values,
        color='#FFD700',
        linewidth=2.5,
        marker='o',
        markersize=7,
        markerfacecolor='#FFD700',
        markeredgecolor='#FFFFFF',
        markeredgewidth=1.5,
        alpha=0.95,
        zorder=10,
    )

    ax.set_ylim(0, 100)
    ax.set_xlim(-0.2, 6.2)

    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.tick_params(length=0, labelbottom=False, labelleft=False)

    temp_graph = TEMP_DIR / f"temp_graph_{int(datetime.now().timestamp())}.png"
    try:
        plt.savefig(temp_graph, dpi=dpi, transparent=True, pad_inches=0)
        plt.close()

        overlay = Image.open(temp_graph).convert('RGBA')
        bg.paste(overlay, (plot_x, plot_y), overlay)

        filename = TEMP_DIR / f"lunar_{int(datetime.now().timestamp())}.jpg"
        bg.convert('RGB').save(filename, 'JPEG', quality=85, optimize=True, progressive=True)

        size_kb = os.path.getsize(filename) / 1024
        logger.info("График создан: %s (%.1f KB)", filename.name, size_kb)
        return str(filename)
    except Exception as exc:
        logger.error("Ошибка генерации графика: %s", exc)
        plt.close()
        return None
    finally:
        if temp_graph.exists():
            temp_graph.unlink()
