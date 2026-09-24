import tkinter as tk
import json
from tkinter import colorchooser, filedialog, messagebox

class Application(tk.Frame):
    def __init__(self, master=None):
        super().__init__(master)
        self.master = master
        self.master.title("Cell Shape Creator")
        self.master.geometry("800x600")
        self.pack()

        self.selected_shapes = []
        self.start_x = None
        self.start_y = None
        self.shape_counter = 0
        self.history = []
        self.history_index = -1
        self.groups = {}
        self.initial_bbox = None
        self.is_dragging = False

        self.create_widgets()
        self.save_state()  # Save initial state

    def create_widgets(self):
        # Controls Frame
        controls_frame = tk.Frame(self)
        controls_frame.pack(side="left", padx=10, pady=10, fill="y")

        # Shape Buttons
        oval_button = tk.Button(controls_frame, text="Oval", command=self.create_oval)
        oval_button.pack(pady=5)

        rect_button = tk.Button(controls_frame, text="Rectangle", command=self.create_rectangle)
        rect_button.pack(pady=5)
        
        # Color Picker
        color_button = tk.Button(controls_frame, text="Color", command=self.change_color)
        color_button.pack(pady=5)
        
        # Delete Button
        delete_button = tk.Button(controls_frame, text="Delete", command=self.delete_shape)
        delete_button.pack(pady=5)

        # Undo/Redo Buttons
        undo_button = tk.Button(controls_frame, text="Undo", command=self.undo)
        undo_button.pack(pady=5)
        
        redo_button = tk.Button(controls_frame, text="Redo", command=self.redo)
        redo_button.pack(pady=5)

        # Group/Ungroup Buttons
        group_button = tk.Button(controls_frame, text="Group", command=self.group_shapes)
        group_button.pack(pady=5)

        ungroup_button = tk.Button(controls_frame, text="Ungroup", command=self.ungroup_shapes)
        ungroup_button.pack(pady=5)

        # Flip Buttons
        flip_h_button = tk.Button(controls_frame, text="Flip Horizontal", command=self.flip_horizontal)
        flip_h_button.pack(pady=5)

        flip_v_button = tk.Button(controls_frame, text="Flip Vertical", command=self.flip_vertical)
        flip_v_button.pack(pady=5)

        # Save/Load Buttons
        save_button = tk.Button(controls_frame, text="Save", command=self.save_canvas)
        save_button.pack(pady=5)

        load_button = tk.Button(controls_frame, text="Load", command=self.load_canvas)
        load_button.pack(pady=5)

        # Canvas
        self.canvas = tk.Canvas(self, width=650, height=550, bg="white", relief="solid", bd=1)
        self.canvas.pack(side="left", expand=True, fill="both")

        self.canvas.bind("<Button-1>", self.on_left_click)
        self.canvas.bind("<B1-Motion>", self.on_left_drag)
        self.canvas.bind("<Button-3>", self.on_right_click)
        self.canvas.bind("<B3-Motion>", self.on_right_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        
        # Quit Button
        self.quit = tk.Button(self, text="QUIT", fg="red",
                              command=self.master.destroy)
        self.quit.pack(side="bottom", pady=10)

    def create_oval(self):
        self.save_state()
        tag = f"shape_{self.shape_counter}"
        self.shape_counter += 1
        self.canvas.create_oval(10, 10, 110, 60, fill="blue", outline="black", tags=(tag, "shape"))

    def create_rectangle(self):
        self.save_state()
        tag = f"shape_{self.shape_counter}"
        self.shape_counter += 1
        self.canvas.create_rectangle(10, 10, 110, 60, fill="green", outline="black", tags=(tag, "shape"))
        
    def change_color(self):
        if self.selected_shapes:
            self.save_state()
            color = colorchooser.askcolor(title="Choose color")
            if color[1]:
                for shape in self.selected_shapes:
                    self.canvas.itemconfig(shape, fill=color[1])
                
    def delete_shape(self):
        if self.selected_shapes:
            self.save_state()
            for shape in self.selected_shapes:
                self.canvas.delete(shape)
            self.selected_shapes = []

    def group_shapes(self):
        if len(self.selected_shapes) > 1:
            self.save_state()
            group_tag = f"group_{self.shape_counter}"
            self.shape_counter += 1
            for shape in self.selected_shapes:
                tags = self.canvas.gettags(shape)
                self.canvas.itemconfig(shape, tags=tags + (group_tag,))
            self.groups[group_tag] = self.selected_shapes
            self.selected_shapes = []

    def ungroup_shapes(self):
        if not self.selected_shapes:
            return

        # Find the group tag from the first selected shape
        tags = self.canvas.gettags(self.selected_shapes[0])
        group_tag = None
        for tag in tags:
            if tag.startswith("group_"):
                group_tag = tag
                break
        
        if group_tag and all(group_tag in self.canvas.gettags(s) for s in self.selected_shapes):
            self.save_state()
            group_shapes = self.groups.pop(group_tag)
            for s in group_shapes:
                s_tags = self.canvas.gettags(s)
                new_tags = tuple(t for t in s_tags if t != group_tag)
                self.canvas.itemconfig(s, tags=new_tags)
            self.selected_shapes = []

    def undo(self):
        if self.history_index > 0:
            self.history_index -= 1
            self.restore_state()

    def redo(self):
        if self.history_index < len(self.history) - 1:
            self.history_index += 1
            self.restore_state()

    def _get_canvas_state(self):
        state = {
            "items": [],
            "groups": {}
        }
        for item in self.canvas.find_withtag("shape"):
            state["items"].append({
                "type": self.canvas.type(item),
                "coords": self.canvas.coords(item),
                "options": {k: v[-1] for k, v in self.canvas.itemconfigure(item).items()}
            })
        
        for group_tag, shapes in self.groups.items():
            state["groups"][group_tag] = [self.canvas.gettags(s)[0] for s in shapes]
        return state

    def save_state(self):
        state = self._get_canvas_state()
        if self.history_index < len(self.history) - 1:
            self.history = self.history[:self.history_index + 1]
            
        self.history.append(state)
        self.history_index = len(self.history) - 1

    def restore_state(self):
        self.canvas.delete("all")
        if not self.history or self.history_index < 0:
            return

        state = self.history[self.history_index]
        
        # Create items
        for item_state in state["items"]:
            item_type = item_state["type"]
            coords = item_state["coords"]
            options = {k: v[-1] for k, v in item_state["options"].items()}
            
            if item_type == "rectangle":
                self.canvas.create_rectangle(*coords, **options)
            elif item_type == "oval":
                self.canvas.create_oval(*coords, **options)
        
        # Rebuild groups
        self.groups = {}
        for group_tag, shape_tags in state.get("groups", {}).items():
            shapes = [self.canvas.find_withtag(tag)[0] for tag in shape_tags if self.canvas.find_withtag(tag)]
            self.groups[group_tag] = shapes

    def on_left_click(self, event):
        self.select_shape(event)

    def on_left_drag(self, event):
        self.is_dragging = True
        self.move_shape(event)

    def on_right_click(self, event):
        self.select_shape(event)
        if self.selected_shapes:
            self.initial_bbox = self.canvas.bbox(*self.selected_shapes)
            self.show_resize_handles()

    def on_right_drag(self, event):
        self.is_dragging = True

        self.resize_shape(event)

    def select_shape(self, event):
        items = self.canvas.find_overlapping(event.x, event.y, event.x, event.y)
        
        # Clear previous selection outlines
        for shape in self.selected_shapes:
            self.canvas.itemconfig(shape, outline="black", width=1)
        self.hide_resize_handles()

        if items:
            shape = items[-1]
            tags = self.canvas.gettags(shape)

            is_group = False
            for tag in tags:
                if tag.startswith("group_"):
                    if tag in self.groups:
                        self.selected_shapes = self.groups[tag]
                        is_group = True
                        break
            
            if not is_group:
                if event.state & 0x0001:  # Shift key pressed
                    if shape in self.selected_shapes:
                        self.selected_shapes.remove(shape)
                    else:
                        self.selected_shapes.append(shape)
                else:
                    self.selected_shapes = [shape]
        else:
            self.selected_shapes = []

        # Outline selected shapes
        for shape in self.selected_shapes:
            self.canvas.itemconfig(shape, outline="red", width=2)
            self.canvas.tag_raise(shape)
            
        self.start_x = event.x
        self.start_y = event.y

    def move_shape(self, event):
        if self.selected_shapes:
            dx = event.x - self.start_x
            dy = event.y - self.start_y
            for shape in self.selected_shapes:
                self.canvas.move(shape, dx, dy)
            self.start_x = event.x
            self.start_y = event.y

    def show_resize_handles(self):
        self.hide_resize_handles()
        if not self.selected_shapes:
            return
            
        x1, y1, x2, y2 = self.canvas.bbox(*self.selected_shapes)
        self.canvas.create_rectangle(x1-2, y1-2, x1+2, y1+2, fill="red", tags=("handle", "handle-nw"))
        self.canvas.create_rectangle(x2-2, y1-2, x2+2, y1+2, fill="red", tags=("handle", "handle-ne"))
        self.canvas.create_rectangle(x1-2, y2-2, x1+2, y2+2, fill="red", tags=("handle", "handle-sw"))
        self.canvas.create_rectangle(x2-2, y2-2, x2+2, y2+2, fill="red", tags=("handle", "handle-se"))

    def hide_resize_handles(self):
        self.canvas.delete("handle")

    def resize_shape(self, event):
        if self.selected_shapes and self.initial_bbox:
            x1, y1, x2, y2 = self.initial_bbox
            
            # Determine which handle is being dragged
            handle = self.canvas.find_withtag("current")
            if not handle:
                return
            
            tags = self.canvas.gettags(handle[0])
            handle_tag = None
            for tag in tags:
                if tag.startswith("handle-"):
                    handle_tag = tag
                    break
            
            if not handle_tag:
                return

            # Restore original size before scaling
            current_bbox = self.canvas.bbox(*self.selected_shapes)
            if current_bbox:
                cx1, cy1, cx2, cy2 = current_bbox
                if (cx2 - cx1) == 0 or (cy2 - cy1) == 0:
                    return
                scale_x_inv = (x2 - x1) / (cx2 - cx1)
                scale_y_inv = (y2 - y1) / (cy2 - cy1)
                for shape in self.selected_shapes:
                    self.canvas.scale(shape, (cx1+cx2)/2, (cy1+cy2)/2, scale_x_inv, scale_y_inv)
            
            scale_x, scale_y = 1, 1
            if handle_tag == "handle-nw":
                scale_x = (x2 - event.x) / (x2 - x1) if (x2-x1) != 0 else 1
                scale_y = (y2 - event.y) / (y2 - y1) if (y2-y1) != 0 else 1
                for shape in self.selected_shapes:
                    self.canvas.scale(shape, x2, y2, scale_x, scale_y)
            elif handle_tag == "handle-ne":
                scale_x = (event.x - x1) / (x2 - x1) if (x2-x1) != 0 else 1
                scale_y = (y2 - event.y) / (y2 - y1) if (y2-y1) != 0 else 1
                for shape in self.selected_shapes:
                    self.canvas.scale(shape, x1, y2, scale_x, scale_y)
            elif handle_tag == "handle-sw":
                scale_x = (x2 - event.x) / (x2 - x1) if (x2-x1) != 0 else 1
                scale_y = (event.y - y1) / (y2 - y1) if (y2-y1) != 0 else 1
                for shape in self.selected_shapes:
                    self.canvas.scale(shape, x2, y1, scale_x, scale_y)
            elif handle_tag == "handle-se":
                scale_x = (event.x - x1) / (x2 - x1) if (x2-x1) != 0 else 1
                scale_y = (event.y - y1) / (y2 - y1) if (y2-y1) != 0 else 1
                for shape in self.selected_shapes:
                    self.canvas.scale(shape, x1, y1, scale_x, scale_y)

            self.show_resize_handles()
            
    def on_release(self, event):
        if self.is_dragging:
            self.save_state()
            self.is_dragging = False
        self.initial_bbox = None

    def flip_horizontal(self):
        if self.selected_shapes:
            self.save_state()
            cx = sum(self.canvas.bbox(*self.selected_shapes)[::2]) / 2
            for shape in self.selected_shapes:
                self.canvas.scale(shape, cx, 0, -1, 1)

    def flip_vertical(self):
        if self.selected_shapes:
            self.save_state()
            cy = sum(self.canvas.bbox(*self.selected_shapes)[1::2]) / 2
            for shape in self.selected_shapes:
                self.canvas.scale(shape, 0, cy, 1, -1)

    def save_canvas(self):
        file_path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON files", "*.json")])
        if not file_path:
            return

        state = self._get_canvas_state()
        
        with open(file_path, "w") as f:
            json.dump(state, f)

    def load_canvas(self):
        file_path = filedialog.askopenfilename(filetypes=[("JSON files", "*.json")])
        if not file_path:
            return

        try:
            with open(file_path, "r") as f:
                state = json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            messagebox.showerror("Error", "Failed to load file. Make sure it's a valid JSON file.")
            return

        self.canvas.delete("all")
        
        # Create items
        for item_state in state.get("items", []):
            item_type = item_state.get("type")
            coords = item_state.get("coords")
            options = item_state.get("options", {})
            
            if item_type == "rectangle":
                self.canvas.create_rectangle(*coords, **options)
            elif item_type == "oval":
                self.canvas.create_oval(*coords, **options)
        
        # Rebuild groups
        self.groups = {}
        for group_tag, shape_tags in state.get("groups", {}).items():
            shapes = [self.canvas.find_withtag(tag)[0] for tag in shape_tags if self.canvas.find_withtag(tag)]
            self.groups[group_tag] = shapes
        
        self.save_state()

root = tk.Tk()
app = Application(master=root)
app.mainloop()
