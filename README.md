# fman-media-file-explorer

Media file explorer plugin for [fman](https://fman.io/).

## Connected phones

The plugin exposes paired Media File Explorer phones in fman under `phone://`. Use the command palette and choose **Show phones**, or type “phones”, “android” or “media file explorer”. Open a phone to browse its shared folders, view file sizes and modification dates, and copy files or folders between the phone and the PC. You can also create, rename and permanently delete phone files and folders.

The Media File Explorer desktop companion must be running with the local-client approval and `/v1/peers` support from todo #12029. A phone must be paired with that companion. On first use, the companion asks you to allow fman to see connected phones; choosing Always allow saves that approval. The plugin pins the companion and each phone's TLS certificate fingerprint.

The fman settings file `Media File Explorer Settings.json` stores the companion port (default `47610`), a stable client ID, the client approval token and the pinned companion certificate fingerprint. Do not share the token or settings file.

Limits: phone trash is unavailable, so delete is permanent; phone-to-phone copy is unsupported; transfers copy whole files. Recursive folder transfers create folders before copying their contents.

Run the unit tests with `tools\\run_tests.bat` and the TLS integration tests with `tools\\run_integration_tests.bat`. Both scripts use the fman's `FMAN_SRC` environment variable and the repository root on `PYTHONPATH`.
