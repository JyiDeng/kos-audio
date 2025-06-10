## 在 /usr/local/bin/ 下新建一个脚本 start_av.sh

```bash

BASE_DIR="/home/pi/kos-audio-camera" # 请改成自己的！

# 检测声卡
echo "Waiting for audio device..."
for i in {1..10}; do
    if arecord -l | grep -q "card"; then
        echo "Audio device found."
        break
    else
        echo "  retry $i/10..."
        sleep 2
    fi
done

# 检测摄像头
echo "Waiting for video device..."
for i in {1..10}; do
    if v4l2-ctl --list-devices &>/dev/null; then
        echo "Video device found."
        break
    else
        echo "  retry $i/10..."
        sleep 2
    fi
done

# 启动音频GUI
echo "Starting audio_control_gui.py..."
python3 "${BASE_DIR}/audio_control_gui.py" &

# 启动摄像头
echo "Starting camera..."
python3 "${BASE_DIR}/camera/your_camera_main.py" &

echo "All started."
```

如果无法运行，给脚本添加权限：
```bash
chmod +x /usr/local/bin/start_av.sh
```