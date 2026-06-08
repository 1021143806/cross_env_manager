#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
平台切换服务 — 通过 SSH 修改 AGV DVRIP 注册平台地址

封装了 SSH + rosservice 调用逻辑，供 Web 路由层调用。
"""

import json
import time
from typing import Optional, Dict, Any, List

import yaml
import paramiko


_ROS_SETUP = (
    "source /opt/ros/kinetic/setup.bash 2>/dev/null && "
    "source /home/dahua/agv_workspace/install/setup.bash 2>/dev/null"
)


class PlatformSwitchError(Exception):
    """平台切换过程中的异常"""
    pass


class PlatformSwitchService:
    """平台切换服务"""

    DEFAULT_SSH_USER = "dahua"
    DEFAULT_SSH_PASS = "123$iRAY567*"

    # ── SSH ──────────────────────────────────────────────────────────

    @staticmethod
    def _exec_ssh(host: str, command: str, timeout: int = 15,
                  username: str = None, password: str = None) -> tuple:
        """SSH 执行命令，返回 (exit_code, stdout, stderr)。"""
        u = username or PlatformSwitchService.DEFAULT_SSH_USER
        p = password or PlatformSwitchService.DEFAULT_SSH_PASS
        with paramiko.SSHClient() as ssh:
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(host, port=22, username=u, password=p, timeout=10)
            _, stdout, stderr = ssh.exec_command(command, timeout=timeout)
            rc = stdout.channel.recv_exit_status()
            return rc, stdout.read().decode(), stderr.read().decode()

    @staticmethod
    def _ros_call(host: str, service_call: str,
                  username: str = None, password: str = None) -> tuple:
        """在远程 ROS 环境中执行 rosservice call。"""
        cmd = f"{_ROS_SETUP} && {service_call}"
        return PlatformSwitchService._exec_ssh(host, cmd, username=username,
                                                password=password)

    # ── 查询当前配置 ────────────────────────────────────────────────

    def query_device(self, host: str, ssh_user: str = None,
                     ssh_pass: str = None) -> Dict[str, Any]:
        """
        查询一台 AGV 当前的 DVRIP 配置。

        Returns:
            dict: {host, address, port, enable, device_id, raw_config}
        """
        cmd = (
            """rosservice call /platform/getConfig "name: 'DVRIP'" """
            """2>/dev/null"""
        )
        try:
            rc, out, err = self._ros_call(host, cmd, username=ssh_user,
                                          password=ssh_pass)
        except Exception as e:
            raise PlatformSwitchError(f"SSH 连接失败: {e}")

        if rc != 0:
            raise PlatformSwitchError(
                f"getConfig 调用失败 (exit={rc}): {err or out[:200]}"
            )

        try:
            data = yaml.safe_load(out)
            config = json.loads(data["config"])
        except Exception as e:
            raise PlatformSwitchError(f"解析配置失败: {e}\n原始输出: {out[:300]}")

        rs = config.get("RegisterServer", {})
        srv = (rs.get("Servers") or [{}])[0]

        return {
            "host":       host,
            "address":    srv.get("Address", ""),
            "port":       srv.get("Port", 3002),
            "enable":     rs.get("Enable", False),
            "device_id":  rs.get("DeviceID", ""),
            "raw_config": config,
        }

    # ── 执行切换 ────────────────────────────────────────────────────

    def switch_device(self, host: str, new_ip: str, port: int = 3002,
                      ssh_user: str = None,
                      ssh_pass: str = None) -> Dict[str, Any]:
        """
        切换一台 AGV 的注册平台地址。

        Returns:
            dict: {host, success, old, new, error?}
        """
        # 1. 获取当前配置
        info = self.query_device(host, ssh_user=ssh_user, ssh_pass=ssh_pass)
        config = info["raw_config"]
        old_val = {
            "address": info["address"],
            "port":    info["port"],
            "enable":  info["enable"],
        }

        # 2. 修改
        rs = config.setdefault("RegisterServer", {})
        rs.setdefault("Servers", [{}])
        rs["Servers"][0]["Address"] = new_ip
        rs["Servers"][0]["Port"] = port

        # 3. 写回
        payload = json.dumps(config, separators=(",", ":"))
        cmd = (
            f"""{_ROS_SETUP} && rosservice call """
            f"""/platform/setConfig $'name: \\'DVRIP\\'\\nconfig: \\'{payload}\\'' """
            f"""2>/dev/null"""
        )
        try:
            rc, out, err = self._exec_ssh(host, cmd, username=ssh_user,
                                          password=ssh_pass)
        except Exception as e:
            return {
                "host": host, "success": False,
                "old": old_val, "new": {"address": new_ip, "port": port},
                "error": f"SSH 连接失败: {e}",
            }

        if rc != 0:
            return {
                "host": host, "success": False,
                "old": old_val, "new": {"address": new_ip, "port": port},
                "error": f"setConfig 返回错误 (exit={rc}): {err[:200]}",
            }

        return {
            "host": host, "success": True,
            "old": old_val,
            "new": {"address": new_ip, "port": port},
        }

    # ── 批量操作 ────────────────────────────────────────────────────

    def batch_query(self, hosts: List[str], ssh_user: str = None,
                    ssh_pass: str = None) -> List[Dict[str, Any]]:
        """批量查询多台设备。"""
        results = []
        for host in hosts:
            try:
                results.append(
                    self.query_device(host, ssh_user=ssh_user,
                                      ssh_pass=ssh_pass)
                )
            except PlatformSwitchError as e:
                results.append({"host": host, "error": str(e)})
            except Exception as e:
                results.append({"host": host, "error": f"未知错误: {e}"})
        return results

    def batch_switch(self, hosts: List[str], new_ip: str, port: int = 3002,
                     ssh_user: str = None, ssh_pass: str = None,
                     interval: int = 1) -> List[Dict[str, Any]]:
        """批量切换多台设备，每台间隔 interval 秒。"""
        results = []
        for i, host in enumerate(hosts):
            try:
                results.append(
                    self.switch_device(host, new_ip, port,
                                       ssh_user=ssh_user, ssh_pass=ssh_pass)
                )
            except PlatformSwitchError as e:
                results.append({
                    "host": host, "success": False,
                    "error": str(e),
                })
            except Exception as e:
                results.append({
                    "host": host, "success": False,
                    "error": f"未知错误: {e}",
                })
            if i < len(hosts) - 1:
                time.sleep(interval)
        return results
