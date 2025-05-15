import os
import shutil
import subprocess
import threading
import signal
import sys
import re
import socket
import webbrowser
import ttkbootstrap as tb
from ttkbootstrap.constants import *
from tkinter import filedialog, messagebox, PhotoImage


REPO_URL = "git@github.com:hihabib/Course-Platform.git"
REPO_DIR = "Course-Platform"
COURSES_DIR = os.path.join(REPO_DIR, "public", "courses")
DEV_COMMAND = ["pnpm", "dev"]
IS_WINDOWS = sys.platform.startswith("win")


def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"


class DevServerManager:
    def __init__(self):
        self.process = None
        self.stdout_thread = None

    def clone_repo(self):
        if not os.path.exists(REPO_DIR):
            subprocess.run(["git", "clone", REPO_URL], shell=True)

    def install_dependencies(self):
        subprocess.run("npm install -g pnpm", shell=True)
        subprocess.run("pnpm install", cwd=REPO_DIR, shell=True)

    def git_pull(self):
        subprocess.run("git pull", cwd=REPO_DIR, shell=True)

    def start_dev_server(self, update_status, on_started, on_url_found):
        def run():
            self.clone_repo()
            update_status("Installing dependencies...")
            self.install_dependencies()
            update_status("Pulling latest changes...")
            self.git_pull()
            update_status("Starting dev server...")

            creation_flags = subprocess.CREATE_NEW_PROCESS_GROUP if IS_WINDOWS else 0
            self.process = subprocess.Popen(
                DEV_COMMAND,
                cwd=REPO_DIR,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                shell=True,
                creationflags=creation_flags,
                text=True
            )

            on_started()
            update_status("Dev server running.")

            def monitor_output():
                ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
                url_regex = re.compile(r"https?://[^\s]+")

                for line in self.process.stdout:
                    clean_line = ansi_escape.sub('', line)
                    match = url_regex.search(clean_line)
                    if match:
                        url = match.group(0)
                        on_url_found(url)
                        break

            self.stdout_thread = threading.Thread(target=monitor_output, daemon=True)
            self.stdout_thread.start()

        threading.Thread(target=run, daemon=True).start()

    def stop_dev_server(self, update_status, on_stopped):
        if self.process:
            update_status("Stopping dev server...")
            try:
                if IS_WINDOWS:
                    self.process.send_signal(signal.CTRL_BREAK_EVENT)
                else:
                    self.process.terminate()
            except Exception:
                self.process.kill()
            self.process = None
            update_status("Dev server stopped.")
            on_stopped()


