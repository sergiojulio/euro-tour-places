import csv

def csv_to_kml(csv_path, kml_path):
    with open(csv_path, newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        points = [
            f"{row['longitude']},{row['latitude']},0"
            for row in sorted(reader, key=lambda r: r['datetime'])
        ]

    with open(kml_path, 'w', encoding='utf-8') as f:
        f.write("""<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <name>GPS Path</name>
    <Placemark>
      <name>Ordered Path</name>
      <LineString>
        <tessellate>1</tessellate>
        <coordinates>\n""")
        for point in points:
            f.write(f"          {point}\n")
        f.write("""        </coordinates>
      </LineString>
    </Placemark>
  </Document>
</kml>""")

# Usage
csv_to_kml("./image_metadata.csv", "./gps_path.kml")
