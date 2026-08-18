# WordService content cache and reloading content

## Why

The study wall was behaving like a client-server service instead of a local
desktop app. The worst offender: on every card play it fetched
`GET /api/entries/<id>` even though the card pane only used two fields from
that response — `sentence` (already present on the list entry) and
`explanation_md` (the one field the list endpoint deliberately omitted). Unit
and filter switches also re-downloaded the identical `state=all` queue and
re-filtered it client-side.

Goal: treat published book content as static. Load each book once, cache it
locally, and reserve network requests for learner state (marks, review
schedule, playback history) and actual content changes.

## What changed

**Server (`wordService/src/`)**

- `repository.rs` — `serialize_entry` now ships `explanation_md` in list
  payloads too, so the card pane renders without a per-entry request. Detail
  gating remains only for the full-ordered `examples` and `source_notes`.
- `models.rs` + `repository.rs` — `/api/summary` now returns a
  `content_revision` field: a SHA-256 hex fingerprint of the content database,
  computed lazily once per process and cached in a shared
  `Arc<Mutex<Option<String>>>` so every per-request repository clone sees the
  same value.

**Client (`wordService/frontend/src/`)**

- `features/study/contentCache.mjs` (new) — per-book localStorage cache under
  `n2-word-service:content:v1:<book>`, storing `{revision, summary, units,
  allEntries}`. LRU-capped at 3 books via an index key. Injectable storage for
  tests.
- `features/study/useStudyCatalog.ts` — on book select, fetch only the cheap
  `/api/summary`; if its `content_revision` matches the cached book, load
  `units` + `allEntries` from localStorage, otherwise fetch them once and
  rewrite the cache. The old per-play `getEntry`/`detail` state is gone.
- `features/study/useStudyEntries.ts` — the visible queue is now a client-side
  derivation of the cached book list (filtered by unit + status), so unit and
  filter switches never hit the network.
- `StudyWallView.tsx` / `useStudyActions.ts` / `App.tsx` — render the pane
  from `activeEntry` (which now carries `explanation_md`) and drop the separate
  `detail` copy.

## How content reload works today

The revision is the only invalidation signal, and it flows like this:

```
content DB file ──SHA-256──▶ content_revision (in /api/summary)
                                        │
   client compares on load / book select
        ├── match  ──▶ load units + allEntries from localStorage (no refetch)
        └── differ ──▶ fetch units + allEntries once, rewrite the cache
```

Because the server computes the hash **once per process**, a server-side
content change becomes visible on the next service **restart**: the new process
hashes the changed file, `/api/summary` returns a different `content_revision`,
and the next page load or book switch makes the client refetch. This already
matches the repo's offline-edit workflow (`migrate_local_databases` and the
importers all say "stop the service" first).

## How to enable reload after a server-side content change

### Option A — restart the service (no code change, already works)

Edit the content DB (import, fix, migrate) while the service is stopped, then
restart it and reload the browser tab. The fresh process serves a new
`content_revision`; the client detects the mismatch and refetches once. This is
the current, supported path.

### Option B — live reload without a restart (requires a small change)

If content can change while the service is running and you want the open page
to pick it up, change the revision so it stops being cached forever:

**Server — stat-then-hash.** Keep a cached `(revision, file mtime, file size)`
triple instead of a bare revision. On each `content_revision()` call, stat the
file (microseconds); if mtime/size still match the cached triple, return the
cached hash; otherwise re-read + re-hash (~100 ms for the 35 MB DB) and update
the cache. The field type changes from `Arc<Mutex<Option<String>>>` to an
`Arc<Mutex<Option<ContentRevisionCache>>>`:

```rust
#[derive(Clone)]
struct ContentRevisionCache {
    revision: String,
    stat: Option<(Option<std::time::SystemTime>, u64)>, // (mtime, len)
}

fn content_revision(&self) -> String {
    let mut guard = self.content_revision.lock().expect("content revision lock");
    let stat = fs::metadata(&self.db_path)
        .ok()
        .map(|meta| (meta.modified().ok(), meta.len()));
    if let Some(cached) = guard.as_ref() {
        if cached.stat == stat {
            return cached.revision.clone();
        }
    }
    let revision = fs::read(&self.db_path)
        .map(|bytes| {
            let digest = Sha256::digest(&bytes);
            digest.iter().map(|byte| format!("{:02x}", byte)).collect()
        })
        .unwrap_or_default();
    *guard = Some(ContentRevisionCache { revision: revision.clone(), stat });
    revision
}
```

**Client — revalidate while the tab is open.** The revision is already checked
on mount and on book select, so a manual reload or a book switch picks the
change up automatically. For an automatic refresh of the open book, poll the
summary while the tab is visible and force the load effect to re-run when the
revision changes (clear the cached book or bump a `contentRevision`-derived
trigger the book-select effect depends on):

```ts
useEffect(() => {
  const interval = window.setInterval(() => {
    if (document.hidden) return;
    getSummary(selectedBook)
      .then((fresh) => {
        if (fresh.content_revision === readContentBook(selectedBook)?.revision) return;
        clearContentBook(selectedBook);      // or set a stale-trigger state
        setReloadTick((tick) => tick + 1);   // re-runs the book-select effect
      })
      .catch(() => {});
  }, 30_000);
  return () => window.clearInterval(interval);
}, [selectedBook]);
```

### Caveats for Option B

- **Spurious revisions.** Any write to the content DB bumps mtime and therefore
  the revision — including the legacy `/api/marks` writer, which copies the
  whole DB to a temp file and copies it back. The active study walls never
  write the content DB (learner state lives in `users.sqlite`/localStorage), so
  in practice only offline imports/migrations touch it; a stray write just costs
  one extra refetch.
- **Hash cost.** Re-hashing happens only when the file changes; the common
  summary path stays a cheap stat.

## Files touched

- `wordService/src/models.rs`, `wordService/src/repository.rs`
- `wordService/tests/repository_tests.rs` — revision stability + change tests
- `wordService/frontend/src/types.ts`
- `wordService/frontend/src/features/study/contentCache.mjs` (new) + `contentCache.test.mjs` (new)
- `wordService/frontend/src/features/study/useStudyCatalog.ts`, `useStudyEntries.ts`, `StudyWallView.tsx`, `useStudyActions.ts`
- `wordService/frontend/src/App.tsx`

## Verification

- Backend: `cargo fmt --check` and `cargo test` (29 tests, including
  `content_revision_is_stable_across_handles_and_ensure_ready` and
  `content_revision_changes_for_a_fresh_process_after_a_content_edit`).
- Frontend: `node --test` (30 tests, incl. new `contentCache.test.mjs`),
  `tsc --noEmit`, `vite build`.
- Browser: 21+ cards auto-played with zero `/api/entries/<id>` requests;
  section/filter switches made zero `/api/entries` requests; a reload with a
  valid cache skipped `units`/`entries` (summary-only validation); a manually
  staleness-forced cache triggered exactly one refetch; the card pane rendered
  sentence + explanation from the list payload, and mark toggling still worked.
