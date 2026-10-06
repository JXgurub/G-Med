# G-MED Liza for Android

This Android WebView app loads the G-MED website in the same secure origin, so the
patient can sign in normally and open **Liza yordamchi** from the site navigation.
The signed-in session is stored by Android System WebView and survives app restarts.

While a YouTube track is playing, the Liza page notifies the native app. Android
then routes communication audio to the built-in loudspeaker and keeps the display
awake. The microphone remains available for Liza voice commands. When playback
pauses, ends, or the player closes, Android's normal audio route is restored.
Microphone access is requested by Android only when Liza first needs it.

## Build

Requirements: JDK 17 and Android SDK Platform 34 with Build Tools 34.0.0.

From this directory on Windows:

```powershell
.\gradlew.bat assembleDebug
```

Install a locally built debug APK on a connected Android device:

```powershell
.\gradlew.bat installDebug
```

The default start URL is `https://g-med.uz/`. Override it for a trusted test
deployment with `-PwebAppUrl=https://your-test-host/`. Only HTTPS pages hosted on
`g-med.uz` can access the native audio bridge.

The embedded YouTube player remains subject to YouTube's availability,
advertising, device volume, and playback policies. The Android app can select the
phone loudspeaker while Liza is active, but does not bypass YouTube restrictions
or provide background playback.
