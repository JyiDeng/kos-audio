import paramiko
import time
import threading
import re
import subprocess
import sys
import select
import datetime

"""
在未确认能否打开摄像头的情况下，自动尝试运行五次 camera-test.sh 以及 kill rtsp2web.json 相关进程，如果成功，则每3秒自动拍照一张，1分钟后自动关闭。

如果连续五次kill rtsp2web.json 相关进程失败，则认为摄像头无法打开，退出。
"""

# 板子ssh信息
HOST = '192.168.42.1'
USER = 'root'
PASSWORD = 'milkv'
RTSP_URL = "rtsp://192.168.42.1/h264"
CAPTURE_CMD = [
    "ffmpeg", "-rtsp_transport", "tcp", "-i", RTSP_URL, "-vframes", "1", "-q:v", "2"
]

cnt = 0

if sys.platform == "win32":
    import msvcrt

def ssh_connect():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PASSWORD)
    return ssh

def start_sample_vi_fd(ssh):
    # 启动sample_vi_fd，返回channel用于读取输出
    transport = ssh.get_transport()
    channel = transport.open_session()
    channel.get_pty()
    channel.exec_command('/mnt/system/usr/bin/camera-test.sh')
    return channel

def kill_rtsp2web(ssh):
    stdin, stdout, stderr = ssh.exec_command("ps -a | grep /etc/rtsp2web.json")
    lines = stdout.readlines()
    for line in lines:
        print(line)
        pid = line.strip().split()[0]
        content = line.strip().split()[2]    
        if int(pid) < 300:
            print(f"**** gonna kill -9 {pid}, content:{content}...")
            ssh.exec_command(f"kill -9 {pid}")
            print(f"**** kill -9 {pid}, done")

def monitor_and_start(ssh):
    global cnt
    while cnt<5:
        channel = start_sample_vi_fd(ssh)
        rtsp_found = False
        failed = False
        while True:
            if channel.recv_ready():
                output = channel.recv(1024).decode()
                print(output, end="")
                if "rtsp://" in output:
                    rtsp_found = True
                    break
                if "init vpss failed" in output or "init middleware failed" in output:
                    failed = True
                    break
            if channel.exit_status_ready():
                break
            time.sleep(0.1)
        if rtsp_found:
            return channel
        if failed:
            kill_rtsp2web(ssh)
            time.sleep(2)
            cnt += 1
            continue
        cnt += 1
    print("sample_vi_fd启动失败，建议reboot后重新运行")
    return None

def capture_loop():
    start_time = time.time()
    count = 1
    print("每3秒自动拍照，1分钟后自动结束。")
    while time.time() - start_time < 60:
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"img_{timestamp}.jpg"
        print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] 正在保存 {filename} ...")
        result = subprocess.run(CAPTURE_CMD + [filename], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] 拍照完成，返回码: {result.returncode}")
        if result.stdout:
            print(f"stdout: {result.stdout.decode(errors='ignore')}")
        if result.stderr:
            print(f"stderr: {result.stderr.decode(errors='ignore')}")
        count += 1
        time.sleep(3)
    print("拍照结束。")

def main():
    ssh = ssh_connect()
    # 启动时先kill rtsp2web.json相关进程
    kill_rtsp2web(ssh)
    channel = monitor_and_start(ssh)
    if channel is not None:
        capture_loop()
        # 拍照结束后优雅终止sample_vi_fd
        try:
            print("拍照结束后，发送Ctrl+C，正确结束camera-test.sh程序...")
            channel.send('\x03')  # 发送Ctrl+C
            time.sleep(1)
            print(f"发送Ctrl+C成功。")
            # 检查进程是否还在
            stdin, stdout, stderr = ssh.exec_command("ps -a | grep sample_vi_fd")
            lines = stdout.readlines()
            if lines:
                print("sample_vi_fd未退出，尝试kill...")
                for line in lines:
                    pid = line.strip().split()[0]
                    ssh.exec_command(f"kill -9 {pid}")
                print("已强制kill sample_vi_fd。")
            else:
                print("sample_vi_fd已正常退出。")
        except Exception as e:
            print(f"发送Ctrl+C失败: {e}")
        channel.close()
    ssh.close()

if __name__ == "__main__":
    main()