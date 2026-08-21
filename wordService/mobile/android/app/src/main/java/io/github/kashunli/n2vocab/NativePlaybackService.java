package io.github.kashunli.n2vocab;

import android.app.PendingIntent;
import android.content.Intent;
import android.net.Uri;
import android.os.Handler;
import android.os.Looper;
import androidx.annotation.Nullable;
import androidx.media3.common.MediaItem;
import androidx.media3.common.MediaMetadata;
import androidx.media3.common.Player;
import androidx.media3.common.util.UnstableApi;
import androidx.media3.database.StandaloneDatabaseProvider;
import androidx.media3.datasource.DefaultHttpDataSource;
import androidx.media3.datasource.cache.CacheDataSource;
import androidx.media3.datasource.cache.LeastRecentlyUsedCacheEvictor;
import androidx.media3.datasource.cache.SimpleCache;
import androidx.media3.exoplayer.ExoPlayer;
import androidx.media3.exoplayer.source.DefaultMediaSourceFactory;
import androidx.media3.session.MediaSession;
import androidx.media3.session.MediaSessionService;
import java.io.File;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.Set;
import java.util.concurrent.CopyOnWriteArraySet;
import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

/**
 * The native owner of learner audio.  Capacitor/React may create a queue, but
 * it must not be responsible for advancing it: WebView timers are suspended
 * after a locked screen, whereas this foreground media service remains alive.
 *
 * <p>The cache is deliberately app-private and bounded.  It contains only
 * downloaded media bytes and is never exposed through shared storage, so it
 * needs no storage permission and can be evicted safely under storage pressure.</p>
 */
@UnstableApi
public final class NativePlaybackService extends MediaSessionService {
    public static final String ACTION_PLAY_QUEUE = "io.github.kashunli.n2vocab.PLAY_QUEUE";
    public static final String ACTION_PAUSE = "io.github.kashunli.n2vocab.PAUSE";
    public static final String ACTION_RESUME = "io.github.kashunli.n2vocab.RESUME";
    public static final String ACTION_SEEK = "io.github.kashunli.n2vocab.SEEK";
    public static final String ACTION_STOP = "io.github.kashunli.n2vocab.STOP";
    public static final String EXTRA_QUEUE_JSON = "queue_json";
    public static final String EXTRA_POSITION_MS = "position_ms";

    // Keep up to 512 MiB of downloaded media for offline replay.  This is an LRU
    // *cache*, not user-visible storage, so Android may still evict it under
    // storage pressure.
    private static final long CACHE_MAX_BYTES = 512L * 1024L * 1024L;
    private static final Set<PlaybackListener> LISTENERS = new CopyOnWriteArraySet<>();
    private static volatile PlaybackSnapshot lastSnapshot = PlaybackSnapshot.idle();

    private final Handler handler = new Handler(Looper.getMainLooper());
    private final Runnable progressRunnable = this::publishProgress;
    private final Runnable nextItemRunnable = this::playNextItem;
    private final List<QueueItem> queue = new ArrayList<>();
    private long queueGeneration;
    private int queueIndex = -1;
    private long pendingGapEndsAtMs;
    private long pendingGapRemainingMs;
    private boolean waitingForGap;
    private ExoPlayer player;
    private MediaSession mediaSession;
    private SimpleCache cache;
    private StandaloneDatabaseProvider databaseProvider;

    public interface PlaybackListener {
        void onPlaybackState(PlaybackSnapshot snapshot);
    }

    public static void addPlaybackListener(PlaybackListener listener) {
        LISTENERS.add(listener);
    }

    public static void removePlaybackListener(PlaybackListener listener) {
        LISTENERS.remove(listener);
    }

    public static PlaybackSnapshot currentSnapshot() {
        return lastSnapshot;
    }

