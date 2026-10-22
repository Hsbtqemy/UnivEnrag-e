# Icônes de l'application (static/icons/). Pillow n'est pas une dépendance du projet :
#   uv run --no-project --with pillow python scripts/icones.py static/icons
"""Génère les icônes de l'application (à relancer seulement si le dessin change)."""

import sys
from pathlib import Path

from PIL import Image, ImageDraw

ACCENT = (47, 93, 140)
WHITE = (255, 255, 255)
SOFT = (230, 238, 247)
out = Path(sys.argv[1])


def draw(size, *, safe=1.0, rounded=True):
    """Un calendrier blanc sur fond bleu ; `safe` réduit le dessin (zone sûre maskable)."""
    scale = 4  # suréchantillonnage pour des bords nets
    s = size * scale
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    if rounded:
        d.rounded_rectangle([0, 0, s - 1, s - 1], radius=int(s * 0.22), fill=ACCENT)
    else:
        d.rectangle([0, 0, s - 1, s - 1], fill=ACCENT)
    w = s * 0.56 * safe
    x0, y0 = (s - w) / 2, (s - w) / 2 + s * 0.02
    x1, y1 = x0 + w, y0 + w * 0.92
    r = w * 0.1
    d.rounded_rectangle([x0, y0, x1, y1], radius=r, fill=WHITE)
    d.rounded_rectangle([x0, y0, x1, y0 + w * 0.24], radius=r, fill=SOFT)
    d.rectangle([x0, y0 + w * 0.14, x1, y0 + w * 0.24], fill=SOFT)
    for fx in (0.3, 0.7):  # anneaux de reliure
        cx = x0 + w * fx
        ring = [cx - w * 0.045, y0 - w * 0.08, cx + w * 0.045, y0 + w * 0.1]
        d.rounded_rectangle(ring, radius=w * 0.04, fill=ACCENT)
    cell = w * 0.17
    for row in range(3):
        for col in range(3):
            cx = x0 + w * (0.25 + col * 0.25)
            cy = y0 + w * (0.42 + row * 0.18)
            colour = ACCENT if (row, col) == (1, 1) else (170, 190, 210)
            box = [cx - cell / 2, cy - cell * 0.35, cx + cell / 2, cy + cell * 0.35]
            d.rounded_rectangle(box, radius=cell * 0.15, fill=colour)
    return img.resize((size, size), Image.LANCZOS)


out.mkdir(parents=True, exist_ok=True)
draw(192).save(out / "icone-192.png")
draw(512).save(out / "icone-512.png")
draw(512, safe=0.8, rounded=False).save(out / "icone-maskable-512.png")
draw(180, rounded=False).convert("RGB").save(out / "apple-touch-icon.png")
draw(32).save(out / "favicon-32.png")
print("ok")
