from typing import List
import tkinter as tk
import math


class PolarPlot(tk.Frame):
    def __init__(self, master=None, size=None, r_max='auto',
                #  angle_min=0, angle_max=180, up_angle=90,
                 canvas_init=None, **kwargs):
        # make plot for -90 to +90 0 is up
        super().__init__(master, **kwargs)
        self.r_max = r_max
        size = 100 if size is None else size
        canvas_init = {} if canvas_init is None else canvas_init
        w = math.sin(math.radians(90)) - math.sin(math.radians(-90))
        h = math.cos(math.radians(0)) - math.cos(math.radians(90))
        self.w = canvas_init['width'] = round(w / max(w,h) * (size))
        self.h = canvas_init['height'] = round(h / max(w, h) * (size))
        if 'bg' not in canvas_init:
            canvas_init.update({'bg': 'white'})
        self.canvas = tk.Canvas(self, **canvas_init)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.center = canvas_init['width'] / 2, canvas_init['height']

    def clear(self):
        self.canvas.delete()

    def _polar_to_cartesian(self, r, theta, scale) -> tuple:
        x = r * math.cos(math.radians(theta)) * scale
        y = r * math.sin(math.radians(theta)) * scale
        return x, y

    def _draw_grid(self, r, t, l, s):
        for tt in t:
            p = self._polar_to_cartesian(l, tt, s)
            self.canvas.create_line(self.center[0], self.center[1], self.center[0] + p[0], self.center[1] - p[1])
        for ll in r:
            self.canvas.create_arc(self.center[0] - ll * s, self.center[1] - ll * s, self.center[0] + ll * s, self.center[1] + ll * s, extent=180, outline='gray')


    def plot(self, r_values, theta_values_deg, r_max=None, grid=None, color='black'):
        self.canvas.delete()
        if isinstance(self.r_max, str) and self.r_max == 'auto':
            r_max = max(r_values)
        elif isinstance(self.r_max , (int, float)):
            r_max = self.r_max
        else:
            raise ValueError(type(self.r_max))
        scale = (self.h - 10) / r_max
        point = [self._polar_to_cartesian(i, j, scale)
                 for i, j in zip(r_values, theta_values_deg)]
        for p0, p1 in zip(point[:-1], point[1:]):
            self.canvas.create_line(self.center[0]+p0[0], self.center[1] - p0[1],
                                    self.center[0]+p1[0], self.center[1] - p1[1], fill=color, width=2)
        self._draw_grid([r_max / 5 * i for i in range(1, 5+1)], [j for j in range(0, 182, 45)], r_max, scale)
        # self.canvas.update()
        # plot_half_circle_polar(self.canvas, r_values, theta_values_deg)


def main_polar():
    root = tk.Tk()
    root.title("Half‑Circle Polar Plot (Aligned Grid, Origin on Baseline)")
    # CANVAS_W, CANVAS_H = 512, 256
    # canvas = tk.Canvas(root, width=CANVAS_W, height=CANVAS_H, bg="white")
    # canvas.pack()
    polar_plot = PolarPlot(root, size=512)
    polar_plot.pack(fill='both', expand=True)

    # Example data: θ = 0°–180°, r = |sin(θ)|
    theta_vals = [i * 180 / 100 for i in range(101)]
    r_vals = [abs(math.sin(math.radians(t))) for t in theta_vals]
    r_vals = [1. + math.sin(math.radians(t*7+90)) for t in theta_vals]
    # r_vals = theta_vals


    # plot_half_circle_polar(canvas, r_vals, theta_vals)
    # Quit button
    tk.Button(root, text="Quit", command=root.destroy).pack(pady=5)
    # send data to plot button
    tk.Button(root, text='Plot', command=lambda: polar_plot.plot(r_vals, theta_vals)).pack(pady=5)

    root.mainloop()



if __name__ == "__main__":
    main_polar()

