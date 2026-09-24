"""
drawing_tool.py
Full-featured Tkinter drawing tool:
- Library panel loads SVG-wrapped images from 'vectorscolor' (data:*;base64,...)
- Drag to canvas to place images at default size
- Resize (corner handles) and rotate (rotation handle)
- Right-click context menu: bring to front / send to back
- Delete object (Delete key or Delete button)
- Export PNG / JPEG / PDF
- Zoom (Ctrl+Wheel) and Pan (middle mouse drag or Space+drag)
- Multi-select (Shift+Click), group (Ctrl+G) / ungroup (Ctrl+U)
"""

import os, io, base64, uuid, math, sys
import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk, ImageOps, ImageChops
import xml.etree.ElementTree as ET
from tkinter.colorchooser import askcolor

VECTORS_FOLDER = "svg_output"  # folder containing SVG-wrapped images for library
DEFAULT_PLACED_SIZE = (180, 180)   # default placed size in canvas pixels

def generate_id():
    return str(uuid.uuid4())[:8]

def parse_embedded_image_from_svg(svg_path):
    """Return PIL.Image (RGBA) extracted from SVG that contains an embedded data:*;base64,..."""
    with open(svg_path, "r", encoding="utf-8", errors="ignore") as f:
        data = f.read()
    idx = data.find("data:")
    if idx == -1:
        raise ValueError("No data URI in SVG")
    start = data.find("base64,", idx)
    if start == -1:
        raise ValueError("No base64 marker in SVG")
    start += len("base64,")
    end = start
    while end < len(data) and data[end] not in "\"' \n\r\t>":
        end += 1
    b64 = data[start:end]
    img_bytes = base64.b64decode(b64)
    im = Image.open(io.BytesIO(img_bytes)).convert("RGBA")
    return im

def pil_tint(image: Image.Image, tint_rgb):
    """Multiply-based tint preserving alpha"""
    if image.mode != "RGBA":
        image = image.convert("RGBA")
    solid = Image.new("RGBA", image.size, tint_rgb + (0,))
    rgb = image.convert("RGB")
    multiplied = ImageChops.multiply(rgb, solid.convert("RGB"))
    alpha = image.split()[3]
    out = Image.merge("RGBA", (*multiplied.split(), alpha))
    return out

# ---------------- SceneObject ----------------
class SceneObject:
    HANDLE_SIZE = 8
    ROT_HANDLE_OFFSET = 30  # pixels above bbox center for rotation handle

    def __init__(self, pil_image: Image.Image, x: float, y: float, default_size=DEFAULT_PLACED_SIZE):
        self.id = generate_id()
        self.original = pil_image.convert("RGBA")  # original raster from SVG wrapper
        self.x = float(x)  # top-left on canvas (world coordinates)
        self.y = float(y)
        # keep base scale such that object default size matches DEFAULT_PLACED_SIZE
        ow, oh = self.original.size
        ds_w, ds_h = default_size
        # choose scale that fits into default_size preserving aspect ratio
        sx = ds_w / ow
        sy = ds_h / oh
        self.base_scale = min(sx, sy)
        self.user_scale = 1.0   # user scaling via handles (relative to base_scale)
        self.angle = 0.0        # degrees clockwise
        self.flip_x = False
        self.flip_y = False
        self.tint = None        # (r,g,b) or None
        self.visible = True
        self.group = None
        # cache for current transform (must be recreated when any transform changes)
        self._cached = None   # PIL image after transform (including base_scale * user_scale and zoom applied externally)
        self._tk = None       # ImageTk.PhotoImage for canvas
        # when rendering, canvas will use an externally applied zoom factor: display_scale = base_scale * user_scale * zoom

    def current_scale_for_display(self, zoom):
        return self.base_scale * self.user_scale * zoom

    def compute_transformed(self, zoom):
        """Return transformed PIL image for the current object transforms and given zoom factor."""
        scale = self.current_scale_for_display(zoom)
        img = self.original.copy()
        if self.flip_x:
            img = ImageOps.mirror(img)
        if self.flip_y:
            img = ImageOps.flip(img)
        if self.tint:
            img = pil_tint(img, self.tint)
        new_w = max(1, int(img.width * scale))
        new_h = max(1, int(img.height * scale))
        img = img.resize((new_w, new_h), Image.LANCZOS)
        if self.angle != 0:
            # negative because PIL rotate is CCW for positive angle; we want clockwise
            img = img.rotate(-self.angle, expand=True, resample=Image.BICUBIC)
        self._cached = img
        return img

    def get_bbox(self, zoom):
        """Return bbox (left, top, right, bottom) in world coordinates considering zoom applied to transform (positions are in world coords)."""
        img = self._cached if self._cached is not None else self.compute_transformed(zoom)
        w, h = img.size
        left = self.x
        top = self.y
        return (left, top, left + w, top + h)

    def center(self, zoom):
        l, t, r, b = self.get_bbox(zoom)
        return ((l + r) / 2, (t + b) / 2)

