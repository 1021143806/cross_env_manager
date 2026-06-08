#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
设备注册平台IP修改工具 (SSH直连版)

功能：通过SSH登录AGV，调用 ROS 服务 /platform/{getConfig,setConfig}
      读取/修改 DVRIP 配置中的 RegisterServer 地址。

使用方法：
# 修改单台
python scripts/DVRIP/set_dvrip.py 10.68.176.57 10.68.2.32

# 仅查看
python scripts/DVRIP/set_dvrip.py 10.68.176.57 --show

# 批量三台
python scripts/DVRIP/set_dvrip.py \
  10.68.176.57 10.68.176.58 10.68.176.59 \
  10.68.2.32
"""

import json
import sys
import time
import argparse
from typing import Optional, Dict, Any, List

import yaml

import paramiko


class DeviceConfigManager:
    """设备配置管理器 - SSH 直连 AGV 版"""

    ROS_SETUP = (
        "source /opt/ros/kinetic/setup.bash 2>/dev/null && "
        "source /home/dahua/agv_workspace/install/setup.bash 2>/dev/null"
    )

    def __init__(self, host: str, port: int = 22,
                 username: str = "dahua", password: str = "123$iRAY567*"):
        self.host = host
        self.port = port
        self.username = username
        self.password = password

    # ── SSH ──────────────────────────────────────────────────────────

    def _exec(self, command: str, timeout: int = 15):
        """执行远程 shell 命令，返回 (exit_code, stdout, stderr)。"""
        with paramiko.SSHClient() as ssh:
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(self.host, port=self.port,
                        username=self.username, password=self.password,
                        timeout=10)
            _, stdout, stderr = ssh.exec_command(command, timeout=timeout)
            rc = stdout.channel.recv_exit_status()
            return rc, stdout.read().decode(), stderr.read().decode()

    def _ros_call(self, service_call: str):
        """在远程 ROS 环境中执行 rosservice call。"""
        cmd = f"{self.ROS_SETUP} && {service_call}"
        return self._exec(cmd)

    # ── 解析 rosservice 输出 ─────────────────────────────────────────

    @staticmethod
    def _parse_getconfig_output(raw: str) -> dict:
        """
        将 rosservice call /getConfig 的输出转为 Python dict。

        ROS kinetic 输出 YAML 格式。长字符串会用 YAML 双引号续行：
            result: 0
            config: "{\"...\":\"...\",\"...\"\\
              ...continued..."
        利用 yaml.safe_load 完整解析 YAML 后取出 config 字段，
        再将 config 的 JSON 文本解析为 Python dict。
        """
        data = yaml.safe_load(raw)
        if not isinstance(data, dict) or "config" not in data:
            raise RuntimeError(
                f"YAML 解析结果缺少 config 字段: {str(data)[:200]}"
            )
        return json.loads(data["config"])

    # ── 核心操作 ─────────────────────────────────────────────────────

    def get_dvrip_config(self) -> dict:
        """获取 AGV 当前的 DVRIP 配置（Python dict）。"""
        cmd = (
            """rosservice call /platform/getConfig "name: 'DVRIP'" """
            """2>/dev/null"""
        )
        rc, out, err = self._ros_call(cmd)
        if rc != 0:
            raise RuntimeError(
                f"/platform/getConfig 调用失败 (exit={rc}): {err or out[:200]}"
            )
        return self._parse_getconfig_output(out)

    def set_dvrip_config(self, config: dict) -> bool:
        """
        将 DVRIP 配置写回 AGV。

        Returns:
            True 表示服务端返回 result: 1（成功）。
        """
        # 紧凑 JSON（与服务端原始格式一致，无多余空格）
        payload = json.dumps(config, separators=(",", ":"))
        # ANSI-C quoting: $'...\n...' 嵌入换行分隔 name / config
        cmd = (
            f"""{self.ROS_SETUP} && rosservice call """
            f"""/platform/setConfig $'name: \\'DVRIP\\'\\nconfig: \\'{payload}\\'' """
            f"""2>/dev/null"""
        )
        rc, out, err = self._exec(cmd)
        if rc != 0:
            raise RuntimeError(
                f"/platform/setConfig 调用失败 (exit={rc}): "
                f"err={err[:300]!r}"
            )
        # result: 0 = 成功（与 getConfig 约定一致）
        return True

    def update_platform_ip(self, new_ip: str, port: int = 3002,
                           device_id: Optional[str] = None,
                           enable: bool = True) -> Dict[str, Any]:
        """
        修改 RegisterServer 中的平台 IP 地址。

        Args:
            new_ip:   新的平台 IP。
            port:     注册端口（默认 3002）。
            device_id: 设备序列号；不传则保留原值。
            enable:   是否启用注册（默认 True）。

        Returns:
            包含旧/新配置的变更摘要。
        """
        config = self.get_dvrip_config()

        rs = config.setdefault("RegisterServer", {})
        rs.setdefault("Servers", [{}])
        server = rs["Servers"][0]

        old_val = {
            "ip":     server.get("Address", "N/A"),
            "port":   server.get("Port", "N/A"),
            "enable": rs.get("Enable", "N/A"),
        }

        rs["Enable"] = enable
        server["Address"] = new_ip
        server["Port"] = port
        if device_id:
            rs["DeviceID"] = device_id

        ok = self.set_dvrip_config(config)

        return {
            "success": ok,
            "host":    self.host,
            "old":     old_val,
            "new":     {"ip": new_ip, "port": port, "enable": enable},
        }

    # ── 批量 ─────────────────────────────────────────────────────────

    def batch_update(self, hosts: List[str], new_ip: str,
                     port: int = 3002, interval: int = 1,
                     device_ids: Optional[Dict[str, str]] = None):
        """
        对多台 AGV 依次执行 update_platform_ip。

        Args:
            hosts:      AGV IP 列表。
            new_ip:     新的平台 IP。
            port:       注册端口。
            interval:   设备间间隔秒数。
            device_ids: {host: device_id} 可选映射。

        Returns:
            list[dict]  每台设备的结果。
        """
        device_ids = device_ids or {}
        results = []
        for i, host in enumerate(hosts, 1):
            mgr = DeviceConfigManager(host, password=self.password)
            try:
                r = mgr.update_platform_ip(
                    new_ip, port, device_id=device_ids.get(host))
                results.append(r)
                status = "✓" if r["success"] else "✗"
                print(f"[{i}/{len(hosts)}] {host}  {status}  "
                      f"{r['old']['ip']}:{r['old']['port']} → "
                      f"{r['new']['ip']}:{r['new']['port']}")
            except Exception as e:
                results.append({"host": host, "success": False, "error": str(e)})
                print(f"[{i}/{len(hosts)}] {host}  ✗  {e}")
            if i < len(hosts):
                time.sleep(interval)
        return results


# ══════════════════════════════════════════════════════════════════════
#  CLI 入口
# ══════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="AGV DVRIP 配置修改工具 (SSH 直连版)")
    parser.add_argument("host", nargs="+",
                        help="AGV IP 地址（可多个，实现批量）")
    parser.add_argument("new_ip",
                        help="新的平台注册 IP")
    parser.add_argument("--port", type=int, default=3002,
                        help="注册端口 (默认 3002)")
    parser.add_argument("--device-id",
                        help="设备序列号（单设备时使用）")
    parser.add_argument("--ssh-user", default="dahua",
                        help="SSH 用户 (默认 dahua)")
    parser.add_argument("--ssh-pass", default="123$iRAY567*",
                        help="SSH 密码")
    parser.add_argument("--show", action="store_true",
                        help="仅查看当前配置，不修改")

    args = parser.parse_args()

    # ── 仅查看 ──
    if args.show:
        for host in args.host:
            mgr = DeviceConfigManager(host, username=args.ssh_user,
                                      password=args.ssh_pass)
            try:
                cfg = mgr.get_dvrip_config()
                rs = cfg.get("RegisterServer", {})
                srv = (rs.get("Servers") or [{}])[0]
                print(f"{host}:  "
                      f"Address={srv.get('Address','?')}  "
                      f"Port={srv.get('Port','?')}  "
                      f"Enable={rs.get('Enable','?')}  "
                      f"DeviceID={rs.get('DeviceID','?')}")
            except Exception as e:
                print(f"{host}:  ✗  {e}")
        return

    # ── 修改 ──
    mgr = DeviceConfigManager(args.host[0], username=args.ssh_user,
                              password=args.ssh_pass)

    if len(args.host) == 1:
        # 单设备
        result = mgr.update_platform_ip(
            args.new_ip, args.port, args.device_id)
        print(json.dumps(result, indent=2, ensure_ascii=False,
                         default=str))
        if result["success"]:
            print(f"\n✓ 修改成功: "
                  f"{result['old']['ip']}:{result['old']['port']} → "
                  f"{result['new']['ip']}:{result['new']['port']}")
        else:
            sys.exit(1)
    else:
        # 多设备
        device_ids = {}
        if args.device_id and len(args.host) == 1:
            device_ids[args.host[0]] = args.device_id
        mgr.batch_update(args.host, args.new_ip, args.port,
                         device_ids=device_ids or None)


def quick_set(host: str, new_ip: str, port: int = 3002,
              device_id: Optional[str] = None,
              ssh_pass: str = "123$iRAY567*") -> Dict[str, Any]:
    """
    快速配置函数，方便在其他脚本中调用。

    Args:
        host:      AGV IP 地址。
        new_ip:    新的平台 IP。
        port:      注册端口。
        device_id: 设备序列号（可选）。
        ssh_pass:  SSH 密码。

    Returns:
        变更结果 dict。
    """
    mgr = DeviceConfigManager(host, password=ssh_pass)
    return mgr.update_platform_ip(new_ip, port, device_id)


if __name__ == "__main__":
    main()
