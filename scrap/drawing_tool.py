# drawing_tool.py
"""
Tkinter OOP Drawing Tool for raster-embedded SVGs
- Place wrapped SVGs (with data:image;base64,...) in folder "vectorscolor"
- Run this script. Click to select, drag to move, resize via corner handles,
  rotate using R + drag (or Ctrl+R), flip with 'h'/'v', tint with 'c'.
- Ctrl+G group, Ctrl+U ungroup, [ send back, ] bring forward.
- Export via File menu to PNG or PDF.
Dependencies: Pillow
Install: pip install --upgrade pip && pip install Pillow
"""

import os, io, base64, uuid, math
import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk, ImageOps, ImageChops

# ---------------- Utilities ----------------
def generate_id():
    return str(uuid.uuid4())[:8]

def parse_embedded_image_from_svg(svg_path):
    """
    Parse SVG file and extract base64 data URI from <image ... href="data:...">.
    Returns PIL.Image (RGBA) or raises ValueError.
    """
    data = open(svg_path, "r", encoding="utf-8", errors="ignore").read()
    idx = data.find("data:")
    if idx == -1:
        raise ValueError("No data URI found in SVG.")
    start = data.find("base64,", idx)
    if start == -1:
        raise ValueError("No base64 marker found in SVG.")
    start += len("base64,")
    end = start
    while end < len(data) and data[end] not in "\"' \n\r\t>":
        end += 1
    b64 = data[start:end]
    img_bytes = base64.b64decode(b64)
    img = Image.open(io.BytesIO(img_bytes)).convert("RGBA")
    return img

def pil_tint(image: Image.Image, tint_rgb):
    """Apply a tint (multiply-style) to image preserving alpha."""
    if image.mode != "RGBA":
        image = image.convert("RGBA")
    # create solid image with tint color (no alpha)
    solid = Image.new("RGBA", image.size, tint_rgb + (0,))
    rgb = image.convert("RGB")
    multiplied = ImageChops.multiply(rgb, solid.convert("RGB"))
    alpha = image.split()[3]
    out = Image.merge("RGBA", (*multiplied.split(), alpha))
    return out

# ---------------- Scene Object ----------------
class SceneObject:
    HANDLE_SIZE = 8

    def __init__(self, pil_image: Image.Image, position=(0,0)):
        self.id = generate_id()
        self.original = pil_image.convert("RGBA")
        self.x, self.y = float(position[0]), float(position[1])  # top-left
        self.scale = 1.0
        self.angle = 0.0               # degrees (clockwise)
        self.flip_x = False
        self.flip_y = False
        self.tint = None               # (r,g,b) or None
        self.visible = True
        self.group = None              # group id if grouped
        # cache
        self._cached = None            # transformed PIL image
        self._tk_image = None          # ImageTk for canvas
        self.width, self.height = self.original.size

    def get_transformed(self):
        """Return transformed PIL image (RGBA) storing in cache."""
        img = self.original.copy()
        # flips
        if self.flip_x:
            img = ImageOps.mirror(img)
        if self.flip_y:
            img = ImageOps.flip(img)
        # tint
        if self.tint:
            img = pil_tint(img, self.tint)
        # scale
        new_w = max(1, int(self.width * self.scale))
        new_h = max(1, int(self.height * self.scale))
        img = img.resize((new_w, new_h), Image.LANCZOS)
        # rotate: PIL rotates counter-clockwise when angle positive, we want clockwise
        if self.angle != 0:
            img = img.rotate(-self.angle, expand=True, resample=Image.BICUBIC)
        self._cached = img
        return img

    def get_tk(self):
        img = self.get_transformed()
        self._tk_image = ImageTk.PhotoImage(img)
        return self._tk_image

    def bbox(self):
        """Return bounding box (left, top, right, bottom) based on cached image."""
        img = self._cached if self._cached is not None else self.get_transformed()
        w, h = img.size
        left = int(self.x)
        top = int(self.y)
        return (left, top, left + w, top + h)

    def center(self):
        left, top, right, bottom = self.bbox()
        return ((left + right) / 2, (top + bottom) / 2)

# ---------------- Group ----------------
class SceneGroup:
    def __init__(self, members):
        self.id = generate_id()
        self.members = list(members)
        for m in self.members:
            m.group = self.id

