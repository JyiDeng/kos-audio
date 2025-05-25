#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试新的文件传输方法
"""

import os
import sys

# 添加当前目录到路径，以便导入audio_control模块
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from audio_control import (
    transfer_from_remote_method1,
    transfer_from_remote_method2, 
    transfer_from_remote_method3,
    transfer_to_remote_method1,
    transfer_to_remote_method2,
    transfer_to_remote_method3,
    REMOTE_ADDR
)

def test_transfer_methods():
    """测试所有传输方法"""
    
    # 创建一个测试文件
    test_content = b"Hello, this is a test file!\nLine 2\nLine 3\n"
    local_test_file = "test_file.txt"
    remote_test_file = "/tmp/test_file.txt"
    
    # 写测试文件
    with open(local_test_file, 'wb') as f:
        f.write(test_content)
    
    print("=" * 50)
    print("测试文件传输方法")
    print("=" * 50)
    
    # 测试上传方法
    print("\n测试上传方法:")
    upload_methods = [
        ("Base64编码", transfer_to_remote_method1),
        ("SSH+tee", transfer_to_remote_method2),
        ("SSH+dd", transfer_to_remote_method3)
    ]
    
    successful_upload = None
    for name, method in upload_methods:
        print(f"\n尝试 {name} 上传...")
        try:
            if method(local_test_file, remote_test_file):
                print(f"✓ {name} 上传成功!")
                successful_upload = name
                break
        except Exception as e:
            print(f"✗ {name} 上传失败: {e}")
    
    if not successful_upload:
        print("所有上传方法都失败了！")
        return
    
    # 测试下载方法
    print(f"\n测试下载方法 (使用 {successful_upload} 成功上传的文件):")
    download_methods = [
        ("Base64编码", transfer_from_remote_method1),
        ("SSH+cat", transfer_from_remote_method2),
        ("SSH+dd", transfer_from_remote_method3)
    ]
    
    for name, method in download_methods:
        print(f"\n尝试 {name} 下载...")
        download_file = f"downloaded_{name.replace('+', '_').lower()}.txt"
        try:
            if method(remote_test_file, download_file):
                # 验证文件内容
                with open(download_file, 'rb') as f:
                    downloaded_content = f.read()
                
                if downloaded_content == test_content:
                    print(f"✓ {name} 下载成功且内容正确!")
                else:
                    print(f"✗ {name} 下载成功但内容不匹配")
                    print(f"原始: {test_content}")
                    print(f"下载: {downloaded_content}")
                    
                # 清理下载的文件
                os.remove(download_file)
        except Exception as e:
            print(f"✗ {name} 下载失败: {e}")
    
    # 清理
    print(f"\n清理测试文件...")
    try:
        os.remove(local_test_file)
        print("✓ 本地测试文件已删除")
    except:
        pass
    
    # 清理远程文件
    try:
        import subprocess
        subprocess.run(["ssh", REMOTE_ADDR, f"rm -f {remote_test_file}"], check=True)
        print("✓ 远程测试文件已删除")
    except:
        print("⚠ 无法删除远程测试文件")

if __name__ == "__main__":
    print(f"连接目标: {REMOTE_ADDR}")
    print("确保你已经配置好SSH密钥或者准备输入密码...")
    input("按Enter键开始测试...")
    
    test_transfer_methods()
    
    print("\n测试完成!") 