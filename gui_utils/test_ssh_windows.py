#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Windows专用SSH连接测试脚本
使用paramiko库测试SSH连接
"""

import subprocess
import sys

REMOTE_USER = "root"
REMOTE_HOST = "192.168.42.1"
REMOTE_PASSWORD = "milkv"
REMOTE_PORT = 22

def test_paramiko():
    """测试paramiko SSH连接"""
    print("测试paramiko SSH连接...")
    try:
        import paramiko
        
        # 创建SSH客户端
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        # 连接到远程主机
        ssh.connect(
            hostname=REMOTE_HOST,
            port=REMOTE_PORT,
            username=REMOTE_USER,
            password=REMOTE_PASSWORD,
            timeout=10
        )
        
        # 执行测试命令
        stdin, stdout, stderr = ssh.exec_command('echo "Hello from paramiko"')
        output = stdout.read().decode().strip()
        error = stderr.read().decode().strip()
        
        ssh.close()
        
        if output:
            print("✓ paramiko连接成功!")
            print(f"远程响应: {output}")
            return True
        else:
            print(f"✗ paramiko连接失败: {error}")
            return False
            
    except ImportError:
        print("✗ paramiko未安装")
        print("安装方法: pip install paramiko")
        return False
    except Exception as e:
        print(f"✗ paramiko连接失败: {e}")
        return False

def test_network():
    """测试网络连通性"""
    print("测试网络连通性...")
    try:
        result = subprocess.run([
            "ping", "-n", "1", REMOTE_HOST
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            print(f"✓ 网络连通性正常 ({REMOTE_HOST})")
            return True
        else:
            print(f"✗ 无法ping通 {REMOTE_HOST}")
            print("请检查网络连接和IP地址")
            return False
    except Exception as e:
        print(f"✗ 网络测试失败: {e}")
        return False

def test_ssh_basic():
    """测试基本SSH命令（需要手动输入密码）"""
    print("\n手动SSH测试:")
    print(f"请在命令行中手动测试: ssh {REMOTE_USER}@{REMOTE_HOST}")
    print(f"密码: {REMOTE_PASSWORD}")
    print("如果手动SSH可以连接，说明SSH服务正常")

def main():
    """主测试流程"""
    print("=" * 50)
    print("Windows SSH连接测试")
    print(f"目标: {REMOTE_USER}@{REMOTE_HOST}")
    print(f"密码: {REMOTE_PASSWORD}")
    print("=" * 50)
    
    # 测试网络连通性
    network_ok = test_network()
    
    if not network_ok:
        print("\n网络不通，请检查:")
        print("1. 设备是否开机")
        print("2. 网络连接是否正常")
        print("3. IP地址是否正确")
        return
    
    print("\n" + "="*30)
    print("测试SSH连接")
    print("="*30)
    
    # 测试paramiko
    paramiko_ok = test_paramiko()
    
    print("\n" + "="*30)
    print("测试结果总结")
    print("="*30)
    
    if paramiko_ok:
        print("✓ Windows SSH连接正常")
        print("可以使用 audio_control_windows.py")
    else:
        print("✗ SSH自动连接失败")
        print("\n可能的问题:")
        print("1. SSH服务未启动")
        print("2. 密码错误")
        print("3. 防火墙阻止连接")
        print("4. paramiko库未正确安装")
        
        print("\n解决方案:")
        print("1. 安装paramiko: pip install paramiko")
        print("2. 检查SSH服务: 在目标设备上运行 systemctl status ssh")
        print("3. 尝试手动SSH连接:")
        test_ssh_basic()
    
    print("\n" + "="*50)

if __name__ == "__main__":
    main() 