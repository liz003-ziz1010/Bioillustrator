import tkinter as tk
from tkinter import filedialog, simpledialog, messagebox, ttk
import tksvg
from pathlib import Path
from lxml import etree
import io
import re
from PIL import Image
try:
    from pixels2svg import pixels2svg
except ImportError:
    pixels2svg = None


class ToolTip:
    """Tooltip widget for showing hover labels"""
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tooltip = None
        self.widget.bind("<Enter>", self.show)
        self.widget.bind("<Leave>", self.hide)
    
    def show(self, event=None):
        x, y, _, _ = self.widget.bbox("insert")
        x += self.widget.winfo_rootx() + 25
        y += self.widget.winfo_rooty() + 25
        
        self.tooltip = tk.Toplevel(self.widget)
        self.tooltip.wm_overrideredirect(True)
        self.tooltip.wm_geometry(f"+{x}+{y}")
        
        label = tk.Label(self.tooltip, text=self.text, background="#ffeb99", 
                        relief=tk.SOLID, borderwidth=1, font=("Arial", 9))
        label.pack()
    
    def hide(self, event=None):
        if self.tooltip:
            self.tooltip.destroy()
            self.tooltip = None


class SVGLibrary(tk.Frame):
    """Library panel for SVG assets with drag-and-drop support"""
    def __init__(self, parent, canvas_app):
        super().__init__(parent, bg="#f0f0f0", relief=tk.RAISED, bd=2)
        self.canvas_app = canvas_app
        self.svg_items = {}
        self.preview_size = 80
        
        # Header
        header = tk.Label(self, text="SVG Library", font=("Arial", 12, "bold"), bg="#f0f0f0")
        header.pack(pady=5)
        
        # Search bar
        search_frame = tk.Frame(self, bg="#f0f0f0")
        search_frame.pack(fill=tk.X, padx=5, pady=5)
        tk.Label(search_frame, text="Search:", bg="#f0f0f0").pack(side=tk.LEFT)
        self.search_var = tk.StringVar()
        self.search_var.trace('w', self.filter_library)
        search_entry = tk.Entry(search_frame, textvariable=self.search_var)
        search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        # Scrollable canvas for library items with scrollbar
        canvas_frame = tk.Frame(self, bg="#f0f0f0")
        canvas_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.canvas = tk.Canvas(canvas_frame, bg="white", highlightthickness=0)
        scrollbar = tk.Scrollbar(canvas_frame, orient=tk.VERTICAL, command=self.canvas.yview)
        self.scrollable_frame = tk.Frame(self.canvas, bg="white")
        
        self.scrollable_frame.bind("<Configure>", 
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=scrollbar.set)
        
        # Pack canvas and scrollbar side by side
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Mouse wheel scrolling
        self.canvas.bind("<MouseWheel>", self._on_mousewheel)
        self.canvas.bind("<Button-4>", self._on_mousewheel)
        self.canvas.bind("<Button-5>", self._on_mousewheel)
        
        # Buttons
        btn_frame = tk.Frame(self, bg="#f0f0f0")
        btn_frame.pack(fill=tk.X, padx=5, pady=5)
        
        add_btn = tk.Button(btn_frame, text="Add SVG", command=self.add_svg_to_library)
        add_btn.pack(fill=tk.X, pady=2)
        ToolTip(add_btn, "Add SVG files to library")
        
        clear_btn = tk.Button(btn_frame, text="Clear Library", command=self.clear_library)
        clear_btn.pack(fill=tk.X, pady=2)
        ToolTip(clear_btn, "Remove all items from library")
    
    def _on_mousewheel(self, event):
        """Handle mouse wheel scrolling"""
        if event.num == 5 or event.delta < 0:
            self.canvas.yview_scroll(1, "units")
        elif event.num == 4 or event.delta > 0:
            self.canvas.yview_scroll(-1, "units")
    
    def add_svg_to_library(self):
        """Add SVG files to the library"""
        filepaths = filedialog.askopenfilenames(title="Select SVG files", 
                                               filetypes=[("SVG files", "*.svg")])
        if filepaths:
            for filepath in filepaths:
                self.load_svg_item(filepath)
    
    def load_svg_item(self, svg_path):
        """Load a single SVG into the library"""
        try:
            path = Path(svg_path)
            item_id = f"lib_{len(self.svg_items)}"
            
            with open(path, 'rb') as f:
                data = f.read()
            
            # Create preview
            preview_img = tksvg.SvgImage(data=data, scaletowidth=self.preview_size)
            
            # Create library item frame
            item_frame = tk.Frame(self.scrollable_frame, bg="white", relief=tk.RIDGE, 
                                 bd=1, cursor="hand2")
            item_frame.pack(fill=tk.X, padx=5, pady=5)
            
            # Preview label
            img_label = tk.Label(item_frame, image=preview_img, bg="white")
            img_label.image = preview_img
            img_label.pack(pady=5)
            
            # Filename label
            name_label = tk.Label(item_frame, text=path.stem, bg="white", font=("Arial", 8))
            name_label.pack()
            
            # Store data
            self.svg_items[item_id] = {
                'frame': item_frame,
                'data': data,
                'preview': preview_img,
                'name': path.stem,
                'path': path
            }
            
            # Bind drag events
            for widget in [item_frame, img_label, name_label]:
                widget.bind("<Button-1>", lambda e, iid=item_id: self.start_drag(e, iid))
                widget.bind("<B1-Motion>", self.on_drag)
                widget.bind("<ButtonRelease-1>", self.end_drag)
            
        except Exception as e:
            messagebox.showerror("Library Error", f"Failed to load {svg_path}:\n{e}")
    
    def start_drag(self, event, item_id):
        """Start dragging an item from the library"""
        self.drag_item = item_id
        self.drag_window = tk.Toplevel(self)
        self.drag_window.overrideredirect(True)
        self.drag_window.attributes('-alpha', 0.7)
        
        preview = self.svg_items[item_id]['preview']
        label = tk.Label(self.drag_window, image=preview, bg="white")
        label.pack()
        
        self.drag_window.geometry(f"+{event.x_root}+{event.y_root}")
    
    def on_drag(self, event):
        """Update drag window position"""
        if hasattr(self, 'drag_window'):
            self.drag_window.geometry(f"+{event.x_root}+{event.y_root}")
    
    def end_drag(self, event):
        """Drop the item onto the canvas"""
        if hasattr(self, 'drag_window'):
            self.drag_window.destroy()
            
            canvas_x = self.canvas_app.canvas.winfo_pointerx() - self.canvas_app.canvas.winfo_rootx()
            canvas_y = self.canvas_app.canvas.winfo_pointery() - self.canvas_app.canvas.winfo_rooty()
            
            # Adjust for zoom
            canvas_x = self.canvas_app.canvas.canvasx(canvas_x) / self.canvas_app.zoom_level
            canvas_y = self.canvas_app.canvas.canvasy(canvas_y) / self.canvas_app.zoom_level
            
            data = self.svg_items[self.drag_item]['data']
            self.canvas_app.add_svg_to_canvas(data, canvas_x, canvas_y)
    
    def filter_library(self, *args):
        """Filter library items based on search"""
        search_text = self.search_var.get().lower()
        for item_id, item_data in self.svg_items.items():
            if search_text in item_data['name'].lower():
                item_data['frame'].pack(fill=tk.X, padx=5, pady=5)
            else:
                item_data['frame'].pack_forget()
    
    def clear_library(self):
        """Clear all items from library"""
        if messagebox.askyesno("Clear Library", "Remove all items from library?"):
            for item_data in self.svg_items.values():
                item_data['frame'].destroy()
            self.svg_items.clear()


