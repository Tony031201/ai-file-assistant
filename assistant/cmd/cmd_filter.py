import re
import os
from typing import TypedDict

class Output(TypedDict):
    """cmd为输出的命令，status表示是否通过过滤器"""
    cmd: str
    status: bool

# 危险命令黑名单 - 禁止执行的命令
BANNED_COMMANDS = [
    # 系统关键操作
    "shutdown", "reboot", "poweroff", "halt", "init",
    "systemctl stop", "systemctl disable", "systemctl restart",
    
    # 文件系统危险操作
    "rm -rf", "rmdir", "del /f", "del /q", "format", "fdisk",
    "mkfs", "dd if=", "shred", "wipe",
    
    # 网络和系统服务
    "iptables", "ufw", "firewall", "netsh", "route add", "route delete",
    
    # 用户和权限管理
    "passwd", "useradd", "userdel", "usermod", "chown", "chmod 777",
    "chmod -R", "chsh", "sudo su", "su -",
    
    # 包管理和软件安装
    "apt remove", "apt purge", "yum remove", "pip uninstall --yes",
    "npm uninstall -g", "choco uninstall",
    
    # 进程管理
    "kill -9", "killall", "pkill", "taskkill /f",
    
    # 注册表操作 (Windows)
    "reg delete", "regedit", "regsvr32",
    
    # 脚本执行
    "eval", "exec", "bash -c", "sh -c", "cmd /c",
    "powershell -command", "powershell -file",
    
    # 压缩和解压危险操作
    "tar --absolute-names", "unzip -o",
]

# 高风险关键词
HIGH_RISK_KEYWORDS = [
    "/dev/", "\\\\", "&&", "||", ";", "|", ">", ">>", 
    "$", "`", "$(", "${", "*", "?", "[", "]",
    "~", "../", "..\\", "/etc/", "/root/", "/boot/",
    "c:\\windows\\", "c:\\system32\\", "%systemroot%"
]

# 允许的安全命令 - 白名单
SAFE_COMMANDS = [
    # 文件和目录查看
    "ls", "dir", "pwd", "cd", "tree", "find", "locate",
    "cat", "type", "more", "less", "head", "tail",
    "wc", "sort", "grep", "findstr", "awk", "sed",
    
    # 系统信息查看
    "ps", "top", "htop", "tasklist", "systeminfo", "uname",
    "whoami", "id", "groups", "date", "uptime", "free",
    "df", "du", "lsblk", "mount", "lscpu", "lsmem",
    
    # 网络查看
    "ping", "tracert", "traceroute", "nslookup", "dig",
    "netstat", "ss", "lsof", "ifconfig", "ipconfig",
    "arp", "route print",
    
    # 文件操作（相对安全）
    "mkdir", "touch", "cp", "copy", "mv", "move",
    "ln", "mklink",
    
    # 压缩解压
    "tar -tf", "tar -tzf", "zip", "unzip -l", "7z l",
    
    # 编程和开发
    "python --version", "node --version", "npm --version",
    "git status", "git log", "git diff", "git branch",
    "pip list", "pip show",
    
    # 文本处理
    "echo", "printf", "cut", "tr", "uniq", "diff",
]

def CMD_Filter(cmd: str) -> Output:
    """
    过滤命令，确保只允许执行安全的命令
    Args:
        cmd: 待执行的命令字符串
    Returns:
        Output: 包含过滤后的命令和状态的字典
    """
    # 数据清洗
    text = cmd.strip()
    cmd_lower = text.lower()
    
    # 空命令检查
    if not text:
        return {"cmd": text, "status": False}
    
    # 检查危险命令黑名单
    for banned in BANNED_COMMANDS:
        if banned.lower() in cmd_lower:
            return {"cmd": text, "status": False}
    
    # 检查高风险关键词
    for risk_keyword in HIGH_RISK_KEYWORDS:
        if risk_keyword in text:
            return {"cmd": text, "status": False}
    
    # 获取命令的第一个词（主命令）
    main_cmd = text.split()[0] if text.split() else ""
    main_cmd_lower = main_cmd.lower()
    
    # 检查主命令是否在安全白名单中
    is_safe = False
    for safe_cmd in SAFE_COMMANDS:
        if main_cmd_lower == safe_cmd.lower() or main_cmd_lower.startswith(safe_cmd.lower() + "."):
            is_safe = True
            break
    
    # 额外检查：禁止以 sudo 开头的命令（除非在安全列表中）
    if cmd_lower.startswith("sudo "):
        sudo_cmd = " ".join(text.split()[1:])  # 移除sudo获取实际命令
        return CMD_Filter(sudo_cmd)  # 递归检查sudo后的命令
    
    # 长度限制（防止命令注入）
    if len(text) > 500:
        return {"cmd": text, "status": False}
    
    # 命令参数安全性检查
    if is_safe:
        # 即使是安全命令，也要检查参数是否包含危险内容
        args = " ".join(text.split()[1:]) if len(text.split()) > 1 else ""
        if args:
            # 检查参数中是否包含危险路径或符号
            dangerous_patterns = [
                r"/etc/passwd", r"/etc/shadow", r"/root/", 
                r"c:\\windows\\system32", r"c:\\users\\[^/]+\\ntuser\.dat",
                r"\.\./", r"\.\.\\", r"&&", r"\|\|", r";\s*rm", r";\s*del"
            ]
            for pattern in dangerous_patterns:
                if re.search(pattern, args, re.IGNORECASE):
                    return {"cmd": text, "status": False}
    
    return {"cmd": text, "status": is_safe}


# 测试用例（注释掉的）
# print(CMD_Filter("ls -la"))                    # ✅ 安全
# print(CMD_Filter("cat /etc/passwd"))           # ❌ 危险路径
# print(CMD_Filter("rm -rf /"))                  # ❌ 危险命令  
# print(CMD_Filter("ping google.com"))           # ✅ 安全
# print(CMD_Filter("sudo shutdown now"))         # ❌ 危险命令
# print(CMD_Filter("python --version"))          # ✅ 安全
# print(CMD_Filter("echo hello && rm file"))     # ❌ 命令链