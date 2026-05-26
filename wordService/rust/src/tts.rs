use crate::config::TtsConfig;
use anyhow::{Context, Result, anyhow};
use edge_tts_rust::{Boundary, EdgeTtsClient, SpeakOptions};
use std::sync::mpsc;
use std::thread;
use tokio::runtime::Runtime;

/// Public handle for sentence synthesis.
///
/// Internally this is just a channel sender. Cloning `TtsService` does not clone
/// the Edge client or create more workers; every clone still feeds the same
/// single FIFO queue.
#[derive(Clone)]
pub struct TtsService {
    sender: mpsc::Sender<TtsJob>,
}

/// One unit of work for the TTS worker.
///
/// The reply channel is created per request so the caller can block until its
/// own audio bytes are ready while the shared queue stays serialized.
struct TtsJob {
    text: String,
    reply: mpsc::Sender<Result<Vec<u8>, String>>,
}

/// The worker owns plain strings instead of borrowing from `AppConfig` because
/// it lives on a background thread for the lifetime of the server.
#[derive(Clone)]
struct TtsWorkerConfig {
    voice: String,
    rate: String,
    pitch: String,
}

impl TtsService {
    pub fn new(config: &TtsConfig) -> Result<Self> {
        // edge-tts-rust needs a Tokio runtime. This app otherwise uses a small
        // synchronous HTTP server, so we create one runtime dedicated to TTS.
        let runtime = Runtime::new().context("create Tokio runtime for Edge TTS")?;
        let _runtime_guard = runtime.enter();
        let client = EdgeTtsClient::builder()
            .ws_pool_size(1)
            .build()
            .context("create Edge TTS client")?;
        drop(_runtime_guard);
        let worker_config = TtsWorkerConfig {
            voice: config.voice.clone(),
            rate: config.rate.clone(),
            pitch: config.pitch.clone(),
        };
        let (sender, receiver) = mpsc::channel::<TtsJob>();
        // The Microsoft/Edge endpoint should not be called in parallel. HTTP
        // request threads enqueue work here, and this one worker calls the
        // remote TTS API strictly one sentence at a time.
        thread::spawn(move || run_tts_worker(receiver, runtime, client, worker_config));
        Ok(Self { sender })
    }

    pub fn synthesize_sentence(&self, text: &str) -> Result<Vec<u8>> {
        // Standard-library channels are enough here: request threads are
        // synchronous, and the project explicitly wants one remote call at a
        // time rather than a fully async fan-out.
        let (reply, result) = mpsc::channel();
        self.sender
            .send(TtsJob {
                text: text.to_string(),
                reply,
            })
            .context("enqueue Edge TTS job")?;
        result
            .recv()
            .context("wait for Edge TTS worker")?
            .map_err(|message| anyhow!(message))
    }
}

fn run_tts_worker(
    receiver: mpsc::Receiver<TtsJob>,
    runtime: Runtime,
    client: EdgeTtsClient,
    config: TtsWorkerConfig,
) {
    for job in receiver {
        // A per-job reply channel lets each request wait for its own audio while
        // the shared receiver preserves FIFO ordering for the remote API calls.
        let result = synthesize_on_worker(&runtime, &client, &config, job.text);
        let _ = job.reply.send(result.map_err(|error| error.to_string()));
    }
}

fn synthesize_on_worker(
    runtime: &Runtime,
    client: &EdgeTtsClient,
    config: &TtsWorkerConfig,
    text: String,
) -> Result<Vec<u8>> {
    // SpeakOptions is rebuilt for every sentence because it is small and keeps
    // each job independent of future configuration changes.
    let options = SpeakOptions {
        voice: config.voice.clone(),
        rate: config.rate.clone(),
        volume: "+0%".to_string(),
        pitch: config.pitch.clone(),
        boundary: Boundary::Sentence,
    };
    let client = client.clone();
    let result = runtime
        .block_on(async move { client.synthesize(text, options).await })
        .context("synthesize sentence with Microsoft Edge TTS")?;
    Ok(result.audio)
}
