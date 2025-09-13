import json
import time
import os
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict
from core.error_handler import error
from data.meta_data import DATA_DIR

# 命令历史记录管理，类似于sql模块中的tracker.py
# 负责记录、管理和查询命令执行历史

f_name = "cmd_history.py"
HISTORY_FILE = os.path.join(DATA_DIR, "cmd_history.json")
MAX_HISTORY_SIZE = 1000  # 最大历史记录数量

@dataclass 
class CommandHistoryEntry:
    """命令历史记录条目"""
    id: int
    command: str
    timestamp: float
    success: bool
    output: str
    error_message: str
    return_code: int
    execution_time: float
    working_directory: str
    user: str

class CommandHistory:
    """命令历史管理类"""
    
    def __init__(self):
        """初始化命令历史管理器"""
        self.history_file = HISTORY_FILE
        self.max_size = MAX_HISTORY_SIZE
        self._ensure_history_file()
    
    def _ensure_history_file(self):
        """确保历史文件存在"""
        try:
            if not os.path.exists(self.history_file):
                self._save_history([])
        except Exception as e:
            error(f_name, "_ensure_history_file", e)
    
    def _load_history(self) -> List[Dict[str, Any]]:
        """
        从文件加载历史记录
        Returns:
            List[Dict]: 历史记录列表
        """
        try:
            if os.path.exists(self.history_file):
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return []
        except Exception as e:
            error(f_name, "_load_history", e)
            return []
    
    def _save_history(self, history: List[Dict[str, Any]]):
        """
        保存历史记录到文件
        Args:
            history: 要保存的历史记录列表
        """
        try:
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(history, f, ensure_ascii=False, indent=2)
        except Exception as e:
            error(f_name, "_save_history", e)
    
    def add_command(self, command: str, success: bool, output: str = "", 
                   error_message: str = "", return_code: int = 0, 
                   execution_time: float = 0, working_directory: str = "", 
                   user: str = "") -> bool:
        """
        添加命令执行记录
        Args:
            command: 执行的命令
            success: 是否成功执行
            output: 命令输出
            error_message: 错误信息
            return_code: 返回码
            execution_time: 执行时间
            working_directory: 工作目录
            user: 执行用户
        Returns:
            bool: 是否成功添加
        """
        try:
            history = self._load_history()
            
            # 生成新的ID
            new_id = max([entry.get('id', 0) for entry in history], default=0) + 1
            
            # 创建新记录
            new_entry = CommandHistoryEntry(
                id=new_id,
                command=command,
                timestamp=time.time(),
                success=success,
                output=output[:1000] if output else "",  # 限制输出长度
                error_message=error_message[:500] if error_message else "",  # 限制错误信息长度
                return_code=return_code,
                execution_time=execution_time,
                working_directory=working_directory,
                user=user
            )
            
            # 添加到历史记录
            history.append(asdict(new_entry))
            
            # 限制历史记录数量
            if len(history) > self.max_size:
                history = history[-self.max_size:]
            
            # 保存到文件
            self._save_history(history)
            return True
            
        except Exception as e:
            error(f_name, "add_command", e)
            return False
    
    def get_recent_commands(self, limit: int = 20) -> List[Dict[str, Any]]:
        """
        获取最近的命令记录
        Args:
            limit: 返回的记录数量限制
        Returns:
            List[Dict]: 最近的命令记录列表
        """
        try:
            history = self._load_history()
            # 按时间戳倒序排序，返回最近的记录
            sorted_history = sorted(history, key=lambda x: x.get('timestamp', 0), reverse=True)
            return sorted_history[:limit]
        except Exception as e:
            error(f_name, "get_recent_commands", e)
            return []
    
    def search_commands(self, keyword: str, limit: int = 50) -> List[Dict[str, Any]]:
        """
        搜索包含关键词的命令记录
        Args:
            keyword: 搜索关键词
            limit: 返回的记录数量限制
        Returns:
            List[Dict]: 匹配的命令记录列表
        """
        try:
            history = self._load_history()
            keyword_lower = keyword.lower()
            
            # 搜索命令或输出中包含关键词的记录
            matching_records = []
            for entry in history:
                if (keyword_lower in entry.get('command', '').lower() or 
                    keyword_lower in entry.get('output', '').lower()):
                    matching_records.append(entry)
            
            # 按时间戳倒序排序
            matching_records.sort(key=lambda x: x.get('timestamp', 0), reverse=True)
            return matching_records[:limit]
            
        except Exception as e:
            error(f_name, "search_commands", e)
            return []
    
    def get_failed_commands(self, limit: int = 20) -> List[Dict[str, Any]]:
        """
        获取失败的命令记录
        Args:
            limit: 返回的记录数量限制
        Returns:
            List[Dict]: 失败的命令记录列表
        """
        try:
            history = self._load_history()
            
            # 过滤失败的命令
            failed_commands = [entry for entry in history if not entry.get('success', False)]
            
            # 按时间戳倒序排序
            failed_commands.sort(key=lambda x: x.get('timestamp', 0), reverse=True)
            return failed_commands[:limit]
            
        except Exception as e:
            error(f_name, "get_failed_commands", e)
            return []
    
    def get_command_by_id(self, command_id: int) -> Optional[Dict[str, Any]]:
        """
        根据ID获取特定命令记录
        Args:
            command_id: 命令ID
        Returns:
            Optional[Dict]: 命令记录，如果找不到则返回None
        """
        try:
            history = self._load_history()
            for entry in history:
                if entry.get('id') == command_id:
                    return entry
            return None
        except Exception as e:
            error(f_name, "get_command_by_id", e)
            return None
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        获取命令执行统计信息
        Returns:
            Dict: 统计信息字典
        """
        try:
            history = self._load_history()
            
            if not history:
                return {
                    "total_commands": 0,
                    "successful_commands": 0,
                    "failed_commands": 0,
                    "success_rate": 0.0,
                    "most_used_commands": [],
                    "average_execution_time": 0.0
                }
            
            total = len(history)
            successful = len([h for h in history if h.get('success', False)])
            failed = total - successful
            success_rate = (successful / total) * 100 if total > 0 else 0
            
            # 统计最常用的命令
            command_counts = {}
            execution_times = []
            
            for entry in history:
                cmd = entry.get('command', '').split()[0] if entry.get('command') else 'unknown'
                command_counts[cmd] = command_counts.get(cmd, 0) + 1
                
                exec_time = entry.get('execution_time', 0)
                if exec_time > 0:
                    execution_times.append(exec_time)
            
            # 获取前5个最常用命令
            most_used = sorted(command_counts.items(), key=lambda x: x[1], reverse=True)[:5]
            
            # 计算平均执行时间
            avg_time = sum(execution_times) / len(execution_times) if execution_times else 0
            
            return {
                "total_commands": total,
                "successful_commands": successful,
                "failed_commands": failed,
                "success_rate": round(success_rate, 2),
                "most_used_commands": most_used,
                "average_execution_time": round(avg_time, 3)
            }
            
        except Exception as e:
            error(f_name, "get_statistics", e)
            return {}
    
    def clear_history(self) -> bool:
        """
        清空命令历史记录
        Returns:
            bool: 是否成功清空
        """
        try:
            self._save_history([])
            return True
        except Exception as e:
            error(f_name, "clear_history", e)
            return False
    
    def export_history(self, export_path: str) -> bool:
        """
        导出命令历史到指定文件
        Args:
            export_path: 导出文件路径
        Returns:
            bool: 是否成功导出
        """
        try:
            history = self._load_history()
            with open(export_path, 'w', encoding='utf-8') as f:
                json.dump(history, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            error(f_name, "export_history", e)
            return False
    
    def format_timestamp(self, timestamp: float) -> str:
        """
        格式化时间戳为可读字符串
        Args:
            timestamp: 时间戳
        Returns:
            str: 格式化的时间字符串
        """
        try:
            return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(timestamp))
        except:
            return "Unknown time"

# 全局历史记录管理器实例
history_manager = CommandHistory()