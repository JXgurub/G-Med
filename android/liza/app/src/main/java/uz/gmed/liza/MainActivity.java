package uz.gmed.liza;

import android.Manifest;
import android.app.Activity;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.media.AudioDeviceInfo;
import android.media.AudioManager;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.util.Log;
import android.view.WindowManager;
import android.webkit.PermissionRequest;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;

import androidx.webkit.JavaScriptReplyProxy;
import androidx.webkit.WebMessageCompat;
import androidx.webkit.WebViewCompat;
import androidx.webkit.WebViewFeature;

import org.json.JSONException;
import org.json.JSONObject;

import java.util.Arrays;
import java.util.HashSet;
import java.util.Set;

public final class MainActivity extends Activity {
    private static final String TAG = "GMedLiza";
    private static final int RECORD_AUDIO_REQUEST = 1001;
    private static final String APP_HOST = "g-med.uz";
    private static final String LAST_URL_KEY = "last_url";

    private final Set<String> trustedFrameHosts = new HashSet<>(Arrays.asList(
            "youtube.com",
            "www.youtube.com",
            "youtube-nocookie.com",
            "www.youtube-nocookie.com",
            "googlevideo.com",
            "www.googlevideo.com",
            "ytimg.com",
            "www.ytimg.com"
    ));

    private WebView webView;
    private AudioManager audioManager;
    private PermissionRequest pendingAudioPermission;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        audioManager = (AudioManager) getSystemService(AUDIO_SERVICE);
        webView = new WebView(this);
        webView.setBackgroundColor(0xFF080D14);
        setContentView(webView);

        WebSettings settings = webView.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setMediaPlaybackRequiresUserGesture(false);
        settings.setAllowFileAccess(false);
        settings.setAllowContentAccess(false);
        settings.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
        settings.setSafeBrowsingEnabled(true);

        webView.setWebViewClient(new LizaWebViewClient());
        webView.setWebChromeClient(new LizaWebChromeClient());
        installAudioBridge();

