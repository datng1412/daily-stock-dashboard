# Desktop packaging

The [Electron main process](../apps/dsa-desktop/main.js) starts the local FastAPI backend and waits for `/api/health` before loading the built React UI. The [preload bridge](../apps/dsa-desktop/preload.js) exposes desktop capabilities to the renderer.

## Develop and package on Windows

From the repository root, use [the developer launcher](../scripts/run-desktop.ps1) for local development and [the build launcher](../scripts/build-all.ps1) for packaging.

```powershell
./scripts/run-desktop.ps1
./scripts/build-all.ps1
```

The build compiles the web bundle, installs Python requirements, packages the backend with PyInstaller, and packages Electron. Build web assets before Electron and run the desktop `npm test` suite. Use a Windows runner with symlink support for the NSIS path. The [backend build script](../scripts/build-backend.ps1) owns hidden imports and packaging options.

## Releases and updater

The [desktop release workflow](../.github/workflows/desktop-release.yml) builds from a version tag or a manual dispatch with `release_tag`. It publishes the Windows NSIS installer, Windows portable ZIP, and Intel and Apple Silicon macOS DMGs. The Windows installer is per-user and requires a writable location. System-protected directories are blocked. For portable distribution, distribute the entire unpacked directory.

Validate the Windows update artifacts on a Windows release runner. Compare the tag, installer version and file name, `latest.yml` version and file entries, and blockmap. Check that the artifacts are attached and downloadable. The [artifact verification script](../scripts/verify-desktop-updater-artifacts.ps1) checks the Windows release path.

Settings receives the desktop version from Electron's `app.getVersion()` through preload. Installed Windows builds can download an update and apply it after the user confirms restart. The app stops the bundled backend, backs up runtime files, and silently reinstalls to the existing directory, including paths containing spaces. Verify that `.env`, the database and its WAL/SHM files, and desktop logs survive the update. Investigate failed restoration using the update backup and `logs/desktop.log`. Portable Windows, macOS DMG, and dev builds use the release download path.

## First launch

Install or extract the package for your operating system and architecture from the repository release assets. Set up a supported analysis model using the [LLM guide](LLM_CONFIG_GUIDE_EN.md), set the inherited `STOCK_LIST`, and optionally configure a news source. Save Settings before starting an analysis. Export a backup of the saved settings before reinstalling or migrating.

## Local configuration and recovery

Windows stores `.env`, `data/`, and `logs/` beside the executable. Packaged macOS stores them in Electron's user-data directory. First launch can seed `.env` from `.env.example`. Old macOS app-bundle files are migrated only while accessible and only where the destination does not already exist.

Configuration export includes saved values only. Import merges keys and reloads applicable settings, and prompts before replacing a local draft. The desktop bridge supports backup directly. Standalone Web access requires enabled administrator authentication and an authenticated session.

For a blank window, check `static/index.html`. For a backend startup failure, inspect `logs/desktop.log` and the chosen listener. For missing packaged modules, check the backend build script. Restore a saved configuration through Settings if an old macOS app bundle has already been replaced.
