import tkinter as tk
from tkinter import filedialog
from PIL import Image, ImageTk
import numpy as np
import math
import os
import json
import psutil
import threading
from collections import OrderedDict
from time import perf_counter
Image.MAX_IMAGE_PIXELS = 346724322
class Application(tk.Frame):
    # Keycodes for rotation
    BUTTON_MODIFIER_CTRL = 1
    BUTTON_MODIFIER_CTRL_LEFT_CLICK = 257
    BUTTON_MODIFIER_RIGHT_CLICK = 1024

    QUALITY = {
            "Nearest": Image.Resampling.NEAREST,
            "Bilinear": Image.Resampling.BILINEAR,
            "Bicubic": Image.Resampling.BICUBIC
        }

    def __init__(self, master=None, 
                 geometry: str=None, lastdir: str=None, 
                 zoom_amount: float=None, rotation_amount: int=None, 
                 auto_fit_var: bool=None, unbound_var: bool=None, 
                 disable_menubar: bool=None, statusbar: bool=None, 
                 initial_filter: Image.Resampling=None, pan_quality: Image.Resampling=None, 
                 quick_zoom: bool=None, quick_pan: bool=None, 
                 filter_delay: int=None, show_advanced: bool=None, 
                 show_ram: bool=None, debounce_delay: int=None, 
                 canvas_color=None, text_color=None, 
                 button_color=None, active_button_color=None, 
                 statusbar_color=None, load_prefs=True):

        """An image viewer contained in a tk.frame. Can be bound to a parent with "master=" 
        Settings are loaded from viewer_prefs.json"""
        self.start = perf_counter()
        savedata = {}
        
        self.load_prefs = load_prefs
        if load_prefs:
            self.save_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "viewer_prefs.json")
            savedata = self.load_json()
        self.savedata = savedata
        window_size = geometry or savedata.get("geometry", None)
        self.lastdir = lastdir or savedata.get("lastdir", None)

        self.own_master = False
        if master == None:
            window_size = window_size or "800x600"
            root = tk.Tk() # Create the MAIN tk window instance.
            root.geometry(window_size)
            master = root
            self.master = master
            self.own_master = True
        else:
            self.master = master
            self.master.update()
            window_size = window_size or f"{self.master.winfo_width()}x{self.master.winfo_height()}"
            self.own_master = False

        super().__init__(master)
        
        self.zoom_amount = zoom_amount or float(savedata.get("zoom_amount", 1.25))
        self.rotation_amount = rotation_amount or int(savedata.get("rotation_amount", -5))

        self.auto_fit_var = tk.BooleanVar(value=auto_fit_var or savedata.get("auto_fit_on_resize", True))
        self.unbound_var = tk.BooleanVar(value=unbound_var or savedata.get("unbound_pan", False))

        self.disable_menubar = disable_menubar or savedata.get("disable_menubar", False)
        self.statusbar = statusbar or tk.BooleanVar(value=savedata.get("statusbar", True))
        self.statusbar.trace_add("write", lambda *_: self.toggle_statusbar())

        self.filter = initial_filter or Application.QUALITY.get(savedata.get("filter", "Nearest").lower().capitalize())
        self.pan_quality = pan_quality or Application.QUALITY.get(savedata.get("pan_quality", "Nearest").lower().capitalize()) # Buffer image initially at self.pan_quality, After self.filter_delay, render at self.filter.
        self.quick_zoom = tk.BooleanVar(value=quick_zoom or savedata.get("quick_zoom", True))
        self.quick_pan = tk.BooleanVar(value=quick_pan or savedata.get("quick_pan", True))
        self.filter_delay = tk.IntVar(value=filter_delay or int(savedata.get("final_filter_delay", 200)))
        self.show_advanced = tk.BooleanVar(value=show_advanced or savedata.get("show_advanced", False))
        self.show_advanced.trace_add("write", lambda *_: self.toggle_advanced())
        self.show_ram = tk.BooleanVar(value=show_ram or savedata.get("show_ram", False))
        self.show_ram.trace_add("write", lambda *_: self.toggle_ram_indicator())
    
        # Will improve performance if images lag when panning or zooming.
        self.debounce_delay = tk.IntVar(value=debounce_delay or int(savedata.get("debounce_delay", 28))) # Default set to 0, disabled. Mainly used with Bicubic, suggested value 25.
        
        self.colors = {}
        self.colors["canvas_color"] = canvas_color
        self.colors["text_color"] = text_color
        self.colors["button_color"] = button_color
        self.colors["active_button_color"] = active_button_color
        self.colors["statusbar_color"] = statusbar_color

        self.colors = savedata.get("colors") or {
            "canvas": "#303276", #141433
            "statusbar": "#202041",
            "button": "#24255C",
            "active_button": "#303276",
            "text": "#FFFFFF"
        }

        #white
        """{
        "canvas": "#000000",
        "statusbar": "#f0f0f0",
        "button": "#f0f0f0",
        "active_button": "#f0f0f0",
        "text": "#000000"
        }"""

        self.master = master
        if load_prefs:
            self.master.geometry(window_size)

        self.my_title = "Python Image Viewer"
        self.master.title(self.my_title)
        if self.own_master:
            self.master.protocol("WM_DELETE_WINDOW", self.window_close)
        
        self.pil_image = None
        self.imageid = None
        self._last_draw_time = 0.0
        self._pending_draw = False
        self.debounce_id = None
        self.image_id = None
        self.save = None
        self.save1 = None
        self.save2 = None
        self.memory_after_id = None
        self._secondary_after_id = None
        self.gif_after_id = None
        self._render_cache = OrderedDict()
        self._cache_max_size = 64
        self.__old = None
        self.frames = []
        self.open_thread = None
        self._stop_thread = threading.Event()
        self.use_cache = False

        self.debug = False
        self.list1 = []

        self.reset_transform()
        self.create_widgets()

    def _schedule_draw(self, low_quality=False, zoom=False):
        """
        Debounce + throttle: ensures _draw() runs at most once every
        DEBOUNCE_DELAY milliseconds, and coalesces multiple requests
        into a single pending call.
        """
        now = perf_counter() * 1000  # ms
        elapsed = now - self._last_draw_time

        # Cancel any previously scheduled call
        if self.debounce_id:
            self.after_cancel(self.debounce_id)
            self.debounce_id = None

        if zoom == False or elapsed >= self.debounce_delay.get():
            # Enough time has passed → draw immediately
            self._execute_draw(low_quality, zoom)

        else:
            # Too soon → schedule one draw at (DEBOUNCE_DELAY - elapsed)
            delay = int(self.debounce_delay.get() - elapsed)
            self.debounce_id = self.after(delay, 
                lambda: self._execute_draw(low_quality, zoom))

    def _execute_draw(self, low_quality=False, zoom=False):
        """
        Actual draw invocation; updates timestamp and clears pending flag.
        """
        self.debounce_id = None
        self._last_draw_time = perf_counter() * 1000
        self._draw(low_quality, zoom)
        
    def _draw(self, low_quality=False, zoom=False):
        """
        This is the single “real” draw entry point.
        The scheduler (_execute_draw) will call this.
        """
        if not self.pil_image:
            return
        # call your existing draw routine

        self.draw_image(self.pil_image, low_quality)
        if zoom and self.quick_zoom.get() and self.selected_option.get() != "Nearest":
            if self.save:
                self.after_cancel(self.save)
            if self.pil_image:
                self.save = self.after(self.filter_delay.get(), lambda: self.after_idle(lambda: self.draw_image(self.pil_image, low_quality=False)))
    # Window
    def window_resize(self, event):
        if event.widget is self.canvas and self.pil_image:
            self.zoom_fit(self.pil_image.width, self.pil_image.height)
            self._schedule_draw(low_quality=True)
            if self.save1:
                self.after_cancel(self.save1)
            self.save1 = self.after(self.filter_delay.get(), lambda: self.after_idle(lambda: self._schedule_draw(low_quality=False)))

    def retrieve_settings(self):
        settings = {
                    "geometry": self.master.winfo_geometry(),       # "600x800+100+100" Width x Height + x + y
                    "disable_menubar": self.disable_menubar,        # Disable the menu bar
                    "statusbar": self.statusbar.get(),     # Disable the statusbar
                    "lastdir": self.lastdir or None,                # Last folder viewed
                    "auto_fit_on_resize": self.auto_fit_var.get(),  # Refit to window when resizing
                    "unbound_pan": self.unbound_var.get(),          # Go out of bounds
                    "rotation_amount": self.rotation_amount,        # Rotation amount
                    "zoom_amount": self.zoom_amount,                # Zoom amount
                    "filter": self.filter.name,                         # Default filter
                    "pan_quality": self.pan_quality.name,              # 
                    "quick_zoom": self.quick_zoom.get(),
                    "final_filter_delay": self.filter_delay.get(),
                    "quick_pan": self.quick_pan.get(),
                    "debounce_delay": self.debounce_delay.get(),
                    "show_advanced": self.show_advanced.get(),
                    "show_ram": self.show_ram.get(),
                    "colors": self.colors
                    }
        return settings

    def window_close(self):
        if self.load_prefs:
            self.save_json()
        if self.debounce_id:
            self.after_cancel(self.debounce_id)
        if self.save:
            self.after_cancel(self.save)
        if self.save1:
            self.after_cancel(self.save1)
        if self.save2:
            self.after_cancel(self.save2)
        # Also cancel the memory‐usage loop
        if self.memory_after_id:
            self.after_cancel(self.memory_after_id)
        if self.gif_after_id:
            self.after_cancel(self.gif_after_id)

        try:
            self.pil_image.close()
        except:
            pass
        finally:
            self.pil_image = None
        try:
            self.image.close()
        except:
            pass
        finally:
            self.image = None

        self.canvas = None
        self.image_id = None
        self.frames.clear()
        self._render_cache.clear()
        self.frames = None
        self._render_cache.clear()
        

        self.destroy()
        if self.own_master:
            self.master.destroy()

    # UI
    def create_widgets(self):
        self.create_menu()
        self.create_status_bar()
        self.create_canvas()
        self.bind_mouse_events()

    # Menu
    def create_menu(self):
        menu_bar = tk.Menu(self.master)

        # File menu
        file_menu = tk.Menu(menu_bar, tearoff=tk.OFF)
        menu_bar.add_cascade(label="File", menu=file_menu)

        file_menu.add_command(label="Open", command=self.menu_open_clicked, accelerator="Ctrl+O")
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.menu_quit_clicked)

        # View menu
        view_menu = tk.Menu(menu_bar, tearoff=tk.OFF)
        menu_bar.add_cascade(label="View", menu=view_menu)

        self.auto_fit_var = self.auto_fit_var
        view_menu.add_checkbutton(
            label="Auto Fit on Resize",
            variable=self.auto_fit_var)

        self.unbound_var = self.unbound_var
        view_menu.add_checkbutton(
            label="Unbound Pan",
            variable=self.unbound_var)
        
        view_menu.add_separator()

        view_menu.add_checkbutton(
            label="Quick Zoom",
            variable=self.quick_zoom)
        
        view_menu.add_checkbutton(
            label="Quick Pan",
            variable=self.quick_pan)
        
        view_menu.add_checkbutton(
            label="Show Advanced",
            variable=self.show_advanced)
        
        view_menu.add_separator()

        view_menu.add_checkbutton(
            label="Statusbar",
            variable=self.statusbar)
        
        view_menu.add_checkbutton(
            label="Show RAM",
            variable=self.show_ram)
        
        
        
        view_menu.add_separator()

        view_menu.add_command(label="Hints", command=self.hints)
        

        self.master.bind_all("<Control-o>", self.menu_open_clicked)

        if not self.disable_menubar:
            self.master.config(menu=menu_bar)

    def hints(self):
        
        height = 300
        width = int(height * 1.85)
        new = tk.Toplevel(self.master, width=width, height=height, bg=self.colors["canvas"])
        new.geometry(f"{width}x{height}+{int(self.master.winfo_width()/2-width/2)}+{int(self.master.winfo_height()/2-height/2)}")
        new.grid_rowconfigure(0, weight=1)  # Allow row to expand
        new.grid_columnconfigure(0, weight=1)  # Allow column to expand
        text = """Small guide:
        
Double-click: "Center & Resize."
Shift or Right-click + Mouse-wheel: "Rotate."
Quick Zoom: Renders canvas with quick filter while zooming.
Quick Pan: Renders canvas with quick filter while panning.

Show Advanced:
Quick filter: The quality of the render while panning and zooming.
Second filter in: How soon the final quality is rendered after panning and zooming stop.
Debounce: How often zoom inputs are received. Helps keep zooming smooth.
            """
        # Create a Label with wraplength
        self.label = tk.Label(
            new,
            text=text,
            justify='left',
            anchor='nw', wraplength=height, bg=self.colors["canvas"], fg=self.colors["text"]
        )
        self.label.pack(fill='both', expand=False, padx=10, pady=10)
        new.bind('<Configure>', self.on_resize)
    def on_resize(self, e):
            new_width = max(e.width - 20, 20)
            self.label.config(wraplength=new_width)

    def menu_open_clicked(self, event=None):
        filename = filedialog.askopenfilename(
            filetypes=[("Image files", "*.png *.jpg *.jpeg *.bmp *.pcx *.tiff *.psd *.jfif *.gif *.webp *.webm *.mp4")],
            initialdir=self.lastdir or os.getcwd()
        )
        self.lastdir = os.path.dirname(filename)
        self.set_image(filename)

    def menu_quit_clicked(self):
        self.window_close()

    # Statusbar
    def create_status_bar(self):
        frame_statusbar = tk.Frame(self.master, bd=1, relief=tk.SUNKEN, background=self.colors["statusbar"])
        self.frame_statusbar = frame_statusbar

        self.label_image_info = tk.Label(
            frame_statusbar, text="image info", anchor=tk.E, padx=5,
            background=self.colors["statusbar"], foreground=self.colors["text"]
        )
        self.label_image_pixel = tk.Label(
            frame_statusbar, text="(x, y)", anchor=tk.W, padx=5,
            background=self.colors["statusbar"], foreground=self.colors["text"]
        )
        self.ram_indicator = tk.Label(
            frame_statusbar, text="RAM:", anchor=tk.W, padx=5,
            background=self.colors["statusbar"], foreground=self.colors["text"]
        )
        
        options = ["Nearest", "Bilinear", "Bicubic"]
        self.selected_option = tk.StringVar(value=self.savedata.get("filter", "Nearest").lower().capitalize())
        self.selected_option.trace_add("write", lambda *_: (self.change_filter(), self._schedule_draw(low_quality=False)))

        self.image_quality = tk.OptionMenu(frame_statusbar, self.selected_option, *options)
        self.image_quality.configure(
            background=self.colors["statusbar"],
            activebackground=self.colors["active_button"],
            foreground=self.colors["text"],
            activeforeground=self.colors["text"],
            highlightthickness=0,
            relief="flat",
            font=('Arial', 8),
            padx=5, pady=0
        )

        # Advanced
        self.delay_input_label = tk.Label(frame_statusbar, text="Debounce:", anchor=tk.W, padx=5, background=self.colors["statusbar"], foreground=self.colors["text"])
        self.delay_input = tk.Entry(frame_statusbar, textvariable=self.debounce_delay, width=5, font=('Arial', 8), justify=tk.CENTER)

        self.filter_delay_input_label = tk.Label(frame_statusbar, text="Second filter in:", anchor=tk.W, padx=5, background=self.colors["statusbar"], foreground=self.colors["text"])
        self.filter_delay_input = tk.Entry(frame_statusbar, textvariable=self.filter_delay, width=5, font=('Arial', 8), justify=tk.CENTER)

        self.pan_quality_label = tk.Label(frame_statusbar, text="Quick filter", anchor=tk.W, padx=5, background=self.colors["statusbar"], foreground=self.colors["text"])
        self.selected_option1 = tk.StringVar(value=self.pan_quality.name.lower().capitalize())
        self.selected_option1.trace_add("write", lambda *_: self.change_pan_quality())
        self.pan_quality_button = tk.OptionMenu(frame_statusbar, self.selected_option1, *options)
        self.pan_quality_button.configure(
            background=self.colors["statusbar"],
            activebackground=self.colors["active_button"],
            foreground=self.colors["text"],
            activeforeground=self.colors["text"],
            highlightthickness=0,
            relief="flat",
            font=('Arial', 8),
            padx=5, pady=0
        )

        self.label_image_info.pack(side=tk.RIGHT)
        self.image_quality.pack(side=tk.RIGHT, pady=0)
        self.label_image_pixel.pack(side=tk.LEFT)
        if self.show_ram.get():
            self.ram_indicator.pack(side=tk.LEFT)
        if self.show_advanced.get():
            self.delay_input.pack(side=tk.RIGHT, padx=5, pady=0)
            self.delay_input_label.pack(side=tk.RIGHT, padx=5, pady=0)
            self.filter_delay_input.pack(side=tk.RIGHT, padx=5, pady=0)
            self.filter_delay_input_label.pack(side=tk.RIGHT, padx=5, pady=0)
            self.pan_quality_button.pack(side=tk.RIGHT, padx=5, pady=0)
            self.pan_quality_label.pack(side=tk.RIGHT, padx=5, pady=0)
        

        if self.statusbar.get():
            frame_statusbar.pack(side=tk.BOTTOM, fill=tk.X)

        self.get_memory_usage()
    
    def toggle_statusbar(self):
        if not self.statusbar.get():
            self.frame_statusbar.pack_forget()
            self.divider.pack_forget()
        else:
            self.divider.pack(expand=False, fill=tk.X)
            self.frame_statusbar.pack(expand=False, fill=tk.X)
    
    def toggle_advanced(self):
        if self.show_advanced.get():
            self.delay_input.pack(side=tk.RIGHT, padx=5, pady=0)
            self.delay_input_label.pack(side=tk.RIGHT, padx=5, pady=0)
            self.filter_delay_input.pack(side=tk.RIGHT, padx=5, pady=0)
            self.filter_delay_input_label.pack(side=tk.RIGHT, padx=5, pady=0)
            self.pan_quality_button.pack(side=tk.RIGHT, padx=5, pady=0)
            self.pan_quality_label.pack(side=tk.RIGHT, padx=5, pady=0)

        else:
            self.delay_input.pack_forget()
            self.delay_input_label.pack_forget()
            self.filter_delay_input.pack_forget()
            self.filter_delay_input_label.pack_forget()
            self.pan_quality_button.pack_forget()
            self.pan_quality_label.pack_forget()
    
    def toggle_ram_indicator(self):
        if self.show_ram.get():
            self.ram_indicator.pack(side=tk.LEFT)
        else:
            self.ram_indicator.pack_forget()

    def change_filter(self):
        self.filter = Application.QUALITY[self.selected_option.get()]
    
    def change_pan_quality(self):
        self.pan_quality = Application.QUALITY[self.selected_option1.get()]

    def get_memory_usage(self):
        # Get the current process
        process = psutil.Process()

        # Get memory info
        memory_info = process.memory_info()

        # Return the RSS (Resident Set Size) in byte
        self.ram_indicator.config(text=f"RAM: {memory_info.rss / (1024 ** 2):.2f} MB")
        self.memory_after_id = self.after(500, self.get_memory_usage)

    # Canvas
    def create_canvas(self):
        self.canvas = tk.Canvas(self.master, background=self.colors["canvas"], highlightthickness=0)
        self.canvas.pack(expand=True, fill=tk.BOTH)
        self.divider = tk.Frame(self.master, bg=self.colors["button"], height=2)
        if self.statusbar.get():
            self.divider.pack(fill=tk.X)
        self.canvas.update()
        self.canvas.bind("<Configure>", self.window_resize)

    def bind_mouse_events(self):
        root = self.master
        root.bind("<Button-1>", self.mouse_down_left)
        root.bind("<B1-Motion>", self.mouse_move_left)
        root.bind("<ButtonRelease-1>", self._on_pan_end)
        root.bind("<Motion>", self.mouse_move)
        self.canvas.bind("<Double-Button-1>", self.mouse_double_click_left)
        root.bind("<MouseWheel>", self.mouse_wheel)

    # Mouse events
    def mouse_down_left(self, event):
        self.__old = event

    def _on_pan_end(self, e):
        self.dragging = False
        # Cancel any pending low-quality draw

        # Perform immediate full-quality draw
        #if self.debounce_id:
        #    self.after_cancel(self.debounce_id)
        #    self.debounce_id = None
       # self.after_idle(lambda: self.draw_image(self.pil_image, low_quality=False))
          
    def mouse_move_left(self, event):
        if not self.pil_image or not self.__old:
            return

        dx, dy = event.x - self.__old.x, event.y - self.__old.y
        self.translate(dx, dy)

        # Restrict panning to prevent the image from moving outside the canvas bounds
        if not self.unbound_var.get():
            self.restrict_pan()
        
        self.start = perf_counter()
        self._schedule_draw(low_quality=self.quick_pan.get())
        if self.quick_pan.get():
            if self.save2:
                self.after_cancel(self.save2)
            self.save2 = self.after(self.filter_delay.get(), lambda: self.after_idle(lambda: self._schedule_draw(low_quality=False)))
        self.__old = event

    def restrict_pan(self):
        cw, ch = self.canvas.winfo_width(), self.canvas.winfo_height()
        iw, ih = self.pil_image.width, self.pil_image.height

        # Compute transformed image size
        tw = iw * self.mat_affine[0, 0]
        th = ih * self.mat_affine[1, 1]

        # Current translation
        tx = self.mat_affine[0, 2]
        ty = self.mat_affine[1, 2]

        # Compute allowed range for tx
        if tw <= cw:
            tx_min, tx_max = 0, cw - tw
        else:
            tx_min, tx_max = cw - tw, 0
        tx = min(max(tx, tx_min), tx_max)

        # Compute allowed range for ty
        if th <= ch:
            ty_min, ty_max = 0, ch - th
        else:
            ty_min, ty_max = ch - th, 0
        ty = min(max(ty, ty_min), ty_max)

        # Update the matrix
        self.mat_affine[0, 2] = tx
        self.mat_affine[1, 2] = ty

    def mouse_move(self, event):
        if not self.pil_image:
            return
        pt = self.to_image_point(event.x, event.y)
        self.label_image_pixel.config(
            text=f"({pt[0]:.2f}, {pt[1]:.2f})" if pt else "(--, --)"
        )

    def mouse_double_click_left(self, event):
        if self.pil_image:
            self.zoom_fit(self.pil_image.width, self.pil_image.height)
            self._schedule_draw(low_quality=False)

    def _center_if_smaller(self):
        """If the scaled image fits entirely in the canvas, center it."""
        cw, ch = self.canvas.winfo_width(), self.canvas.winfo_height()
        iw, ih = self.pil_image.width, self.pil_image.height
        # assume uniform scale in mat_affine[0,0]
        s = self.mat_affine[0, 0]
        tw, th = iw * s, ih * s

        if tw <= cw and th <= ch:
            tx = (cw - tw) / 2
            ty = (ch - th) / 2
            self.mat_affine[0, 2] = tx
            self.mat_affine[1, 2] = ty

    def mouse_wheel(self, event):
        if not self.pil_image:
            return

        # Canvas & image sizes
        cw, ch = self.canvas.winfo_width(), self.canvas.winfo_height()
        iw, ih = self.pil_image.width, self.pil_image.height

        # Current uniform scale
        s_current = self.mat_affine[0, 0]

        # Rotate if modifier held
        if event.state in (
            Application.BUTTON_MODIFIER_CTRL,
            Application.BUTTON_MODIFIER_CTRL_LEFT_CLICK,
            Application.BUTTON_MODIFIER_RIGHT_CLICK
        ):
            self.rotate_at(
                self.rotation_amount if event.delta > 0 else -self.rotation_amount,
                event.x, event.y
            )
        else:
            # Desired zoom factor
            factor = self.zoom_amount if event.delta > 0 else (1 / self.zoom_amount)

            if not self.unbound_var.get():
                # Compute the “fit” scale (aspect-ratio fit inside canvas)
                s_fit = min(cw / iw, ch / ih)

                # When zooming out, don’t go below s_fit
                if factor < 1.0:
                    factor = max(factor, s_fit / s_current)

            # Apply the zoom around the cursor
            self.scale_at(factor, event.x, event.y)

            if not self.unbound_var.get():
                # New scale after zoom
                s_new = s_current * factor

                if s_new <= s_fit:
                    # Snap to exact center when at or below fit
                    tx = (cw - iw * s_new) / 2
                    ty = (ch - ih * s_new) / 2
                    self.mat_affine[0, 2] = tx
                    self.mat_affine[1, 2] = ty
                else:
                    # Otherwise clamp panning to edges
                    self.restrict_pan()

        # Redraw with the updated transform
        self._schedule_draw(low_quality=self.quick_zoom.get(), zoom=self.quick_zoom.get())

    # Affine transforms
    def reset_transform(self):
        self.mat_affine = np.eye(3)

    def translate(self, ox, oy):
        m = np.eye(3)
        m[0, 2], m[1, 2] = ox, oy
        self.mat_affine = m @ self.mat_affine

    def scale(self, s):
        m = np.eye(3)
        m[0, 0], m[1, 1] = s, s
        self.mat_affine = m @ self.mat_affine

    def scale_at(self, s, cx, cy):
        self.translate(-cx, -cy)
        self.scale(s)
        self.translate(cx, cy)

    def rotate(self, deg):
        a = math.radians(deg)
        cos_a, sin_a = math.cos(a), math.sin(a)
        m = np.array([
            [cos_a, -sin_a, 0],
            [sin_a, cos_a, 0],
            [0, 0, 1]
        ])
        self.mat_affine = m @ self.mat_affine

    def rotate_at(self, deg, cx, cy):
        self.translate(-cx, -cy)
        self.rotate(deg)
        self.translate(cx, cy)

    def zoom_fit(self, iw, ih):
        if not self.auto_fit_var.get():
            return
        cw, ch = self.canvas.winfo_width(), self.canvas.winfo_height()
        if iw <= 0 or ih <= 0 or cw <= 0 or ch <= 0:
            return
        self.reset_transform()
        s = min(cw / iw, ch / ih)
        ox, oy = (cw - iw * s) / 2, (ch - ih * s) / 2
        self.scale(s)
        self.translate(ox, oy)

    def to_image_point(self, x, y):
        try:
            inv = np.linalg.inv(self.mat_affine)
            px, py, _ = inv @ [x, y, 1.]
            if 0 <= px < self.pil_image.width and 0 <= py < self.pil_image.height:
                return px, py
        except Exception:
            pass
        return []

    # Image Display
    def set_image(self, filename):
        " Give image path and display it "
        if not filename:
            return
        
        if self._secondary_after_id:
            self.after_cancel(self._secondary_after_id)
            self._secondary_after_id = None
        if self.gif_after_id:
            self.after_cancel(self.gif_after_id)
            self.gif_after_id = None

        # Static image path
        if self.open_thread and self.open_thread.is_alive():
            self._stop_thread.set()
            self.open_thread.join()
            self.open_thread = None

        self._stop_thread.clear()
        self.frames.clear()
        self._render_cache.clear()
        self.use_cache = False
        
        self.canvas.delete("_IMG")

        if getattr(self, "pil_image", None):
            try:
                self.pil_image.close()
            except Exception:
                pass
        self.pil_image = None
        self.image = None
        self.image_id = None
        
        

        self.pil_image = Image.open(filename)
        self.pil_image.seek(0)

        if self.pil_image.n_frames:
            framecount = self.pil_image.n_frames
            if framecount >= 1:
                self.open_thread = threading.Thread(target=self._preload_frames, args=(filename,), daemon=True)
                self.open_thread.start()
                self.secondary(self.frames)
                self.use_cache = True
                print("Using cache")

        if self.pil_image.mode not in ("RGB", "RGBA"):
            self.pil_image = self.pil_image.convert("RGBA")

        self.image_id = None
        self.canvas.delete("_IMG")
        self.bg_color = tuple(int(self.colors["canvas"][i:i+2], 16) for i in (1, 3, 5)) + (0,)

        self.zoom_fit(self.pil_image.width, self.pil_image.height)
        self._schedule_draw(low_quality=False)
        self.master.title(f"{self.my_title} - {os.path.basename(filename)}")
        self.label_image_info.config(
            text=f"{self.pil_image.format} : {self.pil_image.width} x {self.pil_image.height} {self.pil_image.mode}"
        )
        os.chdir(os.path.dirname(filename))


    def _preload_frames(self, img):
        try:
            with Image.open(img, "r") as img:
                for i in range(img.n_frames):
                    if self._stop_thread.is_set():
                        break
                    img.seek(i)
                    duration = img.info.get('duration', 100) or 100
                    frame = img.copy().convert("RGBA")
                    self.frames.append((frame, duration))
        except Exception as e:
            print(e)
        finally:
            self._stop_thread.clear()
        
    def secondary(self, frames, lazy_index=None):
        if not frames:
            self._secondary_after_id = self.after(16, lambda: self.secondary(frames, lazy_index))
            return
        if lazy_index == None:
            lazy_index = 0
            self.zoom_fit(frames[lazy_index][0].width, frames[lazy_index][0].height)
            

        self.pil_image, gif_duration = frames[lazy_index] # Updates reference (for panning/zooming)
        self.after(0, self.draw_image(self.pil_image))
        
        self.gif_after_id = self.after(gif_duration, lambda: self.secondary(frames, lazy_index))
        lazy_index = (lazy_index + 1) % len(frames)

    def draw_image(self, pil_image, low_quality=False):
        
        cw, ch = self.canvas.winfo_width(), self.canvas.winfo_height()
        if cw <= 1 or ch <= 1:
            return

        # Choose resample method
        resample = self.pan_quality if low_quality else self.filter

        # Invert affine, build affine_inv exactly as before…
        inv = np.linalg.inv(self.mat_affine)
        affine_inv = (
            inv[0,0], inv[0,1], inv[0,2],
            inv[1,0], inv[1,1], inv[1,2]
        )

        if not self.use_cache:
            dst = pil_image.transform(
                (cw, ch),
                Image.AFFINE,
                affine_inv,
                resample=resample,
                fillcolor=self.bg_color
            )   
            imagetk = ImageTk.PhotoImage(dst)
        else:
            key = (id(pil_image), affine_inv, resample, cw, ch)
            if key in self._render_cache:
                # Move key to end (most‐recent) and reuse its PhotoImage
                imagetk = self._render_cache.pop(key)
            else:
                # Perform the expensive transform + PhotoImage creation
                dst = pil_image.transform(
                (cw, ch),
                Image.AFFINE,
                affine_inv,
                resample=resample,
                fillcolor=self.bg_color
                )   
                imagetk = ImageTk.PhotoImage(dst)
            self._render_cache[key] = imagetk

        if len(self._render_cache) > self._cache_max_size:
            self._render_cache.popitem(last=False)

        if self.image_id:
            # Update the existing image
            self.canvas.itemconfig(self.image_id, image=imagetk)
        else:
            # Create the image for the first time
            self.image_id = self.canvas.create_image(0, 0, anchor='nw', image=imagetk, tags="_IMG")

        #self.canvas.delete("_IMG")
        #self.canvas.create_image(0, 0, anchor='nw', image=imagetk, tags="_IMG")

        self.image = imagetk
        
        if self.debug:
            if len(self.list1) == 10:
                self.list1.pop(0)
            self.list1.append(perf_counter()-self.start)
            average = 0
            sum = 0
            for x in self.list1:
                sum += float(x)
            average = sum/len(self.list1)
            print(f"{(average):.5f}")

    def redraw_image(self, low_quality=False):
        # Dummy, but will use this for gif rendering.
        if self.pil_image:
            self.draw_image(self.pil_image, low_quality)

    # Preferences
    def load_json(self):
        if os.path.isfile(self.save_path):
            try:
                with open(self.save_path) as f:
                    return json.load(f)
            except Exception as e:
                print("Json load error:", e)
        return {}

    def save_json(self):
        with open(self.save_path, "w") as f:
            json.dump({
                    "geometry": self.master.winfo_geometry(),       # "600x800+100+100" Width x Height + x + y
                    "disable_menubar": self.disable_menubar,        # Disable the menu bar
                    "statusbar": self.statusbar.get(),     # Disable the statusbar
                    "lastdir": self.lastdir or None,                # Last folder viewed
                    "auto_fit_on_resize": self.auto_fit_var.get(),  # Refit to window when resizing
                    "unbound_pan": self.unbound_var.get(),          # Go out of bounds
                    "rotation_amount": self.rotation_amount,        # Rotation amount
                    "zoom_amount": self.zoom_amount,                # Zoom amount
                    "filter": self.filter.name,                         # Default filter
                    "pan_quality": self.pan_quality.name,              # 
                    "quick_zoom": self.quick_zoom.get(),
                    "final_filter_delay": self.filter_delay.get(),
                    "quick_pan": self.quick_pan.get(),
                    "debounce_delay": self.debounce_delay.get(),
                    "show_advanced": self.show_advanced.get(),
                    "show_ram": self.show_ram.get(),
                    "colors": self.colors
                    }, f, indent=4)

if __name__ == "__main__":
    # The application viewer is a tk.frame to be bound to a tk.Tk() window.
    # As a standalone it creates its own root window.
    app = Application() # Give Application the window as master/root.
    #app.set_image(hava/nice/day/ha/gottim!) # display this image.
    app.master.mainloop() # Start the loop.
