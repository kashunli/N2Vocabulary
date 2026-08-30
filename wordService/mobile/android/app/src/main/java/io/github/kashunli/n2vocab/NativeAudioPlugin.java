package io.github.kashunli.n2vocab;

import android.content.Context;
import android.content.Intent;
import android.util.Log;
import androidx.core.content.ContextCompat;
import com.getcapacitor.JSArray;
import com.getcapacitor.JSObject;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;

/**
 * A deliberately small bridge: React retains learner UI state, while the
 * Android service owns bytes, media controls, and the background-safe queue.
 */
@CapacitorPlugin(name = "NativeAudio")
public final class NativeAudioPlugin extends Plugin {
    private static final String TAG = "N2NativePlayback";
    private final NativePlaybackService.PlaybackListener listener = this::publishState;

    @Override
    public void load() {
        NativePlaybackService.addPlaybackListener(listener);
    }

    @Override
    protected void handleOnDestroy() {
        NativePlaybackService.removePlaybackListener(listener);
    }

    @PluginMethod
    public void playQueue(PluginCall call) {
        JSArray items = call.getArray("items");
        if (items == null || items.length() == 0) {
            call.reject("items must contain at least one audio item");
            return;
        }
        Intent intent = commandIntent(NativePlaybackService.ACTION_PLAY_QUEUE);
        intent.putExtra(NativePlaybackService.EXTRA_QUEUE_JSON, items.toString());
        if (dispatchPlaybackCommand(intent, true, call)) call.resolve();
    }

    @PluginMethod
    public void pause(PluginCall call) {
        if (dispatchPlaybackCommand(commandIntent(NativePlaybackService.ACTION_PAUSE), false, call)) call.resolve();
    }

    @PluginMethod
    public void resume(PluginCall call) {
        if (dispatchPlaybackCommand(commandIntent(NativePlaybackService.ACTION_RESUME), true, call)) call.resolve();
    }

    @PluginMethod
    public void seek(PluginCall call) {
        long positionMs = Math.max(0L, call.getLong("positionMs", 0L));
        Intent intent = commandIntent(NativePlaybackService.ACTION_SEEK);
        intent.putExtra(NativePlaybackService.EXTRA_POSITION_MS, positionMs);
        if (dispatchPlaybackCommand(intent, false, call)) call.resolve();
    }

    @PluginMethod
    public void stop(PluginCall call) {
        if (dispatchPlaybackCommand(commandIntent(NativePlaybackService.ACTION_STOP), false, call)) call.resolve();
    }

    @PluginMethod
    public void getState(PluginCall call) {
        call.resolve(toJs(NativePlaybackService.currentSnapshot()));
    }

    private Intent commandIntent(String action) {
        Context context = getContext();
        return new Intent(context, NativePlaybackService.class).setAction(action);
    }

    private void startPlaybackService(Intent intent) {
        // Only a new service needs the foreground-service start exemption. If
        // playback is already alive, startService sends the next queue command
        // without asking Android to promote a second foreground service while
        // the app is backgrounded.
        if (NativePlaybackService.isRunning()) {
            getContext().startService(intent);
        } else {
            ContextCompat.startForegroundService(getContext(), intent);
        }
    }

    private boolean dispatchPlaybackCommand(Intent intent, boolean allowForegroundStart, PluginCall call) {
        try {
            if (allowForegroundStart) startPlaybackService(intent);
            else getContext().startService(intent);
            return true;
        } catch (RuntimeException error) {
            // Android can still reject a new foreground-service start during a
            // background/Activity transition. Reject the bridge call so React
            // can show a recoverable playback error instead of killing the app.
            Log.w(TAG, "Could not dispatch native playback command.", error);
            call.reject("Native playback service is unavailable.");
            return false;
        }
    }

    private void publishState(NativePlaybackService.PlaybackSnapshot snapshot) {
        // Position snapshots are transient. Retaining every one while the
        // WebView is backgrounded would replay an unbounded backlog after an
        // unlock, which can overwhelm the page and look like an app exit.
        notifyListeners("stateChange", toJs(snapshot), false);
    }

    private JSObject toJs(NativePlaybackService.PlaybackSnapshot snapshot) {
        JSObject result = new JSObject();
        result.put("status", snapshot.status);
        result.put("itemId", snapshot.itemId);
        result.put("url", snapshot.url);
        result.put("queueIndex", snapshot.queueIndex);
        result.put("queueLength", snapshot.queueLength);
        result.put("positionMs", snapshot.positionMs);
        result.put("durationMs", snapshot.durationMs);
        if (snapshot.error != null) result.put("error", snapshot.error);
        return result;
    }
}