        String savedUrl = getPreferences(MODE_PRIVATE).getString(LAST_URL_KEY, null);
        webView.loadUrl(isTrustedAppUrl(savedUrl) ? savedUrl : BuildConfig.WEB_APP_URL);
    }

    private void installAudioBridge() {
        if (!WebViewFeature.isFeatureSupported(WebViewFeature.WEB_MESSAGE_LISTENER)) {
            Log.w(TAG, "This Android System WebView does not support the secure audio bridge.");
            return;
        }

        WebViewCompat.addWebMessageListener(
                webView,
                "LizaNativeAudio",
                new HashSet<>(Arrays.asList("https://" + APP_HOST, "https://www." + APP_HOST)),
                (view, message, sourceOrigin, isMainFrame, replyProxy) -> {
                    if (!isMainFrame || !isTrustedAppHost(sourceOrigin.getHost())) return;
                    handleAudioMessage(message, replyProxy);
                }
        );
    }

    private void handleAudioMessage(WebMessageCompat message, JavaScriptReplyProxy replyProxy) {
        try {
            JSONObject payload = new JSONObject(message.getData());
            if (!"playback".equals(payload.optString("action"))) return;
            boolean active = payload.optBoolean("active");
            boolean routed = setPlaybackActive(active);
            replyProxy.postMessage(active ? (routed ? "speaker-on" : "speaker-unavailable") : "speaker-off");
        } catch (JSONException error) {
            Log.w(TAG, "Rejected invalid audio bridge message.", error);
            replyProxy.postMessage("invalid");
        }
    }

    private boolean setPlaybackActive(boolean active) {
        if (active) {
            getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
            return routeToBuiltInSpeaker();
        }
        getWindow().clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        restoreDefaultAudioRoute();
        return true;
    }

    private boolean routeToBuiltInSpeaker() {
        if (audioManager == null) return false;
        try {
            audioManager.setMode(AudioManager.MODE_IN_COMMUNICATION);
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
                AudioDeviceInfo speaker = audioManager.getAvailableCommunicationDevices().stream()
                        .filter(device -> device.getType() == AudioDeviceInfo.TYPE_BUILTIN_SPEAKER)
                        .findFirst()
                        .orElse(null);
                if (speaker != null && audioManager.setCommunicationDevice(speaker)) {
                    Log.i(TAG, "YouTube playback routed to the built-in loudspeaker.");
                    return true;
                }
            }
            audioManager.setSpeakerphoneOn(true);
            Log.i(TAG, "YouTube playback requested on the built-in loudspeaker.");
            return true;
        } catch (RuntimeException error) {
            Log.e(TAG, "Could not route YouTube playback to the built-in loudspeaker.", error);
            return false;
        }
    }

    private void restoreDefaultAudioRoute() {
        if (audioManager == null) return;
        try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
                audioManager.clearCommunicationDevice();
            }
            audioManager.setSpeakerphoneOn(false);
            audioManager.setMode(AudioManager.MODE_NORMAL);
        } catch (RuntimeException error) {
            Log.e(TAG, "Could not restore the default audio route.", error);
        }
    }

    private boolean isTrustedAppUrl(String value) {
        if (value == null) return false;
        Uri uri = Uri.parse(value);
        return "https".equals(uri.getScheme())
                && isTrustedAppHost(uri.getHost())
                && uri.getUserInfo() == null;
    }

    private boolean isTrustedAppHost(String host) {
        return APP_HOST.equals(host) || ("www." + APP_HOST).equals(host);
    }

    private boolean isTrustedFrameHost(String host) {
        return host != null && (trustedFrameHosts.contains(host) || host.endsWith(".youtube.com")
                || host.endsWith(".youtube-nocookie.com") || host.endsWith(".googlevideo.com")
                || host.endsWith(".ytimg.com"));
    }

    private final class LizaWebViewClient extends WebViewClient {
        @Override
        public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
            Uri uri = request.getUrl();
            String host = uri.getHost();
            if (isTrustedAppUrl(uri.toString()) || isTrustedFrameHost(host)) return false;
            if (!request.isForMainFrame()) return true;

            if ("https".equals(uri.getScheme()) && host != null) {
                try {
                    startActivity(new Intent(Intent.ACTION_VIEW, uri));
                } catch (RuntimeException error) {
                    Log.w(TAG, "No application can open external link.", error);
                }
            }
            return true;
        }

        @Override
        public void onPageStarted(WebView view, String url, android.graphics.Bitmap favicon) {
            super.onPageStarted(view, url, favicon);
            if (isTrustedAppUrl(url)) {
                getPreferences(MODE_PRIVATE).edit().putString(LAST_URL_KEY, url).apply();
            } else {
                view.stopLoading();
                view.loadUrl(BuildConfig.WEB_APP_URL);
            }
        }
    }

    private final class LizaWebChromeClient extends WebChromeClient {
        @Override
        public void onPermissionRequest(PermissionRequest request) {
            Uri origin = request.getOrigin();
            String[] requestedResources = request.getResources();
            boolean audioOnly = requestedResources.length == 1
                    && PermissionRequest.RESOURCE_AUDIO_CAPTURE.equals(requestedResources[0]);
            if (!isTrustedAppUrl(origin.toString()) || !audioOnly) {
                request.deny();
                return;
            }

            if (checkSelfPermission(Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED) {
                request.grant(requestedResources);
                return;
            }

            pendingAudioPermission = request;
            requestPermissions(new String[]{Manifest.permission.RECORD_AUDIO}, RECORD_AUDIO_REQUEST);
        }
    }

    @Override
    public void onRequestPermissionsResult(int requestCode, String[] permissions, int[] grantResults) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults);
        if (requestCode != RECORD_AUDIO_REQUEST || pendingAudioPermission == null) return;

        if (grantResults.length > 0 && grantResults[0] == PackageManager.PERMISSION_GRANTED) {
            pendingAudioPermission.grant(new String[]{PermissionRequest.RESOURCE_AUDIO_CAPTURE});
        } else {
            pendingAudioPermission.deny();
        }
        pendingAudioPermission = null;
    }

    @Override
    public void onBackPressed() {
        if (webView != null && webView.canGoBack()) {
            webView.goBack();
            return;
        }
        super.onBackPressed();
    }

    @Override
    protected void onDestroy() {
        if (pendingAudioPermission != null) {
            pendingAudioPermission.deny();
            pendingAudioPermission = null;
        }
        setPlaybackActive(false);
        if (webView != null) {
            webView.stopLoading();
            webView.destroy();
            webView = null;
        }
        super.onDestroy();
    }
}