# ---------------- Scene ----------------
class Scene:
    def __init__(self, canvas_size=(1000,800), background=(255,255,255,255)):
        self.width, self.height = canvas_size
        self.background = background
        self.objects = []       # z-order (first is back)
        self.groups = {}        # id -> SceneGroup

    def add_object(self, obj: SceneObject):
        self.objects.append(obj)

    def remove_object(self, obj: SceneObject):
        if obj in self.objects:
            self.objects.remove(obj)
        if obj.group and obj.group in self.groups:
            grp = self.groups[obj.group]
            if obj in grp.members:
                grp.members.remove(obj)
            if not grp.members:
                del self.groups[obj.group]
            obj.group = None

    def bring_forward(self, obj, steps=1):
        if obj not in self.objects: return
        idx = self.objects.index(obj)
        new_idx = min(len(self.objects)-1, idx + steps)
        self.objects.insert(new_idx+1, self.objects.pop(idx))

    def send_backward(self, obj, steps=1):
        if obj not in self.objects: return
        idx = self.objects.index(obj)
        new_idx = max(0, idx - steps)
        self.objects.insert(new_idx, self.objects.pop(idx))

    def group_objects(self, objs):
        if not objs: return None
        members = [o for o in objs]
        grp = SceneGroup(members)
        self.groups[grp.id] = grp
        return grp.id

    def ungroup(self, grp_id):
        if grp_id not in self.groups: return False
        grp = self.groups.pop(grp_id)
        for m in grp.members:
            m.group = None
        return True

    def render_to_pil(self):
        """Composite all objects to a PIL image and return it (RGBA)."""
        canvas = Image.new("RGBA", (self.width, self.height), self.background)
        for obj in self.objects:
            if not obj.visible: continue
            img = obj.get_transformed()
            left = int(obj.x)
            top = int(obj.y)
            canvas.alpha_composite(img, dest=(left, top))
        return canvas

