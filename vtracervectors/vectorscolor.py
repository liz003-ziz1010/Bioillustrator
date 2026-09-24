import os
import base64
from pathlib import Path

def image_to_svg(input_path, output_path):
    # read image as bytes
    with open(input_path, "rb") as img_file:
        img_bytes = img_file.read()

    # convert to base64
    img_base64 = base64.b64encode(img_bytes).decode("utf-8")

    # detect MIME type
    ext = input_path.split(".")[-1].lower()
    mime = "image/png" if ext == "png" else "image/jpeg"

    # build SVG wrapper
    svg_content = f'''<svg xmlns="http://www.w3.org/2000/svg">
  <image href="data:{mime};base64,{img_base64}"
         x="0" y="0" width="100%" height="100%"/>
</svg>'''

    # write SVG file
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(svg_content)


def batch_embed_images(input_folder="images", output_folder="vectorscolor"):
    # create output folder if not exists
    os.makedirs(output_folder, exist_ok=True)

    valid_ext = (".png", ".jpg", ".jpeg")

    # loop through the images folder
    for filename in os.listdir(input_folder):
        if filename.lower().endswith(valid_ext):
            input_path = os.path.join(input_folder, filename)
            base = Path(filename).stem
            output_path = os.path.join(output_folder, base + ".svg")

            print(f"Embedding: {filename} → {base}.svg")
            image_to_svg(input_path, output_path)

    print("\n✔ All images embedded into color-SVG files in 'vectorscolor'!")


# -------------- RUN PROGRAM --------------
if __name__ == "__main__":
    batch_embed_images("images", "vectorscolor")
