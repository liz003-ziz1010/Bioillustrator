# drawing_scene.py
from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageChops
import os
from typing import Tuple, List, Union, Optional
import uuid

# ---------- Utilities ----------
def ensure_int_tuple(t):
    return tuple(int(x) for x in t)

def generate_id():
    return str(uuid.uuid4())[:8]

# ---------- Base Shape ----------
class Shape:
    def __init__(self, position=(0,0), size=(100,100), visible=True):
        self.id = generate_id()
        self.position = tuple(position)  # top-left (x,y)
        self.size = tuple(size)          # (w,h)
        self.visible = visible
        self.z = 0                       # z-order; Scene manages this
        self.parent = None               # if inside a Group

    def draw_onto(self, image: Image.Image):
        """Draw this shape onto the provided image (PIL.Image)."""
        raise NotImplementedError

    # transforms
    def scale(self, sx: float, sy: Optional[float]=None):
        if sy is None:
            sy = sx
        w, h = self.size
        self.size = (int(w * sx), int(h * sy))
        return self

    def move(self, dx: int, dy: int):
        x, y = self.position
        self.position = (x + int(dx), y + int(dy))
        return self

    def set_position(self, x:int, y:int):
        self.position = (int(x), int(y))
        return self

    def flip_horizontal(self):
        """For vector shapes this does nothing by default; subclasses override where needed."""
        raise NotImplementedError

    def flip_vertical(self):
        raise NotImplementedError

    def colorize(self, color):
        """Apply color or tint. Subclasses implement."""
        raise NotImplementedError

# ---------- Primitive Shapes ----------
class RectShape(Shape):
    def __init__(self, position=(0,0), size=(100,100), fill=(0,0,0), outline=None, outline_width=1):
        super().__init__(position, size)
        self.fill = fill
        self.outline = outline
        self.outline_width = outline_width
        self._flipped_x = False
        self._flipped_y = False

    def draw_onto(self, image):
        if not self.visible: return
        draw = ImageDraw.Draw(image)
        x,y = self.position
        w,h = self.size
        left, top, right, bottom = x, y, x + w, y + h
        draw.rectangle([left, top, right, bottom], fill=self.fill, outline=self.outline, width=self.outline_width)

    def flip_horizontal(self):
        self._flipped_x = not self._flipped_x
        return self

    def flip_vertical(self):
        self._flipped_y = not self._flipped_y
        return self

    def colorize(self, color):
        self.fill = color
        return self

class EllipseShape(Shape):
    def __init__(self, position=(0,0), size=(100,100), fill=(0,0,0), outline=None, outline_width=1):
        super().__init__(position, size)
        self.fill = fill
        self.outline = outline
        self.outline_width = outline_width
        self._flipped_x = False
        self._flipped_y = False

    def draw_onto(self, image):
        if not self.visible: return
        draw = ImageDraw.Draw(image)
        x,y = self.position
        w,h = self.size
        draw.ellipse([x, y, x + w, y + h], fill=self.fill, outline=self.outline, width=self.outline_width)

    def flip_horizontal(self):
        self._flipped_x = not self._flipped_x
        return self

    def flip_vertical(self):
        self._flipped_y = not self._flipped_y
        return self

    def colorize(self, color):
        self.fill = color
        return self

class TextShape(Shape):
    def __init__(self, text, position=(0,0), size=(200,50), font=None, fill=(0,0,0)):
        super().__init__(position, size)
        self.text = str(text)
        self.fill = fill
        # font can be a PIL ImageFont instance or None (use default)
        self.font = font
        self._flipped_x = False
        self._flipped_y = False

    def draw_onto(self, image):
        if not self.visible: return
        draw = ImageDraw.Draw(image)
        x,y = self.position
        # If font not given, use default and scale by size
        if self.font is None:
            # rough size mapping
            font_size = max(10, int(min(self.size)*0.4))
            try:
                font = ImageFont.truetype("arial.ttf", font_size)
            except Exception:
                font = ImageFont.load_default()
        else:
            font = self.font
        draw.text((x,y), self.text, font=font, fill=self.fill)

    def flip_horizontal(self):
        self._flipped_x = not self._flipped_x
        return self

    def flip_vertical(self):
        self._flipped_y = not self._flipped_y
        return self

    def colorize(self, color):
        self.fill = color
        return self

