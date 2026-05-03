# -*- coding: utf-8 -*-
import ctypes
import json
import os
import sys
import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox

try:
    from pynput import mouse, keyboard
    import win32gui
    import win32api
    import win32con
except ImportError as e:
    messagebox.showerror("导入错误", f"缺少必要的库: {e}\n请运行: pip install pynput pywin32")
    sys.exit(1)

try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except:
    try:
        ctypes.windll.user32.SetProcessDpiAware()
    except:
        pass

try:
    DPI_SCALE = win32api.GetDpiForSystem() / 96.0
except:
    try:
        DPI_SCALE = ctypes.windll.shcore.GetDpiForSystem() / 96.0
    except:
        DPI_SCALE = 1.0

CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")


class ClickTask:
    def __init__(self, task_id, countdown, relative_x, relative_y, click_type):
        self.id = task_id
        self.countdown = countdown
        self.relative_x = relative_x
        self.relative_y = relative_y
        self.click_type = click_type

    def to_dict(self):
        return {
            "id": self.id,
            "countdown": self.countdown,
            "relative_x": self.relative_x,
            "relative_y": self.relative_y,
            "click_type": self.click_type
        }

    @classmethod
    def from_dict(cls, data):
        return cls(data["id"], data["countdown"], data["relative_x"], data["relative_y"], data["click_type"])

    def to_list(self):
        return [self.id, f"{self.countdown:.1f}", f"({self.relative_x}, {self.relative_y})", self.click_type]


class TargetWindow:
    def __init__(self, hwnd, title):
        self.hwnd = hwnd
        self.title = title
        self.rect = None
        self.update_rect()

    def update_rect(self):
        try:
            if win32gui.IsWindow(self.hwnd):
                self.rect = win32gui.GetWindowRect(self.hwnd)
                return True
            return False
        except:
            return False

    def is_valid(self):
        try:
            return win32gui.IsWindow(self.hwnd)
        except:
            return False

    def get_relative_to_absolute(self, rel_x, rel_y):
        if not self.update_rect():
            return None, None
        abs_x = int(self.rect[0] + rel_x * DPI_SCALE)
        abs_y = int(self.rect[1] + rel_y * DPI_SCALE)
        return abs_x, abs_y


class CoordinatePicker:
    def __init__(self, target_window):
        self.target_window = target_window
        self.picked_x = None
        self.picked_y = None
        self.picking = False
        self.lock = threading.Lock()
        self.listener = None

    def start_pick(self, callback):
        self.picking = True
        self.listener = mouse.Listener(on_click=self._on_click)
        self.listener.start()
        self._poll_pick(callback)

    def _on_click(self, x, y, button, pressed):
        if pressed and self.picking:
            if self.target_window and self.target_window.is_valid():
                try:
                    rel_x = int((x - self.target_window.rect[0]) / DPI_SCALE)
                    rel_y = int((y - self.target_window.rect[1]) / DPI_SCALE)
                    with self.lock:
                        self.picked_x = rel_x
                        self.picked_y = rel_y
                except:
                    pass

    def _poll_pick(self, callback):
        if self.picking:
            with self.lock:
                if self.picked_x is not None:
                    self.picking = False
                    px, py = self.picked_x, self.picked_y
                    self.picked_x = None
                    self.picked_y = None
                    if self.listener:
                        self.listener.stop()
                    callback(px, py)
                    return
        if self.picking:
            self.target_window.update_rect()
            self.target_window.after(100, lambda: self._poll_pick(callback))


class MouseController:
    def __init__(self):
        self.controller = mouse.Controller()

    def click_left(self, x, y):
        self.controller.position = (x, y)
        time.sleep(0.05)
        self.controller.click(mouse.Button.left, 1)

    def click_right(self, x, y):
        self.controller.position = (x, y)
        time.sleep(0.05)
        self.controller.click(mouse.Button.right, 1)


