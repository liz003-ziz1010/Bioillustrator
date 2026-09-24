import cv2
import os
import numpy as np

def raster_to_svg(input_path, output_path):
    # load image
    img = cv2.imread(input_path)
    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # detect edges
    edges = cv2.Canny(gray, 100, 200)

    # find contours
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    h, w = gray.shape
    svg_header = f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}">\n'
    svg_content = ""

    for cnt in contours:
        # create a mask for this contour
        mask = np.zeros(gray.shape, dtype=np.uint8)
        cv2.drawContours(mask, [cnt], -1, 255, -1)
        # compute mean color inside contour
        mean_color = cv2.mean(img_rgb, mask=mask)[:3]  # ignore alpha
        r, g, b = map(int, mean_color)
        color_hex = f"#{r:02x}{g:02x}{b:02x}"

        # build SVG path
        svg_content += f'<path d="M '
        for point in cnt:
            x, y = point[0]
            svg_content += f"{x} {y} "
        svg_content += f'" stroke="{color_hex}" fill="none" />\n'

    svg_footer = "</svg>"

    # write SVG file
    with open(output_path, "w") as f:
        f.write(svg_header + svg_content + svg_footer)


def batch_vectorize(input_folder, output_folder):
    os.makedirs(output_folder, exist_ok=True)
    valid_ext = (".png", ".jpg", ".jpeg")

    for filename in os.listdir(input_folder):
        if filename.lower().endswith(valid_ext):
            in_path = os.path.join(input_folder, filename)
            base = os.path.splitext(filename)[0]
            out_path = os.path.join(output_folder, base + ".svg")
            print(f"Converting: {filename} → {base}.svg")
            raster_to_svg(in_path, out_path)

    print("\n✔ All images converted successfully!")


# ---------- RUN -----------  
if __name__ == "__main__":
    input_folder = "images"
    output_folder = "vectors2"
    batch_vectorize(input_folder, output_folder)
