#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SSH连接测试脚本
测试到milkv板子的SSH连接是否正常
"""

import subprocess
import sys

REMOTE_USER = "root"
REMOTE_HOST = "192.168.42.1"
REMOTE_PASSWORD = "milkv"
REMOTE_ADDR = f"{REMOTE_USER}@{REMOTE_HOST}"

def test_sshpass():
    """测试sshpass方法"""
    print("测试方法1: sshpass")
    try:
        result = subprocess.run([
            "sshpass", "-p", REMOTE_PASSWORD, 
            "ssh", "-o", "StrictHostKeyChecking=no", 
            REMOTE_ADDR, "echo", "Hello from sshpass"
        ], capture_output=True, text=True, check=True)
        
        print("✓ sshpass连接成功!")
        print(f"远程响应: {result.stdout.strip()}")
        return True
    except FileNotFoundError:
        print("✗ sshpass未安装")
        return False
    except subprocess.CalledProcessError as e:
        print(f"✗ sshpass连接失败: {e}")
        print(f"错误输出: {e.stderr}")
        return False
    except Exception as e:
        print(f"✗ sshpass出现异常: {e}")
        return False

def test_pexpect():
    """测试pexpect方法"""
    print("\n测试方法2: pexpect")
    try:
        import pexpect
        
        child = pexpect.spawn(f'ssh -o StrictHostKeyChecking=no {REMOTE_ADDR} "echo Hello from pexpect"')
        
        try:
            child.expect("password:", timeout=10)
            child.sendline(REMOTE_PASSWORD)
            child.expect(pexpect.EOF)
            output = child.before.decode()
            child.close()
            
            print("✓ pexpect连接成功!")
            print(f"远程响应: {output.strip()}")
            return True
            
        except pexpect.TIMEOUT:
            print("✗ pexpect连接超时")
            child.close()
            return False
            
    except ImportError:
        print("✗ pexpect未安装")
        print("安装方法: pip install pexpect")
        return False
    except Exception as e:
        print(f"✗ pexpect出现异常: {e}")
        return False

def test_basic_ssh():
    """测试基本SSH连接（需要手动输入密码）"""
    print("\n测试方法3: 基本SSH (需要手动输入密码)")
    print(f"请手动测试: ssh {REMOTE_ADDR}")
    print(f"密码: {REMOTE_PASSWORD}")
    return None

def test_network():
    """测试网络连通性"""
    print("测试网络连通性...")
    try:
        result = subprocess.run([
            "ping", "-c", "1" if sys.platform != "win32" else "-n", "1", REMOTE_HOST
        ], capture_output=True)
        
        if result.returncode == 0:
            print(f"✓ 网络连通性正常 ({REMOTE_HOST})")
            return True
        else:
            print(f"✗ 无法ping通 {REMOTE_HOST}")
            return False
    except Exception as e:
        print(f"✗ 网络测试失败: {e}")
        return False

def main():
    """主测试流程"""
    print("=" * 50)
    print("SSH连接测试")
    print(f"目标: {REMOTE_ADDR}")
    print(f"密码: {REMOTE_PASSWORD}")
    print("=" * 50)
    
    # 测试网络连通性
    if not test_network():
        print("\n请检查网络连接和设备IP地址")
        return
    
    print("\n" + "="*30)
    print("测试SSH连接方法")
    print("="*30)
    
    # 测试各种SSH方法
    sshpass_ok = test_sshpass()
    pexpect_ok = test_pexpect()
    
    print("\n" + "="*30)
    print("测试结果总结")
    print("="*30)
    
    if sshpass_ok:
        print("✓ 推荐使用sshpass方法 (最稳定)")
    elif pexpect_ok:
        print("✓ 可以使用pexpect方法")
    else:
        print("✗ 自动SSH方法都不可用")
        print("建议:")
        print("1. 检查密码是否正确")
        print("2. 检查SSH服务是否启动")
        print("3. 安装sshpass或pexpect")
        test_basic_ssh()
    
    print("\n" + "="*50)

if __name__ == "__main__":
    main() 