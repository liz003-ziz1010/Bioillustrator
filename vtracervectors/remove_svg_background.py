import os
import re
from bs4 import BeautifulSoup

def is_background_color(color):
    """Detect if a color is white or near-white."""
    if not color:
        return False
    color = color.lower().strip()
    return color in ["#fff", "#ffffff", "white"]


def is_rectangle_path(d, svg_w, svg_h):
    """Detect if <path d=""> describes a rectangular background."""
    if not d:
        return False

    # Normalize spacing
    d = " ".join(d.upper().split())

    # Very common rectangle patterns in SVGs
    rect_patterns = [
        r"^M0 0 H\d+ V\d+ H0 Z$",                       # M0 0 H2000 V2000 H0 Z
        r"^M0 0 L\d+ 0 L\d+ \d+ L0 \d+ Z$",             # M0 0 L2000 0 L2000 2000 L0 2000 Z
        r"^M0,0 H\d+ V\d+ H0 Z$",
    ]

    for p in rect_patterns:
        if re.match(p, d):
            return True

    # Heuristic: if bounding box covers almost all SVG
    numbers = re.findall(r"[-+]?\d*\.\d+|\d+", d)
    nums = list(map(float, numbers))

    if len(nums) >= 4:
        max_x = max(nums[0::2])
        max_y = max(nums[1::2])

        if max_x >= 0.95 * svg_w and max_y >= 0.95 * svg_h:
            return True

    return False


def remove_svg_background(input_folder, output_folder):
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    for filename in os.listdir(input_folder):
        if not filename.lower().endswith(".svg"):
            continue

        print(f"\nProcessing: {filename}")
        input_path = os.path.join(input_folder, filename)
        output_path = os.path.join(output_folder, filename)

        with open(input_path, "r", encoding="utf-8") as f:
            svg = BeautifulSoup(f.read(), "xml")

        svg_tag = svg.find("svg")
        if svg_tag is None:
            print("   ❌ Invalid SVG")
            continue

        # Read dimensions
        try:
            if svg_tag.has_attr("viewBox"):
                _, _, w, h = map(float, svg_tag["viewBox"].split())
            else:
                w = float(svg_tag.get("width", 1000))
                h = float(svg_tag.get("height", 1000))
        except:
            w, h = 1000, 1000

        removed = 0

        # 1. Remove background rectangles
        for rect in svg.find_all("rect"):
            try:
                rw = float(rect.get("width", 0))
                rh = float(rect.get("height", 0))

                if (rw * rh) >= 0.90 * (w * h):
                    rect.decompose()
                    removed += 1
                    continue

                if is_background_color(rect.get("fill", "")):
                    rect.decompose()
                    removed += 1
            except:
                continue

        # 2. Remove background paths
        for path in svg.find_all("path"):
            fill = path.get("fill", "").lower()
            d = path.get("d", "")

            if is_background_color(fill) or is_rectangle_path(d, w, h):
                path.decompose()
                removed += 1

        # 3. Remove groups containing only background
        for g in svg.find_all("g"):
            children = g.find_all(["rect", "path"])

            if len(children) == 1:
                c = children[0]
                if c.name == "rect" or c.name == "path":
                    if is_background_color(c.get("fill", "")):
                        g.decompose()
                        removed += 1

        # 4. Remove background attributes on <svg>
        for attr in ["style", "fill", "bgcolor"]:
            if svg_tag.has_attr(attr):
                if is_background_color(svg_tag[attr]):
                    del svg_tag[attr]
                    removed += 1

        if removed == 0:
            print("   ⚠ No background found — (But SVG may still not have one)")
        else:
            print(f"   ✔ Removed {removed} background elements")

        # Save output
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(str(svg))

        print(f"   ✔ Saved → {output_path}")


# ---- RUN ----
input_folder = "svg_output"
output_folder = "nobgsvg_out"
remove_svg_background(input_folder, output_folder)
