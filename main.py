import os
import csv
from PIL import Image
import piexif
from pathlib import Path

def get_decimal_from_dms(dms, ref):
    degrees, minutes, seconds = dms
    decimal = degrees + minutes / 60 + seconds / 3600
    if ref in ['S', 'W']:
        decimal = -decimal
    return decimal

def extract_metadata(image_path):
    try:
        img = Image.open(image_path)
        exif_data = piexif.load(img.info.get("exif", b""))

        # Date and time
        dt = exif_data["Exif"].get(piexif.ExifIFD.DateTimeOriginal)
        datetime_str = dt.decode() if dt else "N/A"

        # GPS
        gps_data = exif_data.get("GPS", {})
        if gps_data:
            lat = gps_data.get(piexif.GPSIFD.GPSLatitude)
            lat_ref = gps_data.get(piexif.GPSIFD.GPSLatitudeRef, b'').decode()
            lon = gps_data.get(piexif.GPSIFD.GPSLongitude)
            lon_ref = gps_data.get(piexif.GPSIFD.GPSLongitudeRef, b'').decode()

            latitude = get_decimal_from_dms([x[0]/x[1] for x in lat], lat_ref) if lat else None
            longitude = get_decimal_from_dms([x[0]/x[1] for x in lon], lon_ref) if lon else None
        else:
            latitude = longitude = None

        return {
            "filename": str(image_path),
            "datetime": datetime_str,
            "latitude": latitude,
            "longitude": longitude
        }

    except Exception as e:
        print(f"Error reading {image_path}: {e}")
        return None

def process_folder_recursive(folder_path, output_csv):
    image_paths = list(Path(folder_path).rglob("*.jpg")) + list(Path(folder_path).rglob("*.jpeg"))

    with open(output_csv, mode='w', newline='', encoding='utf-8') as csvfile:
        fieldnames = ['filename', 'datetime', 'latitude', 'longitude']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()

        for image_path in image_paths:
            metadata = extract_metadata(image_path)
            if metadata:
                writer.writerow(metadata)

    print(f"✅ Metadata saved to {output_csv}")

input_folder = "/media/sergio/120A-2F39/EURO TOUR/"
output_file = "./image_metadata.csv"

process_folder_recursive(input_folder, output_file)


