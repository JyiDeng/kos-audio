#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Windows专用音频控制脚本
使用paramiko库解决Windows上SSH密码问题
"""

import os
import subprocess
import base64
import time
from datetime import datetime

REMOTE_USER = "root"
REMOTE_HOST = "192.168.42.1"
REMOTE_PASSWORD = "milkv"
REMOTE_PORT = 22

def get_timestamped_filename(base_name):
    """生成带时间戳的文件名"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    name, ext = os.path.splitext(base_name)
    return f"{name}_{timestamp}{ext}"

# 基础文件名
BASE_RAW = "test_raw.wav"
BASE_PROCESSED = "test.wav"
BASE_RESPONSE = "response.wav"

# 全局SSH客户端
ssh_client = None

def init_ssh_connection():
    """初始化SSH连接"""
    global ssh_client
    try:
        import paramiko
        
        ssh_client = paramiko.SSHClient()
        ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh_client.connect(
            hostname=REMOTE_HOST,
            port=REMOTE_PORT,
            username=REMOTE_USER,
            password=REMOTE_PASSWORD,
            timeout=10
        )
        print("✓ SSH连接建立成功")
        return True
    except ImportError:
        print("错误: 需要安装paramiko库")
        print("安装方法: pip install paramiko")
        return False
    except Exception as e:
        print(f"✗ SSH连接失败: {e}")
        return False

def close_ssh_connection():
    """关闭SSH连接"""
    global ssh_client
    if ssh_client:
        ssh_client.close()
        ssh_client = None

def run_ssh_command(cmd, capture_output=False):
    """执行SSH命令"""
    global ssh_client
    if not ssh_client:
        if not init_ssh_connection():
            raise Exception("SSH连接失败")
    
    try:
        # 如果cmd是列表，转换为字符串
        if isinstance(cmd, list):
            cmd_str = " ".join([f'"{c}"' if " " in c else c for c in cmd])
        else:
            cmd_str = cmd
        
        stdin, stdout, stderr = ssh_client.exec_command(cmd_str)
        
        if capture_output:
            output = stdout.read().decode('utf-8')
            error = stderr.read().decode('utf-8')
            return_code = stdout.channel.recv_exit_status()
            
            # 模拟subprocess.run的返回对象
            class SSHResult:
                def __init__(self, stdout, stderr, returncode):
                    self.stdout = stdout
                    self.stderr = stderr
                    self.returncode = returncode
            
            return SSHResult(output, error, return_code)
        else:
            # 等待命令完成
            return_code = stdout.channel.recv_exit_status()
            
            class SSHResult:
                def __init__(self, returncode):
                    self.returncode = returncode
                    self.stdout = ""
                    self.stderr = ""
            
            return SSHResult(return_code)
            
    except Exception as e:
        print(f"SSH命令执行失败: {e}")
        raise

def transfer_from_remote_base64(remote_path, local_path):
    """使用base64从远程下载文件"""
    print(f"下载文件: {remote_path} -> {local_path}")
    try:
        result = run_ssh_command(f"base64 < {remote_path}", capture_output=True)
        
        if result.returncode != 0:
            print(f"远程命令失败: {result.stderr}")
            return False
        
        # 解码并保存
        with open(local_path, 'wb') as f:
            f.write(base64.b64decode(result.stdout.strip()))
        
        print(f"✓ 成功下载")
        return True
    except Exception as e:
        print(f"✗ 下载失败: {e}")
        return False

def transfer_to_remote_scp(local_path, remote_path):
    """使用paramiko的SCP功能上传文件（更快）"""
    print(f"上传文件 (SCP): {local_path} -> {remote_path}")
    try:
        import paramiko
        from scp import SCPClient
        
        # 使用现有的SSH连接
        global ssh_client
        if not ssh_client:
            if not init_ssh_connection():
                return False
        
        # 使用SCP传输
        with SCPClient(ssh_client.get_transport()) as scp:
            scp.put(local_path, remote_path)
        
        print(f"✓ SCP上传成功")
        return True
    except ImportError:
        print("SCP库未安装，回退到base64方法...")
        return transfer_to_remote_base64(local_path, remote_path)
    except Exception as e:
        print(f"SCP传输失败: {e}，回退到base64方法...")
        return transfer_to_remote_base64(local_path, remote_path)

