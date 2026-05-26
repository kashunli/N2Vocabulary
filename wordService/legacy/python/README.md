# Legacy Python wordService

This folder contains the archived Python implementation of `wordService`.

It is kept only for historical reference. The active backend, API behavior,
SQLite write rules, lazy sentence-audio generation, and tests now live in the
Rust crate at `../../rust/`.

Future maintenance should update Rust first. If this legacy code disagrees with
Rust, trust Rust.