class WindowSelector:
    @staticmethod
    def get_all_windows():
        windows = []

        def enum_handler(hwnd, ctx):
            try:
                if win32gui.IsWindowVisible(hwnd):
                    title = win32gui.GetWindowText(hwnd)
                    if title:
                        windows.append((hwnd, title))
            except:
                pass

        win32gui.EnumWindows(enum_handler, None)
        return windows

    @staticmethod
    def find_window_by_title(title):
        try:
            hwnd = win32gui.FindWindow(None, title)
            if hwnd and win32gui.IsWindow(hwnd):
                return hwnd
        except:
            pass
        return None


class TaskDialog(tk.Toplevel):
    def __init__(self, parent, task=None):
        super().__init__(parent)
        self.task = task
        self.result = None
        self.setup_ui()

        if task:
            self.title("编辑动作")
            self.countdown_entry.insert(0, str(task.countdown))
            self.x_entry.insert(0, str(task.relative_x))
            self.y_entry.insert(0, str(task.relative_y))
            if task.click_type == "左键点击":
                self.click_type_combo.current(0)
            else:
                self.click_type_combo.current(1)
        else:
            self.title("添加动作")

        self.transient(parent)
        self.grab_set()
        self.geometry("350x280+{}+{}".format(
            parent.winfo_x() + 100, parent.winfo_y() + 100))
        self.wait_window()

    def setup_ui(self):
        frame = ttk.Frame(self, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text="倒计时(秒):").grid(row=0, column=0, sticky=tk.W, pady=8)
        self.countdown_entry = ttk.Entry(frame, width=15)
        self.countdown_entry.grid(row=0, column=1, sticky=tk.W, pady=8)

        ttk.Label(frame, text="相对X坐标:").grid(row=1, column=0, sticky=tk.W, pady=8)
        self.x_entry = ttk.Entry(frame, width=15)
        self.x_entry.grid(row=1, column=1, sticky=tk.W, pady=8)

        ttk.Label(frame, text="相对Y坐标:").grid(row=2, column=0, sticky=tk.W, pady=8)
        self.y_entry = ttk.Entry(frame, width=15)
        self.y_entry.grid(row=2, column=1, sticky=tk.W, pady=8)

        ttk.Label(frame, text="点击类型:").grid(row=3, column=0, sticky=tk.W, pady=8)
        self.click_type_combo = ttk.Combobox(frame, values=["左键点击", "右键点击"],
                                              state="readonly", width=13)
        self.click_type_combo.current(0)
        self.click_type_combo.grid(row=3, column=1, sticky=tk.W, pady=8)

        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=4, column=0, columnspan=2, pady=20)

        ttk.Button(btn_frame, text="确定", command=self.on_ok).pack(side=tk.LEFT, padx=10)
        ttk.Button(btn_frame, text="取消", command=self.on_cancel).pack(side=tk.LEFT, padx=10)

    def on_ok(self):
        try:
            countdown = float(self.countdown_entry.get())
            if countdown < 0:
                messagebox.showwarning("输入错误", "倒计时必须为正数", parent=self)
                return

            rel_x = int(self.x_entry.get())
            rel_y = int(self.y_entry.get())
            if rel_x < 0 or rel_y < 0:
                messagebox.showwarning("输入错误", "坐标必须为非负整数", parent=self)
                return

            click_type = self.click_type_combo.get()
            task_id = self.task.id if self.task else 0
            self.result = ClickTask(task_id, countdown, rel_x, rel_y, click_type)
            self.destroy()
        except ValueError:
            messagebox.showwarning("输入错误", "请输入有效的数字", parent=self)

    def on_cancel(self):
        self.destroy()


