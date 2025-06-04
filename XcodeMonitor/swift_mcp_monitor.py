"""
Core logic for Swift MCP Monitor (backend, no UI)
"""
import os
import threading
import queue
import time
import subprocess
from pathlib import Path
import glob
import json
import hashlib
from datetime import datetime

class LSPClient:
    """Simple LSP client for sourcekit-lsp"""
    def __init__(self):
        self.process = None
        self.message_id = 0
    def start(self):
        try:
            self.process = subprocess.Popen(
                ['xcrun', 'sourcekit-lsp'],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=False
            )
            self.initialize()
            return True
        except Exception as e:
            print(f"Failed to start sourcekit-lsp: {e}")
            return False
    def send_request(self, method, params=None):
        self.message_id += 1
        request = {
            "jsonrpc": "2.0",
            "id": self.message_id,
            "method": method,
            "params": params or {}
        }
        message = json.dumps(request)
        content_length = len(message.encode('utf-8'))
        header = f"Content-Length: {content_length}\r\n\r\n"
        self.process.stdin.write(header.encode('utf-8'))
        self.process.stdin.write(message.encode('utf-8'))
        self.process.stdin.flush()
        return self.read_response()
    def read_response(self):
        headers = {}
        while True:
            line = self.process.stdout.readline().decode('utf-8').strip()
            if not line:
                break
            key, value = line.split(': ', 1)
            headers[key] = value
        content_length = int(headers.get('Content-Length', 0))
        content = self.process.stdout.read(content_length).decode('utf-8')
        return json.loads(content) if content else None
    def initialize(self):
        params = {
            "processId": os.getpid(),
            "rootUri": f"file://{os.getcwd()}",
            "capabilities": {
                "textDocument": {
                    "diagnostic": {
                        "dynamicRegistration": True
                    }
                }
            }
        }
        response = self.send_request("initialize", params)
        if response:
            self.send_notification("initialized", {})
            return True
        return False
    def send_notification(self, method, params=None):
        notification = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params or {}
        }
        message = json.dumps(notification)
        content_length = len(message.encode('utf-8'))
        header = f"Content-Length: {content_length}\r\n\r\n"
        self.process.stdin.write(header.encode('utf-8'))
        self.process.stdin.write(message.encode('utf-8'))
        self.process.stdin.flush()
    def shutdown(self):
        if self.process:
            self.send_request("shutdown")
            self.send_notification("exit")
            self.process.terminate()

