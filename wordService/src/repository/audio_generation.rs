use super::{WordRepository, clean_sentence_text_for_tts, now_utc};
use crate::models::AudioGenerationResponse;
use crate::repository::paths::{
    generated_sentence_clip_path, generated_word_clip_path, normalize_generated_audio_dir,
};
use crate::repository::text::word_text_for_tts;
use anyhow::{Context, Result, bail};
use rusqlite::{Connection, OptionalExtension, params};
use std::fs;
use std::path::Path;

impl WordRepository {
    pub fn ensure_example_audio<F>(
        &self,
        entry_id: i64,
        position: i64,
        generated_dir: &str,
        synthesize: F,
    ) -> Result<AudioGenerationResponse>
    where
        F: FnOnce(&str) -> Result<Vec<u8>>,
    {
        let _guard = self
            .write_lock
            .lock()
            .expect("audio write lock should not be poisoned");
        let conn = self.connect()?;
        let row: Option<(i64, String, Option<String>)> = conn
            .query_row(
                r#"
                SELECT be.item_id, ex.text, ex.audio_clip
                FROM book_entries be
                JOIN item_examples ex ON ex.item_id = be.item_id
                WHERE be.book_code = ? AND be.entry_id = ? AND ex.position = ?
                "#,
                params![&self.book_code, entry_id, position],
                |row| Ok((row.get(0)?, row.get(1)?, row.get(2)?)),
            )
            .optional()?;
        drop(conn);

        let Some((item_id, text, current_clip)) = row else {
            bail!("unknown example");
        };
        let sentence = clean_sentence_text_for_tts(&text);
        if sentence.is_empty() {
            bail!("empty sentence");
        }
        if let Some(current) = current_clip.as_deref()
            && let Some(existing_path) = self.resolve_audio_path(current)
            && existing_path.exists()
            && let Some(audio_url) = self.audio_url(Some(current))
        {
            return Ok(AudioGenerationResponse {
                ok: true,
                audio_url,
                generated: false,
            });
        }

        let generated_rel_path = generated_sentence_clip_path(generated_dir, entry_id, position)?;
        let final_path = self
            .resolve_audio_path(&generated_rel_path)
            .context("generated audio path should resolve inside clips")?;
        let audio_bytes = synthesize(&sentence)?;
        if audio_bytes.is_empty() {
            bail!("TTS returned no audio bytes");
        }
        write_file_atomically(&final_path, &audio_bytes)?;
        self.forget_audio_version(&final_path);
        self.update_example_audio_clip(item_id, position, &generated_rel_path, generated_dir)?;
        let audio_url = self
            .audio_url(Some(&generated_rel_path))
            .context("generated audio path should be servable")?;
        Ok(AudioGenerationResponse {
            ok: true,
            audio_url,
            generated: true,
        })
    }

