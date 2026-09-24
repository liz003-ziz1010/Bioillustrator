import os
from vtracer import vtracer

# -------- SETTINGS -------- #
input_folder  = "images"   # folder containing your PNG/JPG images
output_folder = "svg_output"     # folder where SVGs will be saved

# create output folder if it doesn't exist
os.makedirs(output_folder, exist_ok=True)

# supported image extensions
valid_ext = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff"}

# loop over images
for filename in os.listdir(input_folder):
    ext = os.path.splitext(filename)[1].lower()
    if ext not in valid_ext:
        continue

    input_path = os.path.join(input_folder, filename)
    output_name = os.path.splitext(filename)[0] + ".svg"
    output_path = os.path.join(output_folder, output_name)

    print(f"Vectorizing: {filename} → {output_name}")

    # use the correct function in your vtracer version
    vtracer.convert_image_to_svg_py(input_path, output_path)

print("✔ All images converted to SVG successfully!")
