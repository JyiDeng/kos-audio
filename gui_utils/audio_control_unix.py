#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简化版音频控制脚本 - 使用最可靠的传输方法
解决sftp-server不存在的问题
"""

import os
import subprocess
import base64
from datetime import datetime
import requests
import tempfile

REMOTE_USER = "root"
REMOTE_HOST = "192.168.42.1"
REMOTE_PASSWORD = "milkv"
REMOTE_ADDR = f"{REMOTE_USER}@{REMOTE_HOST}"

LOCAL_RAW = "test_raw.wav"
LOCAL_PROCESSED = "test.wav"
LOCAL_RESPONSE = "response.wav"

REMOTE_RAW = "~/record/test_raw.wav"
REMOTE_PROCESSED = "~/record/test.wav"
REMOTE_RESPONSE = "~/record/response.wav"

def ssh_run(cmd, capture_output=False):
    """执行SSH命令，自动使用密码"""
    try:
        # 优先使用sshpass
        ssh_cmd = ["sshpass", "-p", REMOTE_PASSWORD, "ssh", "-o", "StrictHostKeyChecking=no", REMOTE_ADDR] + cmd
        return subprocess.run(ssh_cmd, check=True, capture_output=capture_output)
    except FileNotFoundError:
        # 备选方案：pexpect
        try:
            import pexpect
            cmd_str = " ".join([f'"{c}"' if " " in c else c for c in cmd])
            ssh_cmd = f'ssh -o StrictHostKeyChecking=no {REMOTE_ADDR} {cmd_str}'
            
            child = pexpect.spawn(ssh_cmd)
            try:
                child.expect("password:", timeout=10)
                child.sendline(REMOTE_PASSWORD)
            except pexpect.TIMEOUT:
                pass  # 可能已有密钥
            
            if capture_output:
                child.expect(pexpect.EOF)
                output = child.before.decode()
                child.close()
                
                class Result:
                    def __init__(self, stdout, returncode):
                        self.stdout = stdout
                        self.returncode = returncode
                
                return Result(output, child.exitstatus or 0)
            else:
                child.expect(pexpect.EOF)
                child.close()
                
                class Result:
                    def __init__(self, returncode):
                        self.returncode = returncode
                        self.stdout = ""
                
                return Result(child.exitstatus or 0)
                
        except ImportError:
            print("需要安装 sshpass 或 pexpect: pip install pexpect")
            raise

def transfer_from_remote_base64(remote_path, local_path):
    """使用base64编码从远程下载文件（最可靠的方法）"""
    print(f"从远程下载文件: {remote_path} -> {local_path}")
    try:
        # 通过SSH执行base64编码
        result = ssh_run([f"base64 < {remote_path}"], capture_output=True)
        
        # 解码并保存
        with open(local_path, 'wb') as f:
            f.write(base64.b64decode(result.stdout))
        
        print(f"✓ 成功下载到 {local_path}")
        return True
    except Exception as e:
        print(f"✗ 下载失败: {e}")
        return False

def transfer_to_remote_base64(local_path, remote_path):
    """使用base64编码上传文件到远程（最可靠的方法）"""
    print(f"上传文件到远程: {local_path} -> {remote_path}")
    try:
        # 读取文件并编码
        with open(local_path, 'rb') as f:
            encoded = base64.b64encode(f.read()).decode()
        
        # 分块传输（避免命令行长度限制）
        chunk_size = 1000  # 每块1000字符
        
        # 首先清空远程文件
        ssh_run([f"echo -n '' > {remote_path}"])
        
        # 分块传输
        for i in range(0, len(encoded), chunk_size):
            chunk = encoded[i:i+chunk_size]
            if i == 0:
                # 第一块覆盖文件
                ssh_run([f"echo -n '{chunk}' | base64 -d > {remote_path}"])
            else:
                # 后续块追加
                ssh_run([f"echo -n '{chunk}' | base64 -d >> {remote_path}"])
        
        print(f"✓ 成功上传到 {remote_path}")
        return True
    except Exception as e:
        print(f"✗ 上传失败: {e}")
        return False

def ensure_remote_directory():
    """确保远程目录存在"""
    print("检查远程目录...")
    try:
        # 获取录音文件的目录
        import os
        remote_dir = os.path.dirname(REMOTE_RAW)
        
        # 创建目录（如果不存在）
        result = ssh_run([f"mkdir", "-p", remote_dir])
        print(f"✓ 远程目录准备就绪: {remote_dir}")
        return True
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

def record_remote(duration=5):
    """在远程设备上录音duration秒"""
    print(f"开始远程录音 ({duration}秒)...")
    
    # 先确保目录存在
    if not ensure_remote_directory():
        return False
    
    try:
        ssh_run([
            "arecord", "-D", "hw:0,0", "-f", "S16_LE", 
            "-r", "16000", "-c", "1", "-d", str(duration), REMOTE_RAW
        ])
        print("✓ 录音完成")
        return True
    except Exception as e:
        print(f"✗ 录音失败: {e}")
        return False

def process_audio_local():
    """处理音频：下载、降噪、标准化"""
    print("处理音频...")
    
    # 确保本地record目录存在
    local_record_dir = ensure_local_directory()
    if not local_record_dir:
        print("✗ 无法创建本地目录")
        return False
    
    # 生成带时间戳的本地文件名
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    local_raw = os.path.join(local_record_dir, f"test_raw_{timestamp}.wav")
    local_processed = os.path.join(local_record_dir, f"test_{timestamp}.wav")
    
    # 下载原始录音
    if not transfer_from_remote_base64(REMOTE_RAW, local_raw):
        return False
    
    # 使用FFmpeg处理音频
    try:
        ffmpeg_cmd = [
            "ffmpeg", "-y", "-i", local_raw,
            "-af", "afftdn=nr=12:nt=w, dynaudnorm=f=500:g=15, volume=10000.0",
            local_processed
        ]
        result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"FFmpeg错误: {result.stderr}")
            return False
        
        print("✓ 音频处理完成")
        return local_processed  # 返回处理后的文件路径
    except Exception as e:
        print(f"✗ 音频处理失败: {e}")
        return False

def play_remote_audio(local_wav_path):
    """播放音频：上传并在远程播放"""
    print("播放音频...")
    
    # 上传音频文件
    if not transfer_to_remote_base64(local_wav_path, REMOTE_RESPONSE):
        return False
    
    # 远程播放
    try:
        ssh_run([
            "aplay", "-D", "hw:1,0", "-f", "S16_LE", 
            "-r", "16000", "-c", "1", REMOTE_RESPONSE
        ])
        print("✓ 音频播放完成")
        return True
    except Exception as e:
        print(f"✗ 音频播放失败: {e}")
        return False

def simulate_ai_response(input_file):
    """模拟AI响应（替换为真实的AI调用）"""
    print("模拟AI处理...")
    # 这里应该调用真实的语音识别和AI模型
    # 现在只是复制处理后的音频作为响应
    try:
        import shutil
        # 确保本地record目录存在
        local_record_dir = ensure_local_directory()
        if not local_record_dir:
            return False
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        local_response = os.path.join(local_record_dir, f"response_{timestamp}.wav")
        
        shutil.copy(input_file, local_response)
        print("✓ AI响应生成完成（模拟）")
        return local_response
    except Exception as e:
        print(f"✗ AI响应生成失败: {e}")
        return False

def test_connection():
    """测试SSH连接"""
    print("测试SSH连接...")
    try:
        result = ssh_run(["echo", "Hello from remote"], capture_output=True)
        print("✓ SSH连接正常")
        return True
    except Exception as e:
        print(f"✗ SSH连接失败: {e}")
        return False

def tts_and_play(text):
    """将文本转为语音并通过play_remote_audio播放"""
    url = "https://api.siliconflow.cn/v1/audio/speech"
    payload = {
        "model": "FunAudioLLM/CosyVoice2-0.5B",
        "input": text,
        "voice": "FunAudioLLM/CosyVoice2-0.5B:claire",
        "response_format": "mp3",
        "sample_rate": 32000,
        "stream": False,
        "speed": 1,
        "gain": 0
    }
    from config import AI_API_TOKEN
    headers = {
        "Authorization": AI_API_TOKEN,
        "Content-Type": "application/json"
    }
    try:
        response = requests.post(url, json=payload, headers=headers)
        if response.status_code == 200:
            # 保存音频到临时文件
            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as f:
                f.write(response.content)
                temp_audio_path = f.name
            # 播放音频（通过远程）
            play_remote_audio(temp_audio_path)
            # 删除临时文件
            os.remove(temp_audio_path)
            return True
        else:
            print("TTS API调用失败:", response.text)
            return False
    except Exception as e:
        print("TTS播放出错:", e)
        return False

def main():
    """主程序"""
    print("=" * 50)
    print("简化版音频控制系统")
    print("=" * 50)
    
    # 测试连接
    if not test_connection():
        print("请检查SSH连接配置")
        return
    
    print("\n按 'r' 开始录音和处理, 按 'q' 退出")
    
    try:
        import keyboard
    except ImportError:
        print("请安装keyboard库: pip install keyboard")
        return
    
    while True:
        event = keyboard.read_event()
        if event.event_type == keyboard.KEY_DOWN:
            key = event.name.lower()
            
            if key == 'r':
                print("\n" + "="*30)
                print("开始音频处理流程...")
                
                # 步骤1: 远程录音
                if not record_remote():
                    continue
                
                # 步骤2: 处理音频
                processed_file = process_audio_local()
                if not processed_file:
                    continue
                
                # 步骤3: AI处理（模拟）
                response_file = simulate_ai_response(processed_file)
                if not response_file:
                    continue
                
                # 步骤4: 播放响应
                if not play_remote_audio(response_file):
                    continue
                
                print("✓ 完整流程执行成功!")
                print("="*30)
                
            elif key == 'q':
                print("\n退出程序...")
                break

if __name__ == '__main__':
    main() 