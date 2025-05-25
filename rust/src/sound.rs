
use cpal::traits::{DeviceTrait, HostTrait, StreamTrait};
use std::{fs::File, io::Write};

pub fn get_audio_info() -> anyhow::Result<()> {
    let host = cpal::default_host();

    let input = host.default_input_device();
    let output = host.default_output_device();

    if let Some(ref dev) = input {
        println!("Input: {:?}", dev.name()?);
        println!("Recording formats:");
        for fmt in dev.supported_input_configs()? {
            println!("  {:?}", fmt);
        }
    } else {
        println!("No input device found");
    }

    if let Some(ref dev) = output {
        println!("Output: {:?}", dev.name()?);
        println!("Playback formats:");
        for fmt in dev.supported_output_configs()? {
            println!("  {:?}", fmt);
        }
    } else {
        println!("No output device found");
    }

    Ok(())
}

pub fn play_audio(file_path: &str) -> anyhow::Result<()> {
    use rodio::{Decoder, OutputStream, Sink};
    let (_stream, handle) = OutputStream::try_default()?;
    let sink = Sink::try_new(&handle)?;

    let file = File::open(file_path)?;
    let source = Decoder::new(std::io::BufReader::new(file))?;

    sink.append(source);
    sink.sleep_until_end();

    Ok(())
}
use hound;

pub fn record_audio(file_path: &str, seconds: u32) -> anyhow::Result<()> {
    use cpal::{SampleFormat};
    use std::sync::{Arc, Mutex};
    use std::time::Duration;

    let host = cpal::default_host();
    let device = host.default_input_device().expect("No input device available");
    let config = device.default_input_config()?;

    println!("Recording with config: {:?}", config);

    let sample_format = config.sample_format();
    let sample_rate = config.sample_rate().0;
    let channels = config.channels() as u16;

    let recorded = Arc::new(Mutex::new(Vec::<i16>::new()));
    let recorded_clone = recorded.clone();

    let writer_fn = move |data: &[f32], _: &cpal::InputCallbackInfo| {
        let mut buffer = recorded_clone.lock().unwrap();
        for &sample in data {
            let int_sample = (sample * i16::MAX as f32) as i16;
            buffer.push(int_sample);
        }
    };

    let stream = match sample_format {
        SampleFormat::F32 => device.build_input_stream(&config.into(), writer_fn, err_fn, None)?,
        _ => panic!("Unsupported format"),
    };

    stream.play()?;
    std::thread::sleep(Duration::from_secs(seconds.into()));
    drop(stream);

    let spec = hound::WavSpec {
        channels,
        sample_rate,
        bits_per_sample: 16,
        sample_format: hound::SampleFormat::Int,
    };

    let mut writer = hound::WavWriter::create(file_path, spec)?;
    let data = recorded.lock().unwrap();
    for sample in data.iter() {
        writer.write_sample(*sample)?;
    }
    writer.finalize()?;

    println!("Saved WAV recording to {}", file_path);

    Ok(())
}


fn err_fn(err: cpal::StreamError) {
    eprintln!("Stream error: {}", err);
}