def transfer_to_remote_base64(local_path, remote_path):
    """使用base64上传文件到远程"""
    print(f"上传文件 (Base64): {local_path} -> {remote_path}")
    try:
        # 读取并编码文件
        with open(local_path, 'rb') as f:
            encoded = base64.b64encode(f.read()).decode()
        
        # 优化的分块传输
        chunk_size = 6000  # 进一步增加块大小
        
        # 清空目标文件
        run_ssh_command(f"echo -n '' > {remote_path}")
        
        # 分块传输
        total_chunks = (len(encoded) + chunk_size - 1) // chunk_size
        print(f"  开始传输 {total_chunks} 个数据块...")
        
        for i in range(0, len(encoded), chunk_size):
            chunk = encoded[i:i+chunk_size]
            chunk_num = i // chunk_size + 1
            
            # 每10块显示一次进度
            if chunk_num % 10 == 0 or chunk_num == total_chunks:
                print(f"  进度: {chunk_num}/{total_chunks}")
            
            if i == 0:
                cmd = f"echo -n '{chunk}' | base64 -d > {remote_path}"
            else:
                cmd = f"echo -n '{chunk}' | base64 -d >> {remote_path}"
            
            result = run_ssh_command(cmd)
            if result.returncode != 0:
                print(f"块 {chunk_num} 传输失败")
                return False
        
        print(f"✓ Base64上传完成")
        return True
    except Exception as e:
        print(f"✗ 上传失败: {e}")
        return False

def ensure_remote_directory(remote_path):
    """确保远程目录存在"""
    print("检查远程目录...")
    try:
        # 获取录音文件的目录
        import os
        remote_dir = os.path.dirname(remote_path)
        
        # 创建目录（如果不存在）
        result = run_ssh_command(f"mkdir -p {remote_dir}")
        if result.returncode == 0:
            print(f"✓ 远程目录准备就绪: {remote_dir}")
            return True
        else:
            print(f"✗ 无法创建远程目录: {remote_dir}")
            return False
    except Exception as e:
        print(f"✗ 目录检查失败: {e}")
        return False

def ensure_local_directory():
    """确保本地record目录存在"""
    try:
        import os
        local_record_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "record")
        if not os.path.exists(local_record_dir):
            os.makedirs(local_record_dir)
            print(f"✓ 创建本地目录: {local_record_dir}")
        else:
            print(f"✓ 本地目录已存在: {local_record_dir}")
        return local_record_dir
    except Exception as e:
        print(f"✗ 无法创建本地目录: {e}")
        return None

def record_remote(remote_path, duration=5):
    """远程录音duration秒"""
    print(f"开始远程录音 ({duration}秒)...")
    
    # 先确保目录存在
    if not ensure_remote_directory(remote_path):
        return False
    
    try:
        result = run_ssh_command([
            "arecord", "-D", "hw:0,0", "-f", "S16_LE", 
            "-r", "16000", "-c", "1", "-d", str(duration), remote_path
        ])
        
        if result.returncode == 0:
            print("✓ 录音完成")
            return True
        else:
            print("✗ 录音失败")
            print(f"错误信息: {result.stderr if hasattr(result, 'stderr') else '未知错误'}")
            return False
    except Exception as e:
        print(f"✗ 录音失败: {e}")
        return False

def process_audio_local(remote_raw, local_raw, local_processed):
    """处理音频：下载、降噪、标准化"""
    print("处理音频...")
    
    # 下载原始录音
    if not transfer_from_remote_base64(remote_raw, local_raw):
        return False
    
    # 使用FFmpeg处理音频
    try:
        ffmpeg_cmd = [
            "ffmpeg", "-y", "-i", local_raw,
            "-af", "afftdn=nr=12:nt=w, dynaudnorm=f=500:g=15, volume=1000.0",
            local_processed
        ]
        result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"FFmpeg错误: {result.stderr}")
            return False
        
        print("✓ 音频处理完成")
        return True
    except Exception as e:
        print(f"✗ 音频处理失败: {e}")
        return False

def play_remote_audio(local_wav_path, remote_wav_path):
    """播放音频：上传并在远程播放"""
    print("播放音频...")
    
    # 上传音频文件（优先使用SCP）
    if not transfer_to_remote_scp(local_wav_path, remote_wav_path):
        return False
    
    # 远程播放
    try:
        result = run_ssh_command([
            "aplay", "-D", "hw:1,0", "-f", "S16_LE", 
            "-r", "16000", "-c", "1", remote_wav_path
        ])
        
        if result.returncode == 0:
            print("✓ 音频播放完成")
            return True
        else:
            print("✗ 播放失败")
            return False
    except Exception as e:
        print(f"✗ 播放失败: {e}")
        return False

