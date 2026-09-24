"""
Python Illustrator - simple SVG editor on a Tkinter canvas

Features:
- Load basic SVGs (rect, circle, ellipse, line, polyline, polygon, simple path with M/L/Z)
- Draw objects on the canvas as native Tk items
- Select / Move
- Resize using corner handles
- Flip horizontal / vertical
- Recolor fill and stroke
- Copy / Paste
- Undo / Redo (scene snapshots)
- Export back to SVG

Dependencies:
- Standard library: tkinter, xml.etree.ElementTree, copy
- Optional: Pillow (PIL) for image support, cairosvg for rasterizing arbitrary SVGs

Run: python python_illustrator.py

Notes:
- This is a compact, pragmatic implementation focused on common operations. It intentionally supports a subset of the SVG spec suited for simple vector files and hand-drawn shapes.
"""

import tkinter as tk
from tkinter import filedialog, colorchooser, simpledialog, messagebox
import xml.etree.ElementTree as ET
import copy
import math
import sys

try:
    from PIL import Image, ImageTk
    PIL_AVAILABLE = True
except Exception:
    PIL_AVAILABLE = False

try:
    import cairosvg
    CAIROSVG_AVAILABLE = True
except Exception:
    CAIROSVG_AVAILABLE = False

# ---------------------- Model classes ----------------------
class SVGObject:
    """Model for a simple drawable SVG object."""
    def __init__(self, kind, attrs):
        self.kind = kind  # 'rect', 'circle', 'ellipse', 'line', 'polyline', 'polygon', 'path', 'image'
        self.attrs = dict(attrs)  # attributes like x,y,width,height, points, d, fill, stroke, stroke-width
        self.canvas_id = None

    def get_bbox(self):
        k = self.kind
        a = self.attrs
        if k == 'rect':
            x = float(a.get('x', 0)); y = float(a.get('y', 0))
            w = float(a.get('width', 0)); h = float(a.get('height', 0))
            return (x, y, x + w, y + h)
        if k == 'circle':
            cx = float(a.get('cx', 0)); cy = float(a.get('cy', 0)); r = float(a.get('r', 0))
            return (cx - r, cy - r, cx + r, cy + r)
        if k == 'ellipse':
            cx = float(a.get('cx', 0)); cy = float(a.get('cy', 0))
            rx = float(a.get('rx', 0)); ry = float(a.get('ry', 0))
            return (cx - rx, cy - ry, cx + rx, cy + ry)
        if k == 'line':
            x1 = float(a.get('x1', 0)); y1 = float(a.get('y1', 0))
            x2 = float(a.get('x2', 0)); y2 = float(a.get('y2', 0))
            return (min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2))
        if k in ('polyline','polygon'):
            pts = parse_points(a.get('points',''))
            xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
            if not xs: return (0,0,0,0)
            return (min(xs), min(ys), max(xs), max(ys))
        if k == 'path':
            pts = path_to_points(a.get('d',''))
            if not pts: return (0,0,0,0)
            xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
            return (min(xs), min(ys), max(xs), max(ys))
        if k == 'image':
            x = float(a.get('x',0)); y = float(a.get('y',0))
            w = float(a.get('width', a.get('w', 0))); h = float(a.get('height', a.get('h', 0)))
            return (x,y,x+w,y+h)
        return (0,0,0,0)

    def translate(self, dx, dy):
        a = self.attrs
        if self.kind == 'rect':
            a['x'] = str(float(a.get('x',0)) + dx)
            a['y'] = str(float(a.get('y',0)) + dy)
        elif self.kind == 'circle':
            a['cx'] = str(float(a.get('cx',0)) + dx)
            a['cy'] = str(float(a.get('cy',0)) + dy)
        elif self.kind == 'ellipse':
            a['cx'] = str(float(a.get('cx',0)) + dx)
            a['cy'] = str(float(a.get('cy',0)) + dy)
        elif self.kind == 'line':
            a['x1'] = str(float(a.get('x1',0)) + dx)
            a['y1'] = str(float(a.get('y1',0)) + dy)
            a['x2'] = str(float(a.get('x2',0)) + dx)
            a['y2'] = str(float(a.get('y2',0)) + dy)
        elif self.kind in ('polyline','polygon'):
            pts = parse_points(a.get('points',''))
            pts = [(x+dx, y+dy) for (x,y) in pts]
            a['points'] = points_to_string(pts)
        elif self.kind == 'path':
            pts = path_to_points(a.get('d',''))
            pts = [(x+dx, y+dy) for (x,y) in pts]
            a['d'] = points_to_path(pts)
        elif self.kind == 'image':
            a['x'] = str(float(a.get('x',0)) + dx)
            a['y'] = str(float(a.get('y',0)) + dy)

    def scale_about(self, cx, cy, sx, sy):
        a = self.attrs
        if self.kind == 'rect':
            x = float(a.get('x',0)); y = float(a.get('y',0)); w = float(a.get('width',0)); h = float(a.get('height',0))
            nx = cx + (x - cx) * sx; ny = cy + (y - cy) * sy; nw = w * sx; nh = h * sy
            a['x'] = str(nx); a['y'] = str(ny); a['width'] = str(abs(nw)); a['height'] = str(abs(nh))
        elif self.kind == 'circle':
            cx0 = float(a.get('cx',0)); cy0 = float(a.get('cy',0)); r = float(a.get('r',0))
            nx = cx + (cx0 - cx) * sx; ny = cy + (cy0 - cy) * sy; nr = r * max(abs(sx), abs(sy))
            a['cx'] = str(nx); a['cy'] = str(ny); a['r'] = str(abs(nr))
        elif self.kind == 'ellipse':
            cx0 = float(a.get('cx',0)); cy0 = float(a.get('cy',0)); rx = float(a.get('rx',0)); ry = float(a.get('ry',0))
            nx = cx + (cx0 - cx) * sx; ny = cy + (cy0 - cy) * sy; nrx = rx * abs(sx); nry = ry * abs(sy)
            a['cx'] = str(nx); a['cy'] = str(ny); a['rx'] = str(abs(nrx)); a['ry'] = str(abs(nry))
        elif self.kind == 'line':
            x1 = float(a.get('x1',0)); y1 = float(a.get('y1',0)); x2 = float(a.get('x2',0)); y2 = float(a.get('y2',0))
            nx1 = cx + (x1 - cx) * sx; ny1 = cy + (y1 - cy) * sy; nx2 = cx + (x2 - cx) * sx; ny2 = cy + (y2 - cy) * sy
            a['x1']=str(nx1); a['y1']=str(ny1); a['x2']=str(nx2); a['y2']=str(ny2)
        elif self.kind in ('polyline','polygon'):
            pts = parse_points(a.get('points',''))
            pts = [(cx + (x - cx) * sx, cy + (y - cy) * sy) for (x,y) in pts]
            a['points'] = points_to_string(pts)
        elif self.kind == 'path':
            pts = path_to_points(a.get('d',''))
            pts = [(cx + (x - cx) * sx, cy + (y - cy) * sy) for (x,y) in pts]
            a['d'] = points_to_path(pts)
        elif self.kind == 'image':
            x = float(a.get('x',0)); y = float(a.get('y',0)); w = float(a.get('width',0)); h = float(a.get('height',0))
            nx = cx + (x - cx) * sx; ny = cy + (y - cy) * sy; nw = w * sx; nh = h * sy
            a['x']=str(nx); a['y']=str(ny); a['width']=str(abs(nw)); a['height']=str(abs(nh))

    def flip_about(self, cx, cy, flip_x=False, flip_y=False):
        sx = -1 if flip_x else 1
        sy = -1 if flip_y else 1
        self.scale_about(cx, cy, sx, sy)

    def set_fill(self, fill):
        if fill is None:
            self.attrs.pop('fill', None)
        else:
            self.attrs['fill'] = fill

    def set_stroke(self, stroke):
        if stroke is None:
            self.attrs.pop('stroke', None)
        else:
            self.attrs['stroke'] = stroke

