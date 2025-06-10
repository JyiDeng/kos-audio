import time
import subprocess
import sys
import os
"""
发送cvi_camera指令到板子，根据串流运行截图
1秒1次，截两张图片
"""

# 尝试导入paramiko进行SSH连接
try:
    import paramiko
    PARAMIKO_AVAILABLE = True
except ImportError:
    PARAMIKO_AVAILABLE = False
    print("警告: paramiko未安装，将使用传统SSH命令（需要手动输入密码）")
    print("安装方法: pip install paramiko")

# 配置参数 - 使用大写字母变量
BOARD_HOST = '192.168.0.53'  # 板子IP地址
BOARD_USER = 'root'          # 板子用户名
BOARD_PASSWORD = 'milkv'     # 板子密码
BOARD_PORT = 22              # SSH端口
CAMERA_SCRIPT_PATH = '/root/camera.sh'  # 板子上camera.sh脚本的路径
RTSP_URL = f"rtsp://{BOARD_HOST}/h264"  # RTSP流地址
CAPTURE_INTERVAL = 1         # 截图间隔（秒）
TOTAL_SHOTS = 2             # 总截图数量
IMAGE_QUALITY = 5           # 图片质量（2-31，数值越大质量越低）
IMAGE_SIZE = "640x480"      # 图片分辨率
FRAME_RATE = 5              # 帧率
TIMEOUT = 10                # 超时时间（秒）
CAMERA_STARTUP_WAIT = 10     # 等待摄像头启动的时间（秒）

def execute_ssh_command(command, description=""):
    """执行SSH命令（支持paramiko自动密码输入）"""
    if PARAMIKO_AVAILABLE:
        return execute_ssh_paramiko(command, description)
    else:
        return execute_ssh_subprocess(command, description)

def execute_ssh_paramiko(command, description=""):
    """使用paramiko执行SSH命令"""
    try:
        if description:
            print(f"{description}...")
        
        # 创建SSH客户端
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        # 连接到远程主机
        ssh.connect(
            hostname=BOARD_HOST,
            port=BOARD_PORT,
            username=BOARD_USER,
            password=BOARD_PASSWORD,
            timeout=TIMEOUT
        )
        
        # 执行命令
        stdin, stdout, stderr = ssh.exec_command(command, timeout=TIMEOUT)
        
        # 获取输出
        output = stdout.read().decode().strip()
        error = stderr.read().decode().strip()
        return_code = stdout.channel.recv_exit_status()
        
        ssh.close()
        
        return return_code, output, error
        
    except Exception as e:
        if description:
            print(f"✗ {description}失败: {e}")
        return -1, "", str(e)

def execute_ssh_subprocess(command, description=""):
    """使用subprocess执行SSH命令（需要手动输入密码）"""
    ssh_cmd = ["ssh", f"{BOARD_USER}@{BOARD_HOST}", command]
    
    try:
        if description:
            print(f"{description}...")
        
        result = subprocess.run(ssh_cmd, 
                               stdout=subprocess.PIPE, 
                               stderr=subprocess.PIPE,
                               timeout=TIMEOUT,
                               text=True)
        
        return result.returncode, result.stdout.strip(), result.stderr.strip()
        
    except subprocess.TimeoutExpired:
        return -1, "", "命令超时"
    except Exception as e:
        return -1, "", str(e)

def prepare_camera_script():
    """准备和检查camera.sh脚本"""
    # 检查脚本是否存在
    return_code, output, error = execute_ssh_command(
        f"ls -la {CAMERA_SCRIPT_PATH}",
        "检查camera.sh脚本"
    )
    
    if return_code != 0:
        print(f"✗ camera.sh脚本不存在: {CAMERA_SCRIPT_PATH}")
        return False
    
    # 确保脚本有执行权限
    return_code, output, error = execute_ssh_command(
        f"chmod +x {CAMERA_SCRIPT_PATH}",
        "设置脚本执行权限"
    )
    
    if return_code == 0:
        print("✓ camera.sh脚本权限设置成功")
        return True
    else:
        print(f"✗ 设置脚本权限失败: {error}")
        return False

def stop_all_camera_processes():
    """彻底停止所有cvi_camera相关进程"""
    print("正在彻底停止所有cvi_camera进程...")
    
    # 方法1: 使用killall (更彻底)
    execute_ssh_command("killall cvi_camera 2>/dev/null || echo 'killall完成'", "使用killall停止进程")
    
    # 方法2: 使用pkill (按名称)
    execute_ssh_command("pkill -f cvi_camera 2>/dev/null || echo 'pkill完成'", "使用pkill停止进程")
    
    # 方法3: 强制停止 (使用SIGKILL)
    execute_ssh_command("pkill -9 -f cvi_camera 2>/dev/null || echo 'pkill -9完成'", "强制停止进程")
    
    # 等待进程完全停止和资源释放
    print("等待硬件资源释放...")
    time.sleep(3)
    
    # 验证是否还有残留进程
    return_code, output, error = execute_ssh_command(
        "ps aux | grep cvi_camera | grep -v grep || echo '无残留进程'",
        "检查残留进程"
    )
    
    if output and "cvi_camera" in output:
        print(f"警告: 仍有残留进程: {output}")
        return False
    else:
        print("✓ 所有cvi_camera进程已彻底停止")
        return True

