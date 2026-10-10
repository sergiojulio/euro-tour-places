#!/usr/bin/env python3
"""Genera un SVG del viaje a partir de image_metadata.csv.

Fondo simple con los países de Europa (countries_110m.geojson,
Natural Earth 110m), la ruta enlazada y los puntos coloreados
cronológicamente (mismo gradiente azul->rojo que map.html),
etiquetas de ciudad (las carpetas del CSV) y una leyenda.

Uso: python3 make_map_svg.py [csv] [salida]
"""

import json
import math
import os
import sys
from collections import OrderedDict
from datetime import datetime

from xml.sax.saxutils import escape

from make_map import load_points, mark_outliers

COLOR_STEPS = 32  # pasos del gradiente (agrupa segmentos por color)
COUNTRIES_GEOJSON = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                 "countries_110m.geojson")


def color_for(f):
    """Misma fórmula que el JS de map.html: azul (0) -> rojo (1)."""
    return f"hsl({240 - 240 * f:.0f}, 85%, 45%)"


def main():
    csv_path = sys.argv[1] if len(sys.argv) > 1 else "image_metadata.csv"
    out_path = sys.argv[2] if len(sys.argv) > 2 else "map.svg"

    points = mark_outliers(load_points(csv_path))
    valid = [p for p in points if not p["outlier"]]

    # Límites y proyección equirectangular (corregida por cos(lat) medio)
    lats = [p["lat"] for p in valid]
    lngs = [p["lng"] for p in valid]
    minlat, maxlat = min(lats), max(lats)
    minlng, maxlng = min(lngs), max(lngs)
    pad_lat = (maxlat - minlat) * 0.07
    pad_lng = (maxlng - minlng) * 0.07
    minlat -= pad_lat
    maxlat += pad_lat
    minlng -= pad_lng
    maxlng += pad_lng
    midlat = (maxlat + minlat) / 2
    scale = 32.0  # px por grado de latitud

    def X(lng):
        return (lng - minlng) * math.cos(math.radians(midlat)) * scale

    def Y(lat):
        return (maxlat - lat) * scale

    W = (maxlng - minlng) * math.cos(math.radians(midlat)) * scale
    H = (maxlat - minlat) * scale
    M = 70.0  # margen para etiquetas
    W, H = W + 2 * M, H + 2 * M

    # Fondo: países de Europa (Natural Earth 110m, muy simplificado)
    bg_paths = []
    bg_labels = []
    try:
        with open(COUNTRIES_GEOJSON, encoding="utf-8") as f:
            geo = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        geo = {"features": []}
    for feat in geo.get("features", []):
        geom = feat.get("geometry") or {}
        name = (feat.get("properties") or {}).get("NAME") or ""
        coords = geom.get("coordinates") or []
        gtype = geom.get("type")
        if gtype == "Polygon":
            rings = coords
        elif gtype == "MultiPolygon":
            rings = [ring for poly in coords for ring in poly]
        else:
            continue
        pts = [c for ring in rings for c in ring]
        if not pts:
            continue
        minx = min(c[0] for c in pts); maxx = max(c[0] for c in pts)
        miny = min(c[1] for c in pts); maxy = max(c[1] for c in pts)
        if maxx < minlng or minx > maxlng or maxy < minlat or miny > maxlat:
            continue
        d = ""
        label_pt = None
        largest = 0
        for ring in rings:
            if len(ring) > largest:
                largest = len(ring)
                label_pt = (sum(c[0] for c in ring) / len(ring),
                            sum(c[1] for c in ring) / len(ring))
            ringd = f"M{X(ring[0][0]):.1f},{Y(ring[0][1]):.1f}"
            for c in ring[1:]:
                ringd += f"L{X(c[0]):.1f},{Y(c[1]):.1f}"
            d += ringd + "Z"
        if d:
            bg_paths.append(d)
            if name and label_pt and minlat <= label_pt[1] <= maxlat \
                    and minlng <= label_pt[0] <= maxlng:
                bg_labels.append((name, X(label_pt[0]), Y(label_pt[1])))

    t0 = datetime.strptime(valid[0]["dt"], "%Y:%m:%d %H:%M:%S")
    t1 = datetime.strptime(valid[-1]["dt"], "%Y:%m:%d %H:%M:%S")
    span = (t1 - t0).total_seconds()

    def tf(p):
        return (datetime.strptime(p["dt"], "%Y:%m:%d %H:%M:%S") - t0).total_seconds() / span

    svg = []
    svg.append(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W:.0f} {H:.0f}" '
               f'width="{W:.0f}" height="{H:.0f}" font-family="sans-serif">')
    svg.append(f'<rect width="100%" height="100%" fill="#ffffff"/>')

    # Fondo de países
    if bg_paths:
        svg.append('<g fill="#eef0ee" stroke="#c4c9c4" stroke-width="0.75" '
                   'stroke-linejoin="round">')
        for d in bg_paths:
            svg.append(f'<path d="{d}"/>')
        svg.append('</g>')
        svg.append('<g font-size="11" fill="#a0a6a0" text-anchor="middle">')
        for name, x, y in bg_labels:
            svg.append(f'<text x="{x:.1f}" y="{y:.1f}">{escape(name)}</text>')
        svg.append('</g>')

    # Título
    svg.append(f'<text x="{M}" y="34" font-size="20" font-weight="bold" fill="#222" '
               f'style="paint-order:stroke" stroke="#ffffff" stroke-width="5">'
               f'El viaje: {t0:%d %b} a {t1:%d %b %Y}</text>')

    # Segmentos de ruta agrupados por paso de color (un path por paso)
    groups = OrderedDict()
    for i in range(len(valid) - 1):
        a, b = valid[i], valid[i + 1]
        step = int(((tf(a) + tf(b)) / 2) * (COLOR_STEPS - 1))
        groups.setdefault(step, []).append((a, b))
    for step in sorted(groups):
        f = step / (COLOR_STEPS - 1)
        d = " ".join(
            f"M{X(a['lng']):.1f} {Y(a['lat']):.1f}L{X(b['lng']):.1f} {Y(b['lat']):.1f}"
            for a, b in groups[step]
        )
        svg.append(f'<path d="{d}" stroke="{color_for(f)}" stroke-width="2.5" '
                   f'fill="none" opacity="0.85" stroke-linecap="round"/>')

    # Puntos
    for p in valid:
        svg.append(f'<circle cx="{X(p["lng"]):.1f}" cy="{Y(p["lat"]):.1f}" r="1.8" '
                   f'fill="{color_for(tf(p))}" stroke="#333" stroke-width="0.4"/>')

    # Etiquetas de ciudad: primera foto de cada carpeta
    seen = {}
    for i, p in enumerate(valid):
        parts = p["file"].split("/")
        folder = parts[5] if len(parts) > 5 else p["file"]
        if folder in seen:
            continue
        seen[folder] = i
        x, y = X(p["lng"]), Y(p["lat"])
        svg.append(
            f'<text x="{x + 8:.1f}" y="{y - 6:.1f}" font-size="13" fill="#222" '
            f'style="paint-order:stroke" stroke="#ffffff" stroke-width="3.5">'
            f'{escape(folder)}</text>'
        )

    # Marcas de inicio y fin
    for p, label in ((valid[0], "Inicio"), (valid[-1], "Fin")):
        x, y = X(p["lng"]), Y(p["lat"])
        svg.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="5" fill="none" '
                   f'stroke="#222" stroke-width="1.5"/>')
        svg.append(f'<text x="{x + 10:.1f}" y="{y + 14:.1f}" font-size="12" '
                   f'font-weight="bold" fill="#222" style="paint-order:stroke" '
                   f'stroke="#ffffff" stroke-width="3.5">{label}</text>')

    # Leyenda: barra de gradiente
    lx, ly = M, H - M - 20
    stops = " ".join(
        f'<stop offset="{i * 100 // (COLOR_STEPS - 1)}%" stop-color="{color_for(i / (COLOR_STEPS - 1))}"/>'
        for i in range(COLOR_STEPS)
    )
    svg.append(f'<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="0">{stops}'
               f'</linearGradient></defs>')
    svg.append(f'<text x="{lx}" y="{ly - 8:.0f}" font-size="12" fill="#444">'
               f'Orden cronológico</text>')
    svg.append(f'<rect x="{lx}" y="{ly:.0f}" width="180" height="10" fill="url(#g)" rx="2"/>')
    svg.append(f'<text x="{lx}" y="{ly + 24:.0f}" font-size="11" fill="#666">{t0:%d %b %H:%M}</text>')
    svg.append(f'<text x="{lx + 180}" y="{ly + 24:.0f}" font-size="11" fill="#666" '
               f'text-anchor="end">{t1:%d %b %H:%M}</text>')

    svg.append("</svg>")

    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(svg))
    print(f"✅ {out_path} generado ({W:.0f}x{H:.0f}, {len(valid)} puntos)")


if __name__ == "__main__":
    main()