# ---------------------- Utility functions ----------------------

def parse_points(s):
    if not s: return []
    parts = s.replace(',', ' ').split()
    nums = [float(p) for p in parts]
    return [(nums[i], nums[i+1]) for i in range(0, len(nums), 2)]

def points_to_string(pts):
    return ' '.join(f"{x:g},{y:g}" for (x,y) in pts)

# very simple path -> points converter: supports M and L and Z and space/comma separators
def path_to_points(d):
    if not d: return []
    tokens = []
    cur = ''
    for ch in d:
        if ch.isalpha():
            if cur.strip(): tokens.append(cur.strip())
            tokens.append(ch)
            cur = ''
        else:
            cur += ch
    if cur.strip(): tokens.append(cur.strip())
    pts = []
    i = 0
    cx = cy = 0
    while i < len(tokens):
        t = tokens[i]
        if t.upper() == 'M':
            i += 1
            coords = [float(x) for x in tokens[i].replace(',', ' ').split()]
            cx, cy = coords[0], coords[1]
            pts.append((cx, cy))
            rem = coords[2:]
            j = 0
            while j < len(rem):
                cx, cy = rem[j], rem[j+1]
                pts.append((cx, cy))
                j += 2
            i += 1
        elif t.upper() == 'L':
            i += 1
            coords = [float(x) for x in tokens[i].replace(',', ' ').split()]
            j=0
            while j < len(coords):
                cx, cy = coords[j], coords[j+1]
                pts.append((cx, cy))
                j += 2
            i += 1
        elif t.upper() == 'Z':
            i += 1
        else:
            # fallback: try to parse as numbers (implicit L)
            try:
                coords = [float(x) for x in t.replace(',', ' ').split()]
                j=0
                while j < len(coords):
                    cx, cy = coords[j], coords[j+1]
                    pts.append((cx, cy))
                    j += 2
            except Exception:
                pass
            i += 1
    return pts