# ---------------- Scene ----------------
class Scene:
    def __init__(self, width=1200, height=800, background=(255,255,255,255)):
        self.width = width
        self.height = height
        self.background = background
        self.objects = []  # z-ordered list; last is top
        self.groups = {}

    def add_object(self, obj: SceneObject):
        self.objects.append(obj)

    def remove_object(self, obj: SceneObject):
        if obj in self.objects:
            self.objects.remove(obj)
        if obj.group and obj.group in self.groups:
            grp = self.groups[obj.group]
            if obj in grp['members']:
                grp['members'].remove(obj)
            if not grp['members']:
                del self.groups[obj.group]
            obj.group = None

    def bring_to_front(self, obj: SceneObject):
        if obj in self.objects:
            self.objects.remove(obj)
            self.objects.append(obj)

    def send_to_back(self, obj: SceneObject):
        if obj in self.objects:
            self.objects.remove(obj)
            self.objects.insert(0, obj)

    def group_objects(self, objects):
        if not objects:
            return None
        gid = generate_id()
        self.groups[gid] = {'members': list(objects)}
        for o in objects:
            o.group = gid
        return gid

    def ungroup(self, gid):
        if gid not in self.groups:
            return False
        for o in self.groups[gid]['members']:
            o.group = None
        del self.groups[gid]
        return True
    def _flip_horizontal(self):
        coords = self.canvas.coords(self.selected_item)
        cx = (coords[0] + coords[2]) / 2
        self.canvas.scale(self.selected_item, cx, 0, -1, 1)  # flip horizontally

    def _flip_vertical(self):
        coords = self.canvas.coords(self.selected_item)
        cy = (coords[1] + coords[3]) / 2
        self.canvas.scale(self.selected_item, 0, cy, 1, -1)
    def _recolor(self):
        color = askcolor(title="Choose a color")[1]
        if color:
            self.canvas.itemconfig(self.selected_item, fill=color)
    def composite_to_pil(self, zoom=1.0):
        """Composite current scene to a PIL.Image (RGBA) at world coords using given zoom factor.
        Note: During export we want full resolution (zoom=1). For display we pass current zoom."""
        canvas = Image.new("RGBA", (int(self.width * zoom), int(self.height * zoom)), self.background)
        for obj in self.objects:
            if not obj.visible: continue
            img = obj.compute_transformed(zoom)
            left = int(obj.x * zoom)
            top = int(obj.y * zoom)
            canvas.alpha_composite(img, dest=(left, top))
        return canvas