def start_camera_script():
    """启动板子上的camera.sh脚本"""
    # 首先准备脚本
    if not prepare_camera_script():
        return False
    
    # 彻底停止所有现有的cvi_camera进程
    if not stop_all_camera_processes():
        print("警告: 可能仍有残留进程，但继续尝试启动")
    
    # 启动camera.sh脚本（后台运行）
    return_code, output, error = execute_ssh_command(
        f"nohup {CAMERA_SCRIPT_PATH} > /var/log/cvi_camera.log 2>&1 &",
        "正在启动camera.sh脚本"
    )
    
    if return_code == 0:
        print("✓ camera.sh脚本启动成功")
        return True
    else:
        print(f"✗ camera.sh脚本启动失败，返回码: {return_code}")
        if error:
            print(f"错误信息: {error}")
        return False

def check_camera_process():
    """检查cvi_camera进程是否在运行"""
    # 使用ps命令结合grep查找cvi_camera进程，更稳定
    return_code, output, error = execute_ssh_command(
        "ps aux | grep cvi_camera | grep -v grep",
        "正在检查cvi_camera进程"
    )
    
    if return_code == 0 and output.strip():
        print("✓ cvi_camera进程正在运行")
        print(f"进程信息: {output}")
        return True
    else:
        print("✗ cvi_camera进程未运行")
        if error:
            print(f"错误信息: {error}")
        return False

def wait_for_rtsp_ready():
    """等待RTSP服务完全就绪"""
    print("等待RTSP服务完全就绪...")
    max_attempts = 10
    
    for attempt in range(1, max_attempts + 1):
        print(f"检查RTSP服务状态 ({attempt}/{max_attempts})...")
        
        # 检查进程是否运行
        if not check_camera_process():
            print(f"  进程未运行，等待...")
            time.sleep(1)
            continue
        
        # 检查日志中是否有RTSP初始化成功的信息
        return_code, output, error = execute_ssh_command(
            "tail -10 /var/log/cvi_camera.log | grep -i 'initialize rtsp\\|rtsp://' || echo '未找到RTSP初始化信息'",
            ""
        )
        
        if return_code == 0 and ("Initialize RTSP" in output or "rtsp://" in output):
            print("✓ RTSP服务初始化成功")
            print(f"RTSP信息: {output}")
            
            # 等待1秒确保服务完全就绪
            print("等待1秒确保服务完全就绪...")
            time.sleep(1)
            return True
        else:
            print(f"  RTSP服务尚未初始化，继续等待...")
        
        time.sleep(1)
    
    print("✗ RTSP服务启动超时")
    
    # 检查启动日志
    print("查看完整启动日志:")
    return_code, output, error = execute_ssh_command(
        "tail -20 /var/log/cvi_camera.log",
        ""
    )
    if output:
        print(f"最新日志:\n{output}")
    
    return False

def capture_image(filename):
    """通过RTSP流截图"""
    ffmpeg_cmd = [
        "ffmpeg",
        "-rtsp_transport", "tcp",
        "-rtsp_flags", "prefer_tcp",
        "-timeout", "10000000",  # 超时时间10秒（微秒）
        "-fflags", "nobuffer",  # 禁用缓冲，减少延迟
        "-flags", "low_delay",  # 低延迟模式
        "-probesize", "32",     # 减少探测大小，加快启动
        "-analyzeduration", "0", # 减少分析时间
        "-i", RTSP_URL,
        "-vframes", "1",        # 只要1帧
        "-vsync", "0",          # 禁用视频同步
        "-q:v", str(IMAGE_QUALITY),
        "-s", IMAGE_SIZE,
        "-pix_fmt", "yuvj420p", # 指定像素格式，避免转换
        "-y",  # 覆盖已存在的文件
        filename
    ]
    
    try:
        print(f"正在截图保存 {filename}...")
        result = subprocess.run(ffmpeg_cmd, 
                               stdout=subprocess.DEVNULL, 
                               stderr=subprocess.PIPE,
                               timeout=TIMEOUT + 5,
                               text=True)
        
        if result.returncode == 0:
            print(f"✓ {filename} 截图成功")
            return True
        else:
            print(f"✗ {filename} 截图失败，返回码: {result.returncode}")
            if result.stderr:
                print(f"错误信息: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        print(f"✗ {filename} 截图超时")
        return False
    except Exception as e:
        print(f"✗ {filename} 截图时发生异常: {e}")
        return False

# 主程序
def main():
    print("开始cvi_camera截图程序...")
    
    # 启动camera.sh脚本
    if not start_camera_script():
        print("❌ camera.sh脚本启动失败，程序退出")
        return
    
    # 等待RTSP服务完全就绪
    if not wait_for_rtsp_ready():
        print("❌ RTSP服务启动失败，程序退出")
        return
    
    # 开始截图
    success_count = 0
    for i in range(1, TOTAL_SHOTS + 1):
        filename = f"cvi_img{i:03d}.jpg"
        
        if capture_image(filename):
            success_count += 1
        
        # 如果不是最后一张，等待间隔时间
        if i < TOTAL_SHOTS:
            print(f"等待{CAPTURE_INTERVAL}秒...")
            time.sleep(CAPTURE_INTERVAL)
    
    print(f"\n截图完成。成功: {success_count}/{TOTAL_SHOTS}")
    
    # 可选：停止cvi_camera进程
    # print("正在停止cvi_camera进程...")
    # subprocess.run(["ssh", f"{BOARD_USER}@{BOARD_HOST}", "pkill -f cvi_camera"], 
    #                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

if __name__ == "__main__":
    main() 