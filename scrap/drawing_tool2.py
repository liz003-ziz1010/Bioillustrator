import os
import base64
import tkinter as tk
from tkinter import ttk, Menu
from PIL import Image, ImageTk
from xml.etree import ElementTree as ET


VECTORS_FOLDER = "vectorscolor"
DEFAULT_SIZE = (150, 150)  # default object size on canvas


class DrawableImage:
    def __init__(self, canvas, pil_img, x, y):
        self.canvas = canvas
        self.pil_img = pil_img
        self.tk_img = ImageTk.PhotoImage(self.pil_img)
        self.id = self.canvas.create_image(x, y, image=self.tk_img, anchor="center")

        # Bind selection + dragging
        self.canvas.tag_bind(self.id, "<Button-1>", self.select)
        self.canvas.tag_bind(self.id, "<B1-Motion>", self.drag)

        self.offset_x = 0
        self.offset_y = 0

    def select(self, event):
        self.offset_x = self.canvas.canvasx(event.x) - self.canvas.coords(self.id)[0]
        self.offset_y = self.canvas.canvasy(event.y) - self.canvas.coords(self.id)[1]
        self.canvas.focus_set()

    def drag(self, event):
        x = self.canvas.canvasx(event.x) - self.offset_x
        y = self.canvas.canvasy(event.y) - self.offset_y
        self.canvas.coords(self.id, x, y)

    def bring_to_front(self):
        self.canvas.tag_raise(self.id)

    def send_to_back(self):
        self.canvas.tag_lower(self.id)


class DrawingToolApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Drawing Tool")

        # Main frame with library on left and canvas on right
        main_frame = tk.Frame(root)
        main_frame.pack(fill="both", expand=True)

        # Left panel (library)
        self.library_frame = tk.Frame(main_frame, width=200, bg="#e8e8e8")
        self.library_frame.pack(side="left", fill="y")

        self.library_canvas = tk.Canvas(self.library_frame, bg="#e8e8e8")
        self.library_canvas.pack(side="left", fill="both", expand=True)

        self.library_scroll = ttk.Scrollbar(self.library_frame, orient="vertical",
                                            command=self.library_canvas.yview)
        self.library_scroll.pack(side="right", fill="y")

        self.library_canvas.configure(yscrollcommand=self.library_scroll.set)

        self.library_inner = tk.Frame(self.library_canvas, bg="#e8e8e8")
        self.library_canvas.create_window((0, 0), window=self.library_inner, anchor="nw")

        self.library_inner.bind("<Configure>", lambda e: self.library_canvas.configure(
            scrollregion=self.library_canvas.bbox("all")
        ))

        # Canvas (drawing area)
        self.canvas = tk.Canvas(main_frame, bg="white", width=900, height=600)
        self.canvas.pack(side="right", fill="both", expand=True)

        # Context menu
        self.menu = Menu(root, tearoff=0)
        self.menu.add_command(label="Bring to Front", command=self.bring_front)
        self.menu.add_command(label="Send to Back", command=self.send_back)

        self.selected_item = None

        self.canvas.bind("<Button-3>", self.show_context_menu)  # right click

        # Load SVG-wrapped thumbnails into the library
        self.load_library_images()

    # ---------------------------
    #      SVG IMAGE LOADING
    # ---------------------------
    def load_library_images(self):
        row = 0

        for file in os.listdir(VECTORS_FOLDER):
            if file.lower().endswith(".svg"):
                svg_path = os.path.join(VECTORS_FOLDER, file)

                pil_img = self.extract_image_from_svg(svg_path)
                if pil_img is None:
                    continue

                # Thumbnail
                thumb = pil_img.copy()
                thumb.thumbnail((80, 80))
                tk_thumb = ImageTk.PhotoImage(thumb)

                # Label representing image
                lbl = tk.Label(self.library_inner, image=tk_thumb, bg="white")
                lbl.image = tk_thumb
                lbl.grid(row=row, column=0, pady=5, padx=5)

                # Bind dragging from library
                lbl.bind("<Button-1>", lambda e, img=pil_img: self.start_drag_from_library(e, img))

                row += 1

    def extract_image_from_svg(self, path):
        try:
            tree = ET.parse(path)
            root = tree.getroot()
            image_tag = root.find("{http://www.w3.org/2000/svg}image")

            href = image_tag.attrib.get("href")
            header, b64data = href.split("base64,")
            img_bytes = base64.b64decode(b64data)

            pil_img = Image.open(io.BytesIO(img_bytes))
            pil_img = pil_img.resize(DEFAULT_SIZE, Image.LANCZOS)
            return pil_img

        except Exception as e:
            print("Failed to load SVG:", path, e)
            return None

    # ---------------------------
    #   DRAG FROM LIBRARY
    # ---------------------------
    def start_drag_from_library(self, event, pil_image):
        self.drag_image = pil_image
        self.root.bind("<Motion>", self.follow_mouse)
        self.root.bind("<ButtonRelease-1>", self.place_image)

    def follow_mouse(self, event):
        pass  # no visual preview yet – simple behavior

    def place_image(self, event):
        x = self.canvas.canvasx(event.x)
        y = self.canvas.canvasy(event.y)

        DrawableImage(self.canvas, self.drag_image, x, y)

        # Stop bindings
        self.root.unbind("<Motion>")
        self.root.unbind("<ButtonRelease-1>")

    # ---------------------------
    #        CONTEXT MENU
    # ---------------------------
    def show_context_menu(self, event):
        item = self.canvas.find_closest(event.x, event.y)
        if item:
            self.selected_item = item[0]
            self.menu.post(event.x_root, event.y_root)

    def bring_front(self):
        if self.selected_item:
            self.canvas.tag_raise(self.selected_item)

    def send_back(self):
        if self.selected_item:
            self.canvas.tag_lower(self.selected_item)


# ------------------------------------------------
#                   RUN APP
# ------------------------------------------------
if __name__ == "__main__":
    import io
    root = tk.Tk()
    app = DrawingToolApp(root)
    root.mainloop()
