import time
import subprocess
"""
在已经确认能打开摄像头的情况下，手动拍摄10张图片
"""
rtsp_url = "rtsp://192.168.0.48/h264"
INTERVAL = 2 # 拍摄间隔（秒）
SHOTS = 10

for i in range(1, SHOTS+1):  # 这里设置循环次数
    filename = f"img{i:03d}.jpg" # 文件命名方式：d表示整数，这里是001-999的意思
    cmd = [
        "ffmpeg",
        "-rtsp_transport", "tcp",
        "-i", rtsp_url,
        "-vframes", "1",
        "-q:v", "2",
        filename
    ]
    print(f"正在保存 {filename} ...")
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(INTERVAL)  # 等待INTERVAL秒后再拍

print("拍摄完成。")