# ---------- Image (raster) Shape ----------
class ImageShape(Shape):
    def __init__(self, pil_image: Image.Image, position=(0,0), size=None):
        w,h = pil_image.size
        if size is None:
            size = (w,h)
        super().__init__(position, size)
        self.original = pil_image.copy().convert("RGBA")
        self._image = self.original.copy()
        self._flipped_x = False
        self._flipped_y = False
        self._tint = None  # (r,g,b) or None

    def _update_image_from_ops(self):
        img = self.original.copy()
        if self._flipped_x or self._flipped_y:
            flip_mode = None
            if self._flipped_x and self._flipped_y:
                img = ImageOps.mirror(ImageOps.flip(img))
            elif self._flipped_x:
                img = ImageOps.mirror(img)
            elif self._flipped_y:
                img = ImageOps.flip(img)

        if self._tint:
            # tint: blend a solid color image with the original preserving alpha
            solid = Image.new("RGBA", img.size, self._tint + (0,))
            # Convert to grayscale for better tint result or use multiply
            gray = ImageOps.grayscale(img).convert("RGBA")
            # colorize by blending gray with color
            color_img = Image.new("RGBA", img.size, self._tint + (0,))
            colorized = ImageChops.multiply(gray, color_img)
            img = Image.blend(img, colorized, alpha=0.5)

        # resize
        img = img.resize((max(1,int(self.size[0])), max(1,int(self.size[1]))), Image.LANCZOS)
        self._image = img

    def draw_onto(self, image):
        if not self.visible: return
        self._update_image_from_ops()
        x,y = int(self.position[0]), int(self.position[1])
        image.alpha_composite(self._image, dest=(x,y))

    def flip_horizontal(self):
        self._flipped_x = not self._flipped_x
        return self

    def flip_vertical(self):
        self._flipped_y = not self._flipped_y
        return self

    def colorize(self, color_tuple):
        # color_tuple e.g. (r,g,b)
        self._tint = tuple(int(c) for c in color_tuple)
        return self

    def set_image(self, pil_image:Image.Image):
        self.original = pil_image.copy().convert("RGBA")
        return self

# ---------- Group ----------
class Group(Shape):
    def __init__(self, shapes:List[Shape]=None):
        super().__init__((0,0),(0,0))
        self.shapes: List[Shape] = shapes or []
        for s in self.shapes:
            s.parent = self

    def draw_onto(self, image):
        if not self.visible: return
        for s in self.shapes:
            s.draw_onto(image)

    def add(self, shape:Shape):
        self.shapes.append(shape)
        shape.parent = self
        return self

    def remove(self, shape:Shape):
        shape.parent = None
        self.shapes.remove(shape)
        return self

    def scale(self, sx:float, sy:Optional[float]=None):
        if sy is None: sy = sx
        for s in self.shapes:
            s.scale(sx, sy)
        return self

    def move(self, dx:int, dy:int):
        for s in self.shapes:
            s.move(dx, dy)
        return self

    def flip_horizontal(self):
        for s in self.shapes:
            s.flip_horizontal()
        return self

    def flip_vertical(self):
        for s in self.shapes:
            s.flip_vertical()
        return self

    def colorize(self, color):
        for s in self.shapes:
            try:
                s.colorize(color)
            except Exception:
                pass
        return self

