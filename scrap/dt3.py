import tkinter as tk
from tkinter import filedialog, colorchooser
from pathlib import Path
from PIL import Image, ImageTk

class CanvasImage:
    """Class to track canvas images with metadata"""
    def __init__(self, canvas, img, x, y):
        self.canvas = canvas
        self.img = img  # ImageTk.PhotoImage
        self.id = canvas.create_image(x, y, image=self.img)
        self.x = x
        self.y = y
        self.selected = False

    def move(self, dx, dy):
        self.canvas.move(self.id, dx, dy)
        self.x += dx
        self.y += dy

    def coords(self):
        return self.canvas.coords(self.id)

class DrawingToolApp:
    def __init__(self, root):
        self._root = root
        self._root.title("Drawing Tool")
        self._root.geometry("1200x700")

        self.default_size = (150, 150)
        self.library_images = []
        self.canvas_images = []
        self.selected_image = None
        self.drag_data = {"x": 0, "y": 0, "item": None}

        self._build_ui()
        self._create_context_menu()
        self._load_library("vectorscolor")

    # ---------------- UI -----------------
    def _build_ui(self):
        self.main_frame = tk.Frame(self._root)
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        # Library panel
        self.lib_frame = tk.Frame(self.main_frame, width=200, bg="#ddd")
        self.lib_frame.pack(side=tk.LEFT, fill=tk.Y)

        self.lib_canvas = tk.Canvas(self.lib_frame, bg="#ddd", width=200)
        self.lib_canvas.pack(fill=tk.BOTH, expand=True)
        self.lib_canvas.bind("<ButtonPress-1>", self._on_library_click)

        # Drawing canvas
        self.canvas = tk.Canvas(self.main_frame, bg="white")
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.canvas.bind("<ButtonPress-1>", self._on_canvas_click)
        self.canvas.bind("<B1-Motion>", self._on_canvas_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_canvas_release)
        self.canvas.bind("<Button-3>", self._show_context_menu)

    # ---------------- Load Library ----------------
    def _load_library(self, folder):
        folder_path = Path(folder)
        if not folder_path.exists():
            print(f"Library folder '{folder}' not found!")
            return

        y = 50
        for f in folder_path.iterdir():
            if f.suffix.lower() in [".png", ".jpg", ".jpeg", ".svg"]:
                try:
                    img = Image.open(f)
                    img.thumbnail(self.default_size)
                    tk_img = ImageTk.PhotoImage(img)
                    self.library_images.append(tk_img)
                    self.lib_canvas.create_image(100, y, image=tk_img)
                    y += self.default_size[1] + 20
                except Exception as e:
                    print(f"Failed to load {f}: {e}")

    # ---------------- Drag & Drop ----------------
    def _on_library_click(self, event):
        closest = self.lib_canvas.find_closest(event.x, event.y)
        if not closest:
            return
        idx = closest[0]-1
        if idx < len(self.library_images):
            tk_img = self.library_images[idx]
            # Add to canvas center
            canvas_width = self.canvas.winfo_width()//2
            canvas_height = self.canvas.winfo_height()//2
            canvas_img = CanvasImage(self.canvas, tk_img, canvas_width, canvas_height)
            self.canvas_images.append(canvas_img)
            self._select_image(canvas_img)

    def _on_canvas_click(self, event):
        items = self.canvas.find_overlapping(event.x, event.y, event.x, event.y)
        if items:
            for img in self.canvas_images:
                if img.id in items:
                    self._select_image(img)
                    self.drag_data["item"] = img
                    self.drag_data["x"] = event.x
                    self.drag_data["y"] = event.y
                    break
        else:
            self._select_image(None)

    def _on_canvas_drag(self, event):
        img = self.drag_data["item"]
        if img:
            dx = event.x - self.drag_data["x"]
            dy = event.y - self.drag_data["y"]
            img.move(dx, dy)
            self.drag_data["x"] = event.x
            self.drag_data["y"] = event.y

    def _on_canvas_release(self, event):
        self.drag_data["item"] = None

    # ---------------- Selection ----------------
    def _select_image(self, img):
        if self.selected_image:
            self.canvas.itemconfig(self.selected_image.id, outline="")
        self.selected_image = img
        if img:
            self.canvas.itemconfig(img.id, outline="red")

    # ---------------- Context Menu ----------------
    def _create_context_menu(self):
        self.context_menu = tk.Menu(self._root, tearoff=0)
        self.context_menu.add_command(label="Bring to Front", command=self._bring_to_front)
        self.context_menu.add_command(label="Send to Back", command=self._send_to_back)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Flip Horizontal", command=self._flip_horizontal)
        self.context_menu.add_command(label="Flip Vertical", command=self._flip_vertical)
        self.context_menu.add_command(label="Recolor", command=self._recolor)

    def _show_context_menu(self, event):
        items = self.canvas.find_overlapping(event.x, event.y, event.x, event.y)
        if items:
            for img in self.canvas_images:
                if img.id in items:
                    self._select_image(img)
                    break
            self.context_menu.tk_popup(event.x_root, event.y_root)

    # ---------------- Overlay / Underlay ----------------
    def _bring_to_front(self):
        if self.selected_image:
            self.canvas.tag_raise(self.selected_image.id)

    def _send_to_back(self):
        if self.selected_image:
            self.canvas.tag_lower(self.selected_image.id)

    # ---------------- Flip ----------------
    def _flip_horizontal(self):
        if self.selected_image:
            cx, cy = self.selected_image.coords()
            self.canvas.scale(self.selected_image.id, cx, cy, -1, 1)

    def _flip_vertical(self):
        if self.selected_image:
            cx, cy = self.selected_image.coords()
            self.canvas.scale(self.selected_image.id, cx, cy, 1, -1)

    # ---------------- Recolor ----------------
    def _recolor(self):
        if self.selected_image:
            color = colorchooser.askcolor(title="Choose color")[1]
            if color:
                try:
                    self.canvas.itemconfig(self.selected_image.id, fill=color)
                except Exception:
                    print("Recolor works on vector items or shapes only.")

# ---------------- Run ----------------
if __name__ == "__main__":
    root = tk.Tk()
    app = DrawingToolApp(root)
    root.mainloop()
