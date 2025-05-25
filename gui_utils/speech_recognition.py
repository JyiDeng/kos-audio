#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
语音识别模块
基于sherpa_onnx实现的语音识别功能
"""

import os
import sys
import numpy as np
from typing import Union

# 模型路径配置 - 使用脚本所在目录的绝对路径
def get_script_dir():
    """获取当前脚本所在目录"""
    return os.path.dirname(os.path.abspath(__file__))

# 使用绝对路径确保模型文件能被找到
SCRIPT_DIR = get_script_dir()
DEFAULT_ASR_PATH = os.path.join(SCRIPT_DIR, '../model', 'ASR', 'sherpa-onnx-paraformer-zh-small-2024-03-09')
DEFAULT_VAD_PATH = os.path.join(SCRIPT_DIR, '../model', 'VAD')

class ASR:
    """语音识别基类"""
    def __init__(self):
        self._recognizer = None
        raise NotImplementedError

    def transcribe(self, audio: Union[str, np.ndarray], sample_rate=16000) -> str:
        """转录音频为文字"""
        if isinstance(audio, str):
            # 如果输入是文件路径，使用librosa加载
            try:
                import librosa
                audio, _ = librosa.load(audio, sr=sample_rate)
            except ImportError:
                print("错误: 需要安装librosa库: pip install librosa")
                return ""
            except Exception as e:
                print(f"加载音频文件失败: {e}")
                return ""
        
        try:
            s = self._recognizer.create_stream()
            s.accept_waveform(sample_rate, audio)
            self._recognizer.decode_stream(s)
            return s.result.text
        except Exception as e:
            print(f"语音识别失败: {e}")
            return ""

class Paraformer(ASR):
    """Paraformer语音识别模型"""
    def __init__(self, model_path: str, tokens_path: str, num_threads: int = 8, provider: str = 'cpu'):
        try:
            import sherpa_onnx
            self._recognizer = sherpa_onnx.OfflineRecognizer.from_paraformer(
                paraformer=model_path,
                tokens=tokens_path,
                num_threads=num_threads,
                provider=provider,
            )
        except ImportError:
            print("错误: 需要安装sherpa_onnx库")
            print("安装方法: pip install sherpa-onnx")
            raise
        except Exception as e:
            print(f"初始化Paraformer模型失败: {e}")
            raise

class Whisper(ASR):
    """Whisper语音识别模型"""
    def __init__(self, encoder_path: str, decoder_path: str, tokens_path: str, 
                 num_threads: int = 8, provider: str = 'cpu'):
        try:
            import sherpa_onnx
            self._recognizer = sherpa_onnx.OfflineRecognizer.from_whisper(
                encoder=encoder_path,
                decoder=decoder_path,
                tokens=tokens_path,
                num_threads=num_threads,
                provider=provider,
            )
        except ImportError:
            print("错误: 需要安装sherpa_onnx库")
            print("安装方法: pip install sherpa-onnx")
            raise
        except Exception as e:
            print(f"初始化Whisper模型失败: {e}")
            raise

class SpeechRecognizer:
    """语音识别器封装类"""
    
    def __init__(self, model_type='paraformer', model_path=None, **kwargs):
        self.model_type = model_type
        self.asr = None
        
        # 根据模型类型初始化
        if model_type == 'paraformer':
            self._init_paraformer(model_path, **kwargs)
        elif model_type == 'whisper':
            self._init_whisper(model_path, **kwargs)
        else:
            raise ValueError(f"不支持的模型类型: {model_type}")
    
    def _init_paraformer(self, model_path=None, **kwargs):
        """初始化Paraformer模型"""
        if model_path is None:
            model_path = DEFAULT_ASR_PATH
        
        try:
            model_file = os.path.join(model_path, 'model.int8.onnx')
            tokens_file = os.path.join(model_path, 'tokens.txt')
            
            if not os.path.exists(model_file):
                print(f"警告: 模型文件不存在: {model_file}")
                print("请下载模型文件到指定路径")
                # 尝试使用默认模型路径的其他变体
                alt_model_file = os.path.join(model_path, 'model.onnx')
                if os.path.exists(alt_model_file):
                    model_file = alt_model_file
                    print(f"使用备选模型文件: {model_file}")
                else:
                    raise FileNotFoundError(f"找不到模型文件: {model_file}")
            
            if not os.path.exists(tokens_file):
                raise FileNotFoundError(f"找不到tokens文件: {tokens_file}")
            
            self.asr = Paraformer(
                model_path=model_file,
                tokens_path=tokens_file,
                **kwargs
            )
            print(f"✓ Paraformer模型加载成功: {model_path}")
            
        except Exception as e:
            print(f"✗ Paraformer模型加载失败: {e}")
            # 创建一个模拟的识别器
            self.asr = MockASR()
    
    def _init_whisper(self, model_path=None, **kwargs):
        """初始化Whisper模型"""
        try:
            # Whisper模型需要三个文件
            encoder_path = kwargs.get('encoder_path')
            decoder_path = kwargs.get('decoder_path')
            tokens_path = kwargs.get('tokens_path')
            
            if not all([encoder_path, decoder_path, tokens_path]):
                raise ValueError("Whisper模型需要指定encoder_path, decoder_path, tokens_path")
            
            self.asr = Whisper(
                encoder_path=encoder_path,
                decoder_path=decoder_path,
                tokens_path=tokens_path,
                **{k: v for k, v in kwargs.items() if k not in ['encoder_path', 'decoder_path', 'tokens_path']}
            )
            print("✓ Whisper模型加载成功")
            
        except Exception as e:
            print(f"✗ Whisper模型加载失败: {e}")
            # 创建一个模拟的识别器
            self.asr = MockASR()
    
    def recognize(self, audio_file: str) -> str:
        """识别音频文件"""
        if self.asr is None:
            return ""
        
        try:
            result = self.asr.transcribe(audio_file)
            return result.strip()
        except Exception as e:
            print(f"语音识别出错: {e}")
            return ""
    
    def is_available(self) -> bool:
        """检查模型是否可用"""
        return self.asr is not None and not isinstance(self.asr, MockASR)

class MockASR:
    """模拟语音识别器（当真实模型不可用时使用）"""
    
    def transcribe(self, audio_file: str) -> str:
        """模拟语音识别"""
        import time
        time.sleep(0.5)  # 模拟处理时间
        return "模拟语音识别结果（真实模型未加载）"

def create_recognizer(model_type='paraformer', model_path=None, **kwargs):
    """创建语音识别器的工厂函数"""
    try:
        return SpeechRecognizer(model_type=model_type, model_path=model_path, **kwargs)
    except Exception as e:
        print(f"创建语音识别器失败: {e}")
        print("将使用模拟识别器")
        recognizer = SpeechRecognizer.__new__(SpeechRecognizer)
        recognizer.model_type = 'mock'
        recognizer.asr = MockASR()
        return recognizer

def test_recognition(audio_file: str = None):
    """测试语音识别功能"""
    print("=" * 50)
    print("语音识别功能测试")
    print("=" * 50)
    
    # 创建识别器
    print("1. 创建Paraformer识别器...")
    recognizer = create_recognizer('paraformer')
    
    if recognizer.is_available():
        print("✓ 真实模型加载成功")
    else:
        print("✗ 真实模型加载失败，使用模拟模式")
    
    # 测试识别
    if audio_file and os.path.exists(audio_file):
        print(f"\n2. 测试音频文件: {audio_file}")
        result = recognizer.recognize(audio_file)
        print(f"识别结果: {result}")
    else:
        print("\n2. 无测试音频文件，跳过识别测试")
    
    print("=" * 50)

if __name__ == "__main__":
    if len(sys.argv) > 1:
        test_recognition(sys.argv[1])
    else:
        test_recognition() 