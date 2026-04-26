import matplotlib

matplotlib.use('Agg')
import matplotlib.pyplot as plt
from datetime import datetime
import os
import warnings
from PIL import Image

warnings.filterwarnings('ignore')


def get_chart_url(week_data: list[dict]) -> str:
    # 1. Извлекаем данные (API уже вернул их в порядке Пн-Вс)
    week_values = [d['energy_percentage'] for d in week_data]

    # 2. Загружаем фон
    if not os.path.exists('bg_lunar.png'):
        print("❌ bg_lunar.png не найден!")
        return None

    bg = Image.open('bg_lunar.png').convert('RGBA')
    bg_w, bg_h = bg.size

    # Координаты зоны
    rel_left = 0.30
    rel_right = 0.80
    rel_top = 0.18
    rel_bottom = 0.75

    plot_x = int(bg_w * rel_left)
    plot_y = int(bg_h * rel_top)
    plot_w = int(bg_w * (rel_right - rel_left))
    plot_h = int(bg_h * (rel_bottom - rel_top))

    # 3. Создаём фигуру
    dpi = 100
    fig = plt.figure(figsize=(plot_w / dpi, plot_h / dpi), dpi=dpi)
    fig.patch.set_alpha(0)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_facecolor('none')

    # 4. Рисуем график (7 дней, данные как есть)
    x_pos = range(len(week_values))

    ax.plot(x_pos, week_values,
            color='#FFD700',
            linewidth=2.5,
            marker='o',
            markersize=7,
            markerfacecolor='#FFD700',
            markeredgecolor='#FFFFFF',
            markeredgewidth=1.5,
            alpha=0.95,
            zorder=10)

    ax.set_ylim(0, 100)
    ax.set_xlim(-0.2, 6.2)

    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.tick_params(length=0, labelbottom=False, labelleft=False)

    # 5. Сохраняем
    temp_graph = "temp_graph.png"
    plt.savefig(temp_graph, dpi=dpi, transparent=True, pad_inches=0)
    plt.close()

    try:
        overlay = Image.open(temp_graph).convert('RGBA')
        bg.paste(overlay, (plot_x, plot_y), overlay)

        bg = bg.convert('RGB')
        filename = f"lunar_{int(datetime.now().timestamp())}.jpg"
        bg.save(filename, 'JPEG', quality=75, optimize=True, progressive=True)

        os.remove(temp_graph)

        size_kb = os.path.getsize(filename) / 1024
        print(f"✅ График создан: {filename} ({size_kb:.1f} KB)")
        return filename
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        if os.path.exists(temp_graph):
            os.remove(temp_graph)
        return None