def perform_speech_recognition(audio_file):
    """执行语音识别并输出结果"""
    try:
        from speech_recognition import create_recognizer
        
        print("初始化语音识别模型...")
        recognizer = create_recognizer('paraformer')
        
        if recognizer.is_available():
            print("✓ 语音识别模型加载成功")
        else:
            print("⚠ 使用模拟语音识别（真实模型未找到）")
        
        print("正在进行语音识别...")
        result = recognizer.recognize(audio_file)
        
        if result:
            print(f"📝 语音识别结果: {result}")
            return result
        else:
            print("语音识别结果为空")
            return None
            
    except Exception as e:
        print(f"语音识别错误: {e}")
        return None

def simulate_ai_response(input_path, output_path):
    """AI处理：语音识别 + 生成响应"""
    print("开始AI处理...")
    try:
        # 首先进行语音识别
        recognition_result = perform_speech_recognition(input_path)
        
        if recognition_result:
            print(f"✓ 语音识别成功: {recognition_result}")
        else:
            print("✗ 语音识别失败，继续生成响应音频")
        
        # 生成响应音频（暂时复制原音频）
        import shutil
        shutil.copy(input_path, output_path)
        print("✓ AI响应音频生成完成")
        return True
    except Exception as e:
        print(f"✗ AI处理失败: {e}")
        return False

def test_connection():
    """测试SSH连接"""
    print("测试SSH连接...")
    try:
        if not init_ssh_connection():
            return False
        
        result = run_ssh_command("echo 'Hello from Windows'", capture_output=True)
        if result.returncode == 0:
            print("✓ SSH连接正常")
            print(f"远程响应: {result.stdout.strip()}")
            return True
        else:
            print("✗ SSH连接测试失败")
            return False
    except Exception as e:
        print(f"✗ SSH连接失败: {e}")
        return False

def main():
    """主程序"""
    print("=" * 50)
    print("Windows专用音频控制系统")
    print(f"连接目标: {REMOTE_USER}@{REMOTE_HOST}")
    print(f"使用密码: {REMOTE_PASSWORD}")
    print("=" * 50)
    
    # 测试连接
    if not test_connection():
        print("请检查网络连接和SSH配置")
        return
    
    print("\n按 'r' 开始录音和处理, 按 'q' 退出")
    
    try:
        import keyboard
    except ImportError:
        print("请安装keyboard库: pip install keyboard")
        return
    
    try:
        while True:
            event = keyboard.read_event()
            if event.event_type == keyboard.KEY_DOWN:
                key = event.name.lower()
                
                if key == 'r':
                    print("\n" + "="*40)
                    print("开始音频处理流程...")
                    
                    # 确保本地record目录存在
                    local_record_dir = ensure_local_directory()
                    if not local_record_dir:
                        print("✗ 无法创建本地目录，流程终止")
                        continue
                    
                    # 生成带时间戳的文件名
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    local_raw = os.path.join(local_record_dir, f"test_raw_{timestamp}.wav")
                    local_processed = os.path.join(local_record_dir, f"test_{timestamp}.wav")
                    local_response = os.path.join(local_record_dir, f"response_{timestamp}.wav")
                    remote_raw = f"~/record/test_raw_{timestamp}.wav"
                    remote_response = f"~/record/response_{timestamp}.wav"
                    
                    # 步骤1: 远程录音
                    if not record_remote(remote_raw):
                        continue
                    
                    # 步骤2: 处理音频
                    if not process_audio_local(remote_raw, local_raw, local_processed):
                        continue
                    
                    # 步骤3: AI处理（语音识别 + 响应生成）
                    if not simulate_ai_response(local_processed, local_response):
                        continue
                    
                    # 步骤4: 播放响应
                    if not play_remote_audio(local_response, remote_response):
                        continue
                    
                    print("✓ 完整流程执行成功!")
                    print("="*40)
                    
                elif key == 'q':
                    print("\n退出程序...")
                    # 清理keyboard输入缓冲区
                    while keyboard.is_pressed('q'):
                        time.sleep(0.01)
                    # 清理任何待处理的事件
                    import threading
                    def clear_events():
                        try:
                            while True:
                                event = keyboard.read_event(suppress=True)
                                if event is None:
                                    break
                        except:
                            pass
                    
                    clear_thread = threading.Thread(target=clear_events)
                    clear_thread.daemon = True
                    clear_thread.start()
                    clear_thread.join(timeout=0.1)
                    break
    finally:
        # 清理连接
        close_ssh_connection()

if __name__ == '__main__':
    main() 