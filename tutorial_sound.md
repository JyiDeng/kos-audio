# 麦克风、扬声器使用说明

### 首先，配置环境
**macOS:**
```bash
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
```
或者
```
brew install rust
```
**windows:**
```
https://rustup.rs/
```
从上述网址下载安装包，按照指示安装即可

## 使用方法：

### 编译项目
```
cargo build
```
*会依据`Cargo.toml`中配置编译*

### 获取音频信息
```
cargo run --get-audio-info
```


### 播放
```
cargo run --play --file out.wav
```
-**参数**：
-`--file`：指定文件

### 录制音频
```
cargo run --record --file out.wav --seconds 5
```
-**参数**：
-`--file`：指定文件保存路径
-`--seconds`：指定录制时长

### 远程录制音频

```
cargo run -- remote-record --ip 192.168.42.1 --file out.wav --seconds 5
cargo run -- remote-record --ip 127.0.0.1 --file out1.wav --seconds 5
```
-**参数**：
-`--ip`：该指定IP地址，通过该地址与远程服务器建立gRPC连接
-`--file`：指定远程录制在本地的保存路径
-`--seconds`：指定时长

