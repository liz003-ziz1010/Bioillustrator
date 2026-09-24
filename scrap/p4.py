import os
import tkinter as tk
from tkinter import filedialog, colorchooser
from PIL import Image, ImageDraw, ImageTk
from svgelements import SVG, Path, Shape


# ============================================================
# SVG → PNG using pure Python (svgelements + Pillow)
# ============================================================

def svg_to_png_no_cairo(svg_path, png_path, scale=0.25):
    svg = SVG.parse(svg_path)
    
    # Canvas size based on SVG bounds
    w = int(svg.width * scale)
    h = int(svg.height * scale)

    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Draw each element as vector approximated paths
    for element in svg.elements():
        if isinstance(element, Shape):
            color = element.fill.hex if element.fill is not None else None
            stroke = element.stroke.hex if element.stroke is not None else None
            width = element.stroke_width if element.stroke_width else 1

            try:
                pts = [(p.x * scale, p.y * scale) for p in element]
            except:
                continue

            if len(pts) > 1:
                if color:
                    draw.polygon(pts, fill=color)
                if stroke:
                    draw.line(pts, fill=stroke, width=int(width*scale))

    img.save(png_path)


# ============================================================
# SHAPE CLASS (Image-Based)
# ============================================================

class ImageShape:
    def __init__(self, canvas, x, y, png_path):
        self.canvas = canvas
        self.x = x
        self.y = y
        self.png_path = png_path
        
        self.image = Image.open(png_path)
        self.tk_img = ImageTk.PhotoImage(self.image)

        self.item = self.canvas.create_image(x, y, image=self.tk_img)
        self.selected = False

    def move(self, dx, dy):
        self.x += dx
        self.y += dy
        self.canvas.move(self.item, dx, dy)

    def select(self):
        self.selected = True
        self.canvas.itemconfig(self.item, outline="cyan")

    def unselect(self):
        self.selected = False
        self.canvas.itemconfig(self.item, outline="")

    def delete(self):
        self.canvas.delete(self.item)


# ============================================================
# CANVAS CONTROLLER
# ============================================================

class CanvasController:
    def __init__(self, root):
        self.root = root
        self.canvas = tk.Canvas(root, width=1000, height=700, bg="white")
        self.canvas.pack(fill="both", expand=True)

        self.shapes = []
        self.selected = None

        # Placement mode
        self.placing_mode = False
        self.placing_png_path = None
        self.drag_start = None

        self.setup_menu()
        self.bind_events()

        self.cursor_drag = "fleur"
        self.cursor_place = "hand2"
        self.cursor_normal = "arrow"

    # -------------------- MENU --------------------
    def setup_menu(self):
        bar = tk.Menu(self.root)
        self.root.config(menu=bar)

        file_menu = tk.Menu(bar, tearoff=0)
        file_menu.add_command(label="Add SVG Shape", command=self.pick_svg_to_place)
        bar.add_cascade(label="File", menu=file_menu)

        edit = tk.Menu(bar, tearoff=0)
        edit.add_command(label="Change Color", command=self.change_color)
        edit.add_command(label="Delete Shape", command=self.delete_selected)
        bar.add_cascade(label="Edit", menu=edit)

    # -------------------- EVENTS --------------------
    def bind_events(self):
        self.canvas.bind("<Button-1>", self.on_click)
        self.canvas.bind("<Motion>", self.on_motion)
        self.canvas.bind("<B1-Motion>", self.on_drag)

    # -------------------- SHAPE PLACEMENT --------------------
    def pick_svg_to_place(self):
        path = filedialog.askopenfilename(initialdir="vectors", filetypes=[("SVG files", "*.svg")])
        if not path:
            return

        png_path = "temp_shape.png"
        svg_to_png_no_cairo(path, png_path, scale=0.25)

        self.placing_mode = True
        self.placing_png_path = png_path
        self.canvas.config(cursor=self.cursor_place)

    def on_motion(self, event):
        if self.placing_mode:
            self.canvas.delete("preview")
            img = ImageTk.PhotoImage(Image.open(self.placing_png_path))
            self.preview_img = img
            self.canvas.create_image(event.x, event.y, image=img, tags="preview")

    def on_click(self, event):
        if self.placing_mode:
            self.canvas.delete("preview")
            shape = ImageShape(self.canvas, event.x, event.y, self.placing_png_path)
            self.shapes.append(shape)
            self.select_shape(shape)
            self.placing_mode = False
            self.canvas.config(cursor=self.cursor_normal)
            return

        # Normal selection
        clicked = self.canvas.find_closest(event.x, event.y)
        for s in self.shapes:
            if clicked[0] == s.item:
                self.select_shape(s)
                self.drag_start = (event.x, event.y)
                self.canvas.config(cursor=self.cursor_drag)
                return

        self.unselect_all()

    def on_drag(self, event):
        if self.selected and self.drag_start:
            dx = event.x - self.drag_start[0]
            dy = event.y - self.drag_start[1]
            self.selected.move(dx, dy)
            self.drag_start = (event.x, event.y)

    # -------------------- SELECTION --------------------
    def select_shape(self, shape):
        self.unselect_all()
        shape.select()
        self.selected = shape

    def unselect_all(self):
        for s in self.shapes:
            s.unselect()
        self.selected = None
        self.canvas.config(cursor=self.cursor_normal)

    # -------------------- EDITING --------------------
    def change_color(self):
        if not self.selected:
            return
        color = colorchooser.askcolor()[1]
        if not color:
            return

        img = self.selected.image.convert("RGBA")
        pixels = img.load()

        r_new, g_new, b_new = tuple(int(color[i:i+2], 16) for i in (1,3,5))

        for y in range(img.height):
            for x in range(img.width):
                r, g, b, a = pixels[x, y]
                if a > 0:
                    pixels[x, y] = (r_new, g_new, b_new, a)

        self.selected.image = img
        self.selected.tk_img = ImageTk.PhotoImage(img)
        self.canvas.itemconfig(self.selected.item, image=self.selected.tk_img)

    def delete_selected(self):
        if self.selected:
            self.selected.delete()
            self.shapes.remove(self.selected)
            self.selected = None
            self.canvas.config(cursor=self.cursor_normal)


# -------------------- RUN APP --------------------
if __name__ == "__main__":
    root = tk.Tk()
    root.title("Vector Drawing Canvas - Windows Safe SVG Renderer")
    app = CanvasController(root)
    root.mainloop()
