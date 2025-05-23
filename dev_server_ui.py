import os
import shutil
import subprocess
import threading
import signal
import sys
import re
import socket
import webbrowser
from datetime import datetime
import ttkbootstrap as tb
from ttkbootstrap.constants import *
import tempfile
from tkinter import filedialog, messagebox, PhotoImage

TEMP_DIR = os.path.join(tempfile.gettempdir(), "course_platform_temp")
os.makedirs(TEMP_DIR, exist_ok=True)
REPO_DIR = os.path.join(TEMP_DIR, "Course-Platform")
LOG_DIR = os.path.join(TEMP_DIR, "CoursePlatformLogs")
os.makedirs(LOG_DIR, exist_ok=True)
REPO_URL = "https://github.com/hihabib/Course-Platform.git"
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

    def clone_repo(self, log_file):
        if not os.path.exists(REPO_DIR):
            subprocess.run(["git", "clone", REPO_URL, REPO_DIR], shell=True, stdout=log_file, stderr=log_file, check=True)

    def install_dependencies(self, log_file):
        subprocess.run("npm install -g pnpm", shell=True, stdout=log_file, stderr=log_file, check=True)
        subprocess.run("pnpm install", cwd=REPO_DIR, shell=True, stdout=log_file, stderr=log_file, check=True)

    def git_pull(self, log_file):
        subprocess.run("git pull", cwd=REPO_DIR, shell=True, stdout=log_file, stderr=log_file, check=True)

    def node_sync(self, log_file):
        subprocess.run("node sync.js", cwd=REPO_DIR, shell=True, stdout=log_file, stderr=log_file, check=True)

    def start_dev_server(self, update_status, on_started, on_url_found, reset_button):
        def run():
            timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
            log_file_path = os.path.join(LOG_DIR, f"dev-server-{timestamp}.log")
            log_file = open(log_file_path, "w", encoding="utf-8")

            try:
                self.clone_repo(log_file)
                update_status("Installing dependencies...")
                self.install_dependencies(log_file)
                update_status("Pulling latest changes...")
                self.git_pull(log_file)
                # ✅ Ensure the public/courses folder exists
                if not os.path.exists(COURSES_DIR):
                    os.makedirs(COURSES_DIR, exist_ok=True)
                update_status("Syncing node modules...")
                self.node_sync(log_file)
                update_status("Starting server...")

                creation_flags = subprocess.CREATE_NEW_PROCESS_GROUP if IS_WINDOWS else 0
                self.process = subprocess.Popen(
                    DEV_COMMAND,
                    cwd=REPO_DIR,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    shell=True,
                    creationflags=creation_flags,
                    text=True,
                    universal_newlines=True
                )

                on_started()
                update_status("Server running.")

                def monitor_output():
                    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
                    url_regex = re.compile(r"https?://[^\s]+")

                    for line in self.process.stdout:
                        clean_line = ansi_escape.sub('', line)
                        log_file.write(clean_line)
                        log_file.flush()

                        match = url_regex.search(clean_line)
                        if match:
                            url = match.group(0)
                            on_url_found(url)
                            break

                    self.process.wait()
                    log_file.close()

                self.stdout_thread = threading.Thread(target=monitor_output, daemon=True)
                self.stdout_thread.start()

            except subprocess.CalledProcessError as e:
                error_message = f"Setup failed. See log:\n{log_file_path}"
                update_status(error_message)
                log_file.write(f"\nFAILED: {str(e)}\n")
                log_file.close()
                reset_button()
                messagebox.showerror("Setup Error", error_message)

        threading.Thread(target=run, daemon=True).start()

    def stop_dev_server(self, update_status, on_stopped):
        if self.process:
            update_status("Stopping server...")
            try:
                if IS_WINDOWS:
                    self.process.send_signal(signal.CTRL_BREAK_EVENT)
                else:
                    self.process.terminate()
            except Exception:
                self.process.kill()
            self.process = None
            update_status("Server stopped.")
            on_stopped()

class DevServerUI:
    def __init__(self, root):
        self.manager = DevServerManager()
        self.root = root
        self.root.title("Course Platform")
        self.root.geometry("470x310")
        self.root.resizable(False, False)

        self.dev_server_url_local = ""
        self.dev_server_url_network = ""

        tb.Frame(root, height=40).pack()

        self.button_container = tb.Frame(root)
        self.button_container.pack()

        self.start_button = tb.Button(self.button_container, text="Start Server", bootstyle="success", width=22, command=self.start_server)
        self.stop_button = tb.Button(self.button_container, text="Stop Server", bootstyle="danger", width=22, command=self.stop_server)
        self.add_course_button = tb.Button(self.button_container, text="Add Course", bootstyle="primary", width=22, command=self.add_course)

        self.status_label = tb.Label(self.button_container, text="Status: Server stopped.", bootstyle="info", font=("Segoe UI", 9, "bold"))
        self.render_buttons(running=False)

        self.url_frame = tb.Frame(root)

        try:
            self.copy_icon = PhotoImage(file="copy.png")
        except:
            self.copy_icon = None

        self.local_row = tb.Frame(self.url_frame)
        self.local_prefix = tb.Label(self.local_row, text="Local:   ", font=("Segoe UI", 10, "bold"))
        self.local_label = tb.Label(self.local_row, text="", bootstyle="danger", cursor="hand2", font=("Segoe UI", 10, "underline"))
        self.copy_local_button = tb.Button(self.local_row, image=self.copy_icon if self.copy_icon else None,
                                           text="📋" if not self.copy_icon else "", bootstyle="secondary", command=self.copy_local_url, width=3)
        self.local_prefix.pack(side="left")
        self.local_label.pack(side="left", padx=(0, 5))
        self.copy_local_button.pack(side="left")
        self.local_row.pack(anchor="w", pady=2)

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

    def start_server(self):
        if self.manager.process:
            return
        self.start_button.config(state="disabled")
        self.update_status("Starting...")
        self.manager.start_dev_server(
            update_status=self.update_status,
            on_started=lambda: self.render_buttons(running=True),
            on_url_found=self.show_server_urls,
            reset_button=lambda: self.start_button.config(state="normal")
        )

    def stop_server(self):
        self.manager.stop_dev_server(
            update_status=self.update_status,
            on_stopped=lambda: (
                self.render_buttons(running=False),
                self.url_frame.pack_forget()
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
        webbrowser.open(self.dev_server_url_local)

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
    app = tb.Window(themename="flatly")
    DevServerUI(app)
    app.mainloop()
