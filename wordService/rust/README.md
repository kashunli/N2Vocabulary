# N2 wordService Rust

This folder is a side-by-side Rust version of the Python backend in
`../server.py`. It uses the same SQLite database, the same static frontend, the
same clip folder, and the same environment variables.

The code is intentionally split into a few small files so it is easier to learn
from:

- `src/config.rs` reads runtime paths and mirrors Python `AppConfig`.
- `src/repository.rs` is the SQLite boundary and contains most business logic.
- `src/http.rs` is the tiny HTTP server and route table.
- `src/models.rs` contains JSON response structs.
- `tests/repository_tests.rs` mirrors the Python repository tests with a
  temporary SQLite database.

## Run

From this folder:

```powershell
cargo run
```

Then open:

```text
http://127.0.0.1:8767/
```

If the Python backend is already using port `8767`, run the Rust backend on a
neighboring port:

```powershell
$env:N2_WORD_SERVICE_PORT = "8768"
cargo run
```

## Validate

```powershell
cargo test
```

The Rust tests create a temporary SQLite DB and do not touch the real study DB.

