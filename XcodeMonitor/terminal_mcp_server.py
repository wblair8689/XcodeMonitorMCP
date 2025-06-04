#!/usr/bin/env python3
"""
Mac Terminal MCP Server
Provides secure terminal access to AI assistants via MCP protocol
"""

import os
import subprocess
import asyncio
import shlex
from pathlib import Path
from mcp.server.fastmcp import FastMCP
from typing import Optional, Dict, List
import json
import tempfile

# Create MCP server
mcp = FastMCP("mac_terminal")

# Security: Define allowed/blocked commands
ALLOWED_COMMANDS = {
    # File operations
    'ls', 'cat', 'head', 'tail', 'find', 'grep', 'wc', 'file',
    # Directory operations  
    'pwd', 'cd', 'mkdir', 'rmdir',
    # Git operations
    'git',
    # Development tools
    'python', 'python3', 'pip', 'pip3', 'brew', 'npm', 'node',
    # Xcode tools
    'xcodebuild', 'xcrun', 'xcode-select', 'simctl',
    # System info
    'ps', 'top', 'df', 'du', 'free', 'uname', 'which', 'whereis',
    # Network
    'curl', 'wget', 'ping', 'nc',
    # Docker/Kubernetes
    'docker', 'kubectl', 'gcloud',
    # Text editing (safe editors)
    'nano', 'vim', 'emacs'
}

BLOCKED_COMMANDS = {
    # Dangerous system operations
    'rm', 'sudo', 'su', 'chmod', 'chown', 'kill', 'killall',
    'format', 'fdisk', 'dd', 'mount', 'umount',
    # Network security
    'ssh', 'scp', 'rsync', 'ftp', 'telnet',
    # System modification
    'systemctl', 'service', 'launchctl',
    # Package management (require explicit permission)
    'apt', 'yum', 'pacman'
}

class TerminalSession:
    """Manages a terminal session with working directory tracking"""
    
    def __init__(self):
        self.working_directory = Path.home()
        self.environment = os.environ.copy()
        self.command_history = []
        
    def update_working_directory(self, new_path: str):
        """Update current working directory"""
        try:
            resolved_path = Path(new_path).resolve()
            if resolved_path.exists() and resolved_path.is_dir():
                self.working_directory = resolved_path
                return True
        except Exception:
            pass
        return False

# Global terminal session
terminal_session = TerminalSession()

@mcp.tool()
def execute_command(command: str, working_directory: Optional[str] = None) -> Dict:
    """
    Execute a shell command on the Mac terminal
    
    Args:
        command: The shell command to execute
        working_directory: Optional working directory (defaults to current)
    
    Returns:
        Dict with stdout, stderr, return_code, and working_directory
    """
    
    # Parse command to check security
    try:
        cmd_parts = shlex.split(command)
        if not cmd_parts:
            return {"error": "Empty command"}
            
        base_command = cmd_parts[0]
        
        # Security check
        if base_command in BLOCKED_COMMANDS:
            return {"error": f"Command '{base_command}' is blocked for security reasons"}
            
        if base_command not in ALLOWED_COMMANDS and not Path(base_command).is_absolute():
            return {"error": f"Command '{base_command}' is not in allowed list"}
            
    except ValueError as e:
        return {"error": f"Invalid command syntax: {e}"}
    
    # Handle working directory
    if working_directory:
        if not terminal_session.update_working_directory(working_directory):
            return {"error": f"Invalid working directory: {working_directory}"}
    
    # Handle 'cd' command specially
    if base_command == 'cd':
        if len(cmd_parts) > 1:
            new_dir = cmd_parts[1]
            if terminal_session.update_working_directory(new_dir):
                return {
                    "stdout": "",
                    "stderr": "",
                    "return_code": 0,
                    "working_directory": str(terminal_session.working_directory)
                }
            else:
                return {
                    "stdout": "",
                    "stderr": f"cd: {new_dir}: No such file or directory",
                    "return_code": 1,
                    "working_directory": str(terminal_session.working_directory)
                }
        else:
            # cd with no arguments goes to home
            terminal_session.working_directory = Path.home()
            return {
                "stdout": "",
                "stderr": "",
                "return_code": 0,
                "working_directory": str(terminal_session.working_directory)
            }
    
    try:
        # Execute command
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            cwd=str(terminal_session.working_directory),
            env=terminal_session.environment,
            timeout=30  # 30 second timeout for safety
        )
        
        # Track command in history
        terminal_session.command_history.append({
            "command": command,
            "working_directory": str(terminal_session.working_directory),
            "return_code": result.returncode
        })
        
        # Keep only last 50 commands
        if len(terminal_session.command_history) > 50:
            terminal_session.command_history = terminal_session.command_history[-50:]
        
        return {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "return_code": result.returncode,
            "working_directory": str(terminal_session.working_directory)
        }
        
    except subprocess.TimeoutExpired:
        return {"error": "Command timed out after 30 seconds"}
    except Exception as e:
        return {"error": f"Execution error: {str(e)}"}

@mcp.tool()
def get_working_directory() -> str:
    """Get the current working directory"""
    return str(terminal_session.working_directory)

@mcp.tool()
def change_directory(path: str) -> Dict:
    """Change the current working directory"""
    if terminal_session.update_working_directory(path):
        return {
            "success": True,
            "working_directory": str(terminal_session.working_directory)
        }
    else:
        return {
            "success": False,
            "error": f"Cannot change to directory: {path}"
        }

