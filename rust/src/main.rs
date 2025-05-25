
use clap::{Parser, Subcommand};
mod sound;

#[derive(Parser)]
#[command(name = "sound_tool")]
#[command(about = "Audio Tool: get info, play, record", long_about = None)]
struct Cli {
    #[command(subcommand)]
    command: Commands,
}

#[derive(Subcommand)]
enum Commands {
    GetAudioInfo,
    Play {
        #[arg(short, long)]
        file: String,
    },
    Record {
        #[arg(short, long)]
        file: String,
        #[arg(short, long, default_value_t = 5)]
        seconds: u32,
    },
}

fn main() -> anyhow::Result<()> {
    let cli = Cli::parse();

    match &cli.command {
        Commands::GetAudioInfo => {
            sound::get_audio_info()?;
        }
        Commands::Play { file } => {
            sound::play_audio(file)?;
        }
        Commands::Record { file, seconds } => {
            sound::record_audio(file, *seconds)?;
        }
    }

    Ok(())
}
