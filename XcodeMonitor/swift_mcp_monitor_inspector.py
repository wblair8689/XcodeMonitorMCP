"""
Inspector UI for Swift MCP Monitor (Tkinter-based)
"""
import tkinter as tk
from tkinter import ttk, scrolledtext
from datetime import datetime
import threading
import argparse
import os
from swift_mcp_monitor import SwiftMCPMonitorCore

class SwiftMCPMonitorInspector:
    def __init__(self, root_path=None):
        self.core = SwiftMCPMonitorCore(root_path=root_path)
        self.root = tk.Tk()
        self.root.title(f"Swift MCP Monitor Inspector - {self.core.root_path}")
        self.root.geometry("800x600")
        self.setup_ui()
        self.process_queue()
    def setup_ui(self):
        self.xclog_filter_enabled = True  # default: filter enabled
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(0, weight=0)
        main_frame.rowconfigure(1, weight=0)
        main_frame.rowconfigure(2, weight=2)
        main_frame.rowconfigure(3, weight=1)
        main_frame.rowconfigure(4, weight=0)
        self.path_label = ttk.Label(main_frame, text=f"Monitoring: {self.core.root_path}", font=("TkDefaultFont", 10, "italic"))
        self.path_label.grid(row=0, column=0, columnspan=2, sticky=tk.W, pady=(0, 8))
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
        ttk.Button(button_frame, text="Change Path...", command=self.change_path).grid(row=0, column=2, padx=5)
        ttk.Button(button_frame, text="Quit", command=self.quit).grid(row=0, column=3, padx=5)
        # Add xclogparser filter toggle
        self.xclog_toggle_var = tk.BooleanVar(value=True)
        xclog_toggle = ttk.Checkbutton(button_frame, text="Only show xclogparser diagnostics from current project/workspace", variable=self.xclog_toggle_var, command=self.on_xclog_toggle)
        xclog_toggle.grid(row=1, column=0, columnspan=4, sticky=tk.W, pady=(8,0))
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(1, weight=1)
        diag_frame.columnconfigure(0, weight=1)
        diag_frame.rowconfigure(0, weight=1)
    def process_queue(self):
        try:
            while not self.core.update_queue.empty():
                update_type, *data = self.core.update_queue.get_nowait()
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
    def on_xclog_toggle(self):
        self.xclog_filter_enabled = self.xclog_toggle_var.get()
        self.refresh()

    def update_diagnostics(self, diagnostics):
        import json
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
                prefix = "❌" if severity == 'error' else "⚠️" if severity == 'warning' else "ℹ️"
                file_path = diag.get('file', 'Unknown')
                line = diag.get('line', 0)
                message = diag.get('message', 'Unknown issue')
                file_info = f"{os.path.basename(file_path)}:{line}"
                # Show workspace/project path if present
                workspace_path = diag.get('workspacePath')
                if workspace_path:
                    self.diagnostics_text.insert(tk.END, f"  Project/Workspace: {workspace_path}\n")
                # Show xclogparser log path if present
                if diag.get('source') == 'xclogparser' and diag.get('log_path'):
                    self.diagnostics_text.insert(tk.END, f"  XCLog Log Path: {diag['log_path']}\n")
                self.diagnostics_text.insert(tk.END, f"{prefix} {file_info} - {message}\n")
                # Show all available metadata for inspection
                raw_metadata = diag.get('raw_metadata')
                if raw_metadata:
                    pretty = json.dumps(raw_metadata, indent=2, ensure_ascii=False)
                    self.diagnostics_text.insert(tk.END, f"    [Metadata]\n{pretty}\n")
        self.diagnostics_text.see(tk.END)
    def refresh(self):
        self.diagnostics_text.insert(tk.END, "\n--- Manual refresh ---\n")
        self.diagnostics_text.see(tk.END)
        # Optionally, you could trigger a backend refresh here
        # (Current backend runs periodic updates, so this is mostly UI)
        # If you want to force immediate diagnostics update, you could add a method in the core.
        # For now, just clear and let the next update show new results.
        # If you want to pass the toggle to the backend, you could set a property or use a callback.

    def clear_diagnostics(self):
        self.diagnostics_text.delete(1.0, tk.END)
        self.diagnostics_text.insert(tk.END, "Diagnostics cleared\n")
    def change_path(self):
        import tkinter.filedialog
        import queue as queue_mod
        new_path = tkinter.filedialog.askdirectory(title="Select new project/workspace directory", initialdir=self.core.root_path)
        if new_path and os.path.isdir(new_path) and os.path.abspath(new_path) != os.path.abspath(self.core.root_path):
            # Stop current core and threads
            self.core.stop()
            self.core.join_threads()
            # Clear UI fields BEFORE creating new core
            for key, widget in self.status_labels.items():
                if hasattr(widget, 'delete'):
                    widget.config(state=tk.NORMAL)
                    widget.delete(1.0, tk.END)
                    widget.insert(tk.END, "Checking...")
                    widget.config(state=tk.DISABLED)
                else:
                    widget.config(text="Checking...")
            self.diagnostics_text.delete(1.0, tk.END)
            self.build_text.delete(1.0, tk.END)
            # Clear any pending diagnostics/events from the old core's queue
            try:
                while True:
                    self.core.update_queue.get_nowait()
            except queue_mod.Empty:
                pass
            # Create new core
            self.core = SwiftMCPMonitorCore(root_path=new_path)
            # Update window title and path label
            self.root.title(f"Swift MCP Monitor Inspector - {self.core.root_path}")
            self.path_label.config(text=f"Monitoring: {self.core.root_path}")
            # Preserve xclog filter toggle state
            self.xclog_toggle_var.set(self.xclog_filter_enabled)
            # (No need to re-call self.process_queue; it's already scheduled)
    def quit(self):
        self.core.stop()
        self.root.quit()
    def run(self):
        self.root.mainloop()

def main():
    parser = argparse.ArgumentParser(description="Swift MCP Monitor Inspector")
    parser.add_argument('--root', type=str, default=None, help='Project/workspace directory to monitor (default: current directory)')
    args = parser.parse_args()
    if args.root:
        os.chdir(args.root)
    inspector = SwiftMCPMonitorInspector(root_path=args.root)
    inspector.run()

if __name__ == "__main__":
    main()