    @Override
    public void onCreate() {
        super.onCreate();
        databaseProvider = new StandaloneDatabaseProvider(this);
        File cacheDirectory = new File(getCacheDir(), "native-audio-v1");
        cache = new SimpleCache(
            cacheDirectory,
            new LeastRecentlyUsedCacheEvictor(CACHE_MAX_BYTES),
            databaseProvider
        );
        CacheDataSource.Factory cacheDataSourceFactory = new CacheDataSource.Factory()
            .setCache(cache)
            .setUpstreamDataSourceFactory(new DefaultHttpDataSource.Factory())
            .setFlags(CacheDataSource.FLAG_IGNORE_CACHE_ON_ERROR);
        player = new ExoPlayer.Builder(this)
            .setMediaSourceFactory(new DefaultMediaSourceFactory(cacheDataSourceFactory))
            .build();
        player.addListener(new Player.Listener() {
            @Override
            public void onIsPlayingChanged(boolean isPlaying) {
                if (isPlaying) {
                    startProgressUpdates();
                } else {
                    stopProgressUpdates();
                }
                publishSnapshot(isPlaying ? "playing" : (waitingForGap ? "gap" : "paused"));
            }

            @Override
            public void onPlaybackStateChanged(int state) {
                if (state == Player.STATE_ENDED && !waitingForGap) {
                    finishCurrentItem();
                } else if (state == Player.STATE_READY) {
                    publishSnapshot(player.isPlaying() ? "playing" : "ready");
                }
            }

            @Override
            public void onPlayerError(androidx.media3.common.PlaybackException error) {
                publishSnapshot("error", error.getMessage());
            }
        });

        Intent launchIntent = new Intent(this, MainActivity.class)
            .setFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP | Intent.FLAG_ACTIVITY_SINGLE_TOP);
        PendingIntent sessionActivity = PendingIntent.getActivity(
            this,
            0,
            launchIntent,
            PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE
        );
        mediaSession = new MediaSession.Builder(this, player)
            .setSessionActivity(sessionActivity)
            .build();
        publishSnapshot("idle");
    }

    @Override
    public int onStartCommand(@Nullable Intent intent, int flags, int startId) {
        if (intent != null && intent.getAction() != null) {
            handleCommand(intent);
        }
        return START_NOT_STICKY;
    }

    @Nullable
    @Override
    public MediaSession onGetSession(MediaSession.ControllerInfo controllerInfo) {
        return mediaSession;
    }

    @Override
    public void onDestroy() {
        handler.removeCallbacksAndMessages(null);
        if (mediaSession != null) {
            mediaSession.release();
            mediaSession = null;
        }
        if (player != null) {
            player.release();
            player = null;
        }
        if (cache != null) {
            cache.release();
            cache = null;
        }
        if (databaseProvider != null) {
            databaseProvider.close();
            databaseProvider = null;
        }
        super.onDestroy();
    }

    private void handleCommand(Intent intent) {
        String action = intent.getAction();
        if (ACTION_PLAY_QUEUE.equals(action)) {
            replaceQueue(intent.getStringExtra(EXTRA_QUEUE_JSON));
        } else if (ACTION_PAUSE.equals(action)) {
            pausePlayback();
        } else if (ACTION_RESUME.equals(action)) {
            resumePlayback();
        } else if (ACTION_SEEK.equals(action)) {
            seekTo(intent.getLongExtra(EXTRA_POSITION_MS, 0L));
        } else if (ACTION_STOP.equals(action)) {
            stopPlayback();
        }
    }

    private void replaceQueue(@Nullable String queueJson) {
        List<QueueItem> nextQueue;
        try {
            nextQueue = parseQueue(queueJson);
        } catch (JSONException error) {
            publishSnapshot("error", "Invalid native playback queue.");
            return;
        }
        queueGeneration += 1;
        handler.removeCallbacks(nextItemRunnable);
        waitingForGap = false;
        pendingGapEndsAtMs = 0L;
        pendingGapRemainingMs = 0L;
        queue.clear();
        queue.addAll(nextQueue);
        queueIndex = 0;
        if (queue.isEmpty()) {
            stopPlayback();
            return;
        }
        playCurrentItem();
    }

    private List<QueueItem> parseQueue(@Nullable String queueJson) throws JSONException {
        if (queueJson == null) {
            return Collections.emptyList();
        }
        JSONArray serialized = new JSONArray(queueJson);
        List<QueueItem> parsed = new ArrayList<>();
        for (int index = 0; index < serialized.length(); index += 1) {
            JSONObject value = serialized.getJSONObject(index);
            String url = value.optString("url", "").trim();
            if (url.isEmpty()) continue;
            String id = value.optString("id", "item-" + index);
            String title = value.optString("title", "N2 Vocabulary");
            long pauseAfterMs = Math.max(0L, value.optLong("pauseAfterMs", 0L));
            parsed.add(new QueueItem(id, title, url, pauseAfterMs));
        }
        return parsed;
    }

    private void playCurrentItem() {
        if (queueIndex < 0 || queueIndex >= queue.size() || player == null) {
            finishQueue();
            return;
        }
        QueueItem item = queue.get(queueIndex);
        waitingForGap = false;
        pendingGapEndsAtMs = 0L;
        pendingGapRemainingMs = 0L;
        MediaItem mediaItem = new MediaItem.Builder()
            .setMediaId(item.id)
            .setUri(Uri.parse(item.url))
            .setMediaMetadata(new MediaMetadata.Builder().setTitle(item.title).build())
            .build();
        player.setMediaItem(mediaItem);
        player.prepare();
        player.play();
        publishSnapshot("playing");
    }

    private void finishCurrentItem() {
        if (queueIndex < 0 || queueIndex >= queue.size()) {
            finishQueue();
            return;
        }
        QueueItem current = queue.get(queueIndex);
        long generation = queueGeneration;
        pendingGapRemainingMs = current.pauseAfterMs;
        if (pendingGapRemainingMs <= 0L) {
            queueIndex += 1;
            playCurrentItem();
            return;
        }
        waitingForGap = true;
        pendingGapEndsAtMs = android.os.SystemClock.elapsedRealtime() + pendingGapRemainingMs;
        publishSnapshot("gap");
        handler.removeCallbacks(nextItemRunnable);
        handler.postDelayed(() -> {
            if (generation != queueGeneration || !waitingForGap) return;
            queueIndex += 1;
            playCurrentItem();
        }, pendingGapRemainingMs);
    }

    private void playNextItem() {
        if (!waitingForGap) return;
        queueIndex += 1;
        playCurrentItem();
    }

    private void pausePlayback() {
        if (waitingForGap) {
            pendingGapRemainingMs = Math.max(
                0L,
                pendingGapEndsAtMs - android.os.SystemClock.elapsedRealtime()
            );
            handler.removeCallbacksAndMessages(null);
            waitingForGap = false;
            publishSnapshot("gap-paused");
            return;
        }
        if (player != null) player.pause();
        publishSnapshot("paused");
    }

    private void resumePlayback() {
        if (pendingGapRemainingMs > 0L && !waitingForGap) {
            waitingForGap = true;
            pendingGapEndsAtMs = android.os.SystemClock.elapsedRealtime() + pendingGapRemainingMs;
            publishSnapshot("gap");
            handler.postDelayed(nextItemRunnable, pendingGapRemainingMs);
            return;
        }
        if (player != null) player.play();
        publishSnapshot("playing");
    }

    private void seekTo(long positionMs) {
        if (player == null || waitingForGap) return;
        player.seekTo(Math.max(0L, positionMs));
        publishSnapshot(player.isPlaying() ? "playing" : "paused");
    }

    private void stopPlayback() {
        queueGeneration += 1;
        handler.removeCallbacksAndMessages(null);
        waitingForGap = false;
        pendingGapEndsAtMs = 0L;
        pendingGapRemainingMs = 0L;
        queue.clear();
        queueIndex = -1;
        if (player != null) {
            player.stop();
            player.clearMediaItems();
        }
        publishSnapshot("idle");
        stopSelf();
    }

    private void finishQueue() {
        queue.clear();
        queueIndex = -1;
        waitingForGap = false;
        pendingGapEndsAtMs = 0L;
        pendingGapRemainingMs = 0L;
        publishSnapshot("completed");
        stopSelf();
    }

    private void startProgressUpdates() {
        handler.removeCallbacks(progressRunnable);
        handler.post(progressRunnable);
    }

    private void stopProgressUpdates() {
        handler.removeCallbacks(progressRunnable);
    }

    private void publishProgress() {
        if (player == null || !player.isPlaying()) return;
        publishSnapshot("playing");
        handler.postDelayed(progressRunnable, 500L);
    }

    private void publishSnapshot(String status) {
        publishSnapshot(status, null);
    }

    private void publishSnapshot(String status, @Nullable String error) {
        QueueItem item = queueIndex >= 0 && queueIndex < queue.size() ? queue.get(queueIndex) : null;
        long positionMs = player == null ? 0L : player.getCurrentPosition();
        long durationMs = player == null ? 0L : Math.max(0L, player.getDuration());
        PlaybackSnapshot snapshot = new PlaybackSnapshot(
            status,
            item == null ? "" : item.id,
            item == null ? "" : item.url,
            queueIndex,
            queue.size(),
            positionMs,
            durationMs,
            error
        );
        lastSnapshot = snapshot;
        for (PlaybackListener listener : LISTENERS) listener.onPlaybackState(snapshot);
    }

    private static final class QueueItem {
        final String id;
        final String title;
        final String url;
        final long pauseAfterMs;

        QueueItem(String id, String title, String url, long pauseAfterMs) {
            this.id = id;
            this.title = title;
            this.url = url;
            this.pauseAfterMs = pauseAfterMs;
        }
    }

    public static final class PlaybackSnapshot {
        public final String status;
        public final String itemId;
        public final String url;
        public final int queueIndex;
        public final int queueLength;
        public final long positionMs;
        public final long durationMs;
        @Nullable public final String error;

        PlaybackSnapshot(
            String status,
            String itemId,
            String url,
            int queueIndex,
            int queueLength,
            long positionMs,
            long durationMs,
            @Nullable String error
        ) {
            this.status = status;
            this.itemId = itemId;
            this.url = url;
            this.queueIndex = queueIndex;
            this.queueLength = queueLength;
            this.positionMs = positionMs;
            this.durationMs = durationMs;
            this.error = error;
        }

        static PlaybackSnapshot idle() {
            return new PlaybackSnapshot("idle", "", "", -1, 0, 0L, 0L, null);
        }
    }
}