def points_to_path(pts):
    if not pts: return ''
    s = f"M {pts[0][0]:g},{pts[0][1]:g} "
    for x,y in pts[1:]:
        s += f"L {x:g},{y:g} "
    s += 'Z'
    return s

# ---------------------- Canvas View / Controller ----------------------
class IllustratorApp:
    HANDLE_SIZE = 6

    def __init__(self, root):
        self.root = root
        root.title('Python Illustrator - simple SVG editor')
        self.canvas = tk.Canvas(root, width=1000, height=700, bg='white')
        self.canvas.pack(fill='both', expand=True)

        # Model
        self.objects = []  # list of SVGObject
        self.selected = []
        self.clipboard = []

        # Undo/redo stacks (store deep copies of objects list)
        self.undo_stack = []
        self.redo_stack = []

        # Interaction state
        self.dragging = False
        self.drag_start = (0,0)
        self.last_mouse = (0,0)
        self.current_handle = None

        # images cache for PIL images used as canvas images
        self._image_cache = {}

        self._build_ui()
        self._bind_events()

    def _build_ui(self):
        frm = tk.Frame(self.root)
        frm.pack(fill='x', side='top')
        btn_load = tk.Button(frm, text='Load SVG', command=self.load_svg)
        btn_save = tk.Button(frm, text='Save SVG', command=self.save_svg)
        btn_flip_h = tk.Button(frm, text='Flip H', command=lambda: self.flip_selection(True, False))
        btn_flip_v = tk.Button(frm, text='Flip V', command=lambda: self.flip_selection(False, True))
        btn_undo = tk.Button(frm, text='Undo', command=self.undo)
        btn_redo = tk.Button(frm, text='Redo', command=self.redo)
        btn_copy = tk.Button(frm, text='Copy', command=self.copy)
        btn_paste = tk.Button(frm, text='Paste', command=self.paste)
        btn_recolor_fill = tk.Button(frm, text='Fill Color', command=self.recolor_fill)
        btn_recolor_stroke = tk.Button(frm, text='Stroke Color', command=self.recolor_stroke)
        for w in (btn_load, btn_save, btn_flip_h, btn_flip_v, btn_undo, btn_redo, btn_copy, btn_paste, btn_recolor_fill, btn_recolor_stroke):
            w.pack(side='left', padx=2, pady=4)

    def _bind_events(self):
        c = self.canvas
        c.bind('<Button-1>', self.on_click)
        c.bind('<B1-Motion>', self.on_drag)
        c.bind('<ButtonRelease-1>', self.on_release)
        c.bind('<Double-Button-1>', self.on_double_click)
        self.root.bind_all('<Control-z>', lambda e: self.undo())
        self.root.bind_all('<Control-y>', lambda e: self.redo())
        self.root.bind_all('<Control-c>', lambda e: self.copy())
        self.root.bind_all('<Control-v>', lambda e: self.paste())
        self.root.bind_all('<Delete>', lambda e: self.delete_selection())

    # ---------------- Scene management ----------------
    def push_undo(self):
        self.undo_stack.append(copy.deepcopy(self.objects))
        if len(self.undo_stack) > 50:
            self.undo_stack.pop(0)
        self.redo_stack.clear()

    def undo(self):
        if not self.undo_stack: return
        self.redo_stack.append(copy.deepcopy(self.objects))
        self.objects = self.undo_stack.pop()
        self.selected = []
        self.redraw()

    def redo(self):
        if not self.redo_stack: return
        self.undo_stack.append(copy.deepcopy(self.objects))
        self.objects = self.redo_stack.pop()
        self.selected = []
        self.redraw()

    def redraw(self):
        self.canvas.delete('all')
        self._image_cache.clear()
        for obj in self.objects:
            self._draw_obj(obj)
        self._draw_selection()

    # ---------------- Drawing objects ----------------
    def _draw_obj(self, obj: SVGObject):
        a = obj.attrs
        k = obj.kind
        fill = a.get('fill', '')
        stroke = a.get('stroke', '')
        sw = float(a.get('stroke-width', a.get('stroke_width', 1))) if a.get('stroke-width', a.get('stroke_width')) else 1
        if k == 'rect':
            x = float(a.get('x',0)); y = float(a.get('y',0)); w = float(a.get('width',0)); h = float(a.get('height',0))
            obj.canvas_id = self.canvas.create_rectangle(x, y, x+w, y+h, fill=fill if fill!='none' else '', outline=stroke if stroke!='none' else '', width=sw)
        elif k == 'circle':
            cx = float(a.get('cx',0)); cy = float(a.get('cy',0)); r = float(a.get('r',0))
            obj.canvas_id = self.canvas.create_oval(cx-r, cy-r, cx+r, cy+r, fill=fill if fill!='none' else '', outline=stroke if stroke!='none' else '', width=sw)
        elif k == 'ellipse':
            cx = float(a.get('cx',0)); cy = float(a.get('cy',0)); rx = float(a.get('rx',0)); ry = float(a.get('ry',0))
            obj.canvas_id = self.canvas.create_oval(cx-rx, cy-ry, cx+rx, cy+ry, fill=fill if fill!='none' else '', outline=stroke if stroke!='none' else '', width=sw)
        elif k == 'line':
            x1 = float(a.get('x1',0)); y1 = float(a.get('y1',0)); x2 = float(a.get('x2',0)); y2 = float(a.get('y2',0))
            obj.canvas_id = self.canvas.create_line(x1, y1, x2, y2, fill=stroke if stroke!='none' else '', width=sw)
        elif k in ('polyline','polygon'):
            pts = parse_points(a.get('points',''))
            flat = [coord for p in pts for coord in p]
            if k == 'polyline':
                obj.canvas_id = self.canvas.create_line(*flat, fill=stroke if stroke!='none' else '', width=sw)
            else:
                obj.canvas_id = self.canvas.create_polygon(*flat, fill=fill if fill!='none' else '', outline=stroke if stroke!='none' else '', width=sw)
        elif k == 'path':
            pts = path_to_points(a.get('d',''))
            if pts:
                flat = [coord for p in pts for coord in p]
                obj.canvas_id = self.canvas.create_line(*flat, fill=stroke if stroke!='none' else '', width=sw, smooth=False)
        elif k == 'image':
            href = a.get('href', a.get('{http://www.w3.org/1999/xlink}href'))
            x = float(a.get('x',0)); y = float(a.get('y',0)); w = float(a.get('width',0)); h = float(a.get('height',0))
            if href and (PIL_AVAILABLE or CAIROSVG_AVAILABLE):
                try:
                    if href.lower().endswith('.svg') and CAIROSVG_AVAILABLE:
                        # rasterize to PNG bytes
                        png_bytes = cairosvg.svg2png(url=href)
                        from io import BytesIO
                        im = Image.open(BytesIO(png_bytes))
                        im = im.resize((int(w), int(h)), Image.LANCZOS)
                        tkim = ImageTk.PhotoImage(im)
                        obj.canvas_id = self.canvas.create_image(x, y, anchor='nw', image=tkim)
                        self._image_cache[obj.canvas_id] = tkim
                    else:
                        im = Image.open(href)
                        im = im.resize((int(w), int(h)), Image.LANCZOS)
                        tkim = ImageTk.PhotoImage(im)
                        obj.canvas_id = self.canvas.create_image(x, y, anchor='nw', image=tkim)
                        self._image_cache[obj.canvas_id] = tkim
                except Exception:
                    obj.canvas_id = self.canvas.create_rectangle(x,y,x+w,y+h, outline='red')
            else:
                # fallback: box placeholder
                obj.canvas_id = self.canvas.create_rectangle(x,y,x+w,y+h, outline=stroke if stroke!='none' else 'black')
        else:
            # unknown shape -> placeholder box
            x1,y1,x2,y2 = obj.get_bbox()
            obj.canvas_id = self.canvas.create_rectangle(x1,y1,x2,y2, outline='black')

    # ---------------- Selection UI ----------------
    def _draw_selection(self):
        for obj in self.objects:
            if obj in self.selected:
                x1,y1,x2,y2 = obj.get_bbox()
                self.canvas.create_rectangle(x1,y1,x2,y2, dash=(3,3), tags='selbox')
                # draw handles on bbox corners
                for hx,hy in ((x1,y1),(x2,y1),(x2,y2),(x1,y2)):
                    self.canvas.create_rectangle(hx-self.HANDLE_SIZE, hy-self.HANDLE_SIZE, hx+self.HANDLE_SIZE, hy+self.HANDLE_SIZE, fill='white', outline='black', tags='handle')

    def find_object_at(self, x, y):
        # find topmost object whose bbox contains x,y
        for obj in reversed(self.objects):
            x1,y1,x2,y2 = obj.get_bbox()
            if x1 <= x <= x2 and y1 <= y <= y2:
                return obj
        return None

    # ---------------- Event handlers ----------------
    def on_click(self, event):
        x,y = event.x, event.y
        self.drag_start = (x,y)
        self.last_mouse = (x,y)
        # check handle
        handle = self._hit_handle(x,y)
        if handle:
            self.current_handle = handle
            self.dragging = True
            return
        obj = self.find_object_at(x,y)
        if obj is None:
            # click empty area clears selection
            self.selected = []
            self.redraw()
            return
        if obj not in self.selected:
            self.selected = [obj]
            self.redraw()
        self.dragging = True

    def on_drag(self, event):
        if not self.dragging: return
        x,y = event.x, event.y
        dx = x - self.last_mouse[0]; dy = y - self.last_mouse[1]
        if self.current_handle:
            # resizing selection about opposite corner
            self._resize_selection(self.current_handle, x, y)
        else:
            for obj in self.selected:
                obj.translate(dx, dy)
            self.redraw()
        self.last_mouse = (x,y)

    def on_release(self, event):
        if self.dragging:
            self.push_undo()
        self.dragging = False
        self.current_handle = None

    def on_double_click(self, event):
        x,y = event.x, event.y
        obj = self.find_object_at(x,y)
        if obj:
            # edit fill color quickly
            c = colorchooser.askcolor(title='Choose fill color')
            if c and c[1]:
                obj.set_fill(c[1])
                self.push_undo(); self.redraw()

    def delete_selection(self):
        if not self.selected: return
        self.push_undo()
        for obj in self.selected:
            if obj in self.objects: self.objects.remove(obj)
        self.selected = []
        self.redraw()

    # ---------------- Handles / resizing ----------------
    def _hit_handle(self, x, y):
        # return (obj, corner_index) if a handle was clicked
        for obj in self.selected:
            x1,y1,x2,y2 = obj.get_bbox()
            corners = ((x1,y1),(x2,y1),(x2,y2),(x1,y2))
            for i,(hx,hy) in enumerate(corners):
                if hx - self.HANDLE_SIZE <= x <= hx + self.HANDLE_SIZE and hy - self.HANDLE_SIZE <= y <= hy + self.HANDLE_SIZE:
                    return (obj,i)
        return None

    def _resize_selection(self, handle, x, y):
        obj, idx = handle
        # determine opposite corner
        x1,y1,x2,y2 = obj.get_bbox()
        corners = [(x1,y1),(x2,y1),(x2,y2),(x1,y2)]
        ox,oy = corners[(idx+2)%4]
        # compute scale factors about opposite corner
        if ox == x: sx = 1
        else: sx = (x - ox) / (corners[idx][0] - ox) if corners[idx][0] != ox else 1
        if oy == y: sy = 1
        else: sy = (y - oy) / (corners[idx][1] - oy) if corners[idx][1] != oy else 1
        if sx == 0: sx = 1e-6
        if sy == 0: sy = 1e-6
        obj.scale_about(ox, oy, sx, sy)
        self.redraw()

    # ---------------- Clipboard ----------------
    def copy(self):
        if not self.selected: return
        self.clipboard = copy.deepcopy(self.selected)
        messagebox.showinfo('Copy', f'Copied {len(self.clipboard)} object(s) to internal clipboard')

    def paste(self):
        if not self.clipboard: return
        self.push_undo()
        pasted = copy.deepcopy(self.clipboard)
        # offset pasted a bit
        for obj in pasted:
            obj.translate(10, 10)
            self.objects.append(obj)
        self.selected = pasted
        self.redraw()

    # ---------------- Flip / Recolor ----------------
    def flip_selection(self, flip_x, flip_y):
        if not self.selected: return
        self.push_undo()
        # compute overall bbox
        bboxes = [o.get_bbox() for o in self.selected]
        x1 = min(b[0] for b in bboxes); y1 = min(b[1] for b in bboxes)
        x2 = max(b[2] for b in bboxes); y2 = max(b[3] for b in bboxes)
        cx = (x1 + x2) / 2; cy = (y1 + y2) / 2
        for o in self.selected:
            o.flip_about(cx, cy, flip_x, flip_y)
        self.redraw()

    def recolor_fill(self):
        if not self.selected: return
        c = colorchooser.askcolor(title='Choose fill color')
        if c and c[1]:
            self.push_undo()
            for o in self.selected: o.set_fill(c[1])
            self.redraw()

    def recolor_stroke(self):
        if not self.selected: return
        c = colorchooser.askcolor(title='Choose stroke color')
        if c and c[1]:
            self.push_undo()
            for o in self.selected: o.set_stroke(c[1])
            self.redraw()

    # ---------------- SVG I/O ----------------
    def load_svg(self):
        path = filedialog.askopenfilename(filetypes=[('SVG files','*.svg'), ('All files','*.*')])
        if not path: return
        try:
            tree = ET.parse(path)
            root = tree.getroot()
            ns = {'svg': 'http://www.w3.org/2000/svg'}
            self.push_undo()
            self.objects.clear()
            for child in root:
                tag = child.tag
                if '}' in tag: tag = tag.split('}',1)[1]
                attrs = {k.split('}')[ -1 ]: v for k,v in child.attrib.items()}
                if tag in ('rect','circle','ellipse','line','polyline','polygon','path','image'):
                    so = SVGObject(tag, attrs)
                    self.objects.append(so)
            self.selected = []
            self.redraw()
            messagebox.showinfo('Load SVG', 'Loaded SVG (limited parser: supports rect, circle, ellipse, line, polyline, polygon, path, image).')
        except Exception as e:
            messagebox.showerror('Error', f'Failed to load SVG: {e}')

    def save_svg(self):
        path = filedialog.asksaveasfilename(defaultextension='.svg', filetypes=[('SVG files','*.svg')])
        if not path: return
        svg = ET.Element('svg', xmlns='http://www.w3.org/2000/svg')
        for o in self.objects:
            elem = ET.SubElement(svg, o.kind)
            for k,v in o.attrs.items():
                # xml friendly attribute names
                elem.set(k, str(v))
        tree = ET.ElementTree(svg)
        try:
            tree.write(path)
            messagebox.showinfo('Save SVG', 'Saved successfully')
        except Exception as e:
            messagebox.showerror('Error', f'Failed to save: {e}')

