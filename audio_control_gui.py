#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
音频控制系统 - 可视化界面版本
带有GUI界面的音频录制、处理和播放系统
"""

import os
import sys
import threading
import time
from datetime import datetime
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import platform
# 导入AI响应函数
from gui_utils.audio_control import call_model_and_get_code, tts_and_play
from gui_utils.config import AI_API_TOKEN
from gui_utils.speech_recognition import create_recognizer
import requests
import tempfile
# from playsound import playsound

# 检测系统并导入对应的音频控制模块
def detect_system():
    system = platform.system().lower()
    if system == "windows" or os.name == 'nt':
        return "windows"
    else:
        return "unix"

# 根据系统导入对应模块
system_type = detect_system()
if system_type == "windows":
    try:
        from gui_utils.audio_control_windows import (
            init_ssh_connection, close_ssh_connection, 
            ensure_local_directory, record_remote, 
            process_audio_local, play_remote_audio,
            run_ssh_command
        )
        print("使用Windows版本音频控制模块")
    except ImportError as e:
        print(f"无法导入Windows模块: {e}")
        sys.exit(1)
else:
    try:
        from gui_utils.audio_control_unix import (
            ensure_local_directory, record_remote,
            process_audio_local, play_remote_audio,
            test_connection
        )
        print("使用Unix版本音频控制模块")
    except ImportError as e:
        print(f"无法导入Unix模块: {e}")
        sys.exit(1)
timestamp_record = ""
class AudioControlGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("音频控制系统")
        self.root.geometry("800x600")
        self.root.resizable(True, True)
        
        # 状态变量
        self.is_recording = False
        self.is_processing = False
        self.ssh_connected = False
        
        # 先创建界面
        self.create_widgets()
        
        # 再初始化语音识别模型
        self.log("初始化语音识别模型...")
        self.recognizer = create_recognizer('paraformer')
        if self.recognizer.is_available():
            self.log("✓ 语音识别模型加载成功")
        else:
            self.log("⚠ 使用模拟语音识别（真实模型未找到）")
        
        # 初始化连接
        self.init_connection()
    
    def create_widgets(self):
        """创建界面组件"""
        # 主框架
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 配置行列权重
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(3, weight=1)
        
        # 标题
        title_label = ttk.Label(main_frame, text="音频控制系统", 
                               font=("Arial", 16, "bold"))
        title_label.grid(row=0, column=0, columnspan=3, pady=(0, 20))
        
        # 连接状态
        status_frame = ttk.LabelFrame(main_frame, text="连接状态", padding="5")
        status_frame.grid(row=1, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 10))
        
        self.status_label = ttk.Label(status_frame, text="正在连接...", 
                                     foreground="orange")
        self.status_label.grid(row=0, column=0, sticky=tk.W)
        
        # 控制按钮
        control_frame = ttk.LabelFrame(main_frame, text="录音控制", padding="10")
        control_frame.grid(row=2, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 10))
        
        # 录音时长输入框
        ttk.Label(control_frame, text="录音时长(秒):").grid(row=0, column=0, padx=(0, 5))
        self.duration_var = tk.StringVar(value="5")
        self.duration_entry = ttk.Entry(control_frame, textvariable=self.duration_var, width=5)
        self.duration_entry.grid(row=0, column=1, padx=(0, 10))

        self.record_button = ttk.Button(control_frame, text="开始录音", 
                                       command=self.toggle_recording,
                                       style="Record.TButton")
        self.record_button.grid(row=0, column=2, padx=(0, 10))
        
        self.process_button = ttk.Button(control_frame, text="处理音频", 
                                        command=self.process_audio,
                                        state="disabled")
        self.process_button.grid_forget()  # 隐藏处理按钮
        
        self.play_button = ttk.Button(control_frame, text="播放录音", 
                                     command=self.play_response,
                                     state="disabled")
        self.play_button.grid(row=0, column=4)
        
        # 语音识别结果
        recognition_frame = ttk.LabelFrame(main_frame, text="语音识别-AI回应结果", padding="5")
        recognition_frame.grid(row=3, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        recognition_frame.columnconfigure(0, weight=1)
        recognition_frame.rowconfigure(0, weight=1)
        
        self.recognition_text = scrolledtext.ScrolledText(
            recognition_frame, 
            height=8, 
            wrap=tk.WORD,
            font=("Consolas", 10)
        )
        self.recognition_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 日志输出
        log_frame = ttk.LabelFrame(main_frame, text="系统日志", padding="5")
        log_frame.grid(row=4, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S))
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        
        self.log_text = scrolledtext.ScrolledText(
            log_frame, 
            height=8, 
            wrap=tk.WORD,
            font=("Consolas", 9)
        )
        self.log_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 进度条
        self.progress = ttk.Progressbar(main_frame, mode='indeterminate')
        self.progress.grid(row=5, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(10, 0))
        
        # 配置样式
        style = ttk.Style()
        style.configure("Record.TButton", foreground="red")
    
    def log(self, message):
        """添加日志信息"""
        timestamp_log = datetime.now().strftime("%H:%M:%S")
        log_message = f"[{timestamp_log}] {message}\n"
        
        # 在GUI中显示
        self.log_text.insert(tk.END, log_message)
        self.log_text.see(tk.END)
        
        # 在控制台显示
        print(f"[{timestamp_log}] {message}")
        
        # 更新界面
        self.root.update_idletasks()
    
    def show_recognition_result(self, text, ai_response=None):
        """显示语音识别结果和AI回应"""
        timestamp_recog = datetime.now().strftime("%H:%M:%S")
        result_message = f"[{timestamp_recog}] 识别结果: {text}\n"
        if ai_response is not None:
            result_message += f"[{timestamp_recog}] AI回应: {ai_response}\n"
        # 在GUI中显示
        self.recognition_text.insert(tk.END, result_message)
        self.recognition_text.see(tk.END)
        # 在控制台显示
        # print(f"语音识别结果: {text}")
        if ai_response is not None:
            # print(f"AI回应: {ai_response}")
            pass
        # 更新界面
        self.root.update_idletasks()
    
    def init_connection(self):
        """初始化连接"""
        def connect():
            try:
                if system_type == "windows":
                    success = init_ssh_connection()
                else:
                    success = test_connection()
                
                if success:
                    self.ssh_connected = True
                    self.status_label.config(text="✓ 连接正常", foreground="green")
                    self.log("SSH连接建立成功")
                else:
                    self.status_label.config(text="✗ 连接失败", foreground="red")
                    self.log("SSH连接失败")
            except Exception as e:
                self.status_label.config(text="✗ 连接错误", foreground="red")
                self.log(f"连接错误: {e}")
        
        # 在后台线程中测试连接
        threading.Thread(target=connect, daemon=True).start()
    
    def toggle_recording(self):
        """切换录音状态"""
        if not self.ssh_connected:
            messagebox.showerror("错误", "SSH连接未建立，无法录音")
            return
        
        if not self.is_recording:
            self.start_recording()
        else:
            self.stop_recording()
    
    def start_recording(self):
        """开始录音"""
        def record():
            try:
                self.is_recording = True
                # 获取录音时长
                try:
                    duration = int(self.duration_var.get())
                    if duration <= 0:
                        raise ValueError
                except Exception:
                    self.log("录音时长无效，已重置为5秒")
                    duration = 5
                    self.duration_var.set("5")
                self.record_button.config(text=f"录音中 ({duration}秒)", state="disabled")
                self.progress.start()
                
                # 确保本地目录存在
                local_record_dir = ensure_local_directory()
                if not local_record_dir:
                    self.log("无法创建本地目录")
                    return
                
                # 生成带时间戳的文件名
                timestamp_record = datetime.now().strftime("%Y%m%d_%H%M%S")
                self.current_remote_raw = f"~/record/test_raw_{timestamp_record}.wav"
                self.current_local_raw = os.path.join(local_record_dir, f"test_raw_{timestamp_record}.wav")
                self.current_local_processed = os.path.join(local_record_dir, f"test_{timestamp_record}.wav")
                
                self.log(f"开始远程录音 ({duration}秒)...")
                
                # 远程录音
                if system_type == "windows":
                    success = record_remote(self.current_remote_raw, duration)
                else:
                    success = record_remote(duration)
                
                if success:
                    self.log("录音完成，自动处理音频...")
                    self.process_audio()  # 自动处理音频
                else:
                    self.log("录音失败")
                    
            except Exception as e:
                self.log(f"录音错误: {e}")
            finally:
                self.is_recording = False
                self.record_button.config(text="开始录音", state="normal")
                self.progress.stop()
        
        # 在后台线程中录音
        threading.Thread(target=record, daemon=True).start()
    
    def stop_recording(self):
        """停止录音（当前实现中录音是固定5秒）"""
        # 当前实现中录音时间是事先给定的
        pass
    
    def process_audio(self):
        """处理音频"""
        def process():
            try:
                self.is_processing = True
                self.process_button.config(state="disabled")
                self.progress.start()
                self.log("开始处理音频...")
                # 处理音频
                success = process_audio_local(
                    self.current_remote_raw,
                    self.current_local_raw,
                    self.current_local_processed
                )
                if success:
                    self.log("音频处理完成")
                    # 进行语音识别
                    self.log("开始语音识别...")
                    recognition_result = self.perform_speech_recognition(self.current_local_processed)
                    if recognition_result:
                        self.play_button.config(state="normal")
                        # 自动调用AI响应
                        self.log("正在请求AI响应...")
                        ai_code,ai_response = call_model_and_get_code(self.current_local_processed)
                        self.log(f"AI响应控制代码: {ai_code}")
                        self.show_recognition_result(recognition_result, ai_response=ai_response)
                        if ai_response:
                            self.log("正在将AI回应转换为语音并播放...")
                            tts_and_play(ai_response)
                    else:
                        self.log("语音识别失败")
                else:
                    self.log("音频处理失败")
            except Exception as e:
                self.log(f"处理错误: {e}")
            finally:
                self.is_processing = False
                self.progress.stop()
        threading.Thread(target=process, daemon=True).start()
    
    def perform_speech_recognition(self, audio_file):
        """执行语音识别"""
        try:
            self.log("正在进行语音识别...")
            result = self.recognizer.recognize(audio_file)
            if result:
                self.log(f"语音识别完成: {result}")
                return result
            else:
                self.log("语音识别结果为空")
                return None
        except Exception as e:
            self.log(f"语音识别错误: {e}")
            return None
    
    def play_response(self):
        """播放响应"""
        def play():
            try:
                self.play_button.config(state="disabled")
                self.progress.start()
                
                self.log("播放响应音频...")
                
                # 生成响应文件路径
                remote_response = f"~/record/response_{timestamp_record}.wav"
                
                # 播放处理后的音频作为响应
                success = play_remote_audio(self.current_local_processed, remote_response)
                
                if success:
                    self.log("音频播放完成")
                else:
                    self.log("音频播放失败")
                    
            except Exception as e:
                self.log(f"播放错误: {e}")
            finally:
                self.play_button.config(state="normal")
                self.progress.stop()
        
        # 在后台线程中播放
        threading.Thread(target=play, daemon=True).start()
    
    def on_closing(self):
        """关闭程序时的清理"""
        if system_type == "windows":
            close_ssh_connection()
        self.root.destroy()

def main():
    """主程序"""
    # 检查依赖
    try:
        import tkinter
    except ImportError:
        print("错误: 需要安装tkinter")
        print("Ubuntu/Debian: sudo apt-get install python3-tk")
        return
    
    # 创建GUI
    root = tk.Tk()
    app = AudioControlGUI(root)
    
    # 设置关闭事件
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    
    # 启动GUI
    root.mainloop()

if __name__ == "__main__":
    main() 