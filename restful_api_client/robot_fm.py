"""
ESP32 OTA File Manager (PC-side)
--------------------------------
Two-pane (Norton Commander style) file manager:
- Left pane: Local PC filesystem (with navigation)
- Right pane: ESP32 filesystem over REST
- Supports: ls, mkdir, rm, mv, cp (PC<->ESP)
- OTA enter/apply/exit control

This version ADDS LOCAL DIRECTORY NAVIGATION.
"""

import os
import tkinter as tk
from tkinter import ttk, messagebox
import requests
import binascii
import zlib
import difflib
import hashlib

# =========================
# Configuration
# =========================
ESP32_BASE_URL = "http://192.168.1.80"   # <-- change to your robot IP
REQUEST_TIMEOUT = 5

# =========================
# ESP32 REST FS Adapter
# =========================
# Replace the existing Esp32FS class with this:

class Esp32FS:
    def __init__(self, base_url):
        self.base = base_url.rstrip('/')
        self.cwd = "/"

    def ls(self, path=None):
        path = path or self.cwd
        # Use our new /api/ls endpoint
        r = requests.get(f"{self.base}/ota/ls", params={"path": path}, timeout=REQUEST_TIMEOUT)
        r.raise_for_status()
        return r.json()

    def read_file(self, path):
        # Use streaming download
        # We tell server to send the file. If it's .gz on server, server sends .gz headers
        # requests automatically decompresses it for us!
        r = requests.get(f"{self.base}/ota/download", params={"file": path}, stream=True, timeout=REQUEST_TIMEOUT)
        r.raise_for_status()

        # Return the raw bytes (requests handles gzip decompression automatically)
        return r.content

    def write_file(self, path, data: bytes, compress=False):
        # 1. Compress Client-Side (optional, but good for speed)
        # We compress here, then upload with .gz extension
        if compress:
            compressed_data = zlib.compress(data, level=6)

            # 2. Upload using Streaming (No JSON body!)
            # We append .gz so the ESP32 saves it as a compressed file
            target_filename = path if path.endswith('.gz') else path + '.gz'
        else:
            compressed_data = data
            target_filename = path

        params = {"filename": target_filename, 'compress': 'true' if compress else 'false'}

        # Passing 'data=compressed_data' streams the bytes directly
        r = requests.post(f"{self.base}/ota/upload", params=params, data=compressed_data, timeout=10)
        r.raise_for_status()

    def rm(self, path):
        # We need a delete endpoint (Add this to server if missing, or use a workaround)
        # For now, let's assume you add a simple /api/delete route
        r = requests.post(f"{self.base}/ota/delete", json={"path": path}, timeout=REQUEST_TIMEOUT)
        r.raise_for_status()

    def mkdir(self, path):
        r = requests.post(f"{self.base}/ota/mkdir", json={"path": path}, timeout=REQUEST_TIMEOUT)
        r.raise_for_status()

    def rm(self, path):
        r = requests.post(f"{self.base}/ota/rm", json={"path": path}, timeout=REQUEST_TIMEOUT)
        r.raise_for_status()

    def mv(self, src, dst):
        r = requests.post(f"{self.base}/ota/mv", json={"src": src, "dst": dst}, timeout=REQUEST_TIMEOUT)
        r.raise_for_status()

    # OTA control
    def ota_enter(self):
        requests.post(f"{self.base}/ota/enter", timeout=REQUEST_TIMEOUT)

    def ota_exit(self):
        requests.post(f"{self.base}/ota/exit", timeout=REQUEST_TIMEOUT)


