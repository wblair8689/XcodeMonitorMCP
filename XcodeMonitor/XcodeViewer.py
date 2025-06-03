#!/usr/bin/env python3
"""
Xcode LSP and Diagnostics Monitor

A comprehensive monitoring tool for Xcode projects that shows:
1. Project and workspace information
2. Build server and SourceKit-LSP status
3. Real-time diagnostics from multiple sources (Xcode live, build logs, etc.)
4. Build information and history

This tool is designed to be the foundation for an AI-powered Xcode assistant
that can monitor errors and diagnostics in real-time.

Xcode LSP Diagnostic Viewer
Shows real-time diagnostics from sourcekit-lsp for your Xcode project
"""

import sys
import os
import threading
import queue
import time
import subprocess
from pathlib import Path
import glob
import json
import hashlib
import tkinter as tk
from tkinter import ttk, scrolledtext
from datetime import datetime
from xcode_monitor_core import (
    find_workspace_and_project,
    ensure_build_server_config,
    run_build,
    get_diagnostics
)

class TextRedirector:
    def __init__(self, text_widget, tag="stdout"):
        self.text_widget = text_widget
        self.tag = tag
    def write(self, str_):
        if str_:
            self.text_widget.after(0, self._append, str_)
    def flush(self):
        pass
    def _append(self, str_):
        self.text_widget.insert(tk.END, str_)
        self.text_widget.see(tk.END)

