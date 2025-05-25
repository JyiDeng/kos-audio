#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
音频控制系统统一入口
自动检测操作系统并启动对应的程序
"""

import os
import sys
import platform
import subprocess
import threading
import time
import requests
import json
import tempfile
"""
代码思路：
通过本python脚本：
1. 读取键盘，监测到按下r键开始录音5秒，之后接入api调用大模型
通过system prompt让大模型返回0，1等去决定不同的控制方式，包括键盘或者视觉，
之后调用库将返回的文字转为音频播放。
在录放音部分要通过命令行的方式控制，这个脚本的本质是把命令行通过python的os等库封装起来而已
录制命令是arecord -D hw:0,0 -f S16\_LE -r 16000 -c 1 -d 5 test.wav
播放命令是aplay -D hw:1,0 -f S16\_LE -r 16000 -c 1 test.wav
参考https://github.com/CarrotFish/KOS_Deploy_Guidance/blob/main/documents/audio_speaker.md
之后你在录音时对音频进行处理，- ffmpeg -i input.wav -ac 1 -ar 16000 output.wav
由于录音设备录制效果噪音很大、人声很轻，可以通过ffmpeg粗糙地调整：ffmpeg -i E input.wav -af "afftdn=nr=12\:nt=w, dynaudnorm=f=500\:g=15, volume=1000.0" output.wav 
对应了降噪、标准化、放大声音。