# ---------------- GUI Editor ----------------
class DrawingToolApp(tk.Frame):
    def __init__(self, master):
        super().__init__(master)
        self.master = master
        self.master.title("Drawing Tool (vectorscolor)")
        self.pack(fill="both", expand=True)
        # scene
        self.scene = Scene(width=1400, height=900)
        # zoom & pan state
        self.zoom = 1.0
        self.min_zoom = 0.2
        self.max_zoom = 4.0
        self.pan_x = 0
        self.pan_y = 0
        # selection
        self.selected = []  # list of SceneObject
        self._create_context_menu()
        # dragging/resizing/rotating state
        self._dragging = False
        self._drag_start = None
        self._resize_info = None  # (obj, handle_index, start_mouse, start_bbox, start_scale)
        self._rotating = False
        self._rotate_info = None  # (obj, start_mouse, start_angle)
        # build UI
        self._build_ui()
        # load library
        self._load_library(VECTORS_FOLDER)
        # redraw initial
        self.redraw()
    def _show_context_menu(self, event):
        # get the canvas item closest to the mouse click
        self.selected_item = self.canvas.find_closest(event.x, event.y)[0]
        # show the right-click menu
        self.context_menu.tk_popup(event.x_root, event.y_root)
    def _build_ui(self):
        # top menu
        menubar = tk.Menu(self.master)
        filem = tk.Menu(menubar, tearoff=0)
        filem.add_command(label="Export PNG...", command=self.export_png)
        filem.add_command(label="Export JPEG...", command=self.export_jpeg)
        filem.add_command(label="Export PDF...", command=self.export_pdf)
        menubar.add_cascade(label="File", menu=filem)
        self.master.config(menu=menubar)

        # left library frame
        self.left_frame = tk.Frame(self, width=260, bg="#f3f3f3")
        self.left_frame.pack(side="left", fill="y")
        lbl = tk.Label(self.left_frame, text="Library", bg="#dcdcdc", font=("Arial", 12, "bold"))
        lbl.pack(fill="x")
        # library canvas with scrollbar
        self.lib_canvas = tk.Canvas(self.left_frame, bg="#f3f3f3", width=240, height=800)
        self.lib_scroll = tk.Scrollbar(self.left_frame, orient="vertical", command=self.lib_canvas.yview)
        self.lib_canvas.configure(yscrollcommand=self.lib_scroll.set)
        self.lib_scroll.pack(side="right", fill="y")
        self.lib_canvas.pack(side="left", fill="both", expand=True)
        self.lib_inner = tk.Frame(self.lib_canvas, bg="#f3f3f3")
        self.lib_canvas.create_window((0,0), window=self.lib_inner, anchor="nw")
        self.lib_inner.bind("<Configure>", lambda e: self.lib_canvas.configure(scrollregion=self.lib_canvas.bbox("all")))

        # right side toolbar
        self.right_frame = tk.Frame(self, width=200, bg="#efefef")
        self.right_frame.pack(side="right", fill="y")
        tk.Button(self.right_frame, text="Delete Selected", command=self.delete_selected).pack(padx=8, pady=6, fill="x")
        tk.Button(self.right_frame, text="Group (Ctrl+G)", command=self.group_selected).pack(padx=8, pady=6, fill="x")
        tk.Button(self.right_frame, text="Ungroup (Ctrl+U)", command=self.ungroup_selected).pack(padx=8, pady=6, fill="x")
        tk.Label(self.right_frame, text="Zoom: Ctrl+Wheel").pack(padx=8, pady=10)

        # main canvas area (with world->screen transform)
        self.canvas_frame = tk.Frame(self, bg="black")
        self.canvas_frame.pack(fill="both", expand=True, side="left")
        self.canvas = tk.Canvas(self.canvas_frame, bg="white", width=1000, height=700, highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        # bindings
        self.canvas.bind("<Button-1>", self.on_mouse_down)
        self.canvas.bind("<B1-Motion>", self.on_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_mouse_up)
        self.canvas.bind("<Button-2>", self._start_pan)  # middle-click (some systems)
        self.canvas.bind("<B2-Motion>", self._do_pan)
        self.canvas.bind("<ButtonRelease-2>", self._end_pan)
        self.canvas.bind("<MouseWheel>", self.on_mouse_wheel)  # Windows
        self.canvas.bind("<Button-4>", self.on_mouse_wheel)    # Linux scroll up
        self.canvas.bind("<Button-5>", self.on_mouse_wheel)    # Linux scroll down
        #self.canvas.bind("<Button-3>", self.on_right_click)
        self.canvas.bind("<Button-3>", self._show_context_menu)
        def _show_context_menu(self, event):
            self.selected_item = self.canvas.find_closest(event.x, event.y)[0]
            self.context_menu.tk_popup(event.x_root, event.y_root)
        self.canvas.bind("<Key>", self.on_key)
        self.canvas.focus_set()
        # support space+drag to pan
        #self.canvas.bind("<ButtonPress-1>", self._on_btn1_press, add="+")
        #self.canvas.bind("<B1-Motion>", self._on_btn1_motion, add="+")

        # context menu
        self.context_menu = tk.Menu(self, tearoff=0)
        self.context_menu.add_command(label="Bring to Front", command=self._ctx_bring_front)
        self.context_menu.add_command(label="Send to Back", command=self._ctx_send_back)

        # internal maps
        self.lib_thumbnails = []   # (path, tk_image)
        self.object_canvas_ids = {}  # maps canvas item id -> (SceneObject)
        self.screen_items = []  # items drawn (for ordering)
    def _create_context_menu(self):
        self.context_menu = tk.Menu(self._root, tearoff=0)
        self.context_menu.add_command(label="Bring to Front", command=self._bring_to_front)
        self.context_menu.add_command(label="Send to Back", command=self._send_to_back)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Flip Horizontal", command=self._flip_horizontal)
        self.context_menu.add_command(label="Flip Vertical", command=self._flip_vertical)
        self.context_menu.add_command(label="Recolor", command=self._recolor)
    # ---------------- Library ----------------
    def _load_library(self, folder):
        if not os.path.isdir(folder):
            print("Library folder not found:", folder)
            return
        files = [f for f in sorted(os.listdir(folder)) if f.lower().endswith(".svg")]
        r = 0
        for f in files:
            path = os.path.join(folder, f)
            try:
                pil = parse_embedded_image_from_svg(path)
            except Exception as e:
                print("Skipping", f, ":", e)
                continue
            # create thumbnail
            thumb = pil.copy()
            thumb.thumbnail((100, 100))
            tk_thumb = ImageTk.PhotoImage(thumb)
            # label button
            btn = tk.Label(self.lib_inner, image=tk_thumb, bg="#ffffff", bd=1, relief="solid", cursor="hand2")
            btn.image = tk_thumb
            btn.grid(row=r, column=0, padx=6, pady=6)
            # drag start binding
            btn.bind("<Button-1>", lambda ev, p=path: self._lib_start_drag(ev, p))
            btn.bind("<B1-Motion>", lambda ev, p=path: self._lib_drag_motion(ev, p))
            btn.bind("<ButtonRelease-1>", lambda ev, p=path: self._lib_drop(ev, p))
            r += 1

    # library drag state
    def _lib_start_drag(self, event, path):
        # create preview image on canvas (centered at pointer)
        try:
            pil = parse_embedded_image_from_svg(path)
        except Exception as e:
            print("Failed to read", path, e)
            return
        # create a temporary preview SceneObject-like representation
        self._lib_preview_path = path
        self._lib_preview_pil = pil
        self._lib_preview_tk = ImageTk.PhotoImage(pil.resize(DEFAULT_PLACED_SIZE, Image.LANCZOS))
        # create a canvas image for preview
        sx, sy = event.widget.winfo_pointerx() - self.canvas.winfo_rootx(), event.widget.winfo_pointery() - self.canvas.winfo_rooty()
        self._lib_preview_id = self.canvas.create_image(sx, sy, image=self._lib_preview_tk, anchor="center")
        self.canvas.lift(self._lib_preview_id)
        # mark dragging
        self._dragging_from_lib = True

    def _lib_drag_motion(self, event, path):
        if not hasattr(self, "_lib_preview_id"):
            return
        sx, sy = event.widget.winfo_pointerx() - self.canvas.winfo_rootx(), event.widget.winfo_pointery() - self.canvas.winfo_rooty()
        self.canvas.coords(self._lib_preview_id, sx, sy)

    def _lib_drop(self, event, path):
        if not hasattr(self, "_lib_preview_id"):
            return
        sx, sy = event.widget.winfo_pointerx() - self.canvas.winfo_rootx(), event.widget.winfo_pointery() - self.canvas.winfo_rooty()
        # convert canvas screen coords to world coords taking zoom/pan into account
        world_x = (sx - self.pan_x) / self.zoom
        world_y = (sy - self.pan_y) / self.zoom
        pil = parse_embedded_image_from_svg(path)
        obj = SceneObject(pil, world_x, world_y, default_size=DEFAULT_PLACED_SIZE)
        # ensure placed inside scene bounds
        obj.x = max(0, min(obj.x, self.scene.width - 1))
        obj.y = max(0, min(obj.y, self.scene.height - 1))
        self.scene.add_object(obj)
        # cleanup preview
        self.canvas.delete(self._lib_preview_id)
        delattr(self, "_lib_preview_id")
        self._dragging_from_lib = False
        self.redraw()

    # ---------------- Mouse / keyboard handlers ----------------
    def on_mouse_down(self, event):
        # select object under cursor (topmost)
        sx, sy = event.x, event.y
        # map to world coords
        wx = (sx - self.pan_x) / self.zoom
        wy = (sy - self.pan_y) / self.zoom
        clicked_obj, handle = self._hit_test_world(wx, wy)
        if clicked_obj:
            # if handle -> start resizing
            if handle is not None:
                self._start_resize(clicked_obj, handle, (sx, sy))
                return
            # if click on rotation handle
            if handle == "rotate":
                self._start_rotate(clicked_obj, (sx, sy))
                return
            # normal object click -> select and start dragging
            if (event.state & 0x0001):  # shift -> multi-select
                if clicked_obj in self.selected:
                    self.selected.remove(clicked_obj)
                else:
                    self.selected.append(clicked_obj)
            else:
                if clicked_obj not in self.selected:
                    self.selected = [clicked_obj]
            # start dragging
            self._dragging = True
            self._drag_start = (sx, sy)
            # store selected objects positions
            self._pre_drag_positions = [(o, o.x, o.y) for o in self.selected]
            self.redraw()
        else:
            # clicked empty: clear selection
            self.selected = []
            self.redraw()

    def on_mouse_drag(self, event):
        if self._resize_info:
            self._do_resize(event.x, event.y)
            return
        if self._rotating:
            self._do_rotate(event.x, event.y)
            return
        if self._dragging:
            sx, sy = event.x, event.y
            dx = (sx - self._drag_start[0]) / self.zoom
            dy = (sy - self._drag_start[1]) / self.zoom
            for o, ox, oy in self._pre_drag_positions:
                o.x = ox + dx
                o.y = oy + dy
            self.redraw()

    def on_mouse_up(self, event):
        self._dragging = False
        self._drag_start = None
        self._pre_drag_positions = None
        if self._resize_info:
            self._resize_info = None
        if self._rotating:
            self._rotating = False
            self._rotate_info = None

    def on_mouse_wheel(self, event):
        # ctrl + wheel -> zoom
        ctrl = (event.state & 0x0004) != 0
        if ctrl:
            # position of mouse in screen coords
            sx = event.x
            sy = event.y
            # world coords before zoom
            wx_before = (sx - self.pan_x) / self.zoom
            wy_before = (sy - self.pan_y) / self.zoom
            # adjust zoom
            delta = 0
            if hasattr(event, "delta"):
                delta = event.delta
            else:
                # linux
                delta = 120 if event.num == 4 else -120
            factor = 1.1 if delta > 0 else 0.9
            new_zoom = max(self.min_zoom, min(self.max_zoom, self.zoom * factor))
            # update pan so that world point under mouse remains same
            self.zoom = new_zoom
            self.pan_x = sx - wx_before * self.zoom
            self.pan_y = sy - wy_before * self.zoom
            self.redraw()
        else:
            # default: do nothing (could use wheel to scroll canvas)
            pass

    def _on_btn1_press(self, event):
        # used to detect space+drag for panning
        if event.state & 0x0001:  # shift pressed -> handled elsewhere
            return
        # if space pressed => start pan
        if event.state & 0x0008:  # Alt? Not consistent. We'll support Space via keys
            pass

    # ---------------- Pan (middle button or space+drag) ----------------
    def _start_pan(self, event):
        self._pan_start = (event.x, event.y)
        self._pan_orig = (self.pan_x, self.pan_y)

    def _do_pan(self, event):
        dx = event.x - self._pan_start[0]
        dy = event.y - self._pan_start[1]
        self.pan_x = self._pan_orig[0] + dx
        self.pan_y = self._pan_orig[1] + dy
        self.redraw()

    def _end_pan(self, event):
        self._pan_start = None
        self._pan_orig = None

    # ---------------- Right-click context ----------------
    def on_right_click(self, event):
        sx, sy = event.x, event.y
        wx = (sx - self.pan_x) / self.zoom
        wy = (sy - self.pan_y) / self.zoom
        clicked_obj, _ = self._hit_test_world(wx, wy)
        if clicked_obj:
            self._context_target = clicked_obj
            self.context_menu.post(event.x_root, event.y_root)
        else:
            self._context_target = None

    def _ctx_bring_front(self):
        if getattr(self, "_context_target", None):
            self.scene.bring_to_front(self._context_target)
            self.redraw()

    def _ctx_send_back(self):
        if getattr(self, "_context_target", None):
            self.scene.send_to_back(self._context_target)
            self.redraw()

    # ---------------- Key handling ----------------
    def on_key(self, event):
        k = event.keysym.lower()
        if k == "delete" or k == "backspace":
            self.delete_selected()
        elif k == "g" and (event.state & 0x0004):
            self.group_selected()
        elif k == "u" and (event.state & 0x0004):
            self.ungroup_selected()
        elif k == "r":
            # start rotate mode if selected single object
            if len(self.selected) == 1:
                obj = self.selected[0]
                x, y = self.canvas.winfo_pointerx() - self.canvas.winfo_rootx(), self.canvas.winfo_pointery() - self.canvas.winfo_rooty()
                self._start_rotate(obj, (x, y))

    # ---------------- Selection / hit testing ----------------
    def _hit_test_world(self, wx, wy):
        """Return (topmost_object, handle) where handle is None, 0..3 for corner, or 'rotate' for rotate handle."""
        # check in reverse z-order (topmost first)
        for obj in reversed(self.scene.objects):
            if not obj.visible:
                continue
            # ensure cache for current zoom
            obj.compute_transformed(self.zoom)
            l, t, r, b = obj.get_bbox(self.zoom)
            # check rotation handle
            cx, cy = obj.center(self.zoom)
            rot_x = cx
            rot_y = t - SceneObject.ROT_HANDLE_OFFSET
            # convert world positions to compare with point in world coords
            # wx,wy in world coords already
            # check handle boxes in world coords
            hs = SceneObject.HANDLE_SIZE / self.zoom  # adjust handle detection by zoom
            # rotation handle hit
            if abs(wx - rot_x) <= hs and abs(wy - rot_y) <= hs:
                return obj, "rotate"
            # corner handles (tl, tr, br, bl)
            corners = [(l, t), (r, t), (r, b), (l, b)]
            for i, (cx_h, cy_h) in enumerate(corners):
                if abs(wx - cx_h) <= hs and abs(wy - cy_h) <= hs:
                    return obj, i
            # body hit
            if l <= wx <= r and t <= wy <= b:
                return obj, None
        return None, None

    # ---------------- Resize / rotate helpers ----------------
    def _start_resize(self, obj, handle_index, start_mouse_screen):
        self._resize_info = (obj, handle_index, start_mouse_screen, obj.get_bbox(self.zoom), obj.user_scale)

    def _do_resize(self, mouse_x_screen, mouse_y_screen):
        if not self._resize_info:
            return
        obj, handle, (start_sx, start_sy), box, start_scale = self._resize_info
        # convert screen mouse to world
        mx = (mouse_x_screen - self.pan_x) / self.zoom
        my = (mouse_y_screen - self.pan_y) / self.zoom
        # opposite corner in world coordinates
        l, t, r, b = box
        if handle == 0:
            ox, oy = r, b
            start_dist = math.hypot((start_sx - self.pan_x)/self.zoom - ox, (start_sy - self.pan_y)/self.zoom - oy)
            cur_dist = math.hypot(mx - ox, my - oy)
        elif handle == 1:
            ox, oy = l, b
            start_dist = math.hypot((start_sx - self.pan_x)/self.zoom - ox, (start_sy - self.pan_y)/self.zoom - oy)
            cur_dist = math.hypot(mx - ox, my - oy)
        elif handle == 2:
            ox, oy = l, t
            start_dist = math.hypot((start_sx - self.pan_x)/self.zoom - ox, (start_sy - self.pan_y)/self.zoom - oy)
            cur_dist = math.hypot(mx - ox, my - oy)
        else:
            ox, oy = r, t
            start_dist = math.hypot((start_sx - self.pan_x)/self.zoom - ox, (start_sy - self.pan_y)/self.zoom - oy)
            cur_dist = math.hypot(mx - ox, my - oy)
        if start_dist == 0:
            return
        scale_factor = cur_dist / start_dist
        new_user_scale = max(0.05, start_scale * scale_factor)
        obj.user_scale = new_user_scale
        self.redraw()

    def _start_rotate(self, obj, start_mouse_screen):
        self._rotating = True
        sx, sy = start_mouse_screen
        # world pos of center
        cx, cy = obj.center(self.zoom)
        self._rotate_info = (obj, (sx, sy), obj.angle, cx, cy)

    def _do_rotate(self, mouse_x_screen, mouse_y_screen):
        if not self._rotate_info:
            return
        obj, (sx0, sy0), start_angle, cx, cy = self._rotate_info
        # convert mouse to world coords
        mx = (mouse_x_screen - self.pan_x) / self.zoom
        my = (mouse_y_screen - self.pan_y) / self.zoom
        # compute angle from center to mouse (in degrees)
        ang = math.degrees(math.atan2(my - cy, mx - cx))
        # starting angle is angle at initial mouse; we set new angle = ang
        # We used absolute angle approach for simplicity:
        obj.angle = (360 - ang) % 360  # clockwise convention used earlier (PIL rotation inverted)
        self.redraw()

    # ---------------- Group / delete ----------------
    def delete_selected(self):
        for o in list(self.selected):
            self.scene.remove_object(o)
        self.selected = []
        self.redraw()

    def group_selected(self):
        if not self.selected:
            messagebox.showinfo("Group", "No objects selected.")
            return
        gid = self.scene.group_objects(self.selected)
        messagebox.showinfo("Group", f"Group {gid} created.")
        self.redraw()

    def ungroup_selected(self):
        if not self.selected:
            messagebox.showinfo("Ungroup", "No objects selected.")
            return
        gid = self.selected[0].group
        if not gid:
            messagebox.showinfo("Ungroup", "Selected object is not in a group.")
            return
        self.scene.ungroup(gid)
        messagebox.showinfo("Ungroup", f"Group {gid} removed.")
        self.selected = []
        self.redraw()

    # ---------------- Redraw ----------------
    def redraw(self):
        self.canvas.delete("all")
        self.object_canvas_ids.clear()
        # draw background (white)
        self.canvas.create_rectangle(0, 0, self.canvas.winfo_width(), self.canvas.winfo_height(), fill="white", outline="")
        # draw objects in z-order
        for obj in self.scene.objects:
            if not obj.visible:
                continue
            # compute transformed at current zoom
            img = obj.compute_transformed(self.zoom)
            tkimg = ImageTk.PhotoImage(img)
            # keep reference to avoid GC
            obj._tk = tkimg
            screen_x = obj.x * self.zoom + self.pan_x
            screen_y = obj.y * self.zoom + self.pan_y
            cid = self.canvas.create_image(int(screen_x), int(screen_y), image=tkimg, anchor="nw")
            self.object_canvas_ids[cid] = obj
            # if selected draw bbox and handles (in screen coords)
            if obj in self.selected:
                l, t, r, b = obj.get_bbox(self.zoom)
                sl, st, sr, sb = l * self.zoom + self.pan_x, t * self.zoom + self.pan_y, r * self.zoom + self.pan_x, b * self.zoom + self.pan_y
                # rectangle
                self.canvas.create_rectangle(sl, st, sr, sb, outline="blue", width=2)
                # corner handles
                hs = SceneObject.HANDLE_SIZE
                corners = [(sl, st), (sr, st), (sr, sb), (sl, sb)]
                for (cx, cy) in corners:
                    self.canvas.create_rectangle(cx - hs, cy - hs, cx + hs, cy + hs, fill="white", outline="black")
                # rotation handle
                rot_x = (sl + sr) / 2
                rot_y = st - SceneObject.ROT_HANDLE_OFFSET
                self.canvas.create_oval(rot_x - hs, rot_y - hs, rot_x + hs, rot_y + hs, fill="yellow", outline="black")
        # update
        self.canvas.update_idletasks()

    # ---------------- Export ----------------
    def export_png(self):
        file = filedialog.asksaveasfilename(defaultextension=".png", filetypes=[("PNG","*.png")])
        if not file:
            return
        pil = self.scene.composite_to_pil(zoom=1.0)
        pil.save(file, "PNG")
        messagebox.showinfo("Export", f"Saved PNG: {file}")

    def export_jpeg(self):
        file = filedialog.asksaveasfilename(defaultextension=".jpg", filetypes=[("JPEG","*.jpg;*.jpeg")])
        if not file:
            return
        pil = self.scene.composite_to_pil(zoom=1.0)
        rgb = pil.convert("RGB")
        rgb.save(file, "JPEG", quality=95)
        messagebox.showinfo("Export", f"Saved JPEG: {file}")

    def export_pdf(self):
        file = filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=[("PDF","*.pdf")])
        if not file:
            return
        pil = self.scene.composite_to_pil(zoom=1.0)
        bg = Image.new("RGB", pil.size, (255,255,255))
        bg.paste(pil, mask=pil.split()[3])
        bg.save(file, "PDF", resolution=300.0)
        messagebox.showinfo("Export", f"Saved PDF: {file}")

# ----------------- Run -----------------
if __name__ == "__main__":
    root = tk.Tk()
    app = DrawingToolApp(root)
    root.geometry("1400x900")
    root.mainloop()
