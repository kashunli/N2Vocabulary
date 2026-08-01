use anyhow::{Context, Result, bail};
use std::fs;
use std::io::Write;
use std::path::{Path, PathBuf};

/// One flagged word and its sentence audio in the order used by the exported
/// review track. The repository query fills this with database paths; this
/// module owns the ffmpeg-facing representation and file assembly.
#[derive(Debug)]
pub(super) struct FlaggedAudioExportItem {
    pub(super) source_index: i64,
    pub(super) word_clip: String,
    pub(super) sentence_clip: String,
}

pub(super) fn ensure_silence_clip(path: &Path, seconds: u64) -> Result<()> {
    if path.is_file() {
        return Ok(());
    }
    let parent = path
        .parent()
        .context("silence clip path should have a parent directory")?;
    fs::create_dir_all(parent)?;
    run_ffmpeg([
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-f",
        "lavfi",
        "-i",
        "anullsrc=r=44100:cl=mono",
        "-t",
        &seconds.to_string(),
        "-codec:a",
        "libmp3lame",
        "-q:a",
        "9",
        path.to_str()
            .context("silence clip path must be valid UTF-8 for ffmpeg")?,
    ])
}

pub(super) fn write_flagged_audio_concat_list<F>(
    path: &Path,
    items: &[FlaggedAudioExportItem],
    one_second: &Path,
    two_seconds: &Path,
    resolve_clip: F,
) -> Result<()>
where
    F: Fn(&str) -> Result<PathBuf>,
{
    let mut file = fs::File::create(path)?;
    for item in items {
        // ffmpeg's concat demuxer takes one `file 'path'` line per segment.
        // The sequence here is the user-facing study rhythm:
        // word -> 1s silence -> sentence -> 2s silence -> next word.
        writeln!(
            file,
            "file '{}'",
            ffmpeg_concat_path(&resolve_clip(&item.word_clip)?)
        )?;
        writeln!(file, "file '{}'", ffmpeg_concat_path(one_second))?;
        writeln!(
            file,
            "file '{}'",
            ffmpeg_concat_path(&resolve_clip(&item.sentence_clip)?)
        )?;
        writeln!(file, "file '{}'", ffmpeg_concat_path(two_seconds))?;
    }
    Ok(())
}

fn ffmpeg_concat_path(path: &Path) -> String {
    path.to_string_lossy()
        .replace('\\', "/")
        .replace('\'', r"'\''")
}

pub(super) fn run_ffmpeg<I, S>(args: I) -> Result<()>
where
    I: IntoIterator<Item = S>,
    S: AsRef<str>,
{
    let args = args
        .into_iter()
        .map(|arg| arg.as_ref().to_string())
        .collect::<Vec<_>>();
    let output = std::process::Command::new("ffmpeg")
        .args(&args)
        .output()
        .context("run ffmpeg; install ffmpeg or add it to PATH to use audio export")?;
    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr);
        bail!("ffmpeg failed: {}", stderr.trim());
    }
    Ok(())
}