"""

# 导入配置
try:
    from gui_utils.config import (
        REMOTE_USER, REMOTE_HOST, REMOTE_PASSWORD,
        AI_API_URL, AI_API_TOKEN, AI_MODEL, SYSTEM_PROMPT as CONFIG_SYSTEM_PROMPT,
        API_PARAMS
    )
    REMOTE_ADDR = f"{REMOTE_USER}@{REMOTE_HOST}"
    # 使用配置文件中的系统提示词
    SYSTEM_PROMPT = CONFIG_SYSTEM_PROMPT
except ImportError:
    print("⚠ 配置文件未找到，使用默认配置")
    # 默认配置
    REMOTE_USER = "root"
    REMOTE_HOST = "192.168.42.1"
    REMOTE_PASSWORD = "milkv"
    REMOTE_ADDR = f"{REMOTE_USER}@{REMOTE_HOST}"
    
    # 默认AI API配置
    AI_API_URL = "https://api.siliconflow.cn/v1/chat/completions"
    AI_API_TOKEN = "sk-ixsnrnsobilzvanochaapmgksydomnygsijrajxkjoqctcmv"  # 需要替换
    AI_MODEL = "Qwen/QwQ-32B"
    SYSTEM_PROMPT = "你是一个语音转录专家，请将用户说的话转录成文字，并且给出适当的回应。"
    API_PARAMS = {
        "stream": False,
        "max_tokens": 100,
        "temperature": 0.7
    }

LOCAL_RAW = "test_raw.wav"
LOCAL_PROCESSED = "test.wav"
LOCAL_RESPONSE = "response.wav"

REMOTE_RAW = "/tmp/test_raw.wav"
REMOTE_PROCESSED = "/tmp/test.wav"
REMOTE_RESPONSE = "/tmp/response.wav"

# SSH helper with password
def ssh_run(cmd, capture_output=False):
    try:
        # 首先尝试使用sshpass
        ssh_cmd = ["sshpass", "-p", REMOTE_PASSWORD, "ssh", "-o", "StrictHostKeyChecking=no", REMOTE_ADDR] + cmd
        return subprocess.run(ssh_cmd, check=True, capture_output=capture_output)
    except FileNotFoundError:
        print("警告: sshpass未安装，将尝试使用pexpect...")
        return ssh_run_pexpect(cmd, capture_output)
    except Exception as e:
        print(f"sshpass失败，尝试pexpect: {e}")
        return ssh_run_pexpect(cmd, capture_output)

def ssh_run_pexpect(cmd, capture_output=False):
    """使用pexpect处理SSH密码输入的备选方案"""
    try:
        import pexpect
        ssh_cmd = " ".join(["ssh", "-o", "StrictHostKeyChecking=no", REMOTE_ADDR] + [f'"{c}"' for c in cmd])
        
        if capture_output:
            child = pexpect.spawn(ssh_cmd)
            child.expect("password:")
            child.sendline(REMOTE_PASSWORD)
            child.expect(pexpect.EOF)
            output = child.before.decode()
            child.close()
            
            # 模拟subprocess.run的返回对象
            class Result:
                def __init__(self, stdout, returncode):
                    self.stdout = stdout
                    self.returncode = returncode
            
            return Result(output, child.exitstatus or 0)
        else:
            child = pexpect.spawn(ssh_cmd)
            child.expect("password:")
            child.sendline(REMOTE_PASSWORD)
            child.expect(pexpect.EOF)
            child.close()
            
            class Result:
                def __init__(self, returncode):
                    self.returncode = returncode
            
            return Result(child.exitstatus or 0)
            
    except ImportError:
        print("错误: 需要安装sshpass或pexpect库")
        print("安装方法:")
        print("  Windows: 需要先安装sshpass (通过WSL或其他方式)")
        print("  或者: pip install pexpect")
        raise Exception("无法自动输入密码，请安装sshpass或pexpect")
    except Exception as e:
        print(f"pexpect也失败了: {e}")
        raise

# 替代SCP的文件传输方法
def transfer_from_remote_method1(remote_path, local_path):
    """方法1: 使用ssh + base64编码传输（适合小文件）"""
    print(f"Using SSH+base64 to fetch {remote_path}...")
    try:
        # 通过ssh执行base64编码并获取输出
        try:
            result = subprocess.run([
                "sshpass", "-p", REMOTE_PASSWORD, "ssh", "-o", "StrictHostKeyChecking=no", 
                REMOTE_ADDR, f"base64 < {remote_path}"
            ], capture_output=True, text=True, check=True)
        except FileNotFoundError:
            # 备选方案：使用pexpect
            import pexpect
            child = pexpect.spawn(f'ssh -o StrictHostKeyChecking=no {REMOTE_ADDR} "base64 < {remote_path}"')
            child.expect("password:")
            child.sendline(REMOTE_PASSWORD)
            child.expect(pexpect.EOF)
            result_stdout = child.before.decode()
            child.close()
            
            class Result:
                def __init__(self, stdout):
                    self.stdout = stdout
            result = Result(result_stdout)
        
        # 在本地解码并写入文件
        import base64
        with open(local_path, 'wb') as f:
            f.write(base64.b64decode(result.stdout))
        print(f"Successfully transferred {remote_path} to {local_path}")
        return True
    except Exception as e:
        print(f"Method 1 failed: {e}")
        return False

def transfer_from_remote_method2(remote_path, local_path):
    """方法2: 使用ssh + cat传输（适用于Windows）"""
    print(f"Using SSH+cat to fetch {remote_path}...")
    try:
        # 直接使用cat通过ssh传输
        with open(local_path, 'wb') as f:
            try:
                subprocess.run([
                    "sshpass", "-p", REMOTE_PASSWORD, "ssh", "-o", "StrictHostKeyChecking=no",
                    REMOTE_ADDR, f"cat {remote_path}"
                ], stdout=f, check=True)
            except FileNotFoundError:
                # pexpect备选方案
                import pexpect
                child = pexpect.spawn(f'ssh -o StrictHostKeyChecking=no {REMOTE_ADDR} "cat {remote_path}"')
                child.expect("password:")
                child.sendline(REMOTE_PASSWORD)
                f.write(child.read())
                child.close()
        print(f"Successfully transferred {remote_path} to {local_path}")
        return True
    except Exception as e:
        print(f"Method 2 failed: {e}")
        return False

def transfer_from_remote_method3(remote_path, local_path):
    """方法3: 使用ssh + dd传输"""
    print(f"Using SSH+dd to fetch {remote_path}...")
    try:
        with open(local_path, 'wb') as f:
            subprocess.run([
                "ssh", REMOTE_ADDR, f"dd if={remote_path} bs=1024"
            ], stdout=f, check=True)
        print(f"Successfully transferred {remote_path} to {local_path}")
        return True
    except Exception as e:
        print(f"Method 3 failed: {e}")
        return False

def scp_from_remote(remote_path, local_path):
    """尝试多种方法从远程获取文件"""
    methods = [
        transfer_from_remote_method1,
        transfer_from_remote_method3,
        transfer_from_remote_method2
    ]
    
    for i, method in enumerate(methods, 1):
        print(f"Trying transfer method {i}...")
        if method(remote_path, local_path):
            return
    
    raise Exception("All transfer methods failed")


def transfer_to_remote_method1(local_path, remote_path):
    """方法1: 使用ssh + base64编码传输到远程"""
    print(f"Using SSH+base64 to send {local_path}...")
    try:
        # 读取本地文件并base64编码
        import base64
        with open(local_path, 'rb') as f:
            encoded = base64.b64encode(f.read()).decode()
        
        # 通过ssh传输并解码
        subprocess.run([
            "ssh", REMOTE_ADDR, 
            f"echo '{encoded}' | base64 -d > {remote_path}"
        ], check=True)
        print(f"Successfully transferred {local_path} to {remote_path}")
        return True
    except Exception as e:
        print(f"Method 1 failed: {e}")
        return False

def transfer_to_remote_method2(local_path, remote_path):
    """方法2: 使用ssh + tee传输到远程（适用于Windows）"""
    print(f"Using SSH+tee to send {local_path}...")
    try:
        # 使用tee通过ssh传输
        with open(local_path, 'rb') as f:
            subprocess.run([
                "ssh", REMOTE_ADDR, f"tee {remote_path} > /dev/null"
            ], stdin=f, check=True)
        print(f"Successfully transferred {local_path} to {remote_path}")
        return True
    except Exception as e:
        print(f"Method 2 failed: {e}")
        return False

def transfer_to_remote_method3(local_path, remote_path):
    """方法3: 使用ssh + dd传输到远程"""
    print(f"Using SSH+dd to send {local_path}...")
    try:
        with open(local_path, 'rb') as f:
            subprocess.run([
                "ssh", REMOTE_ADDR, f"dd of={remote_path} bs=1024"
            ], stdin=f, check=True)
        print(f"Successfully transferred {local_path} to {remote_path}")
        return True
    except Exception as e:
        print(f"Method 3 failed: {e}")
        return False

def scp_to_remote(local_path, remote_path):
    """尝试多种方法发送文件到远程"""
    methods = [
        transfer_to_remote_method1,
        transfer_to_remote_method3,
        transfer_to_remote_method2
    ]
    
    for i, method in enumerate(methods, 1):
        print(f"Trying transfer method {i}...")
        if method(local_path, remote_path):
            return
    
    raise Exception("All transfer methods failed")


def record_remote():
    """Trigger remote recording for 5s"""
    print("Starting remote recording...")
    ssh_run([
        "arecord", "-D", "hw:0,0", "-f", "S16_LE", "-r", "16000", "-c", "1", "-d", "5", REMOTE_RAW
    ])


def process_local():
    """Fetch raw remote, process locally with ffmpeg"""
    print("Fetching raw file from robot...")
    scp_from_remote(REMOTE_RAW, LOCAL_RAW)

    print("Processing audio (denoise, normalize, amplify)...")
    ffmpeg_cmd = [
        "ffmpeg", "-y", "-i", LOCAL_RAW,
        "-af", "afftdn=nr=12:nt=w, dynaudnorm=f=500:g=15, volume=1000.0",
        LOCAL_PROCESSED
    ]
    subprocess.run(ffmpeg_cmd, check=True)


def call_model_and_get_code(wav_path):
    """调用AI模型分析音频并返回控制代码"""
    try:
        # 首先进行语音识别获取文本
        try:
            from gui_utils.speech_recognition import create_recognizer
            recognizer = create_recognizer('paraformer')
            text = recognizer.recognize(wav_path)
            if not text:
                text = "无法识别语音内容"
            print(f"[语音识别] 识别结果: {text}")
        except Exception as e:
            print(f"语音识别失败: {e}")
            text = "语音识别失败"
        
        # 准备API请求
        payload = {
            "model": AI_MODEL,
            "messages": [
                {
                    "role": "system",
                    "content": SYSTEM_PROMPT
                },
                {
                    "role": "user", 
                    "content": f"用户说: {text}"
                }
            ],
            **API_PARAMS  # 使用配置文件中的参数
        }
        
        headers = {
            "Authorization": f"Bearer {AI_API_TOKEN}",
            "Content-Type": "application/json"
        }
        
        print(f"[AI模型] 正在调用API...")
        response = requests.post(AI_API_URL, json=payload, headers=headers, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            ai_response = result['choices'][0]['message']['content'].strip()
            print(f"[AI模型] 响应: {ai_response}")
            
            # 尝试从响应中提取数字代码
            import re
            numbers = re.findall(r'\d+', ai_response)
            if numbers:
                code = int(numbers[0])
            else:
                code = 0  # 默认值
            
            print(f"[AI模型] 返回控制代码: {code}")
            return code,ai_response
        else:
            print(f"[AI模型] API调用失败: {response.status_code}")
            print(f"错误信息: {response.text}")
            return 0,None
            
    except Exception as e:
        print(f"[AI模型] 调用出错: {e}")
        return 0,None


system_type = platform.system().lower()
if system_type == "windows" or os.name == 'nt':
    try:
        from gui_utils.audio_control_windows import play_remote_audio, ensure_local_directory
        _tts_backend = 'windows'
    except ImportError:
        play_remote_audio = None
        ensure_local_directory = None
        _tts_backend = None
else:
    try:
        from gui_utils.audio_control_unix import play_remote_audio, ensure_local_directory
        _tts_backend = 'unix'
    except ImportError:
        play_remote_audio = None
        ensure_local_directory = None
        _tts_backend = None

def tts_and_play(text):
    """将文本转为语音并通过play_remote_audio播放，自动适配平台"""
    if play_remote_audio is None or ensure_local_directory is None:
        print("TTS播放功能不可用：未能正确导入平台相关模块。")
        return False
    url = "https://api.siliconflow.cn/v1/audio/speech"
    payload = {
        "model": "FunAudioLLM/CosyVoice2-0.5B",
        "input": text,
        "voice": "FunAudioLLM/CosyVoice2-0.5B:diana",
        "response_format": "wav",
        "sample_rate": 32000,
        "stream": False,
        "speed": 1,
        "gain": 0
    }
    import traceback
    import datetime
    headers = {
        "Authorization": f"Bearer {AI_API_TOKEN}",
        "Content-Type": "application/json"
    }
    try:
        response = requests.post(url, json=payload, headers=headers)
        if response.status_code == 200:
            # 保存音频到本地record目录
            local_record_dir = ensure_local_directory()
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            temp_audio_path = os.path.join(local_record_dir, f"tts_{timestamp}.wav")
            with open(temp_audio_path, 'wb') as f:
                f.write(response.content)
            print(f"TTS音频已保存: {temp_audio_path}")
            # 生成远程路径
            remote_audio_path = f"~/record/tts_{timestamp}.wav"
            # 播放音频（通过远程）
            play_remote_audio(temp_audio_path, remote_audio_path)
            # 删除临时文件
            # os.remove(temp_audio_path)
            return True
        else:
            print("TTS API调用失败:", response.text)
            return False
    except Exception as e:
        print("TTS播放出错:", e)
        traceback.print_exc()
        return False

def play_remote(wav_path):
    """Send audio to remote and play"""
    print("Transferring response to robot...")
    scp_to_remote(wav_path, REMOTE_RESPONSE)
    print("Playing audio on robot...")
    ssh_run([
        "aplay", "-D", "hw:1,0", "-f", "S16_LE", "-r", "16000", "-c", "1", REMOTE_RESPONSE
    ])


def detect_system():
    """检测操作系统"""
    system = platform.system().lower()
    if system == "windows" or os.name == 'nt':
        return "windows"
    elif system in ["linux", "darwin"]:  # Darwin is macOS
        return "unix"
    else:
        return "unknown"

def check_dependencies():
    """检查必要的依赖"""
    try:
        import keyboard
        print("✓ keyboard库已安装")
    except ImportError:
        print("✗ keyboard库未安装")
        return False
    
    system_type = detect_system()
    if system_type == "windows":
        try:
            import paramiko
            print("✓ paramiko库已安装")
            return True
        except ImportError:
            print("✗ paramiko库未安装")
            return False
    else:
        # 检查paramiko是否可用（优先）
        try:
            import paramiko
            print("✓ paramiko库已安装（推荐）")
            return True
        except ImportError:
            pass
        
        # 检查pexpect作为备选
        try:
            import pexpect
            print("✓ pexpect库已安装")
            return True
        except ImportError:
            print("✗ 需要安装paramiko或pexpect库")
            return False

def install_missing_dependencies():
    """安装缺失的依赖"""
    print("尝试自动安装缺失的依赖...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "keyboard", "paramiko"])
        print("✓ 依赖安装完成")
        return True
    except Exception as e:
        print(f"✗ 自动安装失败: {e}")
        print("请手动运行: python install_dependencies.py")
        return False

def run_windows_version():
    """运行Windows版本"""
    print("启动Windows版音频控制系统...")
    try:
        # 导入并运行Windows版本
        from gui_utils.audio_control_windows import main
        main()
    except ImportError as e:
        print(f"无法导入Windows版本: {e}")
        return False
    except Exception as e:
        print(f"Windows版本运行错误: {e}")
        return False

def run_unix_version():
    """运行Unix版本（Linux/macOS）"""
    print("启动Unix版音频控制系统...")
    
    # 优先尝试paramiko版本
    try:
        print("使用paramiko版本...")
        from gui_utils.audio_control_windows import main  # paramiko版本代码相同
        main()
        return True
    except ImportError:
        pass
    except Exception as e:
        print(f"paramiko版本运行错误: {e}")
    
    # 备选pexpect版本
    try:
        print("使用pexpect版本...")
        from gui_utils.audio_control_unix import main
        main()
        return True
    except ImportError as e:
        print(f"无法导入pexpect版本: {e}")
        return False
    except Exception as e:
        print(f"pexpect版本运行错误: {e}")
        return False

def show_help():
    """显示帮助信息"""
    print("=" * 60)
    print("音频控制系统帮助")
    print("=" * 60)
    print("此程序会自动检测你的操作系统并启动对应版本：")
    print()
    print("Windows: 使用paramiko库连接SSH")
    print("Linux/macOS: 优先使用paramiko，备选pexpect")
    print()
    print("使用方法:")
    print("  python audio_control.py        # 正常启动")
    print("  python audio_control.py --help # 显示帮助")
    print("  python audio_control.py --test # 测试连接")
    print()
    print("故障排除:")
    print("  python install_dependencies.py  # 安装依赖")
    print("  python test_ssh_windows.py      # 测试SSH (Windows)")
    print("  python test_ssh_connection.py   # 测试SSH (Linux/macOS)")
    print("  python debug_recording.py       # 诊断录音问题")
    print("=" * 60)

def test_connection():
    """测试连接"""
    system_type = detect_system()
    if system_type == "windows":
        print("运行Windows SSH测试...")
        try:
            from gui_utils.test_ssh_windows import main
            main()
        except Exception as e:
            print(f"测试失败: {e}")
    else:
        print("运行Unix SSH测试...")
        try:
            from gui_utils.test_ssh_unix import main
            main()
        except Exception as e:
            print(f"测试失败: {e}")

def main():
    """主程序入口"""
    print("=" * 60)
    print("音频控制系统 - 统一入口")
    print("=" * 60)
    
    # 检查命令行参数
    if len(sys.argv) > 1:
        if sys.argv[1] == "--help" or sys.argv[1] == "-h":
            show_help()
            return
        elif sys.argv[1] == "--test" or sys.argv[1] == "-t":
            test_connection()
            return
    
    # 检测系统
    system_type = detect_system()
    print(f"检测到操作系统: {system_type}")
    
    if system_type == "unknown":
        print("✗ 不支持的操作系统")
        return
    
    # 检查依赖
    if not check_dependencies():
        print("\n缺少必要的依赖库")
        response = input("是否尝试自动安装？(y/n): ")
        if response.lower() in ['y', 'yes']:
            if not install_missing_dependencies():
                return
        else:
            print("请手动安装依赖后重试")
            return
    
    print("\n依赖检查通过，启动程序...")
    print("=" * 60)
    
    # 根据系统类型启动对应版本
    if system_type == "windows":
        run_windows_version()
    else:
        run_unix_version()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n程序被用户中断")
    except Exception as e:
        print(f"\n\n程序运行出错: {e}")
        print("请查看错误信息或运行 python audio_control.py --help 获取帮助")