# =========================
# GUI
# =========================
class TwoPaneFileManager(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("ESP32 OTA File Manager")
        self.geometry("1000x600")

        self.esp = Esp32FS(ESP32_BASE_URL)
        self.local_cwd = os.getcwd()

        self._build_ui()
        self.refresh_local()
        self.refresh_esp()

    # ---------------------
    def _build_ui(self):
        paned = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True)

        self.local_frame, self.local_tree = self._make_tree(paned, "PC")
        self.esp_frame, self.esp_tree = self._make_tree(paned, "ESP32")

        paned.add(self.local_frame)
        paned.add(self.esp_frame)

        # Bind navigation for both panes
        self.local_tree.bind("<Double-1>", self.on_local_open)
        self.esp_tree.bind("<Double-1>", self.on_esp_open)


        # Bottom toolbar
        bar = ttk.Frame(self)
        bar.pack(fill=tk.X)

        # ... (previous code) ...

        # Add the "Compare" button to the toolbar
        ttk.Button(bar, text="Compare", command=self.compare_files).pack(side=tk.LEFT, padx=5)

        # ... (rest of the buttons) ...

        ttk.Button(bar, text="Copy →", command=self.copy_to_esp).pack(side=tk.LEFT, padx=5)
        ttk.Button(bar, text="← Copy", command=self.copy_from_esp).pack(side=tk.LEFT, padx=5)
        ttk.Button(bar, text="Delete", command=self.delete_esp).pack(side=tk.LEFT, padx=5)
        ttk.Button(bar, text="OTA", command=self.enter_ota).pack(side=tk.LEFT, padx=5)
        ttk.Button(bar, text="OTA End", command=self.exit_ota).pack(side=tk.LEFT, padx=5)
        ttk.Button(bar, text="Quit", command=self.destroy).pack(side=tk.RIGHT, padx=5)
        # add refresh button
        ttk.Button(bar, text="Refresh Local", command=self.refresh_local).pack(side=tk.LEFT, padx=5)
        ttk.Button(bar, text="Refresh Remote", command=self.refresh_esp).pack(side=tk.LEFT, padx=5)

    # ---------------------
    def _make_tree(self, parent, label):
        frame = ttk.Frame(parent)
        ttk.Label(frame, text=label).pack(anchor=tk.W)
        tree = ttk.Treeview(frame, columns=("size",), show="tree headings")
        tree.heading("#0", text="Name")
        tree.heading("size", text="Size")
        tree.pack(fill=tk.BOTH, expand=True)
        return frame, tree

    # ---------------------
    def refresh_local(self):
        tree = self.local_tree
        tree.delete(*tree.get_children())

        # parent directory
        tree.insert('', 'end', text="..", values=("",))
        # directories are first and sorted order the regular files in sorted order
        tree.insert('', 'end', text="Directories", values=("",))
        for name in sorted(os.listdir(self.local_cwd)):
            if os.path.isdir(os.path.join(self.local_cwd, name)):
                tree.insert('', 'end', text=name, values=("<DIR>",))

        tree.insert('', 'end', text="Files", values=("",))
        for name in sorted(os.listdir(self.local_cwd)):
            if not os.path.isfile(os.path.join(self.local_cwd, name)):
                continue
            p = os.path.join(self.local_cwd, name)
            size = os.path.getsize(p) if os.path.isfile(p) else "----"
            tree.insert('', 'end', text=name, values=(size,))

        self.local_frame.winfo_children()[0].config(text=f"PC: {self.local_cwd}")

    # ---------------------
    def refresh_esp(self):
        tree = self.esp_tree
        tree.delete(*tree.get_children())
        try:
            j = self.esp.ls(self.esp.cwd)
            tree.insert('', 'end', text="..", values=("",))
            tree.insert('', 'end', text="Directories", values=("",))
            # sort by name
            j['entries'].sort(key=lambda x: x['name'])
            for e in j.get("entries", []):
                if e.get("size") == "<DIR>":
                    tree.insert('', 'end', text=e['name'], values=(e['size'],))
            tree.insert('', 'end', text="Files", values=("",))
            for e in j.get("entries", []):
                if e.get("size") == "<DIR>":
                    continue
                tree.insert('', 'end', text=e['name'], values=(e['size'],))
            self.esp_frame.winfo_children()[0].config(text=f"ESP32: {self.esp.cwd}")
        except Exception as ex:
            messagebox.showerror("ESP32", str(ex))

    # ---------------------
    def on_local_open(self, event):
        sel = self.local_tree.selection()
        if not sel:
            return
        name = self.local_tree.item(sel[0], 'text')
        if name == "..":
            self.local_cwd = os.path.dirname(self.local_cwd)
        else:
            p = os.path.join(self.local_cwd, name)
            if os.path.isdir(p):
                self.local_cwd = p
            else:
                return
        self.refresh_local()

    # ---------------------
    def on_esp_open(self, event):
        sel = self.esp_tree.selection()
        if not sel:
            return
        name = self.esp_tree.item(sel[0], 'text')
        if name == "..":
            self.esp.cwd = os.path.dirname(self.esp.cwd)
        else:
            self.esp.cwd = os.path.join(self.esp.cwd, name)
        self.refresh_esp()

    # ---------------------
    def copy_to_esp(self):
        sel = self.local_tree.selection()
        if not sel:
            return
        name = self.local_tree.item(sel[0], 'text')
        print('===', sel, name)
        path = os.path.join(self.local_cwd, name)
        if not os.path.isfile(path):
            return
        with open(path, 'rb') as f:
            data = f.read()

        dst = f"{self.esp.cwd}/{name}"
        self.esp.write_file(dst, data)
        self.refresh_esp()

    def copy_from_esp(self):
        sel = self.esp_tree.selection()
        if not sel:
            return
        name = self.esp_tree.item(sel[0], 'text')
        if name == "..":
            return
        data = self.esp.read_file(f"{self.esp.cwd}/{name}")
        with open(os.path.join(self.local_cwd, name), 'wb') as f:
            f.write(data)
        self.refresh_local()

    def delete_esp(self):
        sel = self.esp_tree.selection()
        if not sel:
            return
        name = self.esp_tree.item(sel[0], 'text')
        if name == "..":
            return
        if messagebox.askyesno("Delete", f"Delete {name} on ESP32?"):
            self.esp.rm(f"{self.esp.cwd}/{name}")
            self.refresh_esp()

    def enter_ota(self):
        if messagebox.askyesno("OTA", "Enter OTA mode?"):
            self.esp.ota_enter()
            messagebox.showinfo("OTA", "ESP32 entered OTA mode")

    def exit_ota(self):
        self.esp.ota_exit()
        messagebox.showinfo("OTA", "ESP32 exited OTA mode")