@mcp.tool()
def list_directory(path: Optional[str] = None) -> Dict:
    """List contents of a directory"""
    target_path = Path(path) if path else terminal_session.working_directory
    
    try:
        if not target_path.exists():
            return {"error": f"Path does not exist: {target_path}"}
        
        if not target_path.is_dir():
            return {"error": f"Path is not a directory: {target_path}"}
        
        contents = []
        for item in sorted(target_path.iterdir()):
            item_info = {
                "name": item.name,
                "type": "directory" if item.is_dir() else "file",
                "size": item.stat().st_size if item.is_file() else None,
                "permissions": oct(item.stat().st_mode)[-3:],
                "hidden": item.name.startswith('.')
            }
            contents.append(item_info)
        
        return {
            "path": str(target_path),
            "contents": contents
        }
        
    except PermissionError:
        return {"error": f"Permission denied: {target_path}"}
    except Exception as e:
        return {"error": f"Error listing directory: {str(e)}"}

@mcp.tool()
def read_file(file_path: str, max_lines: Optional[int] = 100) -> Dict:
    """Read contents of a text file"""
    try:
        path = Path(file_path)
        if not path.is_absolute():
            path = terminal_session.working_directory / path
        
        if not path.exists():
            return {"error": f"File does not exist: {path}"}
        
        if not path.is_file():
            return {"error": f"Path is not a file: {path}"}
        
        # Check file size (limit to 1MB for safety)
        if path.stat().st_size > 1024 * 1024:
            return {"error": "File too large (>1MB)"}
        
        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            if max_lines:
                lines = []
                for i, line in enumerate(f):
                    if i >= max_lines:
                        lines.append(f"... (truncated after {max_lines} lines)")
                        break
                    lines.append(line.rstrip())
                content = '\n'.join(lines)
            else:
                content = f.read()
        
        return {
            "file_path": str(path),
            "content": content,
            "size": path.stat().st_size
        }
        
    except UnicodeDecodeError:
        return {"error": "File appears to be binary"}
    except PermissionError:
        return {"error": f"Permission denied: {path}"}
    except Exception as e:
        return {"error": f"Error reading file: {str(e)}"}

@mcp.tool()
def write_file(file_path: str, content: str, create_dirs: bool = False) -> Dict:
    """Write content to a file"""
    try:
        path = Path(file_path)
        if not path.is_absolute():
            path = terminal_session.working_directory / path
        
        # Create parent directories if requested
        if create_dirs:
            path.parent.mkdir(parents=True, exist_ok=True)
        
        # Safety check - don't overwrite system files
        system_paths = ['/bin', '/sbin', '/usr/bin', '/usr/sbin', '/System', '/Library/System']
        if any(str(path).startswith(sys_path) for sys_path in system_paths):
            return {"error": "Cannot write to system directories"}
        
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        return {
            "success": True,
            "file_path": str(path),
            "size": len(content.encode('utf-8'))
        }
        
    except PermissionError:
        return {"error": f"Permission denied: {path}"}
    except Exception as e:
        return {"error": f"Error writing file: {str(e)}"}

@mcp.tool()
def get_command_history() -> List[Dict]:
    """Get recent command history"""
    return terminal_session.command_history[-10:]  # Last 10 commands

@mcp.tool()
def get_system_info() -> Dict:
    """Get basic system information"""
    try:
        result = {
            "platform": "macOS",
            "working_directory": str(terminal_session.working_directory),
            "user": os.getenv('USER', 'unknown'),
            "home": str(Path.home()),
            "python_version": subprocess.check_output(['python3', '--version'], text=True).strip(),
        }
        
        # Get Xcode info if available
        try:
            xcode_path = subprocess.check_output(['xcode-select', '--print-path'], text=True).strip()
            result["xcode_path"] = xcode_path
        except:
            result["xcode_path"] = "Not found"
        
        # Get Git info if available
        try:
            git_version = subprocess.check_output(['git', '--version'], text=True).strip()
            result["git_version"] = git_version
        except:
            result["git_version"] = "Not found"
        
        return result
        
    except Exception as e:
        return {"error": f"Error getting system info: {str(e)}"}

@mcp.tool()
def find_xcode_projects() -> Dict:
    """Find Xcode projects in current directory and subdirectories"""
    try:
        projects = []
        workspaces = []
        
        # Search for .xcodeproj and .xcworkspace files
        for pattern in ['**/*.xcodeproj', '**/*.xcworkspace']:
            for path in terminal_session.working_directory.glob(pattern):
                if pattern.endswith('.xcodeproj'):
                    projects.append(str(path))
                else:
                    workspaces.append(str(path))
        
        return {
            "search_directory": str(terminal_session.working_directory),
            "xcode_projects": projects,
            "xcode_workspaces": workspaces,
            "total_found": len(projects) + len(workspaces)
        }
        
    except Exception as e:
        return {"error": f"Error finding Xcode projects: {str(e)}"}

if __name__ == "__main__":
    print("Starting Mac Terminal MCP Server...")
    print(f"Working directory: {terminal_session.working_directory}")
    print("Available tools:")
    print("  - execute_command: Run shell commands")
    print("  - get_working_directory: Get current directory")
    print("  - change_directory: Change working directory")
    print("  - list_directory: List directory contents")
    print("  - read_file: Read file contents")
    print("  - write_file: Write file contents")
    print("  - get_command_history: View recent commands")
    print("  - get_system_info: Get system information")
    print("  - find_xcode_projects: Find Xcode projects")
    
    mcp.run(transport='stdio')