#!/usr/bin/env python3
"""Genera un mapa interactivo (map.html) a partir de image_metadata.csv.

Lee el CSV con formato: filename,datetime,latitude,longitude
Ordena cronológicamente y genera un HTML autocontenido (Leaflet + OSM)
donde los puntos están enlazados en orden temporal y coloreados
con un gradiente de color según la hora.

Uso: python3 make_map.py [csv] [salida]
"""

import csv
import json
import math
import sys
from datetime import datetime


def haversine_km(a, b):
    la1, lo1 = math.radians(a[0]), math.radians(a[1])
    la2, lo2 = math.radians(b[0]), math.radians(b[1])
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 2 * 6371 * math.asin(math.sqrt(h))


def load_points(csv_path):
    points = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            try:
                points.append({
                    "file": row["filename"].strip(),
                    "dt": row["datetime"].strip(),
                    "lat": float(row["latitude"]),
                    "lng": float(row["longitude"]),
                })
            except (ValueError, KeyError):
                continue
    points.sort(key=lambda p: datetime.strptime(p["dt"], "%Y:%m:%d %H:%M:%S"))
    return points


def mark_outliers(points, link_km=3000.0, min_group=5):
    """Marca como outlier los puntos que forman grupos pequeños.

    Se encadenan puntos consecutivos (orden temporal) separados menos de
    link_km; los puntos de una cadena con menos de min_group forman un
    grupo (p.ej. errores GPS lejos del viaje).
    """
    n = len(points)
    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    for i in range(n - 1):
        a = (points[i]["lat"], points[i]["lng"])
        b = (points[i + 1]["lat"], points[i + 1]["lng"])
        if haversine_km(a, b) < link_km:
            union(i, i + 1)

    groups = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(i)

    outliers = set()
    for members in groups.values():
        if len(members) < min_group:
            outliers.update(members)

    for i, p in enumerate(points):
        p["outlier"] = i in outliers
    return points


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<title>Mapa cronológico del viaje</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
  html, body { margin: 0; height: 100%; }
  #map { height: 100vh; }
  .legend {
    background: white; padding: 10px 12px; border-radius: 8px;
    box-shadow: 0 1px 6px rgba(0,0,0,.3); font: 12px/1.4 sans-serif;
  }
  .legend .bar {
    height: 10px; width: 180px; margin: 6px 0 4px;
    background: linear-gradient(to right,
      hsl(240,85%,45%), hsl(180,85%,40%), hsl(120,85%,40%),
      hsl(60,85%,45%), hsl(0,85%,45%));
    border-radius: 3px;
  }
  .legend .row { display: flex; justify-content: space-between; }
  .legend .out { color: #666; margin-top: 6px; }
</style>
</head>
<body>
<div id="map"></div>
<script>
const DATA = __DATA__;

const map = L.map('map', { preferCanvas: true }).setView([48, 15], 5);
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
  attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
  maxZoom: 19
}).addTo(map);

const t0 = Date.parse(DATA[0].dt);
const t1 = Date.parse(DATA[DATA.length - 1].dt);

// Azul (inicio) -> cian -> verde -> amarillo -> rojo (fin)
function colorFor(t) {
  const f = (t - t0) / (t1 - t0);
  return 'hsl(' + (240 - 240 * f) + ',85%,45%)';
}

const layer = L.layerGroup().addTo(map);
const bounds = L.latLngBounds([]);

// Puntos
DATA.forEach(function (d, i) {
  const t = Date.parse(d.dt);
  const c = d.outlier ? '#888' : colorFor(t);
  const m = L.circleMarker([d.lat, d.lng], {
    radius: d.outlier ? 6 : 4,
    color: d.outlier ? '#555' : '#222',
    weight: 1,
    dashArray: d.outlier ? '3,3' : null,
    fillColor: c,
    fillOpacity: 1
  });
  m.bindPopup(
    '<b>#' + (i + 1) + ' / ' + DATA.length + '</b><br>' +
    new Date(d.dt).toLocaleString() + '<br>' +
    '<span style="font-size:10px;color:#555">' +
    d.file.split('/').pop() + '</span>' +
    (d.outlier ? '<br><span style="color:#a33">⚠ posible error GPS</span>' : '')
  );
  m.addTo(layer);
  if (!d.outlier) bounds.extend([d.lat, d.lng]);
});

// Enlaces cronológicos (solo entre puntos válidos)
for (let i = 0; i < DATA.length - 1; i++) {
  const a = DATA[i], b = DATA[i + 1];
  if (a.outlier || b.outlier) continue;
  const t = (Date.parse(a.dt) + Date.parse(b.dt)) / 2;
  L.polyline([[a.lat, a.lng], [b.lat, b.lng]], {
    color: colorFor(t), weight: 2.5, opacity: 0.8
  }).addTo(layer);
}

map.fitBounds(bounds.pad(0.05));

// Leyenda
const legend = L.control({ position: 'bottomright' });
legend.onAdd = function () {
  const div = L.DomUtil.create('div', 'legend');
  const fmt = function (t) {
    return new Date(t).toLocaleString('es-ES',
      { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' });
  };
  div.innerHTML =
    '<b>Orden cronológico</b>' +
    '<div class="bar"></div>' +
    '<div class="row"><span>' + fmt(t0) + '</span><span>' + fmt(t1) + '</span></div>' +
    '<div class="out">⚠ gris = posible error GPS</div>';
  return div;
};
legend.addTo(map);
</script>
</body>
</html>
"""


def main():
    csv_path = sys.argv[1] if len(sys.argv) > 1 else "image_metadata.csv"
    out_path = sys.argv[2] if len(sys.argv) > 2 else "map.html"

    points = mark_outliers(load_points(csv_path))
    n_out = sum(1 for p in points if p["outlier"])
    data = [{
        "file": p["file"],
        "dt": datetime.strptime(p["dt"], "%Y:%m:%d %H:%M:%S").isoformat(),
        "lat": p["lat"],
        "lng": p["lng"],
        "outlier": p["outlier"],
    } for p in points]

    html = HTML_TEMPLATE.replace("__DATA__", json.dumps(data))
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"✅ {out_path} generado: {len(data)} puntos ({n_out} outliers) "
          f"del {data[0]['dt']} al {data[-1]['dt']}")


if __name__ == "__main__":
    main()
