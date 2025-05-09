import os
import subprocess
import threading
import time
"""
代码思路：
通过本python脚本：
1. 读取键盘，监测到按下r键开始录音5秒，之后接入api调用大模型
通过system prompt让大模型返回0，1等去决定不同的控制方式，包括键盘或者视觉，
之后调用库将返回的文字转为音频播放。
在录放音部分要通过命令行的方式控制，这个脚本的本质是把命令行通过python的os等库封装起来而已
录制命令是arecord -D hw:0,0 -f S16\_LE -r 16000 -c 1 -d 5 test.wav
播放命令是aplay -D hw:1,0 -f S16\_LE -r 16000 -c 1 test.wav
参考https://github.com/CarrotFish/KOS\_Deploy\_Guidance/blob/main/documents/audio\_speaker.md
之后你在录音时对音频进行处理，- ffmpeg -i input.wav -ac 1 -ar 16000 output.wav
由于录音设备录制效果噪音很大、人声很轻，可以通过ffmpeg粗糙地调整：ffmpeg -i E input.wav -af "afftdn=nr=12\:nt=w, dynaudnorm=f=500\:g=15, volume=1000.0" output.wav 
对应了降噪、标准化、放大声音。

"""

REMOTE_USER = "root"
REMOTE_HOST = "192.168.42.1"
REMOTE_ADDR = f"{REMOTE_USER}@{REMOTE_HOST}"


LOCAL_RAW = "test_raw.wav"
LOCAL_PROCESSED = "test.wav"
LOCAL_RESPONSE = "response.wav"

REMOTE_RAW = "/tmp/test_raw.wav"
REMOTE_PROCESSED = "/tmp/test.wav"
REMOTE_RESPONSE = "/tmp/response.wav"

SYSTEM_PROMPT = (
    "You are a controller that outputs a single integer code: 0 for keyboard control, 1 for vision control."
)

# SSH helper
def ssh_run(cmd, capture_output=False):
    ssh_cmd = ["ssh", REMOTE_ADDR] + cmd
    return subprocess.run(ssh_cmd, check=True, capture_output=capture_output)

# SCP helper
def scp_from_remote(remote_path, local_path):
    scp_cmd = ["scp", f"{REMOTE_ADDR}:{remote_path}", local_path]
    subprocess.run(scp_cmd, check=True)


def scp_to_remote(local_path, remote_path):
    scp_cmd = ["scp", local_path, f"{REMOTE_ADDR}:{remote_path}"]
    subprocess.run(scp_cmd, check=True)


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
    # Placeholder for model call - fill in with your API details
    # response = client.transcribe_audio(
    #     system_prompt=SYSTEM_PROMPT,
    #     audio_file=wav_path
    # )
    # code = int(response.text.strip())
    code = 0
    print(f"[Model] returned code: {code}")
    return code


def text_to_speech(text, out_wav=LOCAL_RESPONSE):
    # Placeholder for TTS - implement locally
    print(f"Generating TTS for: {text}")
    # tts_client.synthesize_to_file(text, out_wav)
    # For placeholder, copy processed wav
    subprocess.run(["cp", LOCAL_PROCESSED, out_wav], check=True)
    return out_wav


def play_remote(wav_path):
    """Send audio to remote and play"""
    print("Transferring response to robot...")
    scp_to_remote(wav_path, REMOTE_RESPONSE)
    print("Playing audio on robot...")
    ssh_run([
        "aplay", "-D", "hw:1,0", "-f", "S16_LE", "-r", "16000", "-c", "1", REMOTE_RESPONSE
    ])


def main():
    print("Press 'r' to record & process, 'q' to quit.")
    try:
        import keyboard
    except ImportError:
        print("Please install the 'keyboard' library: pip install keyboard")
        return

    while True:
        event = keyboard.read_event()
        if event.event_type == keyboard.KEY_DOWN:
            key = event.name.lower()
            if key == 'r':
                # Remote record
                record_remote()
                # Fetch & process locally
                process_local()
                # Model decision
                code = call_model_and_get_code(LOCAL_PROCESSED)

                # Choose action text
                if code == 0:
                    response = "Switching to keyboard control."
                elif code == 1:
                    response = "Switching to vision control."
                else:
                    response = f"Unknown code {code}, defaulting to keyboard."

                # TTS locally
                tts_wav = text_to_speech(response)
                # Play remotely
                play_remote(tts_wav)

            elif key == 'q':
                print("Exiting...")
                break

if __name__ == '__main__':
    main()
