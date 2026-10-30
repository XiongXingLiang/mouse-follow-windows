# Performance update — 2026-10-30

Changes:
- Observe the white target directly before running background/shape analysis. Keep frame history for the later fade. Do not clip its top half during the initial countdown.
- Estimate sparse background alignment on a half-size pyramid and map the affine back to original coordinates. Dense target optical flow retains the original MEDIUM preset and iteration counts; tested lower-quality variants were rejected.
- Evaluate dense background-model residuals only inside the target search plus a blur/prediction margin. Noise regression still samples the whole background.
- Reuse template spectra, a shared input transform, sliding-window energy and coordinate grids across all 36 shape templates. Keep the full rotation and scale bank.
- Cache end-caption templates and match at half size, including tests for pixel phase and scale.
- Capture only the game ROI between full-monitor presence checks; keep negative monitor origins supported. No buffered old screenshots.
- Raise the loop ceiling from 22 to 60 updates/second; actual rates depend on computation. The UI and log report measured rates.

Local Mac replay of the second recording, every second source frame (498 processed frames): roughly 91 ms before and 40 ms after per-frame capture-free processing. Transparent geometry frames still take roughly 62 ms; the overall average includes the faster white phase. This is not a claim of 60 FPS or a Windows benchmark. No real Windows pointer movement or labeled tracking accuracy was measured here. Replays of both recordings and synthetic geometric/safety checks were used to assess regressions; there are still ambiguous target frames and no guarantee against loss.

Reproduce with a local recording (not included in this repository):

```sh
PYTHONPATH=. python docs/benchmark_tracking.py /path/to/video.mov --output /path/to/report.json
# A recording without game chrome can use --crop left top width height.
```

Video rendering additionally needs the developer-only `imageio-ffmpeg` package. Source-time video playback displays spatial tracking results and must not be interpreted as real-time mouse throughput.

For Windows testing, use the new performance-edition executable, select the correct monitor or game ROI, and report status-bar FPS and processing milliseconds. Logs are in `%LOCALAPPDATA%\MouseFollower\app.log`. Preview mode, license checks, explicit arming, Esc, F8 and confidence gating remain enforced.
