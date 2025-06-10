import time
import subprocess
"""
在已经确认能打开摄像头的情况下，手动拍摄10张图片
优化版本：降低码率、添加超时和重试机制
"""
HOST = '192.168.0.53'
# HOST = '192.168.42.1'
rtsp_url = f"rtsp://{HOST}/h264"
# rtsp://192.168.0.53/h264
INTERVAL = 3 # 拍摄间隔增加到3秒，减少网络压力
SHOTS = 10
TIMEOUT = 10 # ffmpeg超时时间（秒）
MAX_RETRIES = 3 # 每张照片最大重试次数

def capture_image(filename, retry_count=0):
    """拍摄单张图片，带重试机制"""
    cmd = [
        "ffmpeg",
        "-rtsp_transport", "tcp",
        "-rtsp_flags", "prefer_tcp",
        "-timeout", str(TIMEOUT * 1000000),  # 超时时间（微秒）
        "-i", rtsp_url,
        "-vframes", "1",
        "-q:v", "5",  # 降低质量要求，减少数据量（2-31，数值越大质量越低）
        "-s", "640x480",  # 降低分辨率，减少数据量
        "-r", "5",  # 限制帧率为5fps
        "-y",  # 覆盖已存在的文件
        filename
    ]
    
    try:
        print(f"正在保存 {filename} (尝试 {retry_count + 1}/{MAX_RETRIES + 1})...")
        result = subprocess.run(cmd, 
                               stdout=subprocess.DEVNULL, 
                               stderr=subprocess.PIPE,
                               timeout=TIMEOUT + 5,  # subprocess超时时间
                               text=True)
        
        if result.returncode == 0:
            print(f"✓ {filename} 保存成功")
            return True
        else:
            print(f"✗ {filename} 保存失败，返回码: {result.returncode}")
            if result.stderr:
                print(f"错误信息: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        print(f"✗ {filename} 超时，ffmpeg执行时间超过{TIMEOUT + 5}秒")
        return False
    except Exception as e:
        print(f"✗ {filename} 发生异常: {e}")
        return False

# 主循环
success_count = 0
for i in range(1, SHOTS + 1):
    filename = f"img{i:03d}.jpg"
    
    # 尝试拍摄，最多重试MAX_RETRIES次
    success = False
    for retry in range(MAX_RETRIES + 1):
        success = capture_image(filename, retry)
        if success:
            success_count += 1
            break
        elif retry < MAX_RETRIES:
            print(f"等待2秒后重试...")
            time.sleep(2)
    
    if not success:
        print(f"❌ {filename} 拍摄失败，跳过")
    
    # 如果不是最后一张照片，等待间隔时间
    # if i < SHOTS:
    #     print(f"等待{INTERVAL}秒...")
    #     time.sleep(INTERVAL)

print(f"\n拍摄完成。成功: {success_count}/{SHOTS}")