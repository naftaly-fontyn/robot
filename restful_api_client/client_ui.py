
import math
import time
import threading
import queue
from typing import List
import tkinter as tk
import tkinter.ttk as ttk
# from restful_api_client.polar_plot_widget import PolarPlot
from restful_client import post_to_messagebus, post_to_robot
from polar_plot_widget import PolarPlot





SPRITE_1 = [
    '       g       ',
    '      ggg      ',
    '     ggggg     ',
    '     ggggg     ',
    '    bbbbbbb    ',
    '    bbbbbbb    ',
    ' kk bbbbbbb kk ',
    ' kk bbbbbbb kk ',
    ' kkkbbbbbbbkkk ',
    ' kk bbbbbbb kk ',
    ' kk bbbbbbb kk ',
    '    rrrrrrr    '
]

COLOR_MAP = {
    'b': '#0000FF', # blue,
    'g': 'green',
    'r': 'red',
    'k': 'black',
    ' ': '',
}

# move to other module
class SpriteImage:
    def __init__(self, image: List[str]):
        self.image = image
        self.w = len(image[0])
        self.h = len(image)
        self._base_image = []
        for ln in image:
            l = []
            for c in ln:
                l.append(COLOR_MAP[c])
            self._base_image.append(l)

    def make_image(self, rot_deg: float):
        l = math.sqrt(self.w**2 + self.h**2)
        t0 = math.atan2(self.h, self.w)
        t1 = math.radians(rot_deg)
        w = math.ceil(abs(math.cos(t1 + t0) * l))
        h = math.ceil(abs(math.sin(t1 + t0) * l))
        print(self.w, self.h, l, w, h, math.degrees(t0))
        img = tkinter.PhotoImage(width=w, height=h)
        for y in range(h):
            for x in range(w):
                x0 = round((x-w/2) * math.cos(t1) + (y-h/2) * math.sin(t1) + self.w/2)
                y0 = round(-(x-w/2) * math.sin(t1) + (y-h/2) * math.cos(t1) + self.h/2)
                # print(x0, y0, x, y)
                # if self._base_image[y0][x0] == '{}':
                #     continue
                if 0 <= x0 < self.w and 0 <= y0 < self.h:
                    print(x0, y0, x, y)
                    img.put(self._base_image[y0][x0], to=(x, y, x+1, y+1))
        return img

class PlotXY(tk.Canvas):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        # Margins: Left, Top, Right, Bottom
        self.margins = (40, 10, 10, 30)

        # Inner canvas for the plot area (handles clipping automatically)
        self.inner = tk.Canvas(self, bg=kwargs.get('bg', 'white'), highlightthickness=0)
        self.win_id = self.create_window(0, 0, window=self.inner, anchor='nw')

        self.bind('<Configure>', self._on_resize)

        self.plots = {}
        self.x_min = 0
        self.x_max = 100
        self.y_min = 0
        self.y_max = 100
        self.x_grid = None
        self.y_grid = None

    def clear(self, _id=None):
        if _id:
            self.inner.delete(_id)
            if _id in self.plots:
                del self.plots[_id]
        else:
            self.inner.delete('all')
            self.plots = {}
            self.draw_grid()

    def set_grid(self, x_grid=None, y_grid=None):
        self.x_grid = x_grid
        self.y_grid = y_grid
        self.redraw_plots()

    def draw_grid(self):
        # Draw axes box on outer canvas
        self.delete('grid')
        x0, y0 = self.margins[0], self.margins[1]
        w = int(self.inner['width'])
        h = int(self.inner['height'])
        self.create_rectangle(x0-1, y0-1, x0+w, y0+h, outline='gray', tags='grid')

        # Draw grid lines on inner canvas
        self.inner.delete('grid')

        x_range = self.x_max - self.x_min
        y_range = self.y_max - self.y_min
        if x_range == 0: x_range = 1
        if y_range == 0: y_range = 1
        scale_x = w / x_range
        scale_y = h / y_range

        if self.x_grid:
            for val in self.x_grid:
                sx = (val - self.x_min) * scale_x
                if 0 <= sx <= w:
                    self.inner.create_line(sx, 0, sx, h, fill='lightgray', dash=(2, 4), tags='grid')
        else:
            for i in range(1, 5):
                x = i * w / 5
                self.inner.create_line(x, 0, x, h, fill='lightgray', dash=(2, 4), tags='grid')

        if self.y_grid:
            for val in self.y_grid:
                sy = h - (val - self.y_min) * scale_y
                if 0 <= sy <= h:
                    self.inner.create_line(0, sy, w, sy, fill='lightgray', dash=(2, 4), tags='grid')
        else:
            for i in range(1, 5):
                y = i * h / 5
                self.inner.create_line(0, y, w, y, fill='lightgray', dash=(2, 4), tags='grid')
        self.inner.tag_lower('grid')

    def _on_resize(self, event):
        w, h = event.width, event.height
        iw = w - self.margins[0] - self.margins[2]
        ih = h - self.margins[1] - self.margins[3]
        if iw < 1: iw = 1
        if ih < 1: ih = 1

        self.inner.config(width=iw, height=ih)
        self.coords(self.win_id, self.margins[0], self.margins[1])
        self.redraw_plots()

    def redraw_plots(self):
        self.inner.delete('all')
        self.draw_grid()
        for (x, y, color, style) in self.plots.values():
            self._draw_single_plot(x, y, color, style)

    def set_x_extents(self, x_min=0, x_max=100):
        self.x_min = x_min
        self.x_max = x_max
        self.redraw_plots()

    def set_y_extents(self, y_min=0, y_max=100):
        self.y_min = y_min
        self.y_max = y_max
        self.redraw_plots()

    def add_plot(self, x: list, y: list, color='black', line_style='-'):
        _id = self._draw_single_plot(x, y, color, line_style)
        if _id:
            self.plots[_id] = (x, y, color, line_style)
        return _id

    def _draw_single_plot(self, x, y, color, style):
        w = int(self.inner['width'])
        h = int(self.inner['height'])
        x_range = self.x_max - self.x_min
        y_range = self.y_max - self.y_min
        if x_range == 0: x_range = 1
        if y_range == 0: y_range = 1
        scale_x = w / x_range
        scale_y = h / y_range

        dash = None
        if style == '--':
            dash = (4, 4)
        elif style == ':':
            dash = (1, 2)
        elif style == '-.':
            dash = (4, 2, 1, 2)
        elif isinstance(style, (tuple, list)):
            dash = style

        coords = []
        for i in range(len(x)):
            sx = (x[i] - self.x_min) * scale_x
            sy = h - (y[i] - self.y_min) * scale_y
            coords.extend((sx, sy))

        if len(coords) >= 4:
            return self.inner.create_line(coords, fill=color, width=2, dash=dash)
        return None


