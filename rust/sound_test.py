'''
请先执行如下命令，将rust程序转换为脚本
python -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. kos-audio/sound.proto
'''

import paramiko
import grpc
import asyncio
import sound_pb2
import sound_pb2_grpc

SSH_HOST = '192.168.42.1'
SSH_PORT = 22
SSH_USERNAME = 'root'
SSH_PASSWORD = 'milkv'
GRPC_HOST = '192.168.42.1'
GRPC_PORT = 50051

def execute_ssh_command(command):
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        ssh.connect(SSH_HOST, SSH_PORT, SSH_USERNAME, SSH_PASSWORD)
        stdin, stdout, stderr = ssh.exec_command(command)
        output = stdout.read().decode()
        error = stderr.read().decode()
        if output:
            print(f"output: \n{output}")
        if error:
            print(f"error: \n{error}")
        return output
    except paramiko.AuthenticationException:
        print("authentication failed")
    except paramiko.SSHException as ssh_ex:
        print(f"SSH error: {str(ssh_ex)}")
    except Exception as ex:
        print(f"unknown error: {str(ex)}")
    finally:
        ssh.close()

async def remote_record_audio(ip, seconds, out_file):
    channel = grpc.aio.insecure_channel(f"{ip}:{GRPC_PORT}")
    stub = sound_pb2_grpc.SoundServiceStub(channel)
    config = sound_pb2.AudioConfig(
        sample_rate=44100,
        bit_depth=16,
        channels=1
    )
    request = sound_pb2.RecordAudioRequest(
        config=config,
        duration_ms=seconds * 1000
    )
    try:
        with open(out_file, 'wb') as file:
            async for response in stub.RecordAudio(request):
                file.write(response.audio_data)
        print(f"saved to  {out_file}")
    except grpc.RpcError as e:
        print(f"gRPC error: {e}")
    finally:
        await channel.close()

async def main():
    print("cargo build")
    execute_ssh_command("cargo build")

    print("cargo run -- get-audio-info...")
    execute_ssh_command("cargo run -- get-audio-info")

    # 播放音频
    print("cargo run -- play...")
    execute_ssh_command("cargo run -- play --file out.wav")

    # 录制音频
    print("cargo run -- record...")
    execute_ssh_command("cargo run -- record --file out.wav --seconds 5")

    # 远程录制音频
    print("recording...")
    await remote_record_audio(GRPC_HOST, 5, 'out.wav')
    await remote_record_audio('127.0.0.1', 5, 'out1.wav')

if __name__ == "__main__":
    asyncio.run(main())