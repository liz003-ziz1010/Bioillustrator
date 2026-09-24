import cv2
import numpy as np
import svgwrite
from pathlib import Path

def image_to_color_svg(image_path, svg_path, scale=1.0, blur=1):
    """
    Convert a raster image (PNG/JPG) into a colorful vector SVG.

    Parameters:
    - image_path: input raster image
    - svg_path: output SVG path
    - scale: scaling factor for SVG coordinates
    - blur: Gaussian blur to simplify edges
    """
    # Load image
    img = cv2.imread(image_path)
    if img is None:
        print(f"Failed to load {image_path}")
        return

    h, w, c = img.shape

    # Optional blur to smooth edges
    if blur > 0:
        img = cv2.GaussianBlur(img, (blur, blur), 0)

    # Convert to grayscale for contour detection
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # Threshold to binary (invert so objects are white on black)
    _, thresh = cv2.threshold(gray, 250, 255, cv2.THRESH_BINARY_INV)

    # Find contours (edges)
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    # Create SVG drawing
    dwg = svgwrite.Drawing(svg_path, size=(w*scale, h*scale))

    for cnt in contours:
        # Create mask for this contour
        mask = np.zeros_like(gray)
        cv2.drawContours(mask, [cnt], -1, 255, -1)

        # Compute mean color within contour
        mean_color = cv2.mean(img, mask=mask)  # B, G, R, alpha
        color = svgwrite.rgb(int(mean_color[2]), int(mean_color[1]), int(mean_color[0]))

        # Convert contour points to SVG path string
        path_data = "M " + " L ".join(f"{point[0][0]*scale},{point[0][1]*scale}" for point in cnt) + " Z"

        # Add path to SVG
        dwg.add(dwg.path(d=path_data, fill=color, stroke="none"))

    # Save SVG
    dwg.save()
    print(f"Saved SVG: {svg_path}")

def batch_raster_to_svg(input_folder="images", output_folder="coloredvectorsnocairo"):
    """
    Convert all PNG/JPG images in input_folder to colorful vector SVGs in output_folder
    """
    Path(output_folder).mkdir(parents=True, exist_ok=True)

    valid_ext = [".png", ".jpg", ".jpeg"]
    for f in Path(input_folder).iterdir():
        if f.suffix.lower() in valid_ext:
            out_svg = Path(output_folder)/f"{f.stem}.svg"
            image_to_color_svg(str(f), str(out_svg))

# ------------------- RUN -------------------
if __name__ == "__main__":
    batch_raster_to_svg()
