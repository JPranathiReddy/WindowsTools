import ctypes
import tkinter as tk
from tkinter import ttk, messagebox
import psutil
from ctypes import wintypes
import subprocess

# Windows API constants
SW_HIDE = 0
SW_SHOW = 5
SW_MINIMIZE = 6
SW_RESTORE = 9
GWL_EXSTYLE = -20
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_APPWINDOW = 0x00040000

# Load Windows API functions
user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

EnumWindows = user32.EnumWindows
GetWindowText = user32.GetWindowTextW
GetWindowTextLength = user32.GetWindowTextLengthW
IsWindowVisible = user32.IsWindowVisible
ShowWindow = user32.ShowWindow
GetWindowThreadProcessId = user32.GetWindowThreadProcessId
GetWindowLong = user32.GetWindowLongW
SetWindowLong = user32.SetWindowLongW
IsWindow = user32.IsWindow
SetForegroundWindow = user32.SetForegroundWindow

# Global storage for windows
hidden_apps = {}
all_windows = []
all_windows_including_hidden = []


def get_process_name(hwnd):
    """Get the process name for a given window handle"""
    try:
        pid = wintypes.DWORD()
        GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        process = psutil.Process(pid.value)
        return process.name()
    except:
        return "Unknown"


def enum_window_callback(hwnd, lparam):
    """Callback function for EnumWindows - includes hidden windows"""
    if IsWindow(hwnd):
        length = GetWindowTextLength(hwnd)
        if length > 0:
            buff = ctypes.create_unicode_buffer(length + 1)
            GetWindowText(hwnd, buff, length + 1)
            window_title = buff.value

            # Filter out system windows
            if window_title and len(window_title) > 0:
                process_name = get_process_name(hwnd)
                if process_name not in ["dwm.exe", "svchost.exe", "taskhostw.exe"]:
                    all_windows_including_hidden.append({
                        'hwnd': hwnd,
                        'title': window_title,
                        'process': process_name,
                        'visible': bool(IsWindowVisible(hwnd))
                    })
    return True


def refresh_windows():
    """Refresh the list of open windows"""
    global all_windows, all_windows_including_hidden
    all_windows = []
    all_windows_including_hidden = []

    # Create callback type
    WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    callback = WNDENUMPROC(enum_window_callback)

    # Enumerate all windows (including hidden ones)
    EnumWindows(callback, 0)

    # Separate visible and hidden windows
    all_windows = [w for w in all_windows_including_hidden if w['visible']]

    # Update listbox
    update_listbox()
    update_hidden_label()


def update_listbox():
    """Update the listbox with current windows"""
    listbox.delete(0, tk.END)

    if not all_windows:
        listbox.insert(tk.END, "No visible apps found")
        return

    for window in all_windows:
        title = window['title'][:50]  # Truncate long titles
        process = window['process']
        listbox.insert(tk.END, f"📌 {process} | {title}")


def update_hidden_label():
    """Update the hidden apps label"""
    hidden_count = len([w for w in all_windows_including_hidden if not w['visible']])
    if hidden_count > 0:
        hidden_label.config(text=f"⚠️ You have {hidden_count} hidden app(s). Click below to restore them.", fg="red")
    else:
        hidden_label.config(text="No hidden apps", fg="green")


def hide_selected():
    """Hide selected apps from taskbar"""
    selections = listbox.curselection()

    if not selections:
        messagebox.showwarning("Warning", "Please select apps to hide")
        return

    for idx in selections:
        window = all_windows[idx]
        hwnd = window['hwnd']

        try:
            # Get current extended style
            ex_style = GetWindowLong(hwnd, GWL_EXSTYLE)

            # Set TOOLWINDOW style to hide from taskbar
            new_style = ex_style | WS_EX_TOOLWINDOW
            SetWindowLong(hwnd, GWL_EXSTYLE, new_style)

            # Minimize the window
            ShowWindow(hwnd, SW_MINIMIZE)

            # Store in hidden list
            hidden_apps[hwnd] = window['title']

        except Exception as e:
            messagebox.showerror("Error", f"Failed to hide app: {str(e)}")

    messagebox.showinfo("Success", f"Hid {len(selections)} app(s) from taskbar")
    update_listbox()


def show_selected():
    """Show selected hidden apps"""
    selections = listbox.curselection()

    if not selections:
        messagebox.showwarning("Warning", "Please select apps to show")
        return

    for idx in selections:
        window = all_windows[idx]
        hwnd = window['hwnd']

        if hwnd in hidden_apps:
            try:
                # Get current extended style
                ex_style = GetWindowLong(hwnd, GWL_EXSTYLE)

                # Remove TOOLWINDOW style
                new_style = ex_style & ~WS_EX_TOOLWINDOW
                SetWindowLong(hwnd, GWL_EXSTYLE, new_style)

                # Show the window
                ShowWindow(hwnd, SW_SHOW)

                # Remove from hidden list
                del hidden_apps[hwnd]

            except Exception as e:
                messagebox.showerror("Error", f"Failed to show app: {str(e)}")

    messagebox.showinfo("Success", f"Showed {len(selections)} app(s) on taskbar")
    update_listbox()


