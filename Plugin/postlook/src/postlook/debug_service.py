"""
postlook · 报文调试 Service 层
TCP Client: 连接→发送→接收→断开（一连接一断）
Ping + Telnet 端口检测
报文数据管理（messages.toml 热更新）
"""

import socket
import subprocess
import time
import re
from pathlib import Path
from typing import Dict, Any, Optional, List


# ── 项目路径 ──
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"
MESSAGES_PATH = DATA_DIR / "messages.toml"


# ═══════════════════════════════════════════════
#  Ping + TCP 端口检测
# ═══════════════════════════════════════════════

def ping_host(host: str, timeout: float = 2.0) -> Dict[str, Any]:
    """ICMP Ping 检测主机是否可达
    
    使用系统 ping 命令（Linux: ping -c 1 -W 2）
    不需要 root 权限。
    
    Returns:
        {"reachable": bool, "latency_ms": float | None, "error": str | None}
    """
    try:
        result = subprocess.run(
            ["ping", "-c", "1", "-W", str(int(timeout)), host],
            capture_output=True, text=True, timeout=timeout + 3
        )
        if result.returncode == 0:
            # 解析 RTT: "time=1.23 ms"
            match = re.search(r"time=(\d+\.?\d*)\s*ms", result.stdout)
            latency = float(match.group(1)) if match else None
            return {"reachable": True, "latency_ms": latency, "error": None}
        else:
            # ping 失败但命令成功执行（如 100% packet loss）
            if "100% packet loss" in result.stdout or "0 received" in result.stdout:
                return {"reachable": False, "latency_ms": None, "error": "主机不可达 (100% packet loss)"}
            return {"reachable": False, "latency_ms": None, "error": f"ping 失败: {result.stderr.strip() or '未知错误'}"}
    except subprocess.TimeoutExpired:
        return {"reachable": False, "latency_ms": None, "error": "ping 超时"}
    except FileNotFoundError:
        return {"reachable": False, "latency_ms": None, "error": "系统未安装 ping 命令"}
    except Exception as e:
        return {"reachable": False, "latency_ms": None, "error": str(e)}


def check_port(host: str, port: int, timeout: float = 2.0) -> Dict[str, Any]:
    """TCP 端口探测（telnet 式检测）
    
    Returns:
        {"open": bool, "elapsed_ms": float | None, "error": str | None}
    """
    if not host or not port:
        return {"open": False, "elapsed_ms": None, "error": "host 或 port 为空"}
    try:
        t0 = time.perf_counter()
        sock = socket.create_connection((host, int(port)), timeout=timeout)
        sock.close()
        elapsed = (time.perf_counter() - t0) * 1000
        return {"open": True, "elapsed_ms": round(elapsed, 1), "error": None}
    except socket.timeout:
        return {"open": False, "elapsed_ms": None, "error": f"连接超时 ({timeout}s)"}
    except ConnectionRefusedError:
        elapsed = (time.perf_counter() - t0) * 1000 if 't0' in dir() else None
        return {"open": False, "elapsed_ms": round(elapsed, 1) if elapsed else None, "error": "端口拒绝连接"}
    except OSError as e:
        return {"open": False, "elapsed_ms": None, "error": f"网络错误: {e}"}
    except Exception as e:
        return {"open": False, "elapsed_ms": None, "error": str(e)}


def test_connection(host: str, port: int) -> Dict[str, Any]:
    """综合检测：先 Ping，再端口探测"""
    ping_result = ping_host(host)
    
    if ping_result["reachable"]:
        port_result = check_port(host, port)
    else:
        port_result = {"open": False, "elapsed_ms": None, "error": "主机不可达，跳过端口检测"}
    
    return {
        "ping": ping_result,
        "port": port_result,
        "host": host,
        "port": port,
    }


# ═══════════════════════════════════════════════
#  TCP 报文发送（一连接一断）
# ═══════════════════════════════════════════════