class PickDialog(tk.Toplevel):
    def __init__(self, parent, target_window, on_picked_callback):
        super().__init__(parent)
        self.target_window = target_window
        self.on_picked_callback = on_picked_callback
        self.result_x = None
        self.result_y = None
        self.ctrl_pressed = False
        self.setup_ui()
        self.geometry("300x160+{}+{}".format(
            parent.winfo_x() + 150, parent.winfo_y() + 150))
        self.after(500, self.start_pick)

    def setup_ui(self):
        self.title("拾取窗口坐标")
        frame = ttk.Frame(self, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)

        self.label = ttk.Label(frame, text="请将鼠标移到目标窗口内，按 Ctrl+F1 拾取坐标\n或点击 '手动输入' 按钮直接输入坐标",
                              justify=tk.CENTER)
        self.label.pack(pady=10)

        btn_frame = ttk.Frame(frame)
        btn_frame.pack(pady=10)

        self.hotkey_label = ttk.Label(btn_frame, text="快捷键: Ctrl+F1", font=("", 10, "bold"))
        self.hotkey_label.pack(side=tk.LEFT, padx=10)

        ttk.Button(btn_frame, text="手动输入", command=self.manual_input).pack(side=tk.LEFT, padx=10)

    def start_pick(self):
        self.hotkey_listener = keyboard.Listener(
            on_press=self.on_key_press,
            on_release=self.on_key_release
        )
        self.hotkey_listener.start()

    def on_key_press(self, key):
        try:
            if key == keyboard.Key.ctrl_l or key == keyboard.Key.ctrl_r:
                self.ctrl_pressed = True
            elif key == keyboard.Key.f1 and self.ctrl_pressed:
                self.trigger_pick()
        except:
            pass

    def on_key_release(self, key):
        if key == keyboard.Key.ctrl_l or key == keyboard.Key.ctrl_r:
            self.ctrl_pressed = False

    def trigger_pick(self):
        if self.target_window and self.target_window.is_valid():
            try:
                mx, my = win32api.GetCursorPos()
                self.target_window.update_rect()
                rel_x = int((mx - self.target_window.rect[0]) / DPI_SCALE)
                rel_y = int((my - self.target_window.rect[1]) / DPI_SCALE)
                self.finish_pick(rel_x, rel_y)
            except Exception as e:
                print(f"拾取坐标失败: {e}")

    def finish_pick(self, x, y):
        self.result_x = x
        self.result_y = y
        self.label.config(text=f"拾取成功!\n相对坐标: ({x}, {y})")
        if hasattr(self, 'hotkey_listener') and self.hotkey_listener:
            self.hotkey_listener.stop()
        self.after(500, lambda: self._close_and_notify(x, y))

    def _close_and_notify(self, x, y):
        self.destroy()
        if self.on_picked_callback:
            self.on_picked_callback(x, y)

    def manual_input(self):
        dialog = ManualInputDialog(self)
        if dialog.result:
            self.result_x, self.result_y = dialog.result
            if hasattr(self, 'hotkey_listener') and self.hotkey_listener:
                self.hotkey_listener.stop()
            self._close_and_notify(self.result_x, self.result_y)
        else:
            self.destroy()


class ManualInputDialog(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.result = None
        self.setup_ui()
        self.transient(parent)
        self.grab_set()
        self.geometry("250x150+{}+{}".format(
            parent.winfo_x() + 50, parent.winfo_y() + 50))
        self.wait_window()

    def setup_ui(self):
        self.title("手动输入坐标")
        frame = ttk.Frame(self, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text="X坐标:").grid(row=0, column=0, sticky=tk.W, pady=8)
        self.x_entry = ttk.Entry(frame, width=15)
        self.x_entry.grid(row=0, column=1, sticky=tk.W, pady=8)

        ttk.Label(frame, text="Y坐标:").grid(row=1, column=0, sticky=tk.W, pady=8)
        self.y_entry = ttk.Entry(frame, width=15)
        self.y_entry.grid(row=1, column=1, sticky=tk.W, pady=8)

        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=2, column=0, columnspan=2, pady=15)

        ttk.Button(btn_frame, text="确定", command=self.on_ok).pack(side=tk.LEFT, padx=10)
        ttk.Button(btn_frame, text="取消", command=self.destroy).pack(side=tk.LEFT, padx=10)

    def on_ok(self):
        try:
            x = int(self.x_entry.get())
            y = int(self.y_entry.get())
            if x < 0 or y < 0:
                messagebox.showwarning("输入错误", "坐标必须为非负整数", parent=self)
                return
            self.result = (x, y)
            self.destroy()
        except ValueError:
            messagebox.showwarning("输入错误", "请输入有效的整数", parent=self)


