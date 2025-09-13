import subprocess
import os
import sys
import time
import threading
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from core.error_handler import error
from data.meta_data import get_watch_path
from .cmd_filter import CMD_Filter

# CMD工具类，类似于sql模块中的db_tools.py
# 负责安全地执行系统命令并管理命令历史

f_name = "cmd_tools.py"

@dataclass
class CommandResult:
    """命令执行结果数据类"""
    command: str
    success: bool
    stdout: str
    stderr: str
    return_code: int
    execution_time: float
    timestamp: float

class CMDTools:
    """命令执行工具类"""
    
    def __init__(self, timeout: int = 30, max_output_length: int = 10000):
        """
        初始化CMD工具
        Args:
            timeout: 命令执行超时时间（秒）
            max_output_length: 最大输出长度限制
        """
        self.timeout = timeout
        self.max_output_length = max_output_length
        self.current_dir = get_watch_path()  # 默认工作目录为监听路径
        
    def execute_command(self, command: str, cwd: Optional[str] = None) -> CommandResult:
        """
        安全执行命令
        Args:
            command: 要执行的命令
            cwd: 工作目录，如果为None则使用当前目录
        Returns:
            CommandResult: 命令执行结果
        """
        start_time = time.time()
        timestamp = time.time()
        
        try:
            # 首先通过过滤器检查命令安全性
            filter_result = CMD_Filter(command)
            if not filter_result["status"]:
                return CommandResult(
                    command=command,
                    success=False,
                    stdout="",
                    stderr="命令被安全过滤器拦截：不允许执行该命令",
                    return_code=-1,
                    execution_time=0,
                    timestamp=timestamp
                )
            
            # 设置工作目录
            work_dir = cwd if cwd else self.current_dir
            if not os.path.exists(work_dir):
                work_dir = os.getcwd()  # 如果指定目录不存在，使用当前目录
            
            # 根据操作系统设置命令执行方式
            if sys.platform.startswith('win'):
                # Windows系统
                process = subprocess.Popen(
                    command,
                    shell=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    cwd=work_dir,
                    text=True,
                    encoding='gbk',  # Windows中文编码
                    errors='replace'  # 处理编码错误
                )
            else:
                # Unix-like系统
                process = subprocess.Popen(
                    command,
                    shell=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    cwd=work_dir,
                    text=True,
                    encoding='utf-8',
                    errors='replace'
                )
            
            # 执行命令并等待结果
            try:
                stdout, stderr = process.communicate(timeout=self.timeout)
                return_code = process.returncode
            except subprocess.TimeoutExpired:
                process.kill()
                stdout, stderr = process.communicate()
                stderr = f"命令执行超时（{self.timeout}秒）\\n" + stderr
                return_code = -2
            
            # 限制输出长度
            if len(stdout) > self.max_output_length:
                stdout = stdout[:self.max_output_length] + "\\n... (输出被截断)"
            if len(stderr) > self.max_output_length:
                stderr = stderr[:self.max_output_length] + "\\n... (错误输出被截断)"
            
            execution_time = time.time() - start_time
            success = (return_code == 0)
            
            return CommandResult(
                command=command,
                success=success,
                stdout=stdout,
                stderr=stderr,
                return_code=return_code,
                execution_time=execution_time,
                timestamp=timestamp
            )
            
        except Exception as e:
            execution_time = time.time() - start_time
            error_msg = f"命令执行出现异常: {str(e)}"
            error(f_name, "execute_command", e)
            
            return CommandResult(
                command=command,
                success=False,
                stdout="",
                stderr=error_msg,
                return_code=-3,
                execution_time=execution_time,
                timestamp=timestamp
            )
    
    def execute_safe_command(self, command: str, cwd: Optional[str] = None) -> Dict[str, Any]:
        """
        执行安全命令并返回简化的结果字典（用于与主程序集成）
        Args:
            command: 要执行的命令
            cwd: 工作目录
        Returns:
            Dict: 简化的结果字典
        """
        result = self.execute_command(command, cwd)
        
        return {
            "success": result.success,
            "output": result.stdout if result.success else result.stderr,
            "command": result.command,
            "return_code": result.return_code,
            "execution_time": round(result.execution_time, 2)
        }
    
    def get_system_info(self) -> Dict[str, str]:
        """
        获取系统信息
        Returns:
            Dict: 系统信息字典
        """
        info = {}
        
        # 获取操作系统信息
        if sys.platform.startswith('win'):
            os_info = self.execute_command("systeminfo | findstr /B /C:\"OS Name\" /C:\"OS Version\"")
            if os_info.success:
                info["os"] = os_info.stdout.strip()
        else:
            os_info = self.execute_command("uname -a")
            if os_info.success:
                info["os"] = os_info.stdout.strip()
        
        # 获取当前用户
        user_info = self.execute_command("whoami")
        if user_info.success:
            info["user"] = user_info.stdout.strip()
        
        # 获取当前目录
        info["current_directory"] = self.current_dir
        
        # 获取Python版本
        info["python_version"] = sys.version
        
        return info
    
    def change_directory(self, path: str) -> bool:
        """
        更改当前工作目录
        Args:
            path: 目标目录路径
        Returns:
            bool: 是否成功更改目录
        """
        try:
            if os.path.exists(path) and os.path.isdir(path):
                self.current_dir = os.path.abspath(path)
                return True
            else:
                return False
        except Exception as e:
            error(f_name, "change_directory", e)
            return False
    
    def list_directory(self, path: Optional[str] = None) -> List[Dict[str, str]]:
        """
        列出目录内容
        Args:
            path: 目录路径，如果为None则使用当前目录
        Returns:
            List[Dict]: 目录内容列表
        """
        target_dir = path if path else self.current_dir
        
        try:
            if not os.path.exists(target_dir):
                return []
            
            items = []
            for item in os.listdir(target_dir):
                item_path = os.path.join(target_dir, item)
                item_info = {
                    "name": item,
                    "type": "directory" if os.path.isdir(item_path) else "file",
                    "path": item_path
                }
                
                # 添加文件大小信息
                if os.path.isfile(item_path):
                    try:
                        size = os.path.getsize(item_path)
                        item_info["size"] = self._format_size(size)
                    except:
                        item_info["size"] = "Unknown"
                
                items.append(item_info)
            
            return sorted(items, key=lambda x: (x["type"] == "file", x["name"]))
            
        except Exception as e:
            error(f_name, "list_directory", e)
            return []
    
    def _format_size(self, size_bytes: int) -> str:
        """
        格式化文件大小显示
        Args:
            size_bytes: 文件大小（字节）
        Returns:
            str: 格式化后的大小字符串
        """
        if size_bytes == 0:
            return "0 B"
        size_names = ["B", "KB", "MB", "GB", "TB"]
        i = 0
        while size_bytes >= 1024 and i < len(size_names) - 1:
            size_bytes /= 1024.0
            i += 1
        return f"{size_bytes:.1f} {size_names[i]}"
    
    def get_current_directory(self) -> str:
        """
        获取当前工作目录
        Returns:
            str: 当前工作目录路径
        """
        return self.current_dir
    
    def is_command_safe(self, command: str) -> bool:
        """
        检查命令是否安全
        Args:
            command: 要检查的命令
        Returns:
            bool: 命令是否安全
        """
        filter_result = CMD_Filter(command)
        return filter_result["status"]