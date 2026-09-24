import os
import tkinter as tk
from tkinter import filedialog, colorchooser
from PIL import Image, ImageTk
from svgpathtools import svg2paths
from math import cos, sin, radians


# ===========================================================
# BASE CLASSES
# ===========================================================

class Shape:
    """Abstract base shape with transformation logic"""
    def __init__(self, canvas, x, y):
        self.canvas = canvas
        self.x = x
        self.y = y
        self.scale = 1.0
        self.rotation = 0
        self.flip_x = 1
        self.flip_y = 1
        self.color = "#000000"
        self.selected = False
        self.items = []  # canvas item IDs

    def draw(self):
        raise NotImplementedError

    def delete(self):
        for i in self.items:
            self.canvas.delete(i)

    def set_color(self, color):
        self.color = color
        for i in self.items:
            self.canvas.itemconfig(i, fill=color)

    def move(self, dx, dy):
        self.x += dx
        self.y += dy
        for i in self.items:
            self.canvas.move(i, dx, dy)

    def apply_transform(self):
        pass

    def select(self):
        self.selected = True
        for i in self.items:
            self.canvas.itemconfig(i, width=3)

    def unselect(self):
        self.selected = False
        for i in self.items:
            self.canvas.itemconfig(i, width=1)


# ===========================================================
# SVG SHAPE
# ===========================================================

class SVGShape(Shape):
    """Loads an SVG path as a drawable Tkinter polygon"""
    def __init__(self, canvas, x, y, svg_path):
        super().__init__(canvas, x, y)
        self.svg_path = svg_path
        self.raw_points = self._extract_points()
        self.draw()

    def _extract_points(self):
        """Read SVG & convert path to list of (x,y) points"""
        paths, attrs = svg2paths(self.svg_path)
        points = []
        for path in paths:
            for seg in path:
                for t in [i / 20 for i in range(21)]:  # smooth sampling
                    pt = seg.point(t)
                    points.append((pt.real, pt.imag))
        return points

    def _transform_points(self):
        pts = []
        angle = radians(self.rotation)

        for px, py in self.raw_points:
            px *= self.scale * self.flip_x
            py *= self.scale * self.flip_y

            rx = px * cos(angle) - py * sin(angle)
            ry = px * sin(angle) + py * cos(angle)

            pts.append((self.x + rx, self.y + ry))
        return pts

    def draw(self):
        self.delete()
        pts = self._transform_points()
        flat = [c for xy in pts for c in xy]
        polygon = self.canvas.create_polygon(flat, fill=self.color, outline="black")
        self.items = [polygon]


# ===========================================================
# GROUP CLASS
# ===========================================================

class ShapeGroup:
    def __init__(self, canvas, shapes):
        self.canvas = canvas
        self.shapes = shapes
        self.selected = False

    def move(self, dx, dy):
        for s in self.shapes:
            s.move(dx, dy)

    def delete(self):
        for s in self.shapes:
            s.delete()

    def select(self):
        self.selected = True
        for s in self.shapes:
            s.select()

    def unselect(self):
        self.selected = False
        for s in self.shapes:
            s.unselect()


# ===========================================================
# MAIN CANVAS CONTROLLER
# ===========================================================

class CanvasController:
    def __init__(self, root):
        self.root = root
        self.canvas = tk.Canvas(root, width=1000, height=700, bg="white")
        self.canvas.pack(fill="both", expand=True)

        self.shapes = []
        self.selected = None
        self.drag_start = None

        self.setup_menu()
        self.bind_events()

    # ---------------- MENU ---------------- #

    def setup_menu(self):
        bar = tk.Menu(self.root)
        self.root.config(menu=bar)

        file_menu = tk.Menu(bar, tearoff=0)
        file_menu.add_command(label="Add SVG Shape", command=self.add_svg)
        bar.add_cascade(label="File", menu=file_menu)

        edit_menu = tk.Menu(bar, tearoff=0)
        edit_menu.add_command(label="Change Color", command=self.change_color)
        edit_menu.add_command(label="Flip Horizontal", command=self.flip_horizontal)
        edit_menu.add_command(label="Flip Vertical", command=self.flip_vertical)
        edit_menu.add_command(label="Rotate 15°", command=lambda: self.rotate_selected(15))
        edit_menu.add_command(label="Scale Up", command=lambda: self.scale_selected(1.1))
        edit_menu.add_command(label="Scale Down", command=lambda: self.scale_selected(0.9))
        bar.add_cascade(label="Edit", menu=edit_menu)

    # ---------------- EVENTS ---------------- #

    def bind_events(self):
        self.canvas.bind("<Button-1>", self.on_click)
        self.canvas.bind("<B1-Motion>", self.on_drag)

    def on_click(self, event):
        clicked = self.canvas.find_closest(event.x, event.y)
        for s in self.shapes:
            if clicked[0] in s.items:
                self.select_shape(s)
                self.drag_start = (event.x, event.y)
                return

        self.unselect_all()

    def on_drag(self, event):
        if self.selected and self.drag_start:
            dx = event.x - self.drag_start[0]
            dy = event.y - self.drag_start[1]
            self.selected.move(dx, dy)
            self.drag_start = (event.x, event.y)

    # ---------------- SHAPE FUNCTIONS ---------------- #

    def add_svg(self):
        path = filedialog.askopenfilename(
            initialdir="vectors",
            filetypes=[("SVG Files", "*.svg")]
        )
        if not path:
            return
        s = SVGShape(self.canvas, 200, 200, path)
        self.shapes.append(s)
        self.select_shape(s)

    def select_shape(self, shape):
        self.unselect_all()
        shape.select()
        self.selected = shape

    def unselect_all(self):
        for s in self.shapes:
            s.unselect()
        self.selected = None

    # ---------------- TRANSFORM OPERATIONS ---------------- #

    def change_color(self):
        if not self.selected:
            return
        color = colorchooser.askcolor()[1]
        if color:
            self.selected.set_color(color)

    def flip_horizontal(self):
        if self.selected:
            self.selected.flip_x *= -1
            self.selected.draw()

    def flip_vertical(self):
        if self.selected:
            self.selected.flip_y *= -1
            self.selected.draw()

    def rotate_selected(self, deg):
        if self.selected:
            self.selected.rotation += deg
            self.selected.draw()

    def scale_selected(self, factor):
        if self.selected:
            self.selected.scale *= factor
            self.selected.draw()


# ===========================================================
# MAIN APP
# ===========================================================

if __name__ == "__main__":
    root = tk.Tk()
    root.title("Vector Drawing Canvas (SVG)")
    app = CanvasController(root)
    root.mainloop()
