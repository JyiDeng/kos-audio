## 在/usr/local/bin/下新建start_av.sh

*需要安装 ffmpeg*

```bash

BASE_DIR="/home/pi/kos-audio-camera"
RTSP_URL="rtsp://192.168.0.48/h264"

echo "=== Waiting for audio device ==="
for i in {1..10}; do
    if arecord -l | grep -q "card"; then
        echo "✔ Audio device found."
        break
    else
        echo "  retry $i/10..."
        sleep 2
    fi
done

echo "=== Waiting for RTSP stream at $RTSP_URL ==="

for i in {1..10}; do
    if ffprobe -rtsp_transport tcp -timeout 1000000 -v error -show_streams "$RTSP_URL" > /dev/null 2>&1; then
        echo "✔ RTSP stream is up."
        break
    else
        echo "  retry $i/10..."
        sleep 2
    fi
done

echo "=== Starting audio_control_gui.py ==="
python3 "${BASE_DIR}/audio_control_gui.py" \
    >> /var/log/audio_control.log 2>&1 &

echo "=== Starting camera run_camera.py with RTSP ==="
python3 "${BASE_DIR}/camera/run_camera.py" \
    --rtsp-url "$RTSP_URL" \
    >> /var/log/camera.log 2>&1 &

echo "All services started."

```

如果能支持x11就好了

*在/etc/systemd/system/下新建audio_camera.service*

```bash
[Unit]
Description=Auto-start Audio & Camera for kos-audio-camera
After=network.target sound.target systemd-modules-load.service

[Service]
Type=simple

User=root # ?
# 转发，需要调整，不是x11
Environment=DISPLAY=:0

ExecStart=/usr/local/bin/start_av.sh
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target

```