# --- New Comparison Logic ---
    def compare_files(self):
        """
        Compares selected local file with selected remote file.
        If only one side is selected, tries to find a matching name on the other side.
        """
        # 1. Identify Local File
        local_sel = self.local_tree.selection()
        local_path = None
        if local_sel:
            name = self.local_tree.item(local_sel[0], 'text')
            if name != "..":
                local_path = os.path.join(self.local_cwd, name)

        # 2. Identify Remote File
        remote_sel = self.esp_tree.selection()
        remote_path = None
        if remote_sel:
            name = self.esp_tree.item(remote_sel[0], 'text')
            if name != "..":
                remote_path = f"{self.esp.cwd}/{name}"

        # 3. Auto-match logic (if only one selected)
        if local_path and not remote_path:
            # Try to find same filename on ESP
            filename = os.path.basename(local_path)
            remote_path = f"{self.esp.cwd}/{filename}"
        elif remote_path and not local_path:
            # Try to find same filename on PC
            filename = os.path.basename(remote_path)
            local_path = os.path.join(self.local_cwd, filename)

        if not local_path or not remote_path:
            messagebox.showwarning("Compare", "Please select a file to compare.")
            return

        # 4. Perform Comparison
        try:
            self._show_diff_window(local_path, remote_path)
        except Exception as e:
            messagebox.showerror("Compare Error", str(e))

    def _show_diff_window(self, local_path, remote_path):
        # A. Read Local
        if not os.path.exists(local_path):
            messagebox.showerror("Error", f"Local file not found: {local_path}")
            return

        with open(local_path, 'rb') as f:
            local_data = f.read()

        # B. Download Remote
        try:
            print(f"Downloading {remote_path} for comparison...")
            remote_data = self.esp.read_file(remote_path)
        except Exception as e:
            messagebox.showerror("Download Error", f"Could not read remote file: {e}")
            return

        # C. Compare
        # Check if binary
        if self._is_binary(local_data) or self._is_binary(remote_data):
            self._show_binary_diff(local_path, local_data, remote_path, remote_data)
        else:
            self._show_text_diff(local_path, local_data, remote_path, remote_data)

    def _is_binary(self, data):
        """Simple check for null bytes to detect binary files"""
        return b'\x00' in data[:1024]

    def _show_binary_diff(self, p1, d1, p2, d2):
        hash1 = hashlib.md5(d1).hexdigest()
        hash2 = hashlib.md5(d2).hexdigest()

        msg = f"Local: {p1}\nSize: {len(d1)} bytes\nMD5: {hash1}\n\n"
        msg += f"Remote: {p2}\nSize: {len(d2)} bytes\nMD5: {hash2}\n\n"

        if hash1 == hash2:
            msg += "RESULT: FILES ARE IDENTICAL"
            icon = "info"
        else:
            msg += "RESULT: FILES DIFFER"
            icon = "warning"

        messagebox.showinfo("Binary Compare", msg, icon=icon)

    def _show_text_diff(self, p1, d1, p2, d2):
        # Decode bytes to strings
        try:
            text_local = d1.decode('utf-8').splitlines()
            text_remote = d2.decode('utf-8').splitlines()
        except UnicodeDecodeError:
            messagebox.showerror("Compare", "Could not decode text (not UTF-8).")
            return

        # Generate Diff
        diff = difflib.unified_diff(
            text_local, text_remote,
            fromfile=f"LOCAL ({os.path.basename(p1)})",
            tofile=f"REMOTE ({os.path.basename(p2)})",
            lineterm=""
        )
        diff_text = "\n".join(diff)

        if not diff_text:
            messagebox.showinfo("Compare", "Files are identical.")
            return

        # Create Popup Window
        top = tk.Toplevel(self)
        top.title(f"Diff: {os.path.basename(p1)}")
        top.geometry("800x600")

        # Text Widget with Scrollbar
        txt = tk.Text(top, wrap=tk.NONE, font=("Consolas", 10))
        v_scroll = ttk.Scrollbar(top, orient=tk.VERTICAL, command=txt.yview)
        h_scroll = ttk.Scrollbar(top, orient=tk.HORIZONTAL, command=txt.xview)
        txt.configure(yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set)

        v_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        h_scroll.pack(side=tk.BOTTOM, fill=tk.X)
        txt.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Color Tags
        txt.tag_config("plus", foreground="green", background="#e6ffe6")
        txt.tag_config("minus", foreground="red", background="#ffe6e6")
        txt.tag_config("header", foreground="blue")

        # Insert lines with colors
        for line in diff_text.splitlines():
            tag = None
            if line.startswith("---") or line.startswith("+++"):
                tag = "header"
            elif line.startswith("+"):
                tag = "plus"
            elif line.startswith("-"):
                tag = "minus"

            txt.insert(tk.END, line + "\n", tag)

        txt.configure(state=tk.DISABLED) # Make read-only


# =========================
if __name__ == '__main__':
    TwoPaneFileManager().mainloop()