class MessageSender(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True)
        self._event = threading.Event()
        self._lock = threading.Lock()
        self.return_q = queue.Queue()
        self._topic = None
        self._payload = None
        self.start()

    def send(self, topic, payload, reply_topic=None, reply_timeout=2, wait_timeout=2):
        # Update the current message to be sent (overwriting any pending one)
        with self._lock:
            self._topic = topic
            self._payload = payload
            self._reply_topic = reply_topic
            self._reply_timeout = reply_timeout
            self._wait_timeout = wait_timeout
        # Signal the worker thread that there is a message
        self._event.set()

    def run(self):
        while True:
            self._event.wait()
            self._event.clear()
            with self._lock:
                topic = self._topic
                payload = self._payload
                reply_topic = self._reply_topic
                reply_timeout = self._reply_timeout
                wait_timeout = self._wait_timeout
                self._topic = None
                self._payload = None
                self._reply_topic = None
                self._wait_timeout = 2
                self._reply_timeout = 2
            if topic:
                try:
                    response = post_to_messagebus(topic, payload, reply_topic, reply_timeout, wait_timeout)
                    if reply_topic:
                        self.return_q.put(response)
                except Exception as e:
                    print(f"Error sending message: {e}")


class Joystick(tk.Canvas):
    def __init__(self, master, size=100, callback=None, sampling_rate=0.05, **kwargs):
        super().__init__(master, width=size, height=size, **kwargs)
        self.size = size
        self.center = size / 2
        self.radius = size / 2 * 0.9
        self.knob_radius = min(20, size /10)
        self.max_dist = self.radius - self.knob_radius
        self.callback = callback
        self.sampling_rate = sampling_rate
        self.last_time = 0

        self.create_oval(self.center - self.radius, self.center - self.radius,
                         self.center + self.radius, self.center + self.radius,
                         outline="gray", width=2)
        self.knob = self.create_oval(self.center - self.knob_radius, self.center - self.knob_radius,
                                     self.center + self.knob_radius, self.center + self.knob_radius,
                                     fill="red")

        self.bind("<B1-Motion>", self._on_drag)
        self.bind("<ButtonRelease-1>", self._on_release)

    def _on_drag(self, event):
        x = event.x - self.center
        y = event.y - self.center
        dist = math.sqrt(x**2 + y**2)

        if dist > self.max_dist:
            scale = self.max_dist / dist
            x *= scale
            y *= scale

        self.coords(self.knob,
                    self.center + x - self.knob_radius, self.center + y - self.knob_radius,
                    self.center + x + self.knob_radius, self.center + y + self.knob_radius)

        if self.callback:
            now = time.time()
            if now - self.last_time > self.sampling_rate:
                # Normalize to -1.0 to 1.0, invert Y so up is positive
                self.callback(x / self.max_dist, -y / self.max_dist)
                self.last_time = now

    def _on_release(self, event):
        self.coords(self.knob,
                    self.center - self.knob_radius, self.center - self.knob_radius,
                    self.center + self.knob_radius, self.center + self.knob_radius)
        if self.callback:
            self.callback(0.0, 0.0)