def show_hidden_window(hwnd):
    """Show a single hidden window"""
    try:
        ex_style = GetWindowLong(hwnd, GWL_EXSTYLE)
        new_style = ex_style & ~WS_EX_TOOLWINDOW
        SetWindowLong(hwnd, GWL_EXSTYLE, new_style)
        ShowWindow(hwnd, SW_RESTORE)
        SetForegroundWindow(hwnd)  # Bring to front
        if hwnd in hidden_apps:
            del hidden_apps[hwnd]
        return True
    except:
        return False


def show_all():
    """Show all hidden apps"""
    hidden_windows = [w for w in all_windows_including_hidden if not w['visible']]

    if not hidden_windows:
        messagebox.showinfo("Info", "No hidden apps to restore")
        return

    count = 0
    for window in hidden_windows:
        if show_hidden_window(window['hwnd']):
            count += 1

    refresh_windows()
    messagebox.showinfo("Success", f"Restored {count} app(s)")


def view_hidden_apps():
    """Show a window with all hidden apps"""
    hidden_windows = [w for w in all_windows_including_hidden if not w['visible']]

    if not hidden_windows:
        messagebox.showinfo("Info", "No hidden apps")
        return

    # Create a new window
    hidden_win = tk.Toplevel(root)
    hidden_win.title("Hidden Apps")
    hidden_win.geometry("600x400")

    label = tk.Label(hidden_win, text="Click an app to restore it:", font=("Arial", 10))
    label.pack(padx=10, pady=10)

    hidden_listbox = tk.Listbox(hidden_win, font=("Courier", 9))
    hidden_listbox.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    for i, window in enumerate(hidden_windows):
        title = window['title'][:60]
        hidden_listbox.insert(tk.END, f"🔒 {window['process']} | {title}")

    def restore_selected():
        selection = hidden_listbox.curselection()
        if not selection:
            messagebox.showwarning("Warning", "Please select an app")
            return

        idx = selection[0]
        hwnd = hidden_windows[idx]['hwnd']
        if show_hidden_window(hwnd):
            messagebox.showinfo("Success", f"Restored: {hidden_windows[idx]['title']}")
            refresh_windows()
            hidden_win.destroy()
        else:
            messagebox.showerror("Error", "Failed to restore app")

    restore_btn = tk.Button(hidden_win, text="✓ Restore Selected", command=restore_selected, bg="#FF9800", fg="white")
    restore_btn.pack(padx=10, pady=10)

    def restore_all_from_window():
        for window in hidden_windows:
            show_hidden_window(window['hwnd'])
        refresh_windows()
        messagebox.showinfo("Success", "Restored all apps")
        hidden_win.destroy()

    restore_all_btn = tk.Button(hidden_win, text="Restore All", command=restore_all_from_window, bg="#f44336", fg="white")
    restore_all_btn.pack(padx=10, pady=5, fill=tk.X)


# Create main window
root = tk.Tk()
root.title("Taskbar App Hider")
root.geometry("700x500")
root.resizable(True, True)

# Title label
title_label = tk.Label(root, text="Hide Apps from Taskbar", font=("Arial", 14, "bold"))
title_label.pack(padx=10, pady=10)

# Hidden apps warning label
hidden_label = tk.Label(root, text="No hidden apps", font=("Arial", 10), fg="green")
hidden_label.pack(padx=10, pady=5)

# Instructions
instructions = tk.Label(root, text="Select apps and click 'Hide' to hide them from taskbar.\n(Multi-select with Ctrl+Click or Shift+Click)",
                        font=("Arial", 9), fg="gray")
instructions.pack(padx=10, pady=5)

# Create frame for listbox and scrollbar
list_frame = tk.Frame(root)
list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

# Scrollbar
scrollbar = tk.Scrollbar(list_frame)
scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

# Listbox
listbox = tk.Listbox(list_frame, selectmode=tk.MULTIPLE, yscrollcommand=scrollbar.set, font=("Courier", 9))
listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
scrollbar.config(command=listbox.yview)

# Button frame
button_frame = tk.Frame(root)
button_frame.pack(fill=tk.X, padx=10, pady=10)

refresh_btn = tk.Button(button_frame, text="🔄 Refresh", command=refresh_windows, bg="#4CAF50", fg="white", padx=10)
refresh_btn.pack(side=tk.LEFT, padx=5)

hide_btn = tk.Button(button_frame, text="👁️ Hide Selected", command=hide_selected, bg="#2196F3", fg="white", padx=10)
hide_btn.pack(side=tk.LEFT, padx=5)

show_btn = tk.Button(button_frame, text="✓ Show Selected", command=show_selected, bg="#FF9800", fg="white", padx=10)
show_btn.pack(side=tk.LEFT, padx=5)

show_all_btn = tk.Button(button_frame, text="Show All", command=show_all, bg="#f44336", fg="white", padx=10)
show_all_btn.pack(side=tk.LEFT, padx=5)

# Button frame 2 for hidden apps
button_frame2 = tk.Frame(root)
button_frame2.pack(fill=tk.X, padx=10, pady=5)

view_hidden_btn = tk.Button(button_frame2, text="🔍 View Hidden Apps", command=view_hidden_apps, bg="#9C27B0", fg="white", padx=10)
view_hidden_btn.pack(side=tk.LEFT, padx=5)

# Initial window load
refresh_windows()

# Run the GUI
root.mainloop()
