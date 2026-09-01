use super::{WordRepository, collect_rows};
use crate::models::FlaggedAudioExportResponse;
use anyhow::{Context, Result, bail};
use rusqlite::params;
use std::fs;
use std::io::Write;
use std::path::{Path, PathBuf};
use tempfile::TempDir;

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

impl WordRepository {
    pub fn export_unit_flagged_audio(
        &self,
        unit_number: i64,
    ) -> Result<FlaggedAudioExportResponse> {
        if unit_number <= 0 {
            bail!("unit must be a positive integer");
        }
        let _guard = self
            .write_lock
            .lock()
            .expect("audio export lock should not be poisoned");
        let items = self.list_flagged_audio_export_items(unit_number)?;
        if items.is_empty() {
            bail!("no flagged words in this unit");
        }

        let mut missing = Vec::new();
        for item in &items {
            if self
                .resolve_audio_path(&item.word_clip)
                .is_none_or(|path| !path.is_file())
            {
                missing.push(format!("word #{} word audio", item.source_index));
            }
            if self
                .resolve_audio_path(&item.sentence_clip)
                .is_none_or(|path| !path.is_file())
            {
                missing.push(format!("word #{} sentence audio", item.source_index));
            }
        }
        if !missing.is_empty() {
            bail!("missing audio clips: {}", missing.join(", "));
        }

        let export_dir = self.clips_dir.join("exports").join("flagged_units");
        fs::create_dir_all(&export_dir)?;
        let file_name = format!("unit{:02}_flagged_review.mp3", unit_number);
        let final_path = export_dir.join(&file_name);
        let temp_dir = TempDir::with_prefix("n2_flagged_audio_export_")?;
        let temp_output = temp_dir.path().join(&file_name);
        let one_second = export_dir.join("_silence_1s.mp3");
        let two_seconds = export_dir.join("_silence_2s.mp3");
        ensure_silence_clip(&one_second, 1)?;
        ensure_silence_clip(&two_seconds, 2)?;
        let concat_list = temp_dir.path().join("concat.txt");
        write_flagged_audio_concat_list(&concat_list, &items, &one_second, &two_seconds, |clip| {
            self.resolve_audio_path(clip)
                .context("clip path should resolve")
        })?;

        run_ffmpeg([
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            concat_list
                .to_str()
                .context("concat list path must be valid UTF-8 for ffmpeg")?,
            "-codec:a",
            "libmp3lame",
            "-q:a",
            "4",
            temp_output
                .to_str()
                .context("temporary export path must be valid UTF-8 for ffmpeg")?,
        ])?;
        fs::copy(&temp_output, &final_path)?;

        let relative = format!("clips/exports/flagged_units/{file_name}");
        self.record_audio_id(&relative)?;
        let audio_url = self
            .audio_url(Some(&relative))
            .context("exported audio path should be servable")?;
        Ok(FlaggedAudioExportResponse {
            ok: true,
            unit: unit_number,
            word_count: items.len(),
            audio_url,
            file_name,
        })
    }

    fn list_flagged_audio_export_items(
        &self,
        unit_number: i64,
    ) -> Result<Vec<FlaggedAudioExportItem>> {
        let conn = self.connect()?;
        let mut statement = conn.prepare(
            r#"
            SELECT
              be.source_index,
              COALESCE(be.word_clip, v.word_clip) AS word_clip,
              COALESCE(ex.audio_clip, be.sentence_clip) AS sentence_clip
            FROM book_entries be
            JOIN vocabulary_items v ON v.item_id = be.item_id
            JOIN item_marks m ON m.item_id = be.item_id
            LEFT JOIN item_examples ex
              ON ex.item_id = be.item_id
             AND (ex.kind = 'main_sentence' OR ex.position = 0)
            WHERE be.book_code = ?
              AND be.unit_number = ?
              AND COALESCE(m.flagged, 0) = 1
            ORDER BY be.position, be.source_index
            "#,
        )?;
        let rows = statement.query_map(params![&self.book_code, unit_number], |row| {
            Ok(FlaggedAudioExportItem {
                source_index: row.get(0)?,
                word_clip: row.get::<_, Option<String>>(1)?.unwrap_or_default(),
                sentence_clip: row.get::<_, Option<String>>(2)?.unwrap_or_default(),
            })
        })?;
        collect_rows(rows)
    }
}
