# N2 Vocabulary Android shell

This Capacitor app is a thin Android shell around the hosted WordService. Its
production `server.url` is `https://words.kashunli.com/`, so the web app's
relative `/api` and `/audio` requests use that same origin.

## Local release APK

From the repository root, run the frontend verification/build first so
`wordService/static/react-rail` contains the current committed web assets:

```powershell
Set-Location wordService\frontend
pnpm install --frozen-lockfile
pnpm check

Set-Location ..\mobile
pnpm install --frozen-lockfile
pnpm sync

Set-Location android
.\gradlew.bat clean assembleRelease --console=plain
```

The APK is written to
`android/app/build/outputs/apk/release/app-release.apk` relative to this
directory. The release workflow runs the same synchronization and Gradle build,
then uploads a tag-named APK and its SHA-256 checksum to the GitHub Release.

The Android project uses `keystore.properties` when that gitignored file is
available. Without it, `assembleRelease` uses the debug signing key, which is
appropriate for direct testing but not for a production app whose signing
identity must remain stable across upgrades.