# ---------------------- Run ----------------------
if __name__ == '__main__':
    root = tk.Tk()
    app = IllustratorApp(root)
    root.mainloop()

# --- SVG Library Panel Integration ---
# Enhancements: scrollable library, search/filter, thumbnail caching,
# automatic scaling, bounding box preview on drop, context menu.

    def build_library_panel(self):
        self.library_frame = tk.Frame(self.root, width=220, bg="#f0f0f0")
        self.library_frame.pack(side=tk.RIGHT, fill=tk.Y)

        tk.Label(self.library_frame, text="SVG Library", bg="#f0f0f0", font=("Arial", 12, "bold")).pack(pady=5)

        # search bar
        self.lib_search_var = tk.StringVar()
        search_entry = tk.Entry(self.library_frame, textvariable=self.lib_search_var)
        search_entry.pack(fill=tk.X, padx=5)
        search_entry.bind("<KeyRelease>", lambda e: self.filter_library())

        # load button
        tk.Button(self.library_frame, text="Load Folder", command=self.load_svg_library).pack(pady=5)

        # scrollable canvas
        self.lib_outer = tk.Frame(self.library_frame)
        self.lib_outer.pack(fill=tk.BOTH, expand=True)

        self.lib_scroll = tk.Canvas(self.lib_outer, bg="#ffffff")
        self.lib_scroll.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar = tk.Scrollbar(self.lib_outer, orient="vertical", command=self.lib_scroll.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.lib_scroll.configure(yscrollcommand=scrollbar.set)

        self.lib_inner = tk.Frame(self.lib_scroll, bg="#ffffff")
        self.lib_scroll.create_window((0,0), window=self.lib_inner, anchor="nw")
        self.lib_inner.bind("<Configure>", lambda e: self.lib_scroll.configure(scrollregion=self.lib_scroll.bbox("all")))

        # context menu
        self.lib_menu = tk.Menu(self.root, tearoff=0)
        self.lib_menu.add_command(label="Reload", command=self.reload_library_item)
        self.lib_menu.add_command(label="Remove from List", command=self.remove_library_item)

        self.library_items = []
        self.thumbnail_cache = {}

    def load_svg_library(self):
        folder = filedialog.askdirectory()
        if not folder:
            return
        self.library_folder = Path(folder)
        self.refresh_library_display()

    def refresh_library_display(self):
        for widget in self.lib_inner.winfo_children():
            widget.destroy()
        self.library_items.clear()

        svg_files = list(self.library_folder.glob("*.svg"))
        for path in svg_files:
            name = path.name.lower()
            if self.lib_search_var.get().lower() not in name:
                continue

            if path not in self.thumbnail_cache:
                try:
                    self.thumbnail_cache[path] = tksvg.SvgImage(file=str(path), scale=0.15)
                except:
                    continue

            img = self.thumbnail_cache[path]
            lbl = tk.Label(self.lib_inner, image=img, bg="#ffffff")
            lbl.pack(anchor="nw", pady=5)
            lbl.bind("<ButtonPress-1>", lambda e, p=path: self.start_drag_from_library(e, p))
            lbl.bind("<Button-3>", lambda e, p=path: self.show_library_menu(e, p))
            self.library_items.append((lbl, path))

    def filter_library(self):
        if hasattr(self, "library_folder"):
            self.refresh_library_display()

    def start_drag_from_library(self, event, path):
        self.dragged_svg_path = path
        self.drag_preview = tksvg.SvgImage(file=str(path), scale=0.15)
        self.drag_icon = self.canvas.create_image(0, 0, image=self.drag_preview)
        self.canvas.bind("<Motion>", self.drag_motion)
        self.canvas.bind("<ButtonRelease-1>", self.drop_from_library)

    def drag_motion(self, event):
        self.canvas.coords(self.drag_icon, self.canvas.canvasx(event.x), self.canvas.canvasy(event.y))

    def drop_from_library(self, event):
        x = self.canvas.canvasx(event.x)
        y = self.canvas.canvasy(event.y)

        self.insert_svg_on_canvas(self.dragged_svg_path, x, y, auto_scale=True)

        self.canvas.delete(self.drag_icon)
        del self.dragged_svg_path
        del self.drag_preview
        self.canvas.unbind("<Motion>")
        self.canvas.unbind("<ButtonRelease-1>")

    def show_library_menu(self, event, path):
        self.lib_menu_path = path
        self.lib_menu.post(event.x_root, event.y_root)

    def reload_library_item(self):
        if self.lib_menu_path in self.thumbnail_cache:
            del self.thumbnail_cache[self.lib_menu_path]
        self.refresh_library_display()

    def remove_library_item(self):
        if self.lib_menu_path.exists():
            # only removes from list, not filesystem
            self.thumbnail_cache.pop(self.lib_menu_path, None)
        self.refresh_library_display()

    def insert_svg_on_canvas(self, svg_path, x, y, auto_scale=False):
        # extended auto-scaling and bounding
        try:
            img = tksvg.SvgImage(file=str(svg_path))
            scale = 1.0
            if auto_scale and max(img.width(), img.height()) > 300:
                scale = 300 / max(img.width(), img.height())
                img = tksvg.SvgImage(file=str(svg_path), scale=scale)

            cid = self.canvas.create_image(x, y, image=img)
            self.objects[cid] = {"type":"svg", "path":svg_path, "scale":scale, "image":img}
            self.undo_stack.append(("add", cid))
        except Exception as e:
            print("SVG insert failed", e)
# Functions to load SVG files from a folder, display them as draggable items,
# and allow dropping them onto the main canvas.

    def load_svg_library(self):
        folder = filedialog.askdirectory()
        if not folder:
            return
        self.library_items.clear()
        self.lib_list.delete("all")

        folder_path = Path(folder)
        svg_files = list(folder_path.glob("*.svg"))

        y = 10
        for svg_file in svg_files:
            try:
                thumbnail = tksvg.SvgImage(file=str(svg_file), scale=0.2)
                item_id = self.lib_list.create_image(10, y, anchor="nw", image=thumbnail)
                self.library_items.append((item_id, svg_file, thumbnail))
                y += thumbnail.height() + 10
            except Exception as e:
                print("Failed to load", svg_file, e)

    def start_drag_from_library(self, event):
        self.dragged_item = self.lib_list.find_closest(event.x, event.y)[0]
        for item, path, img in self.library_items:
            if item == self.dragged_item:
                self.dragged_svg_path = path
                break

    def drag_from_library(self, event):
        if not hasattr(self, "dragged_item"):
            return
        self.lib_list.coords(self.dragged_item, event.x, event.y)

    def drop_from_library(self, event):
        if not hasattr(self, "dragged_svg_path"):
            return
        try:
            # Drop SVG onto main canvas
            x = self.canvas.winfo_rootx()
            y = self.canvas.winfo_rooty()
            cx = self.canvas.canvasx(event.x_root - x)
            cy = self.canvas.canvasy(event.y_root - y)
            self.insert_svg_on_canvas(self.dragged_svg_path, cx, cy)
        except:
            pass
        finally:
            del self.dragged_item
            del self.dragged_svg_path