def send_hex_message(
    host: str,
    port: int,
    hex_str: str,
    connect_timeout: float = 3.0,
    recv_timeout: float = 1.0,
    recv_buffer: int = 4096,
    auto_lowercase: bool = True,
    auto_uppercase: bool = False,
) -> Dict[str, Any]:
    """发送单条十六进制报文
    
    流程：创建 socket → connect → send → recv(最多等1s) → close
    
    Args:
        host: 目标 IP
        port: 目标端口
        hex_str: 十六进制字符串（如 "AB 66 00 00 03 01 00 FF FD 03"）
        connect_timeout: 连接超时 (秒)
        recv_timeout: 接收超时 (秒)
        recv_buffer: 接收缓冲区大小
        auto_lowercase: 发送前自动转小写
        auto_uppercase: 发送前自动转大写（优先级高于 lowercase）
    
    Returns:
        {
            "success": bool,
            "sent_hex": str,        # 实际发送的 hex（处理后）
            "sent_bytes": int,      # 发送字节数
            "received_hex": str | None,
            "received_bytes": int,
            "connect_ms": float,    # 连接耗时
            "send_ms": float,       # 发送耗时
            "recv_ms": float,       # 接收耗时
            "total_ms": float,      # 总耗时
            "error": str | None,
        }
    """
    result = {
        "success": False,
        "sent_hex": "",
        "sent_bytes": 0,
        "received_hex": None,
        "received_bytes": 0,
        "connect_ms": 0,
        "send_ms": 0,
        "recv_ms": 0,
        "total_ms": 0,
        "error": None,
    }
    
    # ── 预处理 hex 字符串 ──
    # 去除空格、换行、注释
    cleaned = hex_str.strip()
    # 移除 0x 前缀
    cleaned = cleaned.replace("0x", "").replace("0X", "")
    # 移除所有空白字符
    cleaned = "".join(cleaned.split())
    # 验证只含合法 hex 字符
    if not re.match(r"^[0-9a-fA-F]*$", cleaned):
        result["error"] = "HEX 字符串包含非法字符（仅允许 0-9 a-f A-F 空格）"
        return result
    if len(cleaned) == 0:
        result["error"] = "HEX 字符串为空"
        return result
    if len(cleaned) % 2 != 0:
        result["error"] = "HEX 字符串长度必须为偶数"
        return result
    
    # 大小写转换
    if auto_uppercase:
        cleaned = cleaned.upper()
    elif auto_lowercase:
        cleaned = cleaned.lower()
    
    # 格式化显示（每字节空格分隔）
    formatted = " ".join(cleaned[i:i+2] for i in range(0, len(cleaned), 2)).upper()
    result["sent_hex"] = formatted
    
    try:
        data = bytes.fromhex(cleaned)
    except ValueError as e:
        result["error"] = f"HEX 解析失败: {e}"
        return result
    
    sock = None
    t_total_start = time.perf_counter()
    
    try:
        # ── Step 1: 连接 ──
        t_conn_start = time.perf_counter()
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(connect_timeout)
        sock.connect((host, port))
        result["connect_ms"] = round((time.perf_counter() - t_conn_start) * 1000, 1)
        
        # ── Step 2: 发送 ──
        t_send_start = time.perf_counter()
        sent = sock.send(data)
        result["send_ms"] = round((time.perf_counter() - t_send_start) * 1000, 1)
        result["sent_bytes"] = sent
        
        # ── Step 3: 接收 ──
        t_recv_start = time.perf_counter()
        sock.settimeout(recv_timeout)
        try:
            received = sock.recv(recv_buffer)
            result["received_bytes"] = len(received)
            result["received_hex"] = " ".join(f"{b:02X}" for b in received)
        except socket.timeout:
            result["received_bytes"] = 0
            result["received_hex"] = None
        except OSError:
            result["received_bytes"] = 0
            result["received_hex"] = None
        result["recv_ms"] = round((time.perf_counter() - t_recv_start) * 1000, 1)
        
        result["success"] = True
        
    except socket.timeout:
        result["error"] = f"连接超时 ({connect_timeout}s)"
    except ConnectionRefusedError:
        result["error"] = f"连接被拒绝: {host}:{port}"
    except OSError as e:
        result["error"] = f"网络错误: {e}"
    except Exception as e:
        result["error"] = str(e)
    finally:
        if sock:
            try:
                sock.close()
            except Exception:
                pass
    
    result["total_ms"] = round((time.perf_counter() - t_total_start) * 1000, 1)
    return result


# ═══════════════════════════════════════════════
#  报文数据管理
# ═══════════════════════════════════════════════

def load_messages() -> Dict[str, Any]:
    """加载 messages.toml，返回分组数据"""
    try:
        import tomllib  # Python 3.11+
    except ImportError:
        try:
            import tomli as tomllib
        except ImportError:
            return {"groups": [], "error": "tomli/tomllib 未安装"}

    if not MESSAGES_PATH.exists():
        return {"groups": [], "error": None, "path": str(MESSAGES_PATH)}

    try:
        with open(MESSAGES_PATH, "rb") as f:
            data = tomllib.load(f)
    except Exception as e:
        return {"groups": [], "error": f"TOML 解析失败: {e}", "path": str(MESSAGES_PATH)}

    groups = data.get("group", [])
    
    # 规范化：确保每条 message 有默认字段
    for g in groups:
        msgs = g.get("message", [])
        for m in msgs:
            m.setdefault("type", "hex")
            m.setdefault("annotation", "")
            m.setdefault("seq", 0)
            m.setdefault("delay_ms", 0)
            m.setdefault("color", "")
    
    return {
        "groups": groups,
        "error": None,
        "path": str(MESSAGES_PATH),
        "group_count": len(groups),
        "message_count": sum(len(g.get("message", [])) for g in groups),
    }


def save_messages(toml_content: str) -> Dict[str, Any]:
    """保存 messages.toml，返回重新加载后的数据"""
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        with open(MESSAGES_PATH, "w", encoding="utf-8") as f:
            f.write(toml_content)
    except PermissionError as e:
        return {"success": False, "error": f"无法写入文件: {e}"}
    except Exception as e:
        return {"success": False, "error": str(e)}

    # 重新加载以验证
    result = load_messages()
    result["success"] = result.get("error") is None
    return result


def reload_messages() -> Dict[str, Any]:
    """热重新加载 messages.toml"""
    result = load_messages()
    result["success"] = result.get("error") is None
    return result