class XcodeLSPMonitor:
    """Main monitor application"""
    def __init__(self, root_path=None):
        self.root_path = os.path.abspath(root_path) if root_path else os.getcwd()
        self.root = tk.Tk()
        self.root.title(f"Xcode LSP Monitor")
        self.root.geometry("1100x650")
        self.monitoring = False
        self.monitor_thread = None
        self.file_monitor_thread = None
        self.update_queue = None
        self.last_file_hashes = {}
        self.monitored_extensions = [".swift", ".m", ".h", ".mm", ".c", ".cpp"]
        self.log_panel = None
        self._setup_logging()
        self.start()

    def _setup_logging(self):
        # Will be called before UI setup, so create a dummy widget for now
        self._log_buffer = []
        class Dummy:
            def insert(self, *a, **k): pass
            def see(self, *a, **k): pass
            def after(self, *a, **k): pass
        self.log_panel = Dummy()
        sys.stdout = TextRedirector(self, "stdout")
        sys.stderr = TextRedirector(self, "stderr")

    def log_message(self, message):
        if hasattr(self.log_panel, 'insert'):
            self.log_panel.after(0, lambda: self._append_log(message))
        else:
            self._log_buffer.append(message)
    def _append_log(self, message):
        self.log_panel.insert(tk.END, message)
        self.log_panel.see(tk.END)


    def start(self):
        """(Re)initialize UI and restart all background monitoring."""
        self.stop_all_threads()
        self.last_file_hashes = {}
        self.update_queue = queue.Queue()
        for widget in self.root.winfo_children():
            widget.destroy()
        self.setup_ui()
        self.monitoring = True
        self.monitor_thread = threading.Thread(target=self.monitor_loop, daemon=True)
        self.monitor_thread.start()
        self.file_monitor_thread = threading.Thread(target=self.file_monitor_loop, daemon=True)
        self.file_monitor_thread.start()
        self.process_queue()

    def stop_all_threads(self):
        self.monitoring = False
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=1)
        if self.file_monitor_thread and self.file_monitor_thread.is_alive():
            self.file_monitor_thread.join(timeout=1)

    def setup_ui(self):
        paned = tk.PanedWindow(self.root, orient=tk.HORIZONTAL, sashrelief=tk.RAISED, sashwidth=6)
        paned.pack(fill=tk.BOTH, expand=1)

        # Left: main viewer content
        main_frame = ttk.Frame(paned, padding="10")
        paned.add(main_frame, stretch="always")
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(0, weight=0)
        main_frame.rowconfigure(1, weight=0)
        main_frame.rowconfigure(2, weight=2)
        main_frame.rowconfigure(3, weight=1)
        main_frame.rowconfigure(4, weight=0)
        self.path_var = tk.StringVar(value=self.root_path)
        path_entry = ttk.Entry(main_frame, textvariable=self.path_var, width=60)
        path_entry.grid(row=0, column=0, sticky=tk.W, pady=(0, 8))
        change_btn = ttk.Button(main_frame, text="Change Path", command=self.change_project_path)
        change_btn.grid(row=0, column=1, sticky=tk.W, padx=(8, 0), pady=(0, 8))
        status_frame = ttk.LabelFrame(main_frame, text="Status", padding="10")
        status_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        self.status_labels = {}
        status_items = [
            ("project", "Project:"),
            ("build_server", "Build Server:"),
            ("lsp", "SourceKit-LSP:"),
            ("last_build", "Last Build:")
        ]
        for i, (key, label) in enumerate(status_items):
            ttk.Label(status_frame, text=label).grid(row=i, column=0, sticky=tk.W, pady=2)
            if key == "project":
                self.status_labels[key] = scrolledtext.ScrolledText(status_frame, height=5, width=50)
                self.status_labels[key].insert(tk.END, "Checking...")
                self.status_labels[key].config(state=tk.DISABLED)
            else:
                self.status_labels[key] = ttk.Label(status_frame, text="Checking...")
            self.status_labels[key].grid(row=i, column=1, sticky=tk.W, pady=2)
        diag_frame = ttk.LabelFrame(main_frame, text="Diagnostics", padding="10")
        diag_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)
        diag_frame.columnconfigure(0, weight=1)
        diag_frame.rowconfigure(0, weight=1)
        self.diagnostics_text = scrolledtext.ScrolledText(diag_frame, height=15, width=80)
        self.diagnostics_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        build_frame = ttk.LabelFrame(main_frame, text="Build Information", padding="10")
        build_frame.grid(row=3, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)
        build_frame.columnconfigure(0, weight=1)
        build_frame.rowconfigure(0, weight=1)
        self.build_text = scrolledtext.ScrolledText(build_frame, height=8, width=80)
        self.build_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=4, column=0, columnspan=2, pady=10)
        ttk.Button(button_frame, text="Refresh", command=self.refresh).grid(row=0, column=0, padx=5)
        ttk.Button(button_frame, text="Clear", command=self.clear_diagnostics).grid(row=0, column=1, padx=5)
        ttk.Button(button_frame, text="Build", command=self.trigger_build).grid(row=0, column=2, padx=5)
        ttk.Button(button_frame, text="Quit", command=self.quit).grid(row=0, column=3, padx=5)
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(1, weight=1)
        diag_frame.columnconfigure(0, weight=1)
        diag_frame.rowconfigure(0, weight=1)

        # Right: log panel
        log_frame = ttk.Frame(paned, padding="5")
        log_label = ttk.Label(log_frame, text="Logs", font=("TkDefaultFont", 10, "bold"))
        log_label.pack(anchor=tk.W)
        self.log_panel = scrolledtext.ScrolledText(log_frame, height=40, width=40, state=tk.NORMAL)
        self.log_panel.pack(fill=tk.BOTH, expand=1)
        paned.add(log_frame, minsize=300)

        # If any logs were buffered before UI ready, flush them now
        if hasattr(self, '_log_buffer') and self._log_buffer:
            for msg in self._log_buffer:
                self.log_panel.insert(tk.END, msg)
            self.log_panel.see(tk.END)
            self._log_buffer = []
        # Re-redirect stdout/stderr now that log_panel exists
        sys.stdout = TextRedirector(self.log_panel, "stdout")
        sys.stderr = TextRedirector(self.log_panel, "stderr")

    def change_project_path(self):
        print("[UI] Change Path button pressed.")
        new_path = self.path_var.get().strip()
        if not new_path:
            print("[UI] No new path provided.")
            return
        print(f"[UI] Changing project path to: {new_path}")
        self.root_path = new_path
        self.stop_all_threads()
        self.start()


    def monitor_loop(self):
        while self.monitoring:
            try:
                project_info = self.check_project_status()
                self.update_queue.put(("status", "project", project_info))
                build_server_info = self.check_build_server()
                self.update_queue.put(("status", "build_server", build_server_info))
                lsp_info = self.check_lsp_status()
                self.update_queue.put(("status", "lsp", lsp_info))
                build_info = self.check_recent_builds()
                self.update_queue.put(("status", "last_build", build_info))
                diagnostics = self.get_diagnostics()
                self.update_queue.put(("diagnostics", diagnostics))
                build_details = self.get_build_details()
                self.update_queue.put(("build_info", build_details))
            except Exception as e:
                self.update_queue.put(("error", str(e)))
            time.sleep(5)

    def file_monitor_loop(self):
        while self.monitoring:
            try:
                project_dirs = []
                if Path('buildServer.json').exists():
                    with open('buildServer.json', 'r') as f:
                        config = json.load(f)
                        if 'workspace' in config:
                            workspace_dir = os.path.dirname(config['workspace'])
                            project_dirs.append(workspace_dir)
                if not project_dirs:
                    project_dirs.append(os.getcwd())
                    for proj in Path('.').glob('*.xcodeproj'):
                        project_dirs.append(str(proj))
                changed_files = []
                for directory in project_dirs:
                    for ext in self.monitored_extensions:
                        pattern = os.path.join(directory, '**', f'*{ext}')
                        for file_path in glob.glob(pattern, recursive=True):
                            if 'DerivedData' in file_path or '/build/' in file_path:
                                continue
                            try:
                                with open(file_path, 'rb') as f:
                                    file_hash = hashlib.md5(f.read()).hexdigest()
                                if file_path in self.last_file_hashes and self.last_file_hashes[file_path] != file_hash:
                                    changed_files.append(file_path)
                                self.last_file_hashes[file_path] = file_hash
                            except Exception as file_err:
                                print(f"Error hashing file {file_path}: {file_err}")
                if changed_files:
                    self.update_queue.put(("diagnostics", [{
                        'severity': 'info',
                        'file': os.path.basename(f),
                        'line': 1,
                        'message': f"File changed: {os.path.basename(f)}"
                    } for f in changed_files[:5]]))
                    threading.Thread(target=self.get_diagnostics, daemon=True).start()
            except Exception as e:
                print(f"File monitoring error: {e}")
            time.sleep(2)

    def check_build_server(self):
        try:
            if Path('buildServer.json').exists():
                with open('buildServer.json', 'r') as f:
                    config = json.load(f)
                    return f" Configured ({config.get('name', 'xcode')})"
            else:
                return " Not configured"
        except Exception as e:
            return f"Error: {e}"

    def check_lsp_status(self):
        try:
            result = subprocess.run(
                ['xcrun', '--find', 'sourcekit-lsp'],
                capture_output=True,
                text=True,
                timeout=2
            )
            if result.returncode == 0 and result.stdout.strip():
                path = result.stdout.strip()
                return f" Available at {os.path.basename(path)}"
            else:
                return " Not available"
        except Exception as e:
            return f"Error: {e}"

    def check_project_status(self):
        try:
            project_name = os.path.basename(os.getcwd())
            workspaces = list(Path('.').glob('*.xcworkspace'))
            projects = list(Path('.').glob('*.xcodeproj'))
            status = []
            if workspaces:
                status.append(f"Workspace: {workspaces[0].name}")
                try:
                    workspace_path = workspaces[0] / 'contents.xcworkspacedata'
                    if workspace_path.exists():
                        with open(workspace_path, 'r') as f:
                            contents = f.read()
                            import re
                            project_refs = re.findall(r'location = "group:(.*\.xcodeproj)', contents)
                            if project_refs:
                                status.append(f"Referenced projects: {', '.join(os.path.basename(p) for p in project_refs)}")
                except Exception as workspace_err:
                    status.append(f"Workspace parse error: {workspace_err}")
            if projects:
                if not workspaces:
                    status.append(f"Projects: {', '.join(p.name for p in projects)}")
            if Path('buildServer.json').exists():
                with open('buildServer.json', 'r') as f:
                    config = json.load(f)
                    if 'workspace' in config:
                        status.append(f"Build server workspace: {os.path.basename(config['workspace'])}")
                    if 'scheme' in config:
                        status.append(f"Active scheme: {config['scheme']}")
            return '\n'.join(status) if status else f"{project_name} (no Xcode projects found)"
        except Exception as e:
            return f"Error: {e}"

    def check_recent_builds(self):
        try:
            derived_data = Path.home() / "Library/Developer/Xcode/DerivedData"
            recent_logs = []
            for log_file in derived_data.rglob("*.xcactivitylog"):
                if log_file.stat().st_mtime > time.time() - 86400:
                    recent_logs.append(log_file)
            if recent_logs:
                most_recent = max(recent_logs, key=lambda p: p.stat().st_mtime)
                age = time.time() - most_recent.stat().st_mtime
                if age < 3600:
                    return f" {int(age/60)} minutes ago"
                else:
                    return f" {int(age/3600)} hours ago"
            else:
                return "No recent builds"
        except Exception as e:
            return f"Error: {e}"

    def get_build_details(self):
        try:
            if not Path('buildServer.json').exists():
                return "No build server configuration found"
            with open('buildServer.json', 'r') as f:
                config = json.load(f)
            details = []
            details.append(f"Build server: {config.get('name', 'unknown')}")
            if 'arguments' in config:
                details.append(f"Arguments: {' '.join(config['arguments'][:5])}...")
            if 'workingDirectory' in config:
                details.append(f"Working directory: {config['workingDirectory']}")
            return '\n'.join(details)
        except Exception as e:
            return f"Error getting build details: {e}"

    def get_diagnostics(self):
        try:
            return get_diagnostics()
        except Exception as e:
            print(f"Error getting diagnostics: {e}")
            return []

    def process_queue(self):
        try:
            while not self.update_queue.empty():
                update_type, *data = self.update_queue.get_nowait()
                if update_type == "status":
                    key, value = data
                    if key in self.status_labels:
                        if key == "project":
                            self.status_labels[key].config(state=tk.NORMAL)
                            self.status_labels[key].delete(1.0, tk.END)
                            self.status_labels[key].insert(tk.END, value)
                            self.status_labels[key].config(state=tk.DISABLED)
                        else:
                            self.status_labels[key].config(text=value)
                elif update_type == "diagnostics":
                    self.update_diagnostics(data[0])
                elif update_type == "build_info":
                    self.build_text.delete(1.0, tk.END)
                    self.build_text.insert(tk.END, data[0])
                elif update_type == "error":
                    self.diagnostics_text.insert(tk.END, f"\nError: {data[0]}\n")
                    self.diagnostics_text.see(tk.END)
        except Exception as e:
            print(f"Error processing queue: {e}")
        self.root.after(100, self.process_queue)

    def update_diagnostics(self, diagnostics):
        if not diagnostics:
            return
        timestamp = datetime.now().strftime('%H:%M:%S')
        self.diagnostics_text.insert(tk.END, f"\n--- Diagnostics update: {timestamp} ---\n")
        by_source = {}
        for diag in diagnostics:
            source = diag.get('source', 'unknown')
            if source not in by_source:
                by_source[source] = []
            by_source[source].append(diag)
        for source, source_diags in by_source.items():
            self.diagnostics_text.insert(tk.END, f"\n[{source.upper()}]\n")
            for diag in source_diags:
                severity = diag.get('severity', 'info')
                prefix = "" if severity == 'error' else "" if severity == 'warning' else ""
                file_path = diag.get('file', 'Unknown')
                line = diag.get('line', 0)
                message = diag.get('message', 'Unknown issue')
                file_info = f"{os.path.basename(file_path)}:{line}"
                self.diagnostics_text.insert(tk.END, f"{prefix} {file_info} - {message}\n")
        self.diagnostics_text.see(tk.END)

    def refresh(self):
        self.diagnostics_text.insert(tk.END, "\n--- Manual refresh ---\n")
        self.diagnostics_text.see(tk.END)
        threading.Thread(target=self.check_project_status, daemon=True).start()

    def clear_diagnostics(self):
        self.diagnostics_text.delete(1.0, tk.END)
        self.diagnostics_text.insert(tk.END, "Diagnostics cleared\n")

    def trigger_build(self):
        self.diagnostics_text.insert(tk.END, "\n--- Triggering build ---\n")
        self.diagnostics_text.see(tk.END)
        threading.Thread(target=self.build, daemon=True).start()

    def build(self):
        try:
            workspaces = list(Path('.').glob('*.xcworkspace'))
            projects = list(Path('.').glob('*.xcodeproj'))
            scheme = "default"
            build_target = None
            build_type = None
            if Path('buildServer.json').exists():
                with open('buildServer.json', 'r') as f:
                    config = json.load(f)
                    args = config.get('arguments', [])
                    for i, arg in enumerate(args):
                        if arg == '-scheme' and i + 1 < len(args):
                            scheme = args[i + 1]
            if workspaces:
                workspace = workspaces[0]
                build_target = str(workspace)
                build_type = 'workspace'
                cmd = ['xcodebuild', '-workspace', build_target, '-scheme', scheme, 'build']
            elif projects:
                project = projects[0]
                build_target = str(project)
                build_type = 'project'
                cmd = ['xcodebuild', '-project', build_target, '-scheme', scheme, 'build']
            else:
                self.update_queue.put(("error", "No workspace or project found"))
                return
            self.update_queue.put(("build_info", f"Running: {' '.join(cmd)}"))
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True
            )
            for line in process.stdout:
                if line.strip():
                    self.update_queue.put(("build_info", line.strip()))
            process.wait()
            if process.returncode == 0:
                self.update_queue.put(("build_info", "Build completed successfully"))
            else:
                self.update_queue.put(("build_info", f"Build failed with code {process.returncode}"))
        except Exception as e:
            self.update_queue.put(("error", f"Build error: {e}"))

    def quit(self):
        self.monitoring = False
        self.root.quit()

    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    print("Starting Xcode LSP Monitor...")
    import argparse
    parser = argparse.ArgumentParser(description="Xcode LSP and Diagnostics Monitor")
    parser.add_argument('--root', type=str, default=None, help='Project/workspace directory to monitor (default: current directory)')
    args = parser.parse_args()
    if args.root:
        os.chdir(args.root)
    monitor = XcodeLSPMonitor(root_path=args.root)
    monitor.run()





