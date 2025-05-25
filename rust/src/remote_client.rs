use tonic::transport::Channel;
use kos_proto::sound::sound_service_client::SoundServiceClient;
use kos_proto::sound::{RecordAudioRequest, AudioConfig};
use google::protobuf::Empty;

pub async fn record_from_remote(ip: &str, seconds: u32, out_file: &str) -> anyhow::Result<()> {
    let addr = format!("http://{}:50051", ip); // 远程 gRPC 服务监听地址
    let mut client = SoundServiceClient::connect(addr).await?;

    let config = AudioConfig {
        sample_rate: 44100,
        bit_depth: 16,
        channels: 1,
    };

    let request = RecordAudioRequest {
        config: Some(config),
        duration_ms: seconds * 1000,
    };

    let mut stream = client.record_audio(request).await?.into_inner();

    use std::fs::File;
    use std::io::Write;
    let mut file = File::create(out_file)?;

    while let Some(resp) = stream.message().await? {
        file.write_all(&resp.audio_data)?;
    }

    Ok(())
}

