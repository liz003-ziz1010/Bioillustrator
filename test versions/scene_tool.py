import tkinter as tk
from tkinter import filedialog, simpledialog, colorchooser, messagebox
import tksvg
from pathlib import Path
from lxml import etree
import io
import re
from PIL import Image
from pixels2svg import pixels2svg

class DrawingCanvas:
    def __init__(self, root):
        self.root = root
        self.root.title("Drawing Canvas")
        self.canvas = tk.Canvas(self.root, width=800, height=600, bg="white")
        self.canvas.pack(expand=True, fill="both")

        # Core application state
        self.selected_items = []
        self.groups = {}
        self.svg_images = {}
        self.svg_data = {}

        # State for interactive operations (drag/resize)
        self.drag_info = {}

        self.create_ui()
        self.bind_events()
        self.load_initial_svgs()

    def create_ui(self):
        menubar = tk.Menu(self.root)
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Load SVG(s)", command=self.load_svg_from_dialog)
        file_menu.add_command(label="Import Image to SVG", command=self.import_and_convert_image)
        file_menu.add_command(label="Clear Canvas", command=self.clear_canvas)
        menubar.add_cascade(label="File", menu=file_menu)

        edit_menu = tk.Menu(menubar, tearoff=0)
        edit_menu.add_command(label="Group", command=self.group_items, accelerator="Ctrl+G")
        edit_menu.add_command(label="Ungroup", command=self.ungroup_items, accelerator="Ctrl+U")
        edit_menu.add_command(label="Recolor", command=self.recolor_dialog)
        edit_menu.add_command(label="Flip Horizontal", command=lambda: self.flip_selection("horizontal"))
        edit_menu.add_command(label="Flip Vertical", command=lambda: self.flip_selection("vertical"))
        menubar.add_cascade(label="Edit", menu=edit_menu)

        self.root.config(menu=menubar)

    def import_and_convert_image(self):
        filepath = filedialog.askopenfilename(
            title="Select an Image",
            filetypes=[("Image files", "*.png *.jpg *.jpeg *.bmp")]
        )
        if not filepath:
            return

        try:
            image = Image.open(filepath)
            
            # Generate a unique output path
            output_dir = Path("vectors")
            output_dir.mkdir(exist_ok=True)
            output_path = output_dir / f"converted_{len(self.svg_images)}.svg"

            # Convert the image
            pixels2svg.convert(image, output_path=str(output_path))
            print(f"Image successfully converted to {output_path}")

            # Load the new SVG onto the canvas
            self.load_svgs([output_path])
        except Exception as e:
            messagebox.showerror("Conversion Error", f"Failed to convert image:\n{e}")

    def bind_events(self):
        self.canvas.bind("<ButtonPress-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_motion)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.root.bind("<Control-g>", lambda e: self.group_items())
        self.root.bind("<Control-u>", lambda e: self.ungroup_items())

    def load_initial_svgs(self):
        vector_dir = Path("nobgsvg_out")
        if vector_dir.is_dir():
            self.load_svgs([p for p in vector_dir.glob("*.svg")])
        else:
            messagebox.showinfo("Setup Info", f"Created '{vector_dir}' directory.\nPlace your .svg files there to see them on startup.")
            vector_dir.mkdir(exist_ok=True)


    def load_svg_from_dialog(self):
        filepaths = filedialog.askopenfilenames(
            title="Select SVG files",
            filetypes=[("SVG files", "*.svg")]
        )
        if filepaths: self.load_svgs(filepaths)

    def load_svgs(self, svg_paths):
        for svg_path in svg_paths:
            try:
                path = Path(svg_path)
                image_name = f"svg_{len(self.svg_images)}"
                with open(path, 'rb') as f:
                    data = f.read()
                    self.svg_data[image_name] = data
                
                self.svg_images[image_name] = tksvg.SvgImage(data=data, scaletowidth=100)
                pos_x = 100 + (len(self.svg_images) % 5) * 30
                pos_y = 100 + (len(self.svg_images) % 5) * 30
                self.canvas.create_image(pos_x, pos_y, image=self.svg_images[image_name], anchor="nw", tags=(image_name, "svg"))
            except Exception as e:
                messagebox.showerror("SVG Load Error", f"Failed to load {svg_path}:\n{e}")

    def clear_canvas(self):
        self.canvas.delete("all")
        self.svg_images.clear(); self.svg_data.clear(); self.selected_items.clear(); self.groups.clear()

    def on_press(self, event):
        self.drag_info.clear()
        item = self.canvas.find_closest(event.x, event.y)
        item = item[0] if item else None

        tags = self.canvas.gettags(item) if item else []
        is_handle = "handle" in tags
        is_svg = "svg" in tags

        if is_handle:
            self.drag_info['type'] = 'resize'
            self.drag_info['handle'] = tags
        elif is_svg:
            self.drag_info['type'] = 'drag'
            # Selection logic
            group_id = self.get_group_id(item)
            is_shift = event.state & 0x0001
            
            if group_id and item not in self.selected_items:
                self.selected_items = self.groups.get(group_id, [item])[:]
            elif not is_shift:
                if item not in self.selected_items: self.selected_items = [item]
            else: # Shift-click
                if item in self.selected_items: self.selected_items.remove(item)
                else: self.selected_items.append(item)
        else: # Clicked on empty canvas
            self.selected_items = []
        
        if self.selected_items:
            self.drag_info['start_pos'] = (event.x, event.y)
            self.drag_info['start_bbox'] = self.canvas.bbox(*self.selected_items)
            self.drag_info['item_starts'] = {i: self.canvas.coords(i) for i in self.selected_items}

        self.draw_selection_box()

    def on_motion(self, event):
        if not self.drag_info or not self.selected_items: return
        
        op_type = self.drag_info.get('type')
        if op_type == 'resize':
            self.perform_visual_resize(event)
        elif op_type == 'drag':
            start_x, start_y = self.drag_info['start_pos']
            dx, dy = event.x - start_x, event.y - start_y
            for item, (ix, iy) in self.drag_info['item_starts'].items():
                self.canvas.coords(item, ix + dx, iy + dy)
        
        self.draw_selection_box()

    def on_release(self, event):
        if self.drag_info.get('type') == 'resize':
            self.commit_resize(event)
        self.drag_info.clear()

    def draw_selection_box(self):
        self.canvas.delete("selection_box", "handle")
        if self.selected_items:
            x1, y1, x2, y2 = self.canvas.bbox(*self.selected_items)
            self.canvas.create_rectangle(x1, y1, x2, y2, outline="blue", tags="selection_box")
            tags = ("handle",)
            self.canvas.create_rectangle(x1 - 3, y1 - 3, x1 + 3, y1 + 3, fill="blue", tags=tags+("top_left",))
            self.canvas.create_rectangle(x2 - 3, y1 - 3, x2 + 3, y1 + 3, fill="blue", tags=tags+("top_right",))
            self.canvas.create_rectangle(x1 - 3, y2 - 3, x1 + 3, y2 + 3, fill="blue", tags=tags+("bottom_left",))
            self.canvas.create_rectangle(x2 - 3, y2 - 3, x2 + 3, y2 + 3, fill="blue", tags=tags+("bottom_right",))

    def perform_visual_resize(self, event):
        handle = self.drag_info['handle']
        x1, y1, x2, y2 = self.drag_info['start_bbox']

        # Determine fixed anchor point
        ax = x2 if "left" in handle else x1
        ay = y2 if "top" in handle else y1
        
        new_w = abs(event.x - ax)
        new_h = abs(event.y - ay)
        
        if new_w < 10 or new_h < 10: return

        orig_w = (x2 - x1) or 1
        orig_h = (y2 - y1) or 1
        sx, sy = new_w / orig_w, new_h / orig_h

        for item in self.selected_items:
            start_ix, start_iy = self.drag_info['item_starts'][item]
            rel_x, rel_y = start_ix - ax, start_iy - ay
            self.canvas.coords(item, ax + rel_x * sx, ay + rel_y * sy)
            
            img_name = self.get_image_name(item)
            img = self.svg_images[img_name]
            # Visual scale only
            img.configure(scaletowidth=int(img.width() * sx))
    
    def commit_resize(self, event):
        # Calculate final scale and apply to data
        handle = self.drag_info['handle']
        x1, y1, x2, y2 = self.drag_info['start_bbox']
        ax = x2 if "left" in handle else x1
        ay = y2 if "top" in handle else y1
        new_w, new_h = abs(event.x - ax), abs(event.y - ay)
        if new_w < 10 or new_h < 10: return
        orig_w, orig_h = (x2 - x1) or 1, (y2-y1) or 1
        sx, sy = new_w / orig_w, new_h / orig_h
        
        transform = f"scale({sx}, {sy})"
        for item in self.selected_items:
            self.apply_transform(self.get_image_name(item), transform)

    def get_image_name(self, item): return next((t for t in self.canvas.gettags(item) if t.startswith("svg_")), None)
    def get_group_id(self, item): return next((t for t in self.canvas.gettags(item) if t.startswith("group_")), None)

    def group_items(self):
        if len(self.selected_items) > 1:
            group_id = f"group_{len(self.groups)}"
            self.groups[group_id] = self.selected_items[:]
            for item in self.selected_items: self.canvas.addtag_withtag(group_id, item)
            self.selected_items = self.groups[group_id]
            self.draw_selection_box()

    def ungroup_items(self):
        if self.selected_items:
            group_id = self.get_group_id(self.selected_items[0])
            if group_id:
                for item in self.groups[group_id]:
                    tags = list(self.canvas.gettags(item)); tags.remove(group_id)
                    self.canvas.itemconfig(item, tags=tags)
                del self.groups[group_id]
                self.draw_selection_box()

    def recolor_dialog(self):
        if not self.selected_items: return
        colors = set()
        for item in self.selected_items:
            data = self.svg_data[self.get_image_name(item)]
            colors.update(re.findall(r'(?:fill|stroke)="(#[0-9a-fA-F]{3,6})"', data.decode('utf-8')))
        
        if not colors: print("No colors found."); return
        
        color_to_replace = simpledialog.askstring("Recolor", f"Available: {', '.join(colors)}\nReplace which color?", parent=self.root)
        if color_to_replace in colors:
            new_color = colorchooser.askcolor(parent=self.root)[1]
            if new_color:
                for item in self.selected_items:
                    tree = etree.parse(io.BytesIO(self.svg_data[self.get_image_name(item)]))
                    for attr in ['fill', 'stroke']:
                        for el in tree.xpath(f"//*[@{attr}='{color_to_replace}']"):
                            el.attrib[attr] = new_color
                    self.update_svg(self.get_image_name(item), tree)

    def flip_selection(self, direction):
        if not self.selected_items: return
        bbox = self.canvas.bbox(*self.selected_items)
        cx, cy = (bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2
        
        for item in self.selected_items:
            ix, iy = self.canvas.coords(item)
            # Flip coordinates
            new_x = 2 * cx - (ix + self.svg_images[self.get_image_name(item)].width()) if direction == 'horizontal' else ix
            new_y = 2 * cy - (iy + self.svg_images[self.get_image_name(item)].height()) if direction == 'vertical' else iy
            self.canvas.coords(item, new_x, new_y)
            
            # Flip SVG data
            transform = "scale(-1, 1)" if direction == "horizontal" else "scale(1, -1)"
            self.apply_transform(self.get_image_name(item), transform, from_center=True)
    
    def apply_transform(self, image_name, transform_str, from_center=False):
        tree = etree.parse(io.BytesIO(self.svg_data[image_name]))
        root = tree.getroot()
        
        transform_to_apply = transform_str
        if from_center:
            viewbox = root.get('viewBox'); w=h=0
            if viewbox: _, _, w, h = [float(v) for v in viewbox.split()]
            else: w,h = self.svg_images[image_name].width(), self.svg_images[image_name].height()
            cx, cy = w / 2, h / 2
            transform_to_apply = f"translate({cx}, {cy}) {transform_str} translate({-cx}, {-cy})"
        
        # Ensure a single top-level <g> for transforms
        g = root.find('{http://www.w3.org/2000/svg}g')
        if g is None or len(list(root)) > 1:
            g = etree.Element("g")
            for child in list(root): g.append(child)
            for child in list(root): root.remove(child)
            root.append(g)

        current_transform = g.get('transform', '')
        g.set('transform', f'{transform_to_apply} {current_transform}')
        self.update_svg(image_name, tree)

    def update_svg(self, image_name, tree):
        new_svg_data = etree.tostring(tree)
        self.svg_data[image_name] = new_svg_data
        self.svg_images[image_name].configure(data=new_svg_data)

if __name__ == "__main__":
    root = tk.Tk()
    app = DrawingCanvas(root)
    root.mainloop()