clr = 0
COLORS = ['blue', 'red', 'green', 'yellow', 'magenta', 'cyan', 'black']


class ClientUi(tk.Frame):
    def __init__(self, master: tk.Frame, *args, **kwargs):
        super().__init__(master, *args, **kwargs)
        # add a menu bar, ade a File entry with a call back to OTP
        self._menubar = tk.Menu(master)
        master.config(menu=self._menubar)
        self._menu_file = tk.Menu(self._menubar, tearoff=0)
        self._menubar.add_cascade(label='File', menu=self._menu_file)
        self._menu_file.add_command(label="OTA", command=self._do_ota)
        # self._menu_file.add_command(label="Exit", command=master.quit)
        # self._menu_file.add_cascade(label='File', menu=self._menu_file)


        self.master = master
        # self.main_frame = tk.Frame(self)
        self.us_frame = ttk.LabelFrame(self, text="US Scan")
        self.us_frame.grid(row=0, column=0, sticky="nsew")
        self.polar_plot = PolarPlot(self.us_frame, size=512, r_max=700)
        self.polar_plot.grid(row=0, column=0, sticky="nsew")
        self.us_scan_btn = tk.Button(self.us_frame, text="US Scan", command=lambda: self.do_us_scan_btn())
        self.us_scan_btn.grid(row=1, column=0, sticky="nsew")

        self.ahrc_frame = ttk.LabelFrame(self, text="AHRS")
        self.ahrc_frame.grid(row=0, column=1, sticky="nsew")
        self.ahrc_report_lbls = []
        for i in range(5):
            self.ahrc_report_lbls.append(tk.Label(self.ahrc_frame, text="--", width=50, anchor="w"))
            self.ahrc_report_lbls[i].grid(row=i, column=1, sticky="nsew")
        # self.ahrc_report_lbl  tk.Label(self.ahrc_frame, text="--", width=100)
        # self.ahrc_report_lbl.grid(row=0, column=1, sticky="nsew")
        self.ahrc_btn = tk.Button(self.ahrc_frame, text="AHRC", command=self.do_ahrc_btn)
        self.ahrc_btn.grid(row=0, column=0, sticky="nsew")
        self.motor_calib_btn = tk.Button(self.ahrc_frame, text="Motor Calib", command=self.do_calibrate_motor_btn)
        self.motor_calib_btn.grid(row=8, column=0, sticky="nsew")


        tk.Button(self.ahrc_frame, text="Calibrate", command=self.do_calibrate_btn).grid(row=3, column=0, sticky="nsew")
        self.status_lbl = tk.Label(self.ahrc_frame, text="--")
        self.status_lbl.grid(row=4, column=0, sticky="nsew")
        # manual drive robot
        self.move_frame = ttk.LabelFrame(self, text="Move")
        self.move_frame.grid(row=1, column=0, sticky="nsew")
        self.sender = MessageSender()
        self.joystick = Joystick(self.move_frame, size=400, callback=self.do_joystick)
        self.joystick.pack()

        self.plot_frm = ttk.LabelFrame(self, text="Plot")
        self.plot_frm.grid(row=1, column=1, sticky="nsew")
        self.plot_btn = tk.Button(self.plot_frm, text="Plot", command=lambda: self.do_plot_btn())
        self.plot_btn.grid(row=0, column=0, sticky="nsew")
        self.plot_xy = PlotXY(self.plot_frm, bg='white')
        self.plot_xy.grid(row=1, column=0, sticky="nsew")

    def _do_ota(self):
        post_to_robot('/ota/enter')


    def do_plot_btn(self):
        x = list(range(0, 360 * 3, 5))
        y = [3 * math.sin(math.radians(i)) for i in x]
        self.plot_xy.clear()
        self.plot_xy.set_x_extents(min(x), max(x))
        self.plot_xy.set_y_extents(min(y), max(y))
        self.plot_xy.set_grid(x_grid=range(0, 360*3, 90), y_grid=range(-4, 5))
        # self.plot_xy.add_plot(x, y]
        self.plot_xy.add_plot(x, y, color='blue', line_style='-.')


    def do_joystick(self, x, y):
        print(f"Joystick: {x:.2f}, {y:.2f}")
        # dead zone +- 0.1
        x = x if abs(x) > 0.2 else 0
        y = y if abs(y) > 0.2 else 0
        p = math.sqrt(x*x + y*y)
        p = -p if y < 0 else p
        r = abs(y / x) if x != 0 else None
        p2 = p * (r - 1) /(r + 1) if r is not None else p
        p1, p2 = (p, p2) if x < 0 else (p2, p)
        print('PWR', r, x, y, p1, p2)
        p = 0
        self.sender.send('motors_task', {'motor0_power': p1 * 100, 'motor1_power': p2 * 100})

    def do_ahrc_btn(self):
        response = post_to_messagebus('ahrs_task', {'command': 'single'}, reply_topic='ahrs_report', reply_timeout=2, wait_timeout=2)
        print(response)
        for i, r in enumerate(response[2]['message'].items()):
            self.ahrc_report_lbls[i]['text'] = f"{r[0]}:{r[1]}"
            self.ahrc_report_lbls[i].update()

    def do_us_scan_btn(self):
        global clr
        self.polar_plot
        response = post_to_messagebus('us_scan', {'start_angle': 0, 'stop_angle': 180, 'step': 15}, reply_topic='us_scan_report', reply_timeout=120, wait_timeout=120)
        print(response)
        theta_vals = [i * 180 / 100 for i in range(101)]
        r_vals = [abs(math.sin(math.radians(t))) for t in theta_vals]
        r_vals = [(1. + math.sin(math.radians(t*7+90)))*300 for t in theta_vals]
        theta_vals = []
        r_vals = []
        for r in response[2]['message']['scan_distances']:
            theta_vals.append(r['angle'])
            r_vals.append(r['distance'])
        # plt.clear()
        self.polar_plot.plot(r_vals, theta_vals, color=COLORS[clr])
        clr = (clr+1) % len(COLORS)

    def do_calibrate_motor_btn(self):
        response = post_to_messagebus('motors_task', {'calibrate': 'both'}, reply_topic='motors_report', reply_timeout=60, wait_timeout=60)
        m0 = response[2]['message']['calibrate']['motors']['M0']
        m1 = response[2]['message']['calibrate']['motors']['M2']
        self.plot_xy.clear()
        x = [r['pwm'] for r in m0]
        y = [r['Vss'] for r in m0]
        x_ext = 0, 100  # min(x), max(x)
        y_ext = 0, 180  # min(y), max(y)
        self.plot_xy.set_x_extents(*x_ext)
        self.plot_xy.set_y_extents(*y_ext)
        self.plot_xy.set_grid(range(0, 100, 10), range(0, 180, 20))
        self.plot_xy.add_plot(x, y, color='red', line_style='-')
        x = [r['pwm'] for r in m1]
        y = [r['Vss'] for r in m1]
        self.plot_xy.add_plot(x, y, color='green', line_style='-')
        y = [(r1['Vss']+r2['Vss']) /2  for r1, r2 in zip(m0, m1)]
        self.plot_xy.add_plot(x, y, color='black', line_style=':')
        k = 0
        x0 = [0,5]
        y0 = [0,0]
        i = 0
        while i < len(x):
            if x[i] < x0[-1]:
                i += 1
                continue
            _y = (x[i] - x0[-1]) * k + y0[-1]
            if abs(_y / y[i] - 1) > 0.05:
                x0.append(x[i])
                y0.append(y[i])
                k = (y0[-1] - y0[-2]) / (x0[-1] - x0[-2]) if x0[-1] != x0[-2] else 0
                i += 1
            else:
                x0[-1] = x[i]
                y0[-1] = y[i]
                k = (y0[-1] - y0[-2]) / (x0[-1] - x0[-2]) if x0[-1] != x0[-2] else 0
                i += 1
        x0.append(100)
        y0.append(y0[-1])
        print(len(x0), len(y0))
        self.plot_xy.add_plot(x0, y0, color='blue', line_style='-')



    def do_calibrate_btn(self):
        self.status_lbl['text'] = 'Calibrating'
        self.status_lbl.update()
        response = post_to_messagebus('ahrs_task', {'command': 'calibrate'}, reply_topic='ahrs_report', reply_timeout=60, wait_timeout=60)
        if response[2]['message']['ack'] == 'ACK':
            self.status_lbl['text'] = 'Calibration successful'
        else:
            self.status_lbl['text'] = 'Calibration failed'
        self.status_lbl.update()


    # return main_frame

    # sonnar = PolarPlot(main_frame)
    # sonnar.grid(row=0, column=0, sticky="nsew")


if __name__ == "__main__":
    root = tk.Tk()
    client_ui = ClientUi(root)
    client_ui.pack()
    root.mainloop()

#