class App(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("鼠标点击模拟工具 v1.0")
        self.geometry("850x700")
        self.minsize(700, 450)

        self.target_window = None
        self.tasks = []
        self.task_id_counter = 0
        self.is_running = False
        self.stop_flag = False
        self.mouse_ctrl = MouseController()

        self.setup_ui()
        self.load_config()
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    def setup_ui(self):
        main_frame = ttk.Frame(self, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        self.create_window_selection_area(main_frame)
        self.create_task_list_area(main_frame)
        self.create_button_area(main_frame)
        self.create_control_area(main_frame)
        self.create_status_area(main_frame)

    def create_window_selection_area(self, parent):
        frame = ttk.LabelFrame(parent, text="窗口选择", padding=10)
        frame.pack(fill=tk.X, pady=(0, 10))

        row1 = ttk.Frame(frame)
        row1.pack(fill=tk.X, pady=5)

        ttk.Label(row1, text="窗口列表:").pack(side=tk.LEFT, padx=5)

        self.window_combo = ttk.Combobox(row1, width=50, state="readonly")
        self.window_combo.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)

        ttk.Button(row1, text="刷新", command=self.refresh_windows).pack(side=tk.LEFT, padx=5)
        ttk.Button(row1, text="选择目标窗口", command=self.select_target_window).pack(side=tk.LEFT, padx=5)

        self.target_label = ttk.Label(frame, text="当前未绑定窗口", foreground="gray")
        self.target_label.pack(anchor=tk.W, pady=5)

    def create_task_list_area(self, parent):
        frame = ttk.LabelFrame(parent, text="任务列表", padding=10)
        frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        list_frame = ttk.Frame(frame)
        list_frame.pack(fill=tk.BOTH, expand=True)

        columns = ("序号", "倒计时", "相对坐标", "点击类型")
        self.task_tree = ttk.Treeview(list_frame, columns=columns, show="headings", height=8)

        self.task_tree.heading("序号", text="序号")
        self.task_tree.heading("倒计时", text="倒计时(秒)")
        self.task_tree.heading("相对坐标", text="相对坐标(X, Y)")
        self.task_tree.heading("点击类型", text="点击类型")

        self.task_tree.column("序号", width=60, anchor=tk.CENTER)
        self.task_tree.column("倒计时", width=100, anchor=tk.CENTER)
        self.task_tree.column("相对坐标", width=200, anchor=tk.CENTER)
        self.task_tree.column("点击类型", width=120, anchor=tk.CENTER)

        scrollbar_y = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.task_tree.yview)
        scrollbar_x = ttk.Scrollbar(list_frame, orient=tk.HORIZONTAL, command=self.task_tree.xview)
        self.task_tree.configure(yscrollcommand=scrollbar_y.set, xscrollcommand=scrollbar_x.set)

        self.task_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y)
        scrollbar_x.pack(side=tk.BOTTOM, fill=tk.X)

        self.task_tree.bind("<Double-1>", lambda e: self.edit_selected_task())

    def create_button_area(self, parent):
        frame = ttk.Frame(parent)
        frame.pack(fill=tk.X, pady=(0, 10))

        btn_frame = ttk.Frame(frame)
        btn_frame.pack()

        ttk.Button(btn_frame, text="添加动作", command=self.add_task).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="编辑选中", command=self.edit_selected_task).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="删除选中", command=self.delete_selected_task).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="刷新序号", command=self.refresh_task_ids).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="拾取窗口坐标", command=self.pick_coordinates).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="开始执行", command=self.start_execution).pack(side=tk.LEFT, padx=5)

    def create_control_area(self, parent):
        frame = ttk.LabelFrame(parent, text="控制选项", padding=10)
        frame.pack(fill=tk.X, pady=(0, 10))

        control_frame = ttk.Frame(frame)
        control_frame.pack()

        self.auto_close_var = tk.BooleanVar(value=True)
        self.auto_start_var = tk.BooleanVar(value=False)
        self.minimize_var = tk.BooleanVar(value=False)

        ttk.Checkbutton(control_frame, text="操作完成后5秒自动关闭程序",
                        variable=self.auto_close_var).pack(side=tk.LEFT, padx=10)
        ttk.Checkbutton(control_frame, text="开启后立即自动执行已配置任务",
                        variable=self.auto_start_var).pack(side=tk.LEFT, padx=10)
        ttk.Checkbutton(control_frame, text="执行任务前最小化本窗口",
                        variable=self.minimize_var).pack(side=tk.LEFT, padx=10)

        btn_frame = ttk.Frame(frame)
        btn_frame.pack(pady=5)
        ttk.Button(btn_frame, text="保存设置", command=self.save_config).pack(side=tk.LEFT, padx=5)

    def create_status_area(self, parent):
        frame = ttk.LabelFrame(parent, text="状态提示", padding=10)
        frame.pack(fill=tk.X)

        status_frame = ttk.Frame(frame)
        status_frame.pack(fill=tk.X)

        ttk.Label(status_frame, text="状态:").pack(side=tk.LEFT, padx=5)
        self.status_label = ttk.Label(status_frame, text="就绪", foreground="green")
        self.status_label.pack(side=tk.LEFT, padx=5)

        ttk.Label(status_frame, text="|").pack(side=tk.LEFT, padx=5)

        ttk.Label(status_frame, text="倒计时:").pack(side=tk.LEFT, padx=5)
        self.countdown_label = ttk.Label(status_frame, text="0.0")
        self.countdown_label.pack(side=tk.LEFT, padx=5)

        ttk.Label(status_frame, text="|").pack(side=tk.LEFT, padx=5)

        ttk.Label(status_frame, text="进度:").pack(side=tk.LEFT, padx=5)
        self.progress_label = ttk.Label(status_frame, text="0/0")
        self.progress_label.pack(side=tk.LEFT, padx=5)

        ttk.Label(status_frame, text="|").pack(side=tk.LEFT, padx=5)

        ttk.Label(status_frame, text="拾取坐标:").pack(side=tk.LEFT, padx=5)
        self.picked_coord_label = ttk.Label(status_frame, text="未拾取", foreground="gray")
        self.picked_coord_label.pack(side=tk.LEFT, padx=5)

        self.log_text = tk.Text(frame, height=4, wrap=tk.WORD, state=tk.DISABLED)
        self.log_text.pack(fill=tk.X, pady=10)

    def log_message(self, msg):
        self.log_text.configure(state=tk.NORMAL)
        timestamp = time.strftime("%H:%M:%S")
        self.log_text.insert(tk.END, f"[{timestamp}] {msg}\n")
        self.log_text.see(tk.END)
        self.log_text.configure(state=tk.DISABLED)

    def refresh_windows(self):
        windows = WindowSelector.get_all_windows()
        window_list = [f"{title} (hwnd:{hwnd})" for hwnd, title in windows]
        self.window_combo["values"] = window_list
        if window_list:
            self.window_combo.current(0)
            self.log_message(f"已刷新窗口列表，共 {len(window_list)} 个窗口")

    def select_target_window(self):
        selected = self.window_combo.get()
        if not selected:
            messagebox.showwarning("未选择", "请先选择一个窗口")
            return

        try:
            hwnd = int(selected.split("hwnd:")[1].rstrip(")"))
            title = selected.split(" (hwnd:")[0]
            self.target_window = TargetWindow(hwnd, title)
            if self.target_window.is_valid():
                self.target_label.config(text=f"已绑定: {title}", foreground="green")
                self.log_message(f"已绑定目标窗口: {title}")
                self.save_config()
            else:
                messagebox.showwarning("窗口无效", "选择的窗口已关闭或无效")
                self.target_window = None
                self.target_label.config(text="当前未绑定窗口", foreground="gray")
        except Exception as e:
            messagebox.showwarning("选择错误", f"无法解析窗口信息: {e}")

    def add_task(self):
        dialog = TaskDialog(self)
        if dialog.result:
            self.task_id_counter += 1
            dialog.result.id = self.task_id_counter
            self.tasks.append(dialog.result)
            self.refresh_task_list()
            self.save_config()
            self.log_message(f"添加任务 #{dialog.result.id}: 倒计时{dialog.result.countdown}秒, "
                            f"坐标({dialog.result.relative_x},{dialog.result.relative_y}), "
                            f"{dialog.result.click_type}")

    def edit_selected_task(self):
        selected = self.task_tree.selection()
        if not selected:
            messagebox.showwarning("未选择", "请先选择要编辑的任务")
            return

        task_index = int(self.task_tree.item(selected[0])["values"][0]) - 1
        task = self.tasks[task_index]

        dialog = TaskDialog(self, task)
        if dialog.result:
            self.tasks[task_index] = dialog.result
            self.refresh_task_list()
            self.save_config()
            self.log_message(f"编辑任务 #{dialog.result.id}")

    def delete_selected_task(self):
        selected = self.task_tree.selection()
        if not selected:
            messagebox.showwarning("未选择", "请先选择要删除的任务")
            return

        task_values = self.task_tree.item(selected[0])["values"]
        task_id = int(task_values[0])

        del self.tasks[task_id - 1]
        for i, task in enumerate(self.tasks):
            task.id = i + 1
        self.refresh_task_list()
        self.save_config()
        self.log_message(f"删除任务 #{task_id}")

    def refresh_task_ids(self):
        for i, task in enumerate(self.tasks):
            task.id = i + 1
        self.refresh_task_list()
        self.save_config()
        self.log_message("序号已刷新")

    def pick_coordinates(self):
        if not self.target_window:
            messagebox.showwarning("未绑定窗口", "请先选择并绑定目标窗口")
            return

        self.picked_coord_label.config(text="拾取中...", foreground="blue")
        
        def on_picked(x, y):
            self.picked_coord_label.config(
                text=f"({x}, {y})", foreground="green")
            self.log_message(f"拾取坐标: ({x}, {y})")
            self.add_task_with_coords(x, y)
        
        dialog = PickDialog(self, self.target_window, on_picked)
        dialog.protocol("WM_DELETE_WINDOW", lambda: self._on_pick_cancel(dialog))

    def _on_pick_cancel(self, dialog):
        dialog.destroy()
        self.picked_coord_label.config(text="未拾取", foreground="gray")

    def add_task_with_coords(self, x, y):
        dialog = TaskDialog(self)
        if dialog.result:
            dialog.result.relative_x = x
            dialog.result.relative_y = y
            self.task_id_counter += 1
            dialog.result.id = self.task_id_counter
            self.tasks.append(dialog.result)
            self.refresh_task_list()
            self.save_config()
            self.log_message(f"添加任务 #{dialog.result.id}: 坐标({x},{y})")

    def refresh_task_list(self):
        for item in self.task_tree.get_children():
            self.task_tree.delete(item)

        for task in self.tasks:
            self.task_tree.insert("", tk.END, values=task.to_list())

        self.progress_label.config(text=f"{0}/{len(self.tasks)}")

    def start_execution(self):
        if self.is_running:
            messagebox.showwarning("执行中", "任务正在执行，请勿重复点击")
            return

        if not self.target_window:
            messagebox.showwarning("未绑定窗口", "请先选择并绑定目标窗口")
            return

        if not self.tasks:
            messagebox.showwarning("无任务", "请先添加至少一个点击任务")
            return

        if not self.target_window.is_valid():
            messagebox.showwarning("窗口失效", "目标窗口已关闭，请重新选择")
            self.target_label.config(text="窗口已失效", foreground="red")
            return

        if self.minimize_var.get():
            self.withdraw()

        self.picked_coord_label.config(text="执行中...", foreground="blue")
        self.is_running = True
        self.stop_flag = False
        self.log_message("=" * 40)
        self.log_message("开始执行任务...")
        threading.Thread(target=self.execute_tasks, daemon=True).start()

    def execute_tasks(self):
        try:
            for i, task in enumerate(self.tasks):
                if self.stop_flag:
                    self.log_message("执行已停止")
                    break

                self.target_window.update_rect()
                if not self.target_window.is_valid():
                    self.after(0, lambda: messagebox.showwarning("窗口失效",
                        "目标窗口已关闭，停止执行"))
                    self.after(0, lambda: self.update_status("窗口失效", "red"))
                    self.log_message("错误: 目标窗口已关闭")
                    break

                abs_x, abs_y = self.target_window.get_relative_to_absolute(
                    task.relative_x, task.relative_y)

                if abs_x is None:
                    self.after(0, lambda: messagebox.showwarning("坐标错误", "无法计算目标坐标"))
                    continue

                self.after(0, lambda i=i: self.update_status(f"执行任务 #{i+1}", "blue"))
                self.after(0, lambda i=i: self.progress_label.config(text=f"{i+1}/{len(self.tasks)}"))

                countdown = task.countdown
                while countdown > 0 and not self.stop_flag:
                    self.after(0, lambda c=countdown: self.countdown_label.config(text=f"{c:.1f}"))
                    time.sleep(0.1)
                    countdown -= 0.1

                if self.stop_flag:
                    break

                self.after(0, lambda: self.countdown_label.config(text="0.0"))

                if task.click_type == "左键点击":
                    self.mouse_ctrl.click_left(abs_x, abs_y)
                else:
                    self.mouse_ctrl.click_right(abs_x, abs_y)

                self.log_message(f"执行: #{task.id} - ({abs_x},{abs_y}) {task.click_type}")
                time.sleep(0.3)

            if not self.stop_flag:
                self.log_message("所有任务执行完成!")
                self.after(0, lambda: self.update_status("执行完成", "green"))
                self.after(0, lambda: self.deiconify())

                if self.auto_close_var.get():
                    self.log_message("5秒后自动关闭程序...")
                    self.after(0, lambda: self.update_status("即将关闭", "orange"))
                    threading.Thread(target=self.auto_close, daemon=True).start()
                else:
                    self.is_running = False
            else:
                self.after(0, lambda: self.deiconify())
                self.is_running = False

        except Exception as e:
            self.after(0, lambda: messagebox.showerror("执行错误", f"执行过程中出错: {e}"))
            self.log_message(f"错误: {e}")
            self.is_running = False

    def auto_close(self):
        time.sleep(5)
        self.after(0, self.destroy)

    def update_status(self, text, color="black"):
        self.status_label.config(text=text, foreground=color)

    def save_config(self):
        try:
            config = {
                "window_title": self.target_window.title if self.target_window else None,
                "tasks": [task.to_dict() for task in self.tasks],
                "task_id_counter": self.task_id_counter,
                "auto_close": self.auto_close_var.get(),
                "auto_start": self.auto_start_var.get(),
                "minimize": self.minimize_var.get()
            }
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            self.log_message("设置已保存")
        except Exception as e:
            print(f"保存配置失败: {e}")

    def load_config(self):
        try:
            if os.path.exists(CONFIG_FILE):
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    config = json.load(f)

                if config.get("window_title"):
                    hwnd = WindowSelector.find_window_by_title(config["window_title"])
                    if hwnd:
                        self.target_window = TargetWindow(hwnd, config["window_title"])
                        self.target_label.config(text=f"已绑定: {config['window_title']}", foreground="green")
                        self.log_message(f"已恢复绑定窗口: {config['window_title']}")

                if config.get("tasks"):
                    self.tasks = [ClickTask.from_dict(t) for t in config["tasks"]]
                    self.task_id_counter = config.get("task_id_counter", len(self.tasks))
                    self.refresh_task_list()
                    self.log_message(f"已恢复 {len(self.tasks)} 个任务")

                if config.get("auto_close") is not None:
                    self.auto_close_var.set(config["auto_close"])

                if config.get("auto_start") is not None:
                    self.auto_start_var.set(config["auto_start"])

                if config.get("minimize") is not None:
                    self.minimize_var.set(config["minimize"])

                if self.auto_start_var.get() and self.target_window and self.tasks:
                    self.after(1000, self.start_execution)

        except Exception as e:
            print(f"加载配置失败: {e}")

    def on_closing(self):
        if self.is_running:
            if messagebox.askyesno("退出确认", "任务正在执行，确定要退出吗？"):
                self.stop_flag = True
                self.save_config()
                self.destroy()
        else:
            self.save_config()
            self.destroy()


if __name__ == "__main__":
    app = App()
    app.mainloop()