# ---------- Scene ----------
class Scene:
    def __init__(self, canvas_size=(800,600), background=(255,255,255,255)):
        self.canvas_size = tuple(canvas_size)
        self.background = background
        self.shapes: List[Shape] = []  # ordered list => order = z-order (0 is back)
        self._id_map = {}

    def add_shape(self, shape:Shape):
        shape.z = len(self.shapes)
        self.shapes.append(shape)
        self._id_map[shape.id] = shape
        return shape.id

    def remove_shape(self, shape_or_id:Union[Shape,str]):
        s = shape_or_id
        if isinstance(shape_or_id, str):
            s = self._id_map.get(shape_or_id)
        if s is None:
            return False
        if s in self.shapes:
            self.shapes.remove(s)
        if s.id in self._id_map:
            del self._id_map[s.id]
        return True

    def get(self, shape_id:str) -> Optional[Shape]:
        return self._id_map.get(shape_id)

    def bring_forward(self, shape_id:str, steps=1):
        s = self.get(shape_id)
        if s is None: return False
        idx = self.shapes.index(s)
        new_idx = min(len(self.shapes)-1, idx + steps)
        self.shapes.pop(idx)
        self.shapes.insert(new_idx, s)
        self._reindex_z()
        return True

    def send_backward(self, shape_id:str, steps=1):
        s = self.get(shape_id)
        if s is None: return False
        idx = self.shapes.index(s)
        new_idx = max(0, idx - steps)
        self.shapes.pop(idx)
        self.shapes.insert(new_idx, s)
        self._reindex_z()
        return True

    def _reindex_z(self):
        for i,s in enumerate(self.shapes):
            s.z = i

    def group(self, shape_ids:List[str]) -> Optional[str]:
        shapes = []
        for sid in shape_ids:
            s = self.get(sid)
            if s is None:
                continue
            shapes.append(s)
        if not shapes:
            return None
        # remove shapes from scene order and create group at first index
        indices = [self.shapes.index(s) for s in shapes]
        first_index = min(indices)
        # remove in descending order so indices remain valid
        for s in sorted(shapes, key=lambda x: self.shapes.index(x), reverse=True):
            self.shapes.remove(s)
        grp = Group(shapes)
        self.add_shape_at(grp, first_index)
        # register group and set parent relationship done in Group init
        return grp.id

    def ungroup(self, group_id:str) -> bool:
        grp = self.get(group_id)
        if not isinstance(grp, Group):
            return False
        idx = self.shapes.index(grp)
        # remove group and reinsert children at that index in the same order
        self.shapes.pop(idx)
        for i, child in enumerate(grp.shapes):
            child.parent = None
            self.shapes.insert(idx + i, child)
        # remove group from id map
        if grp.id in self._id_map:
            del self._id_map[grp.id]
        return True

    def add_shape_at(self, shape:Shape, index:int):
        # insert and reindex
        self.shapes.insert(index, shape)
        self._id_map[shape.id] = shape
        self._reindex_z()
        return shape.id

    def export(self, out_path:str, background=None, flatten_alpha=True):
        """
        Composite the scene and save to out_path.
        Supports .png and .pdf (Pillow will embed raster image in a PDF).
        """
        background = background or self.background
        canvas = Image.new("RGBA", (int(self.canvas_size[0]), int(self.canvas_size[1])), background)
        for s in self.shapes:
            s.draw_onto(canvas)

        # If flatten_alpha, composite over white background to avoid transparency in PDF
        ext = out_path.lower().split('.')[-1]
        if ext == "png":
            canvas.save(out_path, "PNG")
        elif ext == "pdf":
            # Pillow can save a single image as PDF. Flatten transparency to white for PDF.
            if flatten_alpha:
                bg = Image.new("RGB", canvas.size, (255,255,255))
                bg.paste(canvas, mask=canvas.split()[3])  # alpha channel as mask
                bg.save(out_path, "PDF", resolution=300.0)
            else:
                # Save RGBA image as PDF — some viewers may not like alpha
                canvas.save(out_path, "PDF", resolution=300.0)
        else:
            # default: save PNG
            canvas.save(out_path, "PNG")
        return out_path

    # convenience: draw to an in-memory Image and return it (PIL image)
    def render_image(self, background=None):
        background = background or self.background
        canvas = Image.new("RGBA", (int(self.canvas_size[0]), int(self.canvas_size[1])), background)
        for s in self.shapes:
            s.draw_onto(canvas)
        return canvas

    def list_shapes(self):
        return [(s.id, type(s).__name__, s.position, s.size, s.z) for s in self.shapes]

# ---------- Example usage ----------
if __name__ == "__main__":
    # Simple demo: builds a scene, manipulates shapes, groups, exports PNG and PDF
    scene = Scene(canvas_size=(800,600), background=(255,255,255,255))

    # Add rectangle
    rect = RectShape(position=(50,50), size=(300,200), fill=(200,50,50), outline=(0,0,0))
    rid = scene.add_shape(rect)

    # Add ellipse
    ell = EllipseShape(position=(250,150), size=(300,200), fill=(50,200,80), outline=(0,0,0))
    eid = scene.add_shape(ell)

    # Add text
    txt = TextShape("Hello Scene!", position=(60,60), size=(200,40), fill=(255,255,255))
    tid = scene.add_shape(txt)

    # Load image (if you have 'photo.jpg' in current dir)
    img_path = "images"
    if os.path.exists(img_path):
        pil = Image.open(img_path).convert("RGBA")
        imshape = ImageShape(pil, position=(420,50), size=(300,200))
        imid = scene.add_shape(imshape)
    else:
        print("Demo: 'photo.jpg' not found — skipping image import.")

    # Operations: scale ellipse, flip rect horizontally, colorize text
    ell.scale(0.8)
    rect.flip_horizontal()
    txt.colorize((255,255,0))

    # Layer control: bring text forward
    scene.bring_forward(tid, steps=2)

    # Group rect+text
    gid = scene.group([rid, tid])
    print("Group created:", gid)

    # Colorize entire group
    grp = scene.get(gid)
    if isinstance(grp, Group):
        grp.colorize((100, 150, 250))

    # Export final scene
    os.makedirs("exports", exist_ok=True)
    out_png = scene.export("exports/scene_output.png")
    out_pdf = scene.export("exports/scene_output.pdf")

    print("Saved:", out_png, out_pdf)
    print("Shapes in scene:", scene.list_shapes())