# ---------------- GUI Editor ----------------
class SceneEditor(tk.Frame):
    def __init__(self, master, scene: Scene, vectors_folder="vectorscolor"):
        super().__init__(master)
        self.master = master
        self.scene = scene
        self.vectors_folder = vectors_folder
        self.pack(fill="both", expand=True)
        self.selected = []     # list of SceneObject
        self.drag_start = None
        self.dragging = False
        self.rotate_mode = False
        self.resizing = False
        self.resize_info = None  # (obj, handle_index, start_mouse, start_box, start_scale)
        self.build_ui()
        self.load_vectors()
        self.redraw()

    def build_ui(self):
        # menu
        menubar = tk.Menu(self.master)
        filem = tk.Menu(menubar, tearoff=0)
        filem.add_command(label="Export PNG", command=self.export_png)
        filem.add_command(label="Export PDF", command=self.export_pdf)
        menubar.add_cascade(label="File", menu=filem)
        self.master.config(menu=menubar)

        # canvas
        self.canvas = tk.Canvas(self, width=self.scene.width, height=self.scene.height, bg="white")
        self.canvas.pack(side="left", fill="both", expand=True)
        self.canvas.bind("<Button-1>", self.on_click)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.canvas.bind("<MouseWheel>", self.on_wheel)      # Windows
        self.canvas.bind("<Button-4>", self.on_wheel)        # Linux
        self.canvas.bind("<Button-5>", self.on_wheel)        # Linux
        self.canvas.bind("<Key>", self.on_key)
        self.canvas.focus_set()

        # panel
        panel = tk.Frame(self)
        panel.pack(side="right", fill="y")
        instr = tk.Label(panel, text=(
            "Controls:\n"
            "Click: select\nShift+Click: multi-select\nDrag: move\n"
            "Drag corner: resize\nWheel: scale selected\nR + drag: rotate\n"
            "h/v: flip\nc: tint\nCtrl+G: group\nCtrl+U: ungroup\n[: back  ]: forward\nDelete: remove"
        ), justify="left")
        instr.pack(padx=6, pady=6)

        btn_frame = tk.Frame(panel)
        btn_frame.pack(pady=6)
        tk.Button(btn_frame, text="Delete", command=self.delete_selected).pack(fill="x")
        tk.Button(btn_frame, text="Bring Forward", command=lambda: self.layer_change(1)).pack(fill="x")
        tk.Button(btn_frame, text="Send Backward", command=lambda: self.layer_change(-1)).pack(fill="x")
        tk.Button(btn_frame, text="Group (Ctrl+G)", command=self.group_selected).pack(fill="x")
        tk.Button(btn_frame, text="Ungroup (Ctrl+U)", command=self.ungroup_selected).pack(fill="x")

        self._canvas_items = {}  # image id -> object

    def load_vectors(self):
        if not os.path.isdir(self.vectors_folder):
            print("Vectors folder not found:", self.vectors_folder)
            return
        x_off, y_off = 20, 20
        spacing = 20
        for filename in sorted(os.listdir(self.vectors_folder)):
            if not filename.lower().endswith(".svg"): continue
            path = os.path.join(self.vectors_folder, filename)
            try:
                pil = parse_embedded_image_from_svg(path)
                obj = SceneObject(pil, position=(x_off, y_off))
                self.scene.add_object(obj)
                x_off += int(obj.width * 0.5) + spacing
                if x_off > self.scene.width - 200:
                    x_off = 20
                    y_off += int(obj.height * 0.5) + spacing
            except Exception as e:
                print(f"Failed to load {filename}: {e}")

    def on_click(self, event):
        self.canvas.focus_set()
        x, y = event.x, event.y
        clicked_obj, handle = self._hit_test(x, y)
        if clicked_obj:
            if handle is not None:
                # start resizing
                self.resizing = True
                # store initial state
                box = clicked_obj.bbox()
                self.resize_info = (clicked_obj, handle, (x, y), box, clicked_obj.scale)
                if clicked_obj not in self.selected:
                    self.selected = [clicked_obj]
                return
            # selection logic
            if event.state & 0x0001:  # Shift
                if clicked_obj in self.selected:
                    self.selected.remove(clicked_obj)
                else:
                    self.selected.append(clicked_obj)
            else:
                if clicked_obj not in self.selected:
                    self.selected = [clicked_obj]
            # prepare for move or rotate
            self.drag_start = (x, y)
            self.dragging = True
        else:
            # click empty: clear selection
            self.selected = []
            self.drag_start = None
            self.dragging = False
        self.redraw()

    def on_drag(self, event):
        x, y = event.x, event.y
        if self.resizing and self.resize_info:
            self._perform_resize(x, y)
            self.redraw()
            return
        if not self.dragging or not self.drag_start:
            return
        dx = x - self.drag_start[0]
        dy = y - self.drag_start[1]
        if self.rotate_mode:
            for obj in self.selected:
                # angle delta proportional to horizontal mouse movement
                obj.angle = (obj.angle + dx * 0.3) % 360
            self.drag_start = (x, y)
        else:
            for obj in self.selected:
                obj.x += dx
                obj.y += dy
            self.drag_start = (x, y)
        self.redraw()

    def on_release(self, event):
        self.dragging = False
        self.drag_start = None
        if self.resizing:
            self.resizing = False
            self.resize_info = None

    def on_wheel(self, event):
        delta = 0
        if hasattr(event, 'delta'):
            delta = event.delta
        else:
            if event.num == 4: delta = 120
            else: delta = -120
        fine = (event.state & 0x0004) != 0
        factor = 1.02 if delta > 0 else 0.98
        if fine: factor = 1.01 if delta > 0 else 0.99
        for obj in self.selected:
            obj.scale *= factor
            if obj.scale < 0.05: obj.scale = 0.05
        self.redraw()

    def on_key(self, event):
        key = event.keysym.lower()
        if key == 'r':
            # enable rotate mode until key release
            self.rotate_mode = True
            self.master.bind("<KeyRelease-r>", self.on_key_release_r)
            return
        if key == 'h':
            for obj in self.selected:
                obj.flip_x = not obj.flip_x
            self.redraw()
        elif key == 'v':
            for obj in self.selected:
                obj.flip_y = not obj.flip_y
            self.redraw()
        elif key == 'c':
            import random
            for obj in self.selected:
                obj.tint = (random.randint(60,255), random.randint(60,255), random.randint(60,255))
            self.redraw()
        elif key == 'bracketleft':
            for obj in self.selected:
                self.scene.send_backward(obj)
            self.redraw()
        elif key == 'bracketright':
            for obj in self.selected:
                self.scene.bring_forward(obj)
            self.redraw()
        elif key == 'g' and (event.state & 0x0004):  # Ctrl+G
            self.group_selected()
        elif key == 'u' and (event.state & 0x0004):  # Ctrl+U
            self.ungroup_selected()
        elif key == 'delete' or key == 'backspace':
            self.delete_selected()
        elif key == 'r' and (event.state & 0x0004):
            for obj in self.selected:
                obj.angle = (obj.angle + 15) % 360
            self.redraw()

    def on_key_release_r(self, event):
        self.rotate_mode = False
        self.master.unbind("<KeyRelease-r>")

    # ---------------- Resizing helpers ----------------
    def _hit_test(self, x, y):
        """
        Return (object, handle_index)
        handle_index: 0..3 for corners (tl, tr, br, bl), or None for body click.
        """
        # check handles first (topmost objects first)
        for obj in reversed(self.scene.objects):
            if not obj.visible: continue
            obj.get_transformed()
            left, top, right, bottom = obj.bbox()
            # compute corner handle positions
            handles = [
                (left, top),      # tl
                (right, top),     # tr
                (right, bottom),  # br
                (left, bottom)    # bl
            ]
            for i, (hx, hy) in enumerate(handles):
                if (hx - SceneObject.HANDLE_SIZE <= x <= hx + SceneObject.HANDLE_SIZE and
                    hy - SceneObject.HANDLE_SIZE <= y <= hy + SceneObject.HANDLE_SIZE):
                    return obj, i
        # if no handle hit, check body hit
        for obj in reversed(self.scene.objects):
            if not obj.visible: continue
            obj.get_transformed()
            left, top, right, bottom = obj.bbox()
            if left <= x <= right and top <= y <= bottom:
                return obj, None
        return None, None

    def _perform_resize(self, mx, my):
        obj, handle, (start_x, start_y), box, start_scale = self.resize_info
        left, top, right, bottom = box
        # compute opposite corner depending on handle
        if handle == 0:  # tl
            ox, oy = right, bottom
            start_dist = math.hypot(start_x - ox, start_y - oy)
            cur_dist = math.hypot(mx - ox, my - oy)
        elif handle == 1:  # tr
            ox, oy = left, bottom
            start_dist = math.hypot(start_x - ox, start_y - oy)
            cur_dist = math.hypot(mx - ox, my - oy)
        elif handle == 2:  # br
            ox, oy = left, top
            start_dist = math.hypot(start_x - ox, start_y - oy)
            cur_dist = math.hypot(mx - ox, my - oy)
        else:  # bl
            ox, oy = right, top
            start_dist = math.hypot(start_x - ox, start_y - oy)
            cur_dist = math.hypot(mx - ox, my - oy)
        if start_dist == 0:
            return
        scale_factor = cur_dist / start_dist
        new_scale = max(0.05, start_scale * scale_factor)
        obj.scale = new_scale

    # ---------------- Selection / group / delete ----------------
    def delete_selected(self):
        for obj in list(self.selected):
            self.scene.remove_object(obj)
        self.selected = []
        self.redraw()

    def layer_change(self, direction):
        if not self.selected: return
        for obj in self.selected:
            if direction > 0:
                self.scene.bring_forward(obj)
            else:
                self.scene.send_backward(obj)
        self.redraw()

    def group_selected(self):
        if not self.selected:
            messagebox.showinfo("Group", "No objects selected.")
            return
        gid = self.scene.group_objects(self.selected)
        messagebox.showinfo("Group", f"Created group {gid}")
        self.redraw()

    def ungroup_selected(self):
        if not self.selected:
            messagebox.showinfo("Ungroup", "No objects selected.")
            return
        grp_id = self.selected[0].group
        if not grp_id:
            messagebox.showinfo("Ungroup", "Selected object not in a group.")
            return
        self.scene.ungroup(grp_id)
        messagebox.showinfo("Ungroup", f"Ungrouped {grp_id}")
        self.redraw()

    # ---------------- Rendering ----------------
    def redraw(self):
        self.canvas.delete("all")
        self._canvas_items.clear()
        for obj in self.scene.objects:
            if not obj.visible: continue
            tk_img = obj.get_tk()
            cid = self.canvas.create_image(int(obj.x), int(obj.y), anchor="nw", image=tk_img)
            self._canvas_items[cid] = obj
            if obj in self.selected:
                # draw selection rectangle (bbox) and corner handles
                left, top, right, bottom = obj.bbox()
                self.canvas.create_rectangle(left, top, right, bottom, outline="blue", width=2)
                # handles
                handles = [(left, top), (right, top), (right, bottom), (left, bottom)]
                for (hx, hy) in handles:
                    self.canvas.create_rectangle(hx-SceneObject.HANDLE_SIZE, hy-SceneObject.HANDLE_SIZE,
                                                 hx+SceneObject.HANDLE_SIZE, hy+SceneObject.HANDLE_SIZE,
                                                 fill="white", outline="black")
        self.canvas.update_idletasks()

    # ---------------- Export ----------------
    def export_png(self):
        file = filedialog.asksaveasfilename(defaultextension=".png", filetypes=[("PNG","*.png")])
        if not file: return
        pil = self.scene.render_to_pil()
        pil.save(file, "PNG")
        messagebox.showinfo("Export", f"Saved PNG: {file}")

    def export_pdf(self):
        file = filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=[("PDF","*.pdf")])
        if not file: return
        pil = self.scene.render_to_pil()
        bg = Image.new("RGB", pil.size, (255,255,255))
        bg.paste(pil, mask=pil.split()[3])
        bg.save(file, "PDF", resolution=300.0)
        messagebox.showinfo("Export", f"Saved PDF: {file}")

# ---------------- Main ----------------
if __name__ == "__main__":
    root = tk.Tk()
    root.title("Wrapped-SVG Drawing Tool (vectorscolor)")
    scene = Scene(canvas_size=(1200,900))
    editor = SceneEditor(root, scene, vectors_folder="vectorscolor")
    root.geometry("1300x940")
    root.mainloop()