class DrawingCanvas:
    def __init__(self, root):
        self.root = root
        self.root.title("SVG Canvas Editor")
        self.root.geometry("1200x700")
        
        # Zoom state
        self.zoom_level = 1.0
        self.min_zoom = 0.1
        self.max_zoom = 5.0
        
        # Create main layout
        self.setup_layout()
        

        self.selected_items = []
        self.groups = {}
        self.svg_images = {}
        self.svg_data = {}
        self.history = []
        self.history_index = -1
        
        # State for interactive operations
        self.drag_info = {}
        
        # Create UI and bind events
        self.create_ui()
        self.bind_events()
        self.load_initial_svgs()
        
        self.update_status("Ready")
    
    def setup_layout(self):
        """Create the main layout with library panel and canvas"""
        main_container = tk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        main_container.pack(fill=tk.BOTH, expand=True)
        
        # Library panel
        self.library = SVGLibrary(main_container, self)
        main_container.add(self.library, width=250)
        
        # Canvas container
        canvas_container = tk.Frame(main_container)
        main_container.add(canvas_container)
        
        # Toolbar
        toolbar = tk.Frame(canvas_container, bg="#e0e0e0", height=40)
        toolbar.pack(fill=tk.X)
        
        btn_data = [
            ("⬆", self.move_forward, "Bring forward"),
            ("⬇", self.move_backward, "Send backward"),
            ("🗑", self.delete_selection, "Delete selection"),
            ("↺", lambda: self.rotate_selection(-15), "Rotate left 15°"),
            ("↻", lambda: self.rotate_selection(15), "Rotate right 15°"),
            ("📋", self.duplicate_selection, "Duplicate selection"),
            ("🔍+", self.zoom_in, "Zoom in"),
            ("🔍-", self.zoom_out, "Zoom out"),
            ("⊡", self.zoom_reset, "Reset zoom"),
        ]
        
        for text, cmd, tooltip in btn_data:
            btn = tk.Button(toolbar, text=text, command=cmd, width=3)
            btn.pack(side=tk.LEFT, padx=2, pady=5)
            ToolTip(btn, tooltip)
        
        # Zoom label
        self.zoom_label = tk.Label(toolbar, text="100%", bg="#e0e0e0", font=("Arial", 9))
        self.zoom_label.pack(side=tk.LEFT, padx=10)
        
        # Canvas with scrollbars
        canvas_frame = tk.Frame(canvas_container)
        canvas_frame.pack(fill=tk.BOTH, expand=True)
        
        self.canvas = tk.Canvas(canvas_frame, bg="white")
        h_scroll = tk.Scrollbar(canvas_frame, orient=tk.HORIZONTAL, command=self.canvas.xview)
        v_scroll = tk.Scrollbar(canvas_frame, orient=tk.VERTICAL, command=self.canvas.yview)
        
        self.canvas.configure(xscrollcommand=h_scroll.set, yscrollcommand=v_scroll.set)
        self.canvas.configure(scrollregion=(0, 0, 2000, 2000))
        
        self.canvas.grid(row=0, column=0, sticky="nsew")
        h_scroll.grid(row=1, column=0, sticky="ew")
        v_scroll.grid(row=0, column=1, sticky="ns")
        
        canvas_frame.grid_rowconfigure(0, weight=1)
        canvas_frame.grid_columnconfigure(0, weight=1)
        
        # Status bar
        self.status_bar = tk.Label(self.root, text="Ready", bd=1, relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)
    
    def create_ui(self):
        """Create menu bar"""
        menubar = tk.Menu(self.root)
        
        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Import Image to SVG", command=self.import_and_convert_image)
        file_menu.add_command(label="Export Canvas as SVG", command=self.export_canvas)
        file_menu.add_separator()
        file_menu.add_command(label="Clear Canvas", command=self.clear_canvas)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit)
        menubar.add_cascade(label="File", menu=file_menu)
        
        # Edit menu
        edit_menu = tk.Menu(menubar, tearoff=0)
        edit_menu.add_command(label="Undo", command=self.undo, accelerator="Ctrl+Z")
        edit_menu.add_separator()
        edit_menu.add_command(label="Duplicate", command=self.duplicate_selection, accelerator="Ctrl+D")
        edit_menu.add_command(label="Delete", command=self.delete_selection, accelerator="Delete")
        edit_menu.add_separator()
        edit_menu.add_command(label="Group", command=self.group_items, accelerator="Ctrl+G")
        edit_menu.add_command(label="Ungroup", command=self.ungroup_items, accelerator="Ctrl+U")
        edit_menu.add_separator()
        edit_menu.add_command(label="Select All", command=self.select_all, accelerator="Ctrl+A")
        menubar.add_cascade(label="Edit", menu=edit_menu)
        
        # Transform menu
        transform_menu = tk.Menu(menubar, tearoff=0)
        transform_menu.add_command(label="Flip Horizontal", command=lambda: self.flip_selection("horizontal"))
        transform_menu.add_command(label="Flip Vertical", command=lambda: self.flip_selection("vertical"))
        transform_menu.add_command(label="Rotate 90° CW", command=lambda: self.rotate_selection(90))
        transform_menu.add_command(label="Rotate 90° CCW", command=lambda: self.rotate_selection(-90))
        transform_menu.add_separator()
        transform_menu.add_command(label="Bring Forward", command=self.move_forward)
        transform_menu.add_command(label="Send Backward", command=self.move_backward)
        menubar.add_cascade(label="Transform", menu=transform_menu)
        
        # View menu
        view_menu = tk.Menu(menubar, tearoff=0)
        view_menu.add_command(label="Zoom In", command=self.zoom_in, accelerator="Ctrl++")
        view_menu.add_command(label="Zoom Out", command=self.zoom_out, accelerator="Ctrl+-")
        view_menu.add_command(label="Reset Zoom", command=self.zoom_reset, accelerator="Ctrl+0")
        menubar.add_cascade(label="View", menu=view_menu)
        
        # Style menu
        style_menu = tk.Menu(menubar, tearoff=0)
        style_menu.add_command(label="Adjust Opacity", command=self.adjust_opacity)
        menubar.add_cascade(label="Style", menu=style_menu)
        
        self.root.config(menu=menubar)
    
    def bind_events(self):
        """Bind keyboard and mouse events"""
        self.canvas.bind("<ButtonPress-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_motion)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        
        # Mouse wheel zoom
        self.canvas.bind("<Control-MouseWheel>", self.on_zoom_wheel)
        self.canvas.bind("<Control-Button-4>", self.on_zoom_wheel)
        self.canvas.bind("<Control-Button-5>", self.on_zoom_wheel)
        
        # Keyboard shortcuts
        self.root.bind("<Control-g>", lambda e: self.group_items())
        self.root.bind("<Control-u>", lambda e: self.ungroup_items())
        self.root.bind("<Control-d>", lambda e: self.duplicate_selection())
        self.root.bind("<Control-a>", lambda e: self.select_all())
        self.root.bind("<Control-z>", lambda e: self.undo())
        self.root.bind("<Delete>", lambda e: self.delete_selection())
        
        # Zoom shortcuts
        self.root.bind("<Control-plus>", lambda e: self.zoom_in())
        self.root.bind("<Control-equal>", lambda e: self.zoom_in())
        self.root.bind("<Control-minus>", lambda e: self.zoom_out())
        self.root.bind("<Control-0>", lambda e: self.zoom_reset())
        
        # Arrow keys for nudging
        self.root.bind("<Left>", lambda e: self.nudge_selection(-5, 0))
        self.root.bind("<Right>", lambda e: self.nudge_selection(5, 0))
        self.root.bind("<Up>", lambda e: self.nudge_selection(0, -5))
        self.root.bind("<Down>", lambda e: self.nudge_selection(0, 5))
    
    def zoom_in(self):
        """Zoom in the canvas"""
        if self.zoom_level < self.max_zoom:
            self.zoom_level = min(self.zoom_level * 1.2, self.max_zoom)
            self.apply_zoom()
    
    def zoom_out(self):
        """Zoom out the canvas"""
        if self.zoom_level > self.min_zoom:
            self.zoom_level = max(self.zoom_level / 1.2, self.min_zoom)
            self.apply_zoom()
    
    def zoom_reset(self):
        """Reset zoom to 100%"""
        self.zoom_level = 1.0
        self.apply_zoom()
    
    def on_zoom_wheel(self, event):
        """Handle mouse wheel zoom"""
        if event.num == 5 or event.delta < 0:
            self.zoom_out()
        elif event.num == 4 or event.delta > 0:
            self.zoom_in()
    
    def apply_zoom(self):
        """Apply zoom transformation to canvas"""
        self.canvas.scale("all", 0, 0, self.zoom_level / getattr(self, '_last_zoom', 1.0), 
                         self.zoom_level / getattr(self, '_last_zoom', 1.0))
        self._last_zoom = self.zoom_level
        
        # Update scroll region
        bbox = self.canvas.bbox("all")
        if bbox:
            self.canvas.configure(scrollregion=bbox)
        
        self.zoom_label.config(text=f"{int(self.zoom_level * 100)}%")
        self.update_status(f"Zoom: {int(self.zoom_level * 100)}%")
        self.draw_selection_box()
    
    def load_initial_svgs(self):
        """Load SVGs from default directory into library"""
        vector_dir = Path("nobgsvg_out")
        if vector_dir.is_dir():
            for svg_path in vector_dir.glob("*.svg"):
                self.library.load_svg_item(svg_path)
        else:
            vector_dir.mkdir(exist_ok=True)
    
    def add_svg_to_canvas(self, data, x, y):
        """Add an SVG to the canvas at specified position"""
        try:
            image_name = f"svg_{len(self.svg_images)}"
            self.svg_data[image_name] = data
            self.svg_images[image_name] = tksvg.SvgImage(data=data, scaletowidth=100)
            
            # Apply zoom to coordinates
            x *= self.zoom_level
            y *= self.zoom_level
            
            self.canvas.create_image(x, y, image=self.svg_images[image_name], 
                                   anchor="center", tags=(image_name, "svg"))
            self.update_status(f"Added {image_name}")
        except Exception as e:
            messagebox.showerror("Canvas Error", f"Failed to add SVG:\n{e}")
    
    def import_and_convert_image(self):
        """Convert raster image to SVG"""
        if pixels2svg is None:
            messagebox.showerror("Import Error", "pixels2svg library not installed")
            return
        
        filepath = filedialog.askopenfilename(
            title="Select an Image",
            filetypes=[("Image files", "*.png *.jpg *.jpeg *.bmp")]
        )
        if not filepath:
            return
        
        try:
            image = Image.open(filepath)
            output_dir = Path("vectors")
            output_dir.mkdir(exist_ok=True)
            output_path = output_dir / f"converted_{len(self.svg_images)}.svg"
            
            pixels2svg.convert(image, output_path=str(output_path))
            self.library.load_svg_item(output_path)
            self.update_status(f"Converted {Path(filepath).name}")
        except Exception as e:
            messagebox.showerror("Conversion Error", f"Failed to convert image:\n{e}")
    
    def export_canvas(self):
        """Export entire canvas as SVG"""
        filepath = filedialog.asksaveasfilename(
            defaultextension=".svg",
            filetypes=[("SVG files", "*.svg")]
        )
        if not filepath:
            return
        
        try:
            svg_root = etree.Element("svg", 
                                    xmlns="http://www.w3.org/2000/svg",
                                    width="2000", height="2000")
            
            for item in self.canvas.find_withtag("svg"):
                img_name = self.get_image_name(item)
                x, y = self.canvas.coords(item)
                
                # Adjust for zoom
                x /= self.zoom_level
                y /= self.zoom_level
                
                tree = etree.parse(io.BytesIO(self.svg_data[img_name]))
                root = tree.getroot()
                
                g = etree.Element("g", transform=f"translate({x},{y})")
                for child in root:
                    g.append(child)
                svg_root.append(g)
            
            with open(filepath, 'wb') as f:
                f.write(etree.tostring(svg_root, pretty_print=True))
            
            self.update_status(f"Exported to {Path(filepath).name}")
        except Exception as e:
            messagebox.showerror("Export Error", f"Failed to export:\n{e}")
    
    def clear_canvas(self):
        """Clear all items from canvas"""
        if messagebox.askyesno("Clear Canvas", "Remove all items from canvas?"):
            self.canvas.delete("all")
            self.svg_images.clear()
            self.svg_data.clear()
            self.selected_items.clear()
            self.groups.clear()
            self.zoom_level = 1.0
            self._last_zoom = 1.0
            self.zoom_label.config(text="100%")
            self.update_status("Canvas cleared")
    
    def on_press(self, event):
        """Handle mouse press"""
        self.drag_info.clear()
        item = self.canvas.find_closest(self.canvas.canvasx(event.x), 
                                       self.canvas.canvasy(event.y))
        item = item[0] if item else None
        
        tags = self.canvas.gettags(item) if item else []
        is_handle = "handle" in tags
        is_svg = "svg" in tags
        
        if is_handle:
            self.drag_info['type'] = 'resize'
            self.drag_info['handle'] = tags
        elif is_svg:
            self.drag_info['type'] = 'drag'
            group_id = self.get_group_id(item)
            is_shift = event.state & 0x0001
            
            if group_id and item not in self.selected_items:
                self.selected_items = self.groups.get(group_id, [item])[:]
            elif not is_shift:
                if item not in self.selected_items:
                    self.selected_items = [item]
            else:
                if item in self.selected_items:
                    self.selected_items.remove(item)
                else:
                    self.selected_items.append(item)
        else:
            self.selected_items = []
        
        if self.selected_items:
            self.drag_info['start_pos'] = (self.canvas.canvasx(event.x), 
                                          self.canvas.canvasy(event.y))
            self.drag_info['start_bbox'] = self.canvas.bbox(*self.selected_items)
            self.drag_info['item_starts'] = {i: self.canvas.coords(i) for i in self.selected_items}
        
        self.draw_selection_box()
        self.update_status(f"Selected {len(self.selected_items)} item(s)")
    
    def on_motion(self, event):
        """Handle mouse motion with smooth resizing (unchanged from original)"""
        if not self.drag_info or not self.selected_items:
            return
        
        canvas_x = self.canvas.canvasx(event.x)
        canvas_y = self.canvas.canvasy(event.y)
        
        op_type = self.drag_info.get('type')
        if op_type == 'resize':
            self.perform_smooth_resize(canvas_x, canvas_y)
        elif op_type == 'drag':
            start_x, start_y = self.drag_info['start_pos']
            dx, dy = canvas_x - start_x, canvas_y - start_y
            for item, (ix, iy) in self.drag_info['item_starts'].items():
                self.canvas.coords(item, ix + dx, iy + dy)
        
        self.draw_selection_box()
    
    def perform_smooth_resize(self, event_x, event_y):
        """Perform smooth visual resize during drag (unchanged from original)"""
        if 'resize_initialized' not in self.drag_info:
            # Store initial sizes on first resize motion
            self.drag_info['resize_initialized'] = True
            self.drag_info['initial_sizes'] = {}
            for item in self.selected_items:
                img_name = self.get_image_name(item)
                if img_name in self.svg_images:
                    img = self.svg_images[img_name]
                    self.drag_info['initial_sizes'][item] = img.width()
        
        handle = self.drag_info['handle']
        x1, y1, x2, y2 = self.drag_info['start_bbox']
        
        # Determine anchor point (opposite corner from handle)
        ax = x2 if "left" in handle else x1
        ay = y2 if "top" in handle else y1
        
        # Calculate new dimensions
        new_w = abs(event_x - ax)
        new_h = abs(event_y - ay)
        
        # Minimum size constraint
        if new_w < 20 or new_h < 20:
            return
        
        orig_w = (x2 - x1) or 1
        orig_h = (y2 - y1) or 1
        
        # Calculate scale factors
        sx = new_w / orig_w
        sy = new_h / orig_h
        
        # Update positions and sizes
        for item in self.selected_items:
            start_ix, start_iy = self.drag_info['item_starts'][item]
            rel_x, rel_y = start_ix - ax, start_iy - ay
            
            new_x = ax + rel_x * sx
            new_y = ay + rel_y * sy
            self.canvas.coords(item, new_x, new_y)
            
            # Update image size based on initial size
            img_name = self.get_image_name(item)
            if img_name in self.svg_images and item in self.drag_info['initial_sizes']:
                img = self.svg_images[img_name]
                initial_width = self.drag_info['initial_sizes'][item]
                new_width = max(20, int(initial_width * sx))
                img.configure(scaletowidth=new_width)
    
    def on_release(self, event):
        """Handle mouse release (unchanged from original)"""
        if self.drag_info.get('type') == 'resize':
            canvas_x = self.canvas.canvasx(event.x)
            canvas_y = self.canvas.canvasy(event.y)
            self.commit_resize(canvas_x, canvas_y)
        self.drag_info.clear()
    
    def commit_resize(self, event_x, event_y):
        """Commit resize transformation by updating SVG data (unchanged from original)"""
        handle = self.drag_info['handle']
        x1, y1, x2, y2 = self.drag_info['start_bbox']
        ax = x2 if "left" in handle else x1
        ay = y2 if "top" in handle else y1
        
        new_w = abs(event_x - ax)
        new_h = abs(event_y - ay)
        
        if new_w < 20 or new_h < 20:
            return
        
        orig_w = (x2 - x1) or 1
        orig_h = (y2 - y1) or 1
        sx, sy = new_w / orig_w, new_h / orig_h
        
        # Update the SVG data for each item with proper scaling
        for item in self.selected_items:
            img_name = self.get_image_name(item)
            if img_name and img_name in self.svg_data:
                # Reload the SVG at the new size instead of applying transform
                if item in self.drag_info.get('initial_sizes', {}):
                    new_width = max(20, int(self.drag_info['initial_sizes'][item] * sx))
                    self.svg_images[img_name].configure(scaletowidth=new_width)
    
    def draw_selection_box(self):
        """Draw selection box and resize handles"""
        self.canvas.delete("selection_box", "handle")
        if self.selected_items:
            bbox = self.canvas.bbox(*self.selected_items)
            if bbox:
                x1, y1, x2, y2 = bbox
                self.canvas.create_rectangle(x1, y1, x2, y2, outline="blue", 
                                           width=2, tags="selection_box")
                
                # Resize handles
                handles = [
                    (x1, y1, "top_left"), (x2, y1, "top_right"),
                    (x1, y2, "bottom_left"), (x2, y2, "bottom_right")
                ]
                for hx, hy, pos in handles:
                    self.canvas.create_rectangle(hx-4, hy-4, hx+4, hy+4, 
                                                fill="blue", outline="white",
                                                tags=("handle", pos))
    
    def get_image_name(self, item):
        """Get image name from item tags"""
        return next((t for t in self.canvas.gettags(item) if t.startswith("svg_")), None)
    
    def get_group_id(self, item):
        """Get group ID from item tags"""
        return next((t for t in self.canvas.gettags(item) if t.startswith("group_")), None)
    
    def group_items(self):
        """Group selected items"""
        if len(self.selected_items) > 1:
            group_id = f"group_{len(self.groups)}"
            self.groups[group_id] = self.selected_items[:]
            for item in self.selected_items:
                self.canvas.addtag_withtag(group_id, item)
            self.update_status(f"Grouped {len(self.selected_items)} items")
            self.draw_selection_box()
    
    def ungroup_items(self):
        """Ungroup selected items"""
        if self.selected_items:
            group_id = self.get_group_id(self.selected_items[0])
            if group_id and group_id in self.groups:
                for item in self.groups[group_id]:
                    tags = list(self.canvas.gettags(item))
                    tags.remove(group_id)
                    self.canvas.itemconfig(item, tags=tags)
                del self.groups[group_id]
                self.update_status("Ungrouped items")
                self.draw_selection_box()
    
    def duplicate_selection(self):
        """Duplicate selected items"""
        if not self.selected_items:
            return
        
        new_items = []
        for item in self.selected_items:
            img_name = self.get_image_name(item)
            if img_name and img_name in self.svg_data:
                x, y = self.canvas.coords(item)
                data = self.svg_data[img_name]
                
                new_name = f"svg_{len(self.svg_images)}"
                self.svg_data[new_name] = data
                self.svg_images[new_name] = tksvg.SvgImage(data=data, 
                    scaletowidth=self.svg_images[img_name].width())
                
                new_item = self.canvas.create_image(x+20, y+20, 
                    image=self.svg_images[new_name], anchor="center",
                    tags=(new_name, "svg"))
                new_items.append(new_item)
        
        self.selected_items = new_items
        self.draw_selection_box()
        self.update_status(f"Duplicated {len(new_items)} item(s)")
    
    def delete_selection(self):
        """Delete selected items"""
        if not self.selected_items:
            return
        
        count = len(self.selected_items)
        for item in self.selected_items:
            img_name = self.get_image_name(item)
            self.canvas.delete(item)
            if img_name:
                self.svg_images.pop(img_name, None)
                self.svg_data.pop(img_name, None)
        
        self.selected_items = []
        self.draw_selection_box()
        self.update_status(f"Deleted {count} item(s)")
    
    def select_all(self):
        """Select all SVG items"""
        self.selected_items = list(self.canvas.find_withtag("svg"))
        self.draw_selection_box()
        self.update_status(f"Selected all ({len(self.selected_items)} items)")
    
    def nudge_selection(self, dx, dy):
        """Move selection by small increments"""
        if not self.selected_items:
            return
        for item in self.selected_items:
            x, y = self.canvas.coords(item)
            self.canvas.coords(item, x + dx, y + dy)
        self.draw_selection_box()
    
    def move_forward(self):
        """Bring selected items forward"""
        for item in self.selected_items:
            self.canvas.tag_raise(item)
        self.update_status("Moved forward")
    
    def move_backward(self):
        """Send selected items backward"""
        for item in self.selected_items:
            self.canvas.tag_lower(item)
        self.update_status("Moved backward")
    
    def rotate_selection(self, angle):
        """Rotate selected items"""
        if not self.selected_items:
            return
        
        for item in self.selected_items:
            img_name = self.get_image_name(item)
            if img_name:
                self.apply_transform(img_name, f"rotate({angle})", from_center=True)
        
        self.update_status(f"Rotated {angle}°")
    
    def flip_selection(self, direction):
        """Flip selected items horizontally or vertically"""
        if not self.selected_items:
            return
        
        bbox = self.canvas.bbox(*self.selected_items)
        cx, cy = (bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2
        
        for item in self.selected_items:
            ix, iy = self.canvas.coords(item)
            img_name = self.get_image_name(item)
            
            if img_name and img_name in self.svg_images:
                if direction == 'horizontal':
                    new_x = 2 * cx - ix
                    self.canvas.coords(item, new_x, iy)
                else:
                    new_y = 2 * cy - iy
                    self.canvas.coords(item, ix, new_y)
                
                transform = "scale(-1, 1)" if direction == "horizontal" else "scale(1, -1)"
                self.apply_transform(img_name, transform, from_center=True)
        
        self.draw_selection_box()
        self.update_status(f"Flipped {direction}")
    
    def adjust_opacity(self):
        """Adjust opacity of selected items"""
        if not self.selected_items:
            messagebox.showinfo("Opacity", "Please select items first")
            return
        
        opacity = simpledialog.askfloat(
            "Adjust Opacity",
            "Enter opacity (0.0 to 1.0):",
            minvalue=0.0,
            maxvalue=1.0,
            initialvalue=1.0,
            parent=self.root
        )
        
        if opacity is not None:
            for item in self.selected_items:
                img_name = self.get_image_name(item)
                if img_name and img_name in self.svg_data:
                    tree = etree.parse(io.BytesIO(self.svg_data[img_name]))
                    root = tree.getroot()
                    root.set('opacity', str(opacity))
                    self.update_svg(img_name, tree)
            
            self.update_status(f"Set opacity to {opacity}")
    
    def apply_transform(self, image_name, transform_str, from_center=False):
        """Apply SVG transform to an image"""
        if image_name not in self.svg_data:
            return
        
        tree = etree.parse(io.BytesIO(self.svg_data[image_name]))
        root = tree.getroot()
        
        transform_to_apply = transform_str
        
        if from_center:
            viewbox = root.get('viewBox')
            w = h = 0
            if viewbox:
                _, _, w, h = [float(v) for v in viewbox.split()]
            else:
                w = self.svg_images[image_name].width()
                h = self.svg_images[image_name].height()
            
            cx, cy = w / 2, h / 2
            transform_to_apply = f"translate({cx}, {cy}) {transform_str} translate({-cx}, {-cy})"
        
        g = root.find('{http://www.w3.org/2000/svg}g')
        if g is None or len(list(root)) > 1:
            g = etree.Element("g")
            for child in list(root):
                g.append(child)
            for child in list(root):
                root.remove(child)
            root.append(g)
        
        current_transform = g.get('transform', '')
        g.set('transform', f'{transform_to_apply} {current_transform}')
        
        self.update_svg(image_name, tree)
    
    def update_svg(self, image_name, tree):
        """Update SVG data and refresh display"""
        new_svg_data = etree.tostring(tree)
        self.svg_data[image_name] = new_svg_data
        self.svg_images[image_name].configure(data=new_svg_data)
    
    def undo(self):
        """Undo last operation (placeholder)"""
        messagebox.showinfo("Undo", "Undo feature coming soon!")
    
    def update_status(self, message):
        """Update status bar message"""
        self.status_bar.config(text=message)


if __name__ == "__main__":
    root = tk.Tk()
    app = DrawingCanvas(root)
    root.mainloop()