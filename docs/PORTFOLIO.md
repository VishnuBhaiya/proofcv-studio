# ProofCV portfolio overview

## Problem and approach

Turn a reviewed candidate profile into job-specific CVs and an approved portfolio website while keeping generated claims tied to confirmed evidence. A bounded Gemini agent coordinates profile operations and MiniLM retrieval; Python validates references and stores revisioned SQLite workspaces.

## Contributions

- Vishnu Bhaiya: original CV-builder project and the Portfolio Studio extension, including multimodal evidence review, website generation, project tours and recruiter-facing approved snapshots.
- Tirth: Interview Coach module, as credited in the team README and source.
- Supplied fictional profiles, jobs, recordings and other dependencies retain their stated provenance. Avery's example project list is not a claim that Avery is a real person or the author of SolarVision.

## Run and verify

Use the README's Python-only setup and launchers. A server-side Gemini key is needed for live agent responses; offline tests use mocked provider responses. `av` is a direct audio-decoding dependency and is listed explicitly in requirements.

Run `python -m unittest discover -v`, `pnpm run build` and `pnpm run test:portfolio` in an isolated checkout. The publication check results are recorded in VALIDATION.md. An offline pass is not a new live Gemini, Whisper or Piper evaluation.

## Public release scope

Tracked source, labelled examples and production frontend builds are included. Personal CVs, uploaded documents, runtime databases, model caches and `.env` files are excluded. A credential scan of reachable Git history was run before the visibility change. Each user supplies their own provider credentials.

The owner application and local recruiter service have different responsibilities. Running on localhost does not make the service available to recruiters on the internet. Public GitHub access exposes the source, not a hosted backend.
