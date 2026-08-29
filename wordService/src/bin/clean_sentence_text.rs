use anyhow::{Context, Result, bail};
use chrono::Utc;
use n2_word_service_rust::repository::clean_sentence_text_for_tts;
use rusqlite::{Connection, params};
use std::env;
use std::fs;
use std::path::{Path, PathBuf};

fn main() -> Result<()> {
    let options = Options::from_env()?;
    if options.apply {
        backup_database(&options.db_path)?;
    }

    let conn = Connection::open(&options.db_path)
        .with_context(|| format!("open SQLite database {}", options.db_path.display()))?;
    conn.execute_batch("PRAGMA foreign_keys = ON;")?;

    let mut rows = load_examples(&conn)?;
    let mut changed = 0usize;
    let mut emptied = 0usize;
    let mut cleared_generated_audio = 0usize;

    for row in &mut rows {
        row.cleaned = clean_sentence_text_for_tts(&row.text);
        if row.cleaned == row.text {
            continue;
        }
        if row.cleaned.is_empty() {
            emptied += 1;
            if options.apply {
                conn.execute(
                    "DELETE FROM entry_examples WHERE entry_id = ? AND position = ?",
                    params![row.entry_id, row.position],
                )?;
            }
            continue;
        }

        changed += 1;
        if changed <= options.preview_limit {
            println!(
                "{}:{}\n  old: {}\n  new: {}",
                row.entry_id, row.position, row.text, row.cleaned
            );
        }

        let clear_generated_audio = row
            .audio_clip
            .as_deref()
            .is_some_and(|path| path.starts_with("clips/generated_sentences/edge_tts/"));
        if clear_generated_audio {
            cleared_generated_audio += 1;
        }

        if options.apply {
            conn.execute(
                "UPDATE entry_examples SET text = ?, audio_clip = CASE WHEN ? THEN NULL ELSE audio_clip END
                 WHERE entry_id = ? AND position = ?",
                params![
                    &row.cleaned,
                    clear_generated_audio,
                    row.entry_id,
                    row.position
                ],
            )?;
        }
    }

    if options.apply {
        reindex_examples(&conn)?;
        conn.execute(
            "UPDATE entries
             SET sentence = (
               SELECT text FROM entry_examples
               WHERE entry_examples.entry_id = entries.entry_id
                 AND (entry_examples.kind = 'main_sentence' OR entry_examples.position = 0)
               ORDER BY CASE WHEN entry_examples.kind = 'main_sentence' THEN 0 ELSE 1 END,
                        entry_examples.position
               LIMIT 1
             )
             WHERE EXISTS (
               SELECT 1 FROM entry_examples
               WHERE entry_examples.entry_id = entries.entry_id
                 AND (entry_examples.kind = 'main_sentence' OR entry_examples.position = 0)
             )",
            [],
        )?;
    }

    println!(
        "{} rows would change; {} marker-only rows {} deleted; {} generated audio links {} cleared",
        changed,
        emptied,
        if options.apply { "were" } else { "would be" },
        cleared_generated_audio,
        if options.apply { "were" } else { "would be" }
    );
    if !options.apply {
        println!("Preview only. Rerun with --apply to update SQLite.");
    }

    Ok(())
}

#[derive(Debug)]
struct Options {
    db_path: PathBuf,
    apply: bool,
    preview_limit: usize,
}

impl Options {
    fn from_env() -> Result<Self> {
        let mut db_path = PathBuf::from("data/n2vocab.sqlite");
        let mut apply = false;
        let mut preview_limit = 20usize;
        let mut args = env::args().skip(1);

        while let Some(arg) = args.next() {
            match arg.as_str() {
                "--apply" => apply = true,
                "--db" => {
                    let Some(value) = args.next() else {
                        bail!("--db requires a path");
                    };
                    db_path = PathBuf::from(value);
                }
                "--preview-limit" => {
                    let Some(value) = args.next() else {
                        bail!("--preview-limit requires a number");
                    };
                    preview_limit = value.parse().context("parse --preview-limit")?;
                }
                "--help" | "-h" => {
                    print_help();
                    std::process::exit(0);
                }
                other => bail!("unknown argument: {other}"),
            }
        }

        Ok(Self {
            db_path,
            apply,
            preview_limit,
        })
    }
}

#[derive(Debug)]
struct ExampleRow {
    entry_id: i64,
    position: i64,
    text: String,
    audio_clip: Option<String>,
    cleaned: String,
}

fn load_examples(conn: &Connection) -> Result<Vec<ExampleRow>> {
    let mut statement = conn.prepare(
        "SELECT entry_id, position, text, audio_clip
         FROM entry_examples
         ORDER BY entry_id, position",
    )?;
    let rows = statement.query_map([], |row| {
        Ok(ExampleRow {
            entry_id: row.get(0)?,
            position: row.get(1)?,
            text: row.get(2)?,
            audio_clip: row.get(3)?,
            cleaned: String::new(),
        })
    })?;

    let mut examples = Vec::new();
    for row in rows {
        examples.push(row?);
    }
    Ok(examples)
}

fn reindex_examples(conn: &Connection) -> Result<()> {
    let entry_ids = {
        let mut statement =
            conn.prepare("SELECT DISTINCT entry_id FROM entry_examples ORDER BY entry_id")?;
        let rows = statement.query_map([], |row| row.get::<_, i64>(0))?;
        let mut values = Vec::new();
        for row in rows {
            values.push(row?);
        }
        values
    };

    for entry_id in entry_ids {
        let positions = {
            let mut statement = conn.prepare(
                "SELECT position FROM entry_examples WHERE entry_id = ? ORDER BY position",
            )?;
            let rows = statement.query_map([entry_id], |row| row.get::<_, i64>(0))?;
            let mut values = Vec::new();
            for row in rows {
                values.push(row?);
            }
            values
        };

        for old_position in &positions {
            conn.execute(
                "UPDATE entry_examples SET position = ? WHERE entry_id = ? AND position = ?",
                params![old_position + 10_000, entry_id, old_position],
            )?;
        }
        for (new_position, old_position) in positions.iter().enumerate() {
            conn.execute(
                "UPDATE entry_examples SET position = ? WHERE entry_id = ? AND position = ?",
                params![new_position as i64, entry_id, old_position + 10_000],
            )?;
        }
    }

    Ok(())
}

fn backup_database(db_path: &Path) -> Result<()> {
    let timestamp = Utc::now().format("%Y%m%d_%H%M%S");
    let file_name = db_path
        .file_name()
        .and_then(|name| name.to_str())
        .context("database path should have a file name")?;
    let backup_path = db_path.with_file_name(format!("{file_name}.backup_{timestamp}"));
    fs::copy(db_path, &backup_path).with_context(|| {
        format!(
            "copy SQLite backup from {} to {}",
            db_path.display(),
            backup_path.display()
        )
    })?;
    println!("Backup: {}", backup_path.display());
    Ok(())
}

fn print_help() {
    println!(
        "Clean entry_examples.text into plain learner sentences.\n\
         \n\
         Usage:\n\
           cargo run --bin clean_sentence_text -- [--db data/n2vocab.sqlite] [--apply]\n\
         \n\
         Without --apply this prints a preview only. With --apply it creates a\n\
         timestamped SQLite backup, updates entry_examples.text, deletes\n\
         marker-only rows, reindexes positions per entry, syncs entries.sentence\n\
         from the main-sentence example row, and clears stale generated-audio\n\
         links for rows whose text changed."
    );
}
