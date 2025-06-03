"""
Core logic for Xcode monitoring, diagnostics, and build operations.
Reusable by both GUI and MCP server.
"""
import json
import subprocess
import os
import time
from pathlib import Path
import re
import glob
import plistlib
from datetime import datetime

# --- Core Monitor Class ---
class XcodeMonitorCore:
    """Encapsulates the monitored project path and core operations."""
    def __init__(self, root_path=None):
        self.root_path = os.path.abspath(root_path) if root_path else os.getcwd()
        self.monitoring = False
        self.monitor_thread = None
        self.file_watcher_thread = None
        # Add any other relevant threads/processes here (build server, LSP, etc.)

    def start_monitoring(self):
        print(f"[XcodeMonitorCore] Starting monitoring for: {self.root_path}")
        self.monitoring = True
        # Start monitor thread
        if self.monitor_thread is None or not self.monitor_thread.is_alive():
            print("[XcodeMonitorCore] Starting monitor thread...")
            self.monitor_thread = threading.Thread(target=self.monitor_loop, daemon=True)
            self.monitor_thread.start()
        # Start file watcher thread
        if self.file_watcher_thread is None or not self.file_watcher_thread.is_alive():
            print("[XcodeMonitorCore] Starting file watcher thread...")
            self.file_watcher_thread = threading.Thread(target=self.file_watcher_loop, daemon=True)
            self.file_watcher_thread.start()
        # TODO: Start build server/LSP/etc as needed, with logging

    def stop_monitoring(self):
        print(f"[XcodeMonitorCore] Stopping monitoring for: {self.root_path}")
        self.monitoring = False
        # Stop monitor thread
        if self.monitor_thread and self.monitor_thread.is_alive():
            print("[XcodeMonitorCore] Joining monitor thread...")
            self.monitor_thread.join(timeout=2)
            self.monitor_thread = None
        # Stop file watcher thread
        if self.file_watcher_thread and self.file_watcher_thread.is_alive():
            print("[XcodeMonitorCore] Joining file watcher thread...")
            self.file_watcher_thread.join(timeout=2)
            self.file_watcher_thread = None
        # TODO: Stop/clean up build server/LSP/etc as needed, with logging

    def set_project_path(self, new_path):
        print(f"[XcodeMonitorCore] Request to change project path to: {new_path}")
        self.stop_monitoring()
        self.root_path = os.path.abspath(new_path)
        print(f"[XcodeMonitorCore] Project path updated to: {self.root_path}")
        self.start_monitoring()
        print(f"[XcodeMonitorCore] Monitoring restarted for: {self.root_path}")
        return self.root_path

    def get_project_path(self):
        return self.root_path

    # Example monitor loop (should be implemented/expanded as needed)
    def monitor_loop(self):
        print(f"[XcodeMonitorCore] Monitor loop started for: {self.root_path}")
        while self.monitoring:
            # Insert monitoring logic here
            time.sleep(5)
        print(f"[XcodeMonitorCore] Monitor loop stopped for: {self.root_path}")

    # Example file watcher loop (should be implemented/expanded as needed)
    def file_watcher_loop(self):
        print(f"[XcodeMonitorCore] File watcher loop started for: {self.root_path}")
        while self.monitoring:
            # Insert file watching logic here
            time.sleep(5)
        print(f"[XcodeMonitorCore] File watcher loop stopped for: {self.root_path}")

    def start_monitoring(self):
        """Start Xcode monitoring (placeholder for real logic)."""
        # TODO: Implement actual monitoring startup logic here
        print(f"[XcodeMonitorCore] Monitoring started for: {self.root_path}")
        self.monitoring = True

    def stop_monitoring(self):
        """Stop Xcode monitoring (placeholder for real logic)."""
        # TODO: Implement actual monitoring shutdown logic here
        print(f"[XcodeMonitorCore] Monitoring stopped for: {self.root_path}")
        self.monitoring = False

    def set_project_path(self, new_path):
        """Change the monitored project path and restart monitoring."""
        self.stop_monitoring()
        self.root_path = os.path.abspath(new_path)
        self.start_monitoring()
        return self.root_path

    def get_project_path(self):
        return self.root_path

# --- Project/Workspace Detection ---
def find_workspace_and_project(directory=None):
    """Return (workspace, project) Path objects or None if not found."""
    directory = directory or os.getcwd()
    workspaces = list(Path(directory).glob('*.xcworkspace'))
    projects = list(Path(directory).glob('*.xcodeproj'))
    workspace = workspaces[0] if workspaces else None
    project = projects[0] if projects else None
    return workspace, project

# --- Scheme Extraction ---
def get_scheme_from_config(config_path='buildServer.json'):
    """Extract scheme from buildServer.json if available, else return None."""
    if Path(config_path).exists():
        with open(config_path, 'r') as f:
            config = json.load(f)
            args = config.get('arguments', [])
            for i, arg in enumerate(args):
                if arg == '-scheme' and i + 1 < len(args):
                    return args[i + 1]
    return None