    pub fn ensure_word_audio<F>(
        &self,
        entry_id: i64,
        generated_dir: &str,
        synthesize: F,
    ) -> Result<AudioGenerationResponse>
    where
        F: FnOnce(&str) -> Result<Vec<u8>>,
    {
        let _guard = self
            .write_lock
            .lock()
            .expect("audio write lock should not be poisoned");
        let conn = self.connect()?;
        let row: Option<(i64, String, Option<String>, Option<String>)> = conn
            .query_row(
                r#"
                SELECT be.entry_id, v.kanji, v.reading,
                       COALESCE(be.word_clip, v.word_clip) AS word_clip
                FROM book_entries be
                JOIN vocabulary_items v ON v.item_id = be.item_id
                WHERE be.book_code = ? AND be.entry_id = ?
                "#,
                params![&self.book_code, entry_id],
                |row| Ok((row.get(0)?, row.get(1)?, row.get(2)?, row.get(3)?)),
            )
            .optional()?;
        drop(conn);

        let Some((entry_id, word, reading, current_clip)) = row else {
            bail!("unknown entry");
        };
        let word = word_text_for_tts(&word, reading.as_deref());
        if word.is_empty() {
            bail!("empty word");
        }
        if let Some(current) = current_clip.as_deref()
            && let Some(existing_path) = self.resolve_audio_path(current)
            && existing_path.exists()
            && let Some(audio_url) = self.audio_url(Some(current))
        {
            return Ok(AudioGenerationResponse {
                ok: true,
                audio_url,
                generated: false,
            });
        }

        let generated_rel_path = generated_word_clip_path(generated_dir, entry_id)?;
        let final_path = self
            .resolve_audio_path(&generated_rel_path)
            .context("generated word audio path should resolve inside clips")?;
        let audio_bytes = synthesize(&word)?;
        if audio_bytes.is_empty() {
            bail!("TTS returned no audio bytes");
        }
        write_file_atomically(&final_path, &audio_bytes)?;
        self.forget_audio_version(&final_path);
        self.update_word_audio_clip(entry_id, &generated_rel_path, generated_dir)?;
        let audio_url = self
            .audio_url(Some(&generated_rel_path))
            .context("generated word audio path should be servable")?;
        Ok(AudioGenerationResponse {
            ok: true,
            audio_url,
            generated: true,
        })
    }

    fn update_example_audio_clip(
        &self,
        item_id: i64,
        position: i64,
        clip_path: &str,
        generated_dir: &str,
    ) -> Result<()> {
        let conn = Connection::open(&self.db_path)?;
        ensure_settings_table(&conn)?;
        let changed = conn.execute(
            "UPDATE item_examples SET audio_clip = ? WHERE item_id = ? AND position = ?",
            params![clip_path, item_id, position],
        )?;
        if changed != 1 {
            bail!("unknown example");
        }
        store_generated_dir(&conn, "generated_sentence_audio_dir", generated_dir)
    }

    fn update_word_audio_clip(
        &self,
        entry_id: i64,
        clip_path: &str,
        generated_dir: &str,
    ) -> Result<()> {
        let conn = Connection::open(&self.db_path)?;
        ensure_settings_table(&conn)?;
        let changed = conn.execute(
            "UPDATE book_entries SET word_clip = ? WHERE book_code = ? AND entry_id = ?",
            params![clip_path, &self.book_code, entry_id],
        )?;
        if changed != 1 {
            bail!("unknown entry");
        }
        store_generated_dir(&conn, "generated_word_audio_dir", generated_dir)
    }
}

fn ensure_settings_table(conn: &Connection) -> Result<()> {
    conn.execute_batch(
        r#"
        PRAGMA foreign_keys = ON;
        PRAGMA busy_timeout = 5000;
        CREATE TABLE IF NOT EXISTS word_service_settings (
          key TEXT PRIMARY KEY,
          value TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );
        "#,
    )?;
    Ok(())
}

fn store_generated_dir(conn: &Connection, key: &str, generated_dir: &str) -> Result<()> {
    conn.execute(
        r#"
        INSERT INTO word_service_settings(key, value, updated_at)
        VALUES(?, ?, ?)
        ON CONFLICT(key) DO UPDATE SET
          value = excluded.value,
          updated_at = excluded.updated_at
        "#,
        params![
            key,
            normalize_generated_audio_dir(generated_dir)?,
            now_utc()
        ],
    )?;
    Ok(())
}

fn write_file_atomically(path: &Path, data: &[u8]) -> Result<()> {
    let parent = path
        .parent()
        .context("generated audio path should have a parent directory")?;
    fs::create_dir_all(parent)?;
    let tmp_path = path.with_file_name(format!(
        ".{}.tmp",
        path.file_name()
            .and_then(|name| name.to_str())
            .unwrap_or("generated_audio.mp3")
    ));
    if tmp_path.exists() {
        fs::remove_file(&tmp_path)?;
    }
    fs::write(&tmp_path, data)?;
    if path.exists() {
        fs::remove_file(path)?;
    }
    fs::rename(&tmp_path, path)?;
    Ok(())
}