class DevServerUI:
    def __init__(self, root):
        self.manager = DevServerManager()
        self.root = root
        self.root.title("Dev Server Manager")
        self.root.geometry("470x310")
        self.root.resizable(False, False)

        self.dev_server_url_local = ""
        self.dev_server_url_network = ""

        # === Top Margin ===
        tb.Frame(root, height=40).pack()

        # === Button Container ===
        self.button_container = tb.Frame(root)
        self.button_container.pack()

        self.start_button = tb.Button(self.button_container, text="Start Dev Server", bootstyle="success", width=22, command=self.start_server)
        self.stop_button = tb.Button(self.button_container, text="Stop Dev Server", bootstyle="danger", width=22, command=self.stop_server)
        self.add_course_button = tb.Button(self.button_container, text="Add Course", bootstyle="primary", width=22, command=self.add_course)

        self.status_label = tb.Label(self.button_container, text="Status: Dev server stopped.", bootstyle="info", font=("Segoe UI", 9, "bold"))
        self.render_buttons(running=False)

        # === Server URL Display Frame ===
        self.url_frame = tb.Frame(root)

        # Icons
        try:
            self.copy_icon = PhotoImage(file="copy.png")
        except:
            self.copy_icon = None

        # --- Local URL Row ---
        self.local_row = tb.Frame(self.url_frame)
        self.local_prefix = tb.Label(self.local_row, text="Local:   ", font=("Segoe UI", 10, "bold"))
        self.local_label = tb.Label(self.local_row, text="", bootstyle="danger", cursor="hand2", font=("Segoe UI", 10, "underline"))
        self.copy_local_button = tb.Button(self.local_row, image=self.copy_icon if self.copy_icon else None,
                                           text="📋" if not self.copy_icon else "", bootstyle="secondary", command=self.copy_local_url, width=3)
        self.local_prefix.pack(side="left")
        self.local_label.pack(side="left", padx=(0, 5))
        self.copy_local_button.pack(side="left")
        self.local_row.pack(anchor="w", pady=2)

        # --- Network URL Row ---
        self.network_row = tb.Frame(self.url_frame)
        self.network_prefix = tb.Label(self.network_row, text="Network:", font=("Segoe UI", 10, "bold"))
        self.network_label = tb.Label(self.network_row, text="", bootstyle="danger", cursor="hand2", font=("Segoe UI", 10, "underline"))
        self.copy_network_button = tb.Button(self.network_row, image=self.copy_icon if self.copy_icon else None,
                                             text="📋" if not self.copy_icon else "", bootstyle="secondary", command=self.copy_network_url, width=3)
        self.network_prefix.pack(side="left")
        self.network_label.pack(side="left", padx=(0, 5))
        self.copy_network_button.pack(side="left")
        self.network_row.pack(anchor="w", pady=2)

        self.url_frame.pack(pady=5)
        self.url_frame.pack_forget()

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def start_server(self):
        self.start_button.config(state="disabled")
        self.update_status("Starting...")
        self.manager.start_dev_server(
            update_status=self.update_status,
            on_started=lambda: self.render_buttons(running=True),
            on_url_found=self.show_server_urls
        )

    def update_status(self, message):
        self.status_label.config(text=f"Status: {message}")

    def render_buttons(self, running=False):
        for widget in self.button_container.winfo_children():
            widget.pack_forget()

        if running:
            self.stop_button.pack()
        else:
            self.start_button.config(state="normal")
            self.start_button.pack()

        self.add_course_button.pack(pady=(5, 10))
        self.status_label.pack(pady=(0, 5))

    def show_server_urls(self, url):
        ip = get_local_ip()
        self.dev_server_url_local = url
        self.dev_server_url_network = url.replace("localhost", ip).replace("127.0.0.1", ip)

        # Update labels
        self.local_label.config(text=self.dev_server_url_local)
        self.local_label.bind("<Button-1>", lambda e: webbrowser.open(self.dev_server_url_local))

        self.network_label.config(text=self.dev_server_url_network)
        self.network_label.bind("<Button-1>", lambda e: webbrowser.open(self.dev_server_url_network))

        self.url_frame.pack()

        # ✅ Auto-open in browser
        webbrowser.open(self.dev_server_url_network)

    def stop_server(self):
        self.manager.stop_dev_server(
            update_status=self.update_status,
            on_stopped=lambda: (
                self.render_buttons(running=False),
                self.url_frame.pack_forget()  # ✅ Hide the URL section
            )
        )

    def on_close(self):
        self.stop_server()
        self.root.destroy()

    def show_server_urls(self, url):
        ip = get_local_ip()
        self.dev_server_url_local = url
        self.dev_server_url_network = url.replace("localhost", ip).replace("127.0.0.1", ip)

        self.local_label.config(text=self.dev_server_url_local)
        self.local_label.bind("<Button-1>", lambda e: webbrowser.open(self.dev_server_url_local))

        self.network_label.config(text=self.dev_server_url_network)
        self.network_label.bind("<Button-1>", lambda e: webbrowser.open(self.dev_server_url_network))

        self.url_frame.pack()

    def copy_local_url(self):
        self.root.clipboard_clear()
        self.root.clipboard_append(self.dev_server_url_local)
        messagebox.showinfo("Copied", f"Copied to clipboard:\n{self.dev_server_url_local}")

    def copy_network_url(self):
        self.root.clipboard_clear()
        self.root.clipboard_append(self.dev_server_url_network)
        messagebox.showinfo("Copied", f"Copied to clipboard:\n{self.dev_server_url_network}")

    def add_course(self):
        folder_path = filedialog.askdirectory(title="Select Course Folder")
        if not folder_path:
            return

        course_name = os.path.basename(folder_path)
        dest_path = os.path.join(COURSES_DIR, course_name)

        if not os.path.exists(COURSES_DIR):
            os.makedirs(COURSES_DIR)

        def copy_course():
            self.update_status(f"Copying course: {course_name}")
            try:
                if os.path.exists(dest_path):
                    shutil.rmtree(dest_path)
                shutil.copytree(folder_path, dest_path)
                self.update_status(f"Course '{course_name}' copied successfully.")
                messagebox.showinfo("Success", f"Course '{course_name}' added successfully.")
            except Exception as e:
                self.update_status("Copy failed.")
                messagebox.showerror("Error", f"Failed to copy course:\n{str(e)}")

        threading.Thread(target=copy_course, daemon=True).start()


if __name__ == "__main__":
    app = tb.Window(themename="flatly")  # You can also try "superhero" for dark mode
    DevServerUI(app)
    app.mainloop()