# --- Build Server Config ---
def ensure_build_server_config(directory=None):
    """Auto-create buildServer.json for workspace or project if missing."""
    directory = directory or os.getcwd()
    config_path = Path(directory) / 'buildServer.json'
    if config_path.exists():
        return True
    workspaces = list(Path(directory).glob('*.xcworkspace'))
    if workspaces:
        workspace = workspaces[0]
        scheme = detect_scheme(workspace=workspace)
        if not scheme:
            print("No scheme found; cannot auto-configure build server.")
            return False
        try:
            subprocess.run([
                'xcode-build-server', 'config',
                '-workspace', str(workspace),
                '-scheme', scheme
            ], check=True)
            print(f"Auto-configured buildServer.json for {workspace} (scheme: {scheme})")
            return True
        except Exception as e:
            print(f"Failed to run xcode-build-server config: {e}")
            return False
    projects = list(Path(directory).glob('*.xcodeproj'))
    if projects:
        project = projects[0]
        scheme = detect_scheme(project=project)
        if not scheme:
            print("No scheme found; cannot auto-configure build server.")
            return False
        try:
            subprocess.run([
                'xcode-build-server', 'config',
                '-project', str(project),
                '-scheme', scheme
            ], check=True)
            print(f"Auto-configured buildServer.json for {project} (scheme: {scheme})")
            return True
        except Exception as e:
            print(f"Failed to run xcode-build-server config: {e}")
            return False
    print("No .xcworkspace or .xcodeproj found for build server config.")
    return False

def detect_scheme(workspace=None, project=None):
    """Detect the first available scheme from workspace or project."""
    if workspace:
        try:
            result = subprocess.run(
                ['xcodebuild', '-list', '-workspace', str(workspace)],
                capture_output=True, text=True, timeout=10
            )
            lines = result.stdout.splitlines()
            for i, line in enumerate(lines):
                if line.strip().startswith("Schemes:"):
                    for l in lines[i+1:]:
                        l = l.strip()
                        if l:
                            return l
                    break
        except Exception as e:
            print(f"Could not determine scheme: {e}")
    if project:
        try:
            result = subprocess.run(
                ['xcodebuild', '-list', '-project', str(project)],
                capture_output=True, text=True, timeout=10
            )
            lines = result.stdout.splitlines()
            for i, line in enumerate(lines):
                if line.strip().startswith("Schemes:"):
                    for l in lines[i+1:]:
                        l = l.strip()
                        if l:
                            return l
                    break
        except Exception as e:
            print(f"Could not determine scheme: {e}")
    return None

# --- Build Logic ---
def run_build(directory=None):
    """Run xcodebuild for workspace or project. Returns (success, output_lines)."""
    directory = directory or os.getcwd()
    workspace, project = find_workspace_and_project(directory)
    scheme = get_scheme_from_config(Path(directory) / 'buildServer.json') or 'default'
    if workspace:
        cmd = ['xcodebuild', '-workspace', str(workspace), '-scheme', scheme, 'build']
    elif project:
        cmd = ['xcodebuild', '-project', str(project), '-scheme', scheme, 'build']
    else:
        return False, ["No workspace or project found"]
    output_lines = []
    try:
        process = subprocess.Popen(
            cmd,
            cwd=directory,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True
        )
        for line in process.stdout:
            if line.strip():
                output_lines.append(line.strip())
        process.wait()
        return process.returncode == 0, output_lines
    except Exception as e:
        return False, [f"Build error: {e}"]

# --- Diagnostics Extraction ---
def get_diagnostics(directory=None):
    """Get diagnostics from build logs and Xcode's error display."""
    directory = directory or os.getcwd()
    diagnostics = []
    try:
        # 0. Get live diagnostics directly from Xcode (stub: implement as needed)
        # diagnostics.extend(get_xcode_live_diagnostics())
        # 1. Try to parse recent build logs with XCLogParser
        result = subprocess.run(
            ['which', 'xclogparser'],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            derived_data = Path.home() / "Library/Developer/Xcode/DerivedData"
            recent_logs = []
            for log_file in derived_data.rglob("*.xcactivitylog"):
                if log_file.stat().st_mtime > time.time() - 86400:
                    recent_logs.append(log_file)
            if recent_logs:
                most_recent = max(recent_logs, key=lambda p: p.stat().st_mtime)
                parser_cmd = [
                    'xclogparser', 'parse', '--project', str(most_recent)
                ]
                try:
                    parser_result = subprocess.run(
                        parser_cmd,
                        capture_output=True,
                        text=True,
                        timeout=10
                    )
                    if parser_result.returncode == 0:
                        # Parse output for errors/warnings (stub: implement as needed)
                        pass
                except Exception as e:
                    diagnostics.append({'severity': 'error', 'message': f'XCLogParser error: {e}'})
        # 2. Parse diagnostics.plist
        derived_data = Path.home() / "Library/Developer/Xcode/DerivedData"
        for plist_path in derived_data.rglob('diagnostics.plist'):
            try:
                with open(plist_path, 'rb') as f:
                    plist = plistlib.load(f)
                    for diag in plist.get('diagnostics', []):
                        diagnostics.append(diag)
            except Exception as plist_err:
                diagnostics.append({'severity': 'error', 'message': f'Error parsing diagnostics.plist: {plist_err}'})
        # 3. SwiftPM logs
        swift_pm_logs = Path.home() / ".build/logs"
        if swift_pm_logs.exists():
            log_files = list(swift_pm_logs.glob("*.log"))
            if log_files:
                most_recent_log = max(log_files, key=lambda p: p.stat().st_mtime)
                if most_recent_log.stat().st_mtime > time.time() - 3600:
                    with open(most_recent_log, 'r') as f:
                        log_content = f.read()
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
        return [{'severity': 'error', 'message': f'Error getting diagnostics: {e}'}]