class SwiftMCPMonitorCore:
    """Core monitor logic (no UI)"""
    def __init__(self, root_path=None):
        self.root_path = os.path.abspath(root_path) if root_path else os.getcwd()
        self.update_queue = queue.Queue()
        self.last_file_hashes = {}
        self.monitored_extensions = [".swift", ".m", ".h", ".mm", ".c", ".cpp"]
        self.monitoring = True
        self.monitor_thread = threading.Thread(target=self.monitor_loop, daemon=True)
        self.monitor_thread.start()
        self.file_monitor_thread = threading.Thread(target=self.file_monitor_loop, daemon=True)
        self.file_monitor_thread.start()
    # All methods from XcodeLSPMonitor that do not use Tkinter or UI go here
    def check_build_server(self):
        try:
            if Path('buildServer.json').exists():
                with open('buildServer.json', 'r') as f:
                    config = json.load(f)
                    return f"✅ Configured ({config.get('name', 'xcode')})"
            else:
                return "❌ Not configured"
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
                return f"✅ Available at {os.path.basename(path)}"
            else:
                return "❌ Not available"
        except Exception as e:
            return f"Error: {e}"
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
                    return f"✅ {int(age/60)} minutes ago"
                else:
                    return f"✅ {int(age/3600)} hours ago"
            else:
                return "No recent builds"
        except Exception as e:
            return f"Error: {e}"
    def get_xcode_live_diagnostics(self):
        diagnostics = []
        try:
            xcode_data_dir = Path.home() / "Library/Developer/Xcode/UserData/IDEEditorInteractivityHistory"
            if not xcode_data_dir.exists():
                return []
            diagnostic_files = list(xcode_data_dir.glob("*.xcdiagnostics"))
            if not diagnostic_files:
                return []
            most_recent = max(diagnostic_files, key=lambda p: p.stat().st_mtime)
            if most_recent.stat().st_mtime < time.time() - 3600:
                return []
            try:
                result = subprocess.run(
                    ['plutil', '-convert', 'json', '-o', '-', str(most_recent)],
                    capture_output=True,
                    text=True
                )
                if result.returncode == 0 and result.stdout:
                    diag_data = json.loads(result.stdout)
                    # Try to get workspace/project info from the file
                    workspace_path = diag_data.get('workspacePath') or diag_data.get('workspace') or diag_data.get('project') or None
                    root_abs = os.path.abspath(self.root_path)
                    def is_relevant(file_path, workspace_path):
                        # If workspace_path is present, must be under current root
                        if workspace_path and os.path.exists(workspace_path):
                            return os.path.commonpath([os.path.abspath(workspace_path), root_abs]) == root_abs
                        # Otherwise, check file_path
                        if file_path and os.path.exists(file_path):
                            return os.path.commonpath([os.path.abspath(file_path), root_abs]) == root_abs
                        return True  # fallback: show if can't determine
                    # Handle both formats
                    if 'diagnostics' in diag_data:
                        for diag in diag_data['diagnostics'][:20]:
                            severity = 'error' if diag.get('severity', 0) >= 3 else 'warning'
                            location = diag.get('location', {})
                            file_path = location.get('path', 'Unknown')
                            line = location.get('line', 0)
                            message = diag.get('description', 'Unknown issue')
                            # Filtering
                            if not is_relevant(file_path, workspace_path):
                                continue
                            diagnostics.append({
                                'severity': severity,
                                'file': file_path,
                                'line': line,
                                'message': message,
                                'source': 'xcode_live',
                                'workspacePath': workspace_path,
                                'raw_metadata': diag
                            })
                    elif 'diagnostics-items' in diag_data:
                        for diag in diag_data['diagnostics-items'][:20]:
                            severity = 'error' if 'error' in diag.get('kind', '').lower() else 'warning'
                            location = diag.get('diagnostic-context', {})
                            file_path = location.get('file-path', 'Unknown')
                            line = location.get('line-number', 0)
                            message = diag.get('message', 'Unknown issue')
                            # Filtering
                            if not is_relevant(file_path, workspace_path):
                                continue
                            diagnostics.append({
                                'severity': severity,
                                'file': file_path,
                                'line': line,
                                'message': message,
                                'source': 'xcode_live',
                                'workspacePath': workspace_path,
                                'raw_metadata': diag
                            })
            except Exception as e:
                print(f"Error parsing Xcode diagnostics: {e}")
            return diagnostics
        except Exception as e:
            print(f"Error getting Xcode live diagnostics: {e}")
            return []
    def get_diagnostics(self, filter_xclogparser=True):
        diagnostics = []
        try:
            # 0. Get live diagnostics directly from Xcode
            xcode_live_diagnostics = self.get_xcode_live_diagnostics()
            diagnostics.extend(xcode_live_diagnostics)
            result = subprocess.run(
                ['which', 'xclogparser'],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                derived_data = Path.home() / "Library/Developer/Xcode/DerivedData"
                root_abs = os.path.abspath(self.root_path)
                relevant_logs = []
                # Always include all recent .xcactivitylog files (last 24h)
                relevant_logs = [log_file for log_file in derived_data.rglob('*.xcactivitylog') if log_file.stat().st_mtime > time.time() - 86400]
                if relevant_logs:
                    most_recent = max(relevant_logs, key=lambda p: p.stat().st_mtime)
                    result = subprocess.run(
                        ['xclogparser', 'parse', '--file', str(most_recent), '--reporter', 'issues'],
                        capture_output=True,
                        text=True
                    )
                    if result.returncode == 0 and result.stdout:
                        issues = json.loads(result.stdout)
                        for issue in issues.get('errors', [])[:10]:
                            diagnostics.append({
                                'severity': 'error',
                                'file': issue.get('documentURL', 'Unknown'),
                                'line': issue.get('startingLineNumber', 0),
                                'message': issue.get('title', 'Unknown error'),
                                'source': 'xclogparser',
                                'log_path': str(most_recent)
                            })
                        for issue in issues.get('warnings', [])[:5]:
                            diagnostics.append({
                                'severity': 'warning',
                                'file': issue.get('documentURL', 'Unknown'),
                                'line': issue.get('startingLineNumber', 0),
                                'message': issue.get('title', 'Unknown warning'),
                                'source': 'xclogparser',
                                'log_path': str(most_recent)
                            })
                else:
                    # No logs found: show error diagnostic
                    diagnostics.append({
                        'severity': 'error',
                        'file': '',
                        'line': 0,
                        'message': f"No .xcactivitylog files found for xclogparser in {str(derived_data)} (filter_xclogparser={filter_xclogparser})",
                        'source': 'xclogparser',
                        'log_path': str(derived_data)
                    })
            if Path('buildServer.json').exists():
                with open('buildServer.json', 'r') as f:
                    config = json.load(f)
                    if 'build_root' in config:
                        build_root = Path(config['build_root'])
                        diag_files = list(build_root.glob('**/diagnostics.plist'))
                        if diag_files:
                            most_recent_diag = max(diag_files, key=lambda p: p.stat().st_mtime)
                            try:
                                result = subprocess.run(
                                    ['plutil', '-convert', 'json', '-o', '-', str(most_recent_diag)],
                                    capture_output=True,
                                    text=True
                                )
                                if result.returncode == 0 and result.stdout:
                                    diag_data = json.loads(result.stdout)
                                    for diag in diag_data.get('diagnostics', [])[:15]:
                                        severity = 'error' if diag.get('severity', 0) >= 3 else 'warning'
                                        location = diag.get('location', {})
                                        file_path = location.get('file', 'Unknown')
                                        line = location.get('line', 0)
                                        message = diag.get('message', 'Unknown issue')
                                        diagnostics.append({
                                            'severity': severity,
                                            'file': os.path.basename(file_path),
                                            'line': line,
                                            'message': message,
                                            'source': 'diagnostics.plist'
                                        })
                            except Exception as plist_err:
                                print(f"Error parsing diagnostics.plist: {plist_err}")
            swift_pm_logs = Path.home() / ".build/logs"
            if swift_pm_logs.exists():
                log_files = list(swift_pm_logs.glob("*.log"))
                if log_files:
                    most_recent_log = max(log_files, key=lambda p: p.stat().st_mtime)
                    if most_recent_log.stat().st_mtime > time.time() - 3600:
                        with open(most_recent_log, 'r') as f:
                            log_content = f.read()
                            import re
                            error_matches = re.findall(r'([^:]+\.swift):(\d+):(\d+): (error|warning): (.+)', log_content)
                            for match in error_matches[:10]:
                                file_path, line, column, level, message = match
                                diagnostics.append({
                                    'severity': level,
                                    'file': os.path.basename(file_path),
                                    'line': int(line),
                                    'message': message,
                                    'source': 'swiftpm'
                                })
            return diagnostics
        except Exception as e:
            print(f"Error getting diagnostics: {e}")
            return []
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
    def stop(self):
        self.monitoring = False
    def join_threads(self, timeout=3.0):
        # Wait for threads to exit (with timeout)
        if hasattr(self, 'monitor_thread') and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=timeout)
        if hasattr(self, 'file_monitor_thread') and self.file_monitor_thread.is_alive():
            self.file_monitor_thread.join(timeout=timeout)
