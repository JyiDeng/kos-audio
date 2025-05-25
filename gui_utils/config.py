#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
音频控制系统配置文件
请根据需要修改以下配置
"""

# =============================================================================
# AI API配置
# =============================================================================

# API端点URL
AI_API_URL = "https://api.siliconflow.cn/v1/chat/completions"

# API Token (Bearer Token) - 请替换为您的实际token
AI_API_TOKEN = "sk-ixsnrnsobilzvanochaapmgksydomnygsijrajxkjoqctcmv"

# 使用的模型名称
AI_MODEL = "Qwen/QwQ-32B"

# 系统提示词
SYSTEM_PROMPT = (
    "你是一个语音转录专家，请将用户说的话转录成文字，并且给出适当的回应。"
)

# API请求参数
API_PARAMS = {
    "stream": False,
    "max_tokens": 100,
    "temperature": 0.7,
    "thinking_budget": 512,
    "min_p": 0.05,
    "top_p": 0.7,
    "top_k": 50,
    "frequency_penalty": 0.5,
    "n": 1,
    "response_format": {"type": "text"}
}

# =============================================================================
# 远程设备配置
# =============================================================================

# 远程设备连接信息
REMOTE_USER = "root"
REMOTE_HOST = "192.168.42.1" 
REMOTE_PASSWORD = "milkv"
REMOTE_PORT = 22

# =============================================================================
# 语音识别配置
# =============================================================================

# 默认语音识别模型路径
DEFAULT_ASR_PATH = 'model/ASR/sherpa-onnx-paraformer-zh-small-2024-03-09'
DEFAULT_VAD_PATH = 'model/VAD'

# 语音识别参数
ASR_PARAMS = {
    "sample_rate": 16000,
    "num_threads": 8,
    "provider": "cpu"  # 可选: "cpu", "cuda"
}

# =============================================================================
# 音频处理配置
# =============================================================================

# FFmpeg音频处理参数
AUDIO_PROCESS_PARAMS = {
    "denoise": "afftdn=nr=12:nt=w",
    "normalize": "dynaudnorm=f=500:g=15", 
    "amplify": "volume=1000.0"
}

# 音频格式设置
AUDIO_FORMAT = {
    "format": "S16_LE",
    "rate": 16000,
    "channels": 1,
    "duration": 5  # 录音时长（秒）
}

# =============================================================================
# 文件路径配置
# =============================================================================

# 本地文件路径
LOCAL_RECORD_DIR = "record"

# 远程文件路径
REMOTE_RECORD_DIR = "~/record"

# =============================================================================
# 网络配置
# =============================================================================

# 文件传输配置
TRANSFER_CONFIG = {
    "chunk_size": 6000,      # base64传输块大小
    "timeout": 30,           # 传输超时时间
    "retry_count": 3,        # 重试次数
    "progress_interval": 10  # 进度显示间隔
}

# SSH连接配置
SSH_CONFIG = {
    "timeout": 10,
    "auto_add_host_key": True,
    "strict_host_key_checking": False
} 