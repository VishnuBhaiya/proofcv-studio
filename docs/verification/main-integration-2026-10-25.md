# Combined main integration — 25 October 2026

Base: `998aff72cb90e9bb55995a1da40ab27a69ebb872` from GitHub main. Tirth's
Interview Coach setup, skill check, adaptive plan, spoken answers and existing
evaluation/data files are preserved. The only Interview Coach implementation
change closes SQLite connections after transactions, fixing Windows file locks.

Portfolio Studio is integrated through the common workspace/sidebar and API.
It includes the existing island simulator, project-specific 3D environments,
reviewed media, guided voice tours, static exports and approved-source AI guide.
The optional shared demo loader imports only the fictional story fixture and
supplied SolarVision recording; it refuses to overwrite custom portfolios.

Validation:

- `python -m unittest discover -v`: 315 tests passed before the final independent
  combined-module regression was added; that HTTP regression also passed.
- All 11 frontend test scripts: 245 checks passed.
- TypeScript project check, owner Vite build and standalone portfolio Vite build passed.
- Chrome: both modules opened from the sidebar using the same Avery workspace.
- Preview: four island destinations, SolarVision project world, full-width final
  project and six video chapters were present. Video decoded at 1280×720,
  duration 207.83 seconds, readyState 4, playing without a media error.
- Review used a fresh isolated local database. No private workspaces or keys are
  committed. No external hosting was activated.

These are offline/provider-mocked checks. Actual Gemini responses depend on a
valid local key and provider availability. Piper and Whisper first-run model
downloads were not exercised; browser narration remains the supported fallback.
