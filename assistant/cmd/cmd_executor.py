import os
import time
from typing import Dict, Any, Optional
from .cmd_filter import CMD_Filter
from .cmd_tools import CMDTools
from .cmd_history import history_manager
from core.error_handler import error

# 命令执行器 - 整合命令过滤、执行和历史记录功能
# 这是cmd模块的主要对外接口

f_name = "cmd_executor.py"

class CommandExecutor:
    """
    命令执行器 - cmd模块的核心类
    整合了命令安全过滤、执行和历史记录功能
    """
    
    def __init__(self, timeout: int = 30, enable_history: bool = True):
        """
        初始化命令执行器
        Args:
            timeout: 命令执行超时时间（秒）
            enable_history: 是否启用历史记录
        """
        self.cmd_tools = CMDTools(timeout=timeout)
        self.enable_history = enable_history
        self.current_user = self._get_current_user()
    
    def execute(self, command: str, cwd: Optional[str] = None, 
               record_history: Optional[bool] = None) -> Dict[str, Any]:
        """
        执行命令的主要接口
        Args:
            command: 要执行的命令
            cwd: 工作目录，如果为None则使用默认目录
            record_history: 是否记录历史，如果为None则使用默认设置
        Returns:
            Dict: 命令执行结果
        """
        start_time = time.time()
        should_record = record_history if record_history is not None else self.enable_history
        
        try:
            # 数据清洗
            command = command.strip()
            if not command:
                result = {
                    "success": False,
                    "output": "",
                    "error": "命令为空",
                    "command": command,
                    "return_code": -1,
                    "execution_time": 0,
                    "filtered": True,
                    "working_directory": cwd or self.cmd_tools.get_current_directory()
                }
                return result
            
            # 安全检查
            filter_result = CMD_Filter(command)
            if not filter_result["status"]:
                result = {
                    "success": False,
                    "output": "",
                    "error": "命令被安全过滤器拦截：不允许执行该命令",
                    "command": command,
                    "return_code": -1,
                    "execution_time": 0,
                    "filtered": True,
                    "working_directory": cwd or self.cmd_tools.get_current_directory()
                }
                
                # 记录被拦截的命令
                if should_record:
                    self._record_command(
                        command=command,
                        success=False,
                        output="",
                        error_message=result["error"],
                        return_code=-1,
                        execution_time=0,
                        working_directory=result["working_directory"]
                    )
                
                return result
            
            # 执行命令
            cmd_result = self.cmd_tools.execute_command(command, cwd)
            
            # 格式化结果
            result = {
                "success": cmd_result.success,
                "output": cmd_result.stdout,
                "error": cmd_result.stderr,
                "command": cmd_result.command,
                "return_code": cmd_result.return_code,
                "execution_time": cmd_result.execution_time,
                "filtered": False,
                "working_directory": cwd or self.cmd_tools.get_current_directory()
            }
            
            # 记录命令历史
            if should_record:
                self._record_command(
                    command=command,
                    success=cmd_result.success,
                    output=cmd_result.stdout,
                    error_message=cmd_result.stderr,
                    return_code=cmd_result.return_code,
                    execution_time=cmd_result.execution_time,
                    working_directory=result["working_directory"]
                )
            
            return result
            
        except Exception as e:
            execution_time = time.time() - start_time
            error_msg = f"命令执行器异常: {str(e)}"
            error(f_name, "execute", e)
            
            result = {
                "success": False,
                "output": "",
                "error": error_msg,
                "command": command,
                "return_code": -3,
                "execution_time": execution_time,
                "filtered": False,
                "working_directory": cwd or ""
            }
            
            # 记录异常
            if should_record:
                self._record_command(
                    command=command,
                    success=False,
                    output="",
                    error_message=error_msg,
                    return_code=-3,
                    execution_time=execution_time,
                    working_directory=result["working_directory"]
                )
            
            return result
    
    def batch_execute(self, commands: list, cwd: Optional[str] = None, 
                     stop_on_error: bool = False) -> Dict[str, Any]:
        """
        批量执行命令
        Args:
            commands: 命令列表
            cwd: 工作目录
            stop_on_error: 遇到错误时是否停止执行后续命令
        Returns:
            Dict: 批量执行结果
        """
        results = []
        successful_count = 0
        failed_count = 0
        
        for i, command in enumerate(commands):
            result = self.execute(command, cwd)
            results.append({
                "index": i,
                "command": command,
                "result": result
            })
            
            if result["success"]:
                successful_count += 1
            else:
                failed_count += 1
                if stop_on_error:
                    break
        
        return {
            "total_commands": len(commands),
            "executed_commands": len(results),
            "successful_commands": successful_count,
            "failed_commands": failed_count,
            "results": results,
            "stopped_on_error": stop_on_error and failed_count > 0
        }
    
    def get_command_help(self, command: str) -> Dict[str, Any]:
        """
        获取命令帮助信息
        Args:
            command: 命令名称
        Returns:
            Dict: 帮助信息结果
        """
        help_commands = {
            "windows": f"{command} /?",
            "unix": f"man {command}"
        }
        
        # 根据系统选择帮助命令
        if os.name == 'nt':
            help_cmd = help_commands["windows"]
        else:
            help_cmd = help_commands["unix"]
        
        return self.execute(help_cmd, record_history=False)
    
    def test_command_safety(self, command: str) -> Dict[str, Any]:
        """
        测试命令安全性（不执行）
        Args:
            command: 要测试的命令
        Returns:
            Dict: 安全性测试结果
        """
        filter_result = CMD_Filter(command)
        
        return {
            "command": command,
            "is_safe": filter_result["status"],
            "filtered_command": filter_result["cmd"],
            "message": "命令安全，可以执行" if filter_result["status"] else "命令不安全，将被拦截"
        }
    
    def get_system_info(self) -> Dict[str, Any]:
        """
        获取系统信息
        Returns:
            Dict: 系统信息
        """
        return self.cmd_tools.get_system_info()
    
    def change_directory(self, path: str) -> Dict[str, Any]:
        """
        更改工作目录
        Args:
            path: 目标目录路径
        Returns:
            Dict: 操作结果
        """
        success = self.cmd_tools.change_directory(path)
        
        if success:
            # 记录目录更改
            if self.enable_history:
                self._record_command(
                    command=f"cd {path}",
                    success=True,
                    output=f"工作目录已更改为: {path}",
                    error_message="",
                    return_code=0,
                    execution_time=0,
                    working_directory=path
                )
        
        return {
            "success": success,
            "message": f"工作目录已更改为: {path}" if success else f"无法更改到目录: {path}",
            "current_directory": self.cmd_tools.get_current_directory()
        }
    
    def list_directory(self, path: Optional[str] = None) -> Dict[str, Any]:
        """
        列出目录内容
        Args:
            path: 目录路径
        Returns:
            Dict: 目录内容
        """
        items = self.cmd_tools.list_directory(path)
        
        return {
            "success": len(items) >= 0,
            "directory": path or self.cmd_tools.get_current_directory(),
            "items": items,
            "count": len(items)
        }
    
    def get_history(self, limit: int = 20) -> Dict[str, Any]:
        """
        获取命令历史记录
        Args:
            limit: 返回的记录数量限制
        Returns:
            Dict: 历史记录
        """
        if not self.enable_history:
            return {"error": "历史记录功能未启用"}
        
        recent_commands = history_manager.get_recent_commands(limit)
        
        return {
            "success": True,
            "commands": recent_commands,
            "count": len(recent_commands),
            "limit": limit
        }
    
    def search_history(self, keyword: str, limit: int = 50) -> Dict[str, Any]:
        """
        搜索命令历史
        Args:
            keyword: 搜索关键词
            limit: 返回的记录数量限制
        Returns:
            Dict: 搜索结果
        """
        if not self.enable_history:
            return {"error": "历史记录功能未启用"}
        
        matching_commands = history_manager.search_commands(keyword, limit)
        
        return {
            "success": True,
            "keyword": keyword,
            "commands": matching_commands,
            "count": len(matching_commands),
            "limit": limit
        }
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        获取执行统计信息
        Returns:
            Dict: 统计信息
        """
        if not self.enable_history:
            return {"error": "历史记录功能未启用"}
        
        return history_manager.get_statistics()
    
    def _record_command(self, command: str, success: bool, output: str,
                       error_message: str, return_code: int, execution_time: float,
                       working_directory: str):
        """
        记录命令到历史
        Args:
            command: 执行的命令
            success: 是否成功
            output: 输出内容
            error_message: 错误信息
            return_code: 返回码
            execution_time: 执行时间
            working_directory: 工作目录
        """
        try:
            history_manager.add_command(
                command=command,
                success=success,
                output=output,
                error_message=error_message,
                return_code=return_code,
                execution_time=execution_time,
                working_directory=working_directory,
                user=self.current_user
            )
        except Exception as e:
            error(f_name, "_record_command", e)
    
    def _get_current_user(self) -> str:
        """
        获取当前用户名
        Returns:
            str: 当前用户名
        """
        try:
            return os.getenv('USERNAME') or os.getenv('USER') or 'unknown'
        except:
            return 'unknown'

# 全局命令执行器实例
executor = CommandExecutor()