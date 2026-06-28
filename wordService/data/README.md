# wordService Data

Place the canonical service SQLite database here:

```text
wordService/data/n2vocab.sqlite
```

The Rust service, sentence-cleaner helper, audio path repair helper, and Anki
builders use this path by default. `N2_WORD_SERVICE_DB` can still override the
service path for temporary experiments.

Do not keep a second active copy under `output/`; that makes vocabulary-content
bugs harder to trace.
