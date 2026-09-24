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
        self.canvas = tk.Canvas(self, bg="white", width=800, height=500)
        self.canvas.pack(side="top", fill="both", expand=True)

        self.toolbar = tk.Frame(self)
        self.toolbar.pack(side="bottom", fill="x")

        self.rect_button = tk.Button(self.toolbar, text="Rectangle", command=self.set_rectangle_mode)
        self.rect_button.pack(side="left")

        self.oval_button = tk.Button(self.toolbar, text="Oval", command=self.set_oval_mode)
        self.oval_button.pack(side="left")

        self.color_button = tk.Button(self.toolbar, text="Set Color", command=self.choose_color)
        self.color_button.pack(side="left")

        self.save_button = tk.Button(self.toolbar, text="Save", command=self.save_shapes)
        self.save_button.pack(side="left")

        self.load_button = tk.Button(self.toolbar, text="Load", command=self.load_shapes)
        self.load_button.pack(side="left")

        self.undo_button = tk.Button(self.toolbar, text="Undo", command=self.undo)
        self.undo_button.pack(side="left")

        self.redo_button = tk.Button(self.toolbar, text="Redo", command=self.redo)
        self.redo_button.pack(side="left")

        self.group_button = tk.Button(self.toolbar, text="Group", command=self.group_shapes)
        self.group_button.pack(side="left")

        self.ungroup_button = tk.Button(self.toolbar, text="Ungroup", command=self.ungroup_shapes)
        self.ungroup_button.pack(side="left")

        self.canvas.bind("<Button-1>", self.on_canvas_click)
        self.canvas.bind("<B1-Motion>", self.on_canvas_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_canvas_release)

        #self.current_shape_type = "rectangle"
        self.current_color = "#000000"

root = tk.Tk()
app = Application(master=root)
app.mainloop()
