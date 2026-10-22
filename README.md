# ProofCV Studio — connected app

React/TypeScript with a Python/Gemini runtime agent, SQLite workspaces, MiniLM
retrieval across nine supplied jobs, confirmed-source CV generation and PDF export.

## Team repository — Assignment 3 baseline

This repository starts from the final Assignment 1 CV builder. Its application
source, supplied datasets and production frontend were compared with the working
app before import. Assignment 3 portfolio features are not implemented yet.

Clone this repository into your own folder. On Windows, follow the setup and start
commands below. Each teammate must create their own `.env` from `.env.example` and
use their own authorised Gemini API key. The template keeps the existing primary
model and fallback order; actual availability depends on the provider account.
Never commit `.env`, personal CVs, uploaded resumes or `runtime/` databases.

For development, create a feature branch and open a pull request into `main`.
See [CONTRIBUTING.md](CONTRIBUTING.md) for the collaboration and verification steps.
The checked-in `dist/` is intentional so a fresh clone can run without Node.js.
Frontend changes must also rebuild and update `dist/` before merging.

Repository import verification (22 October 2026): all 61 offline Python unit tests
passed on the clean team checkout. These tests mock Gemini; this check did not
make live provider calls. No Assignment 1 private workspace data was imported.

## Run the connected app on this computer

```powershell
powershell -ExecutionPolicy Bypass -File .\start-proofcv.ps1
```

Open http://127.0.0.1:8000. The launcher uses only the `.venv` contained in this
project, so ProofCV Studio has no dependency on an older sibling project. Port 8000
must be available.

## Tutor quick start (Node.js is not required)

The verified `dist/` production frontend is intentionally included as a reviewed
runtime artifact, not a temporary build folder. From this folder, the simplest
one-time setup is:

```powershell
powershell -ExecutionPolicy Bypass -File .\setup-proofcv.ps1
```

The setup script rejects unsupported Python versions and accepts only Python 3.12
or 3.13 before creating the virtual environment.

The script performs these Python-only steps (shown for reproducibility):

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Open `.env` and paste the tutor's key only after `GEMINI_API_KEY=`. The primary model
and ordered fallbacks are already configured. Never use a `VITE_` credential prefix.
Then start the app:

```powershell
powershell -ExecutionPolicy Bypass -File .\start-proofcv.ps1
```

Open http://127.0.0.1:8000. On macOS/Linux use `.venv/bin/python` and run
`.venv/bin/python -m server.http`. Provider availability and quota depend on the
key's account; no silent demo fallback occurs.

MiniLM loads from the local cache first; first-time use requires internet to download
`sentence-transformers/all-MiniLM-L6-v2`. There is no lexical fallback in the live app.
Node.js 22 and pnpm 11.19.0 are optional. Frontend developers can reproduce the locked
dependency graph with `pnpm install --frozen-lockfile`, then
`pnpm run build` or `pnpm run dev`; Vite proxies `/api` during development.

## Live workflow

1. Create one workspace per person. Introduce yourself, answer follow-ups, or enter
   facts directly. Chat shares the supplied information with Gemini.
2. Review every fact, check acceptance and press Confirm profile. Use `None` for no
   experience or achievements. Edits invalidate confirmation and retrieval.
3. Ask the agent to find jobs. Inspect three IDs, cosine scores, excerpts and full
   descriptions. Similarity does not establish hiring eligibility.
4. Select a role. Gemini chooses existing source facts, skills and ordering; Python
   validates references and inserts exact confirmed text into the CV.
5. Edit, then Validate & save. New summary wording must first become a profile
   summary fact and be explicitly reconfirmed. This intentionally favours traceability
   over unrestricted AI paraphrasing. Accept emphasis, dismiss order, or undo.
6. Save versions, compare jobs and download PDF. Changing jobs preserves confirmed
   facts. A draft using an older profile cannot be exported.

## Tests and evidence

```sh
python -m unittest discover -v
python -m server.check_connection
python -m server.live_journeys
```

Unit tests are offline with mocked provider responses. The last two commands make
real API calls and consume quota. Live tests use the five supplied synthetic profiles
and save predictions before retrieval. Read each actual status under
`runtime/evaluation/`; a single passed journey is not five passes.

Current repository verification: 61 offline tests passed on 22 October 2026.
The Assignment 1 submission separately contains historical five-profile live
journeys and deterministic integration evidence. Those assessment artifacts,
personal sample PDFs and runtime databases are not included in this source-only
team repository, and no new live journeys were run during the repository import.
Post-acceptance follow-up questions use model `final_answer` Actions validated
against `missing_fields`, not fixed service text. Run the live commands above to
produce your own local evidence. They consume quota; passing offline tests does
not guarantee future provider availability.

## Architecture and limitations

```text
React → loopback JSON API → application service
                           ├─ SQLite workspace + confirmed revision
                           ├─ Gemini action → Python tool → observation loop
                           ├─ MiniLM → cosine top three of nine jobs
                           └─ validated source selection → CV → ReportLab PDF
```

Source map: agent.py = bounded loop; prompts.py = runtime rules; store.py = persistence;
retrieval.py = embeddings; cv.py = source validation; pdf.py = pagination;
http.py = transport; src/LiveStudio.tsx = connected screens.

This is a local single-operator app, not authenticated accounts. Anyone with access
to it can switch workspaces. SQLite holds unencrypted personal data; use synthetic
profiles for assessment testing. Only dist files are web-served, never .env or runtime.
Matched/missing checks are conservative text checks, not exhaustive qualification
assessment. Inspect full job requirements, especially seniority and experience.
Confirmation is user review, not independent verification. Provider failures retain
submitted messages and completed tool writes. Exclude .env, runtime databases,
node_modules, model weights, caches and personal data from any eventual submission.
The supplied `dist/` is the intentional, verified production runtime frontend;
transient build caches remain excluded.
No billing changes, report writing, deployment or submission is automated.

API reference: https://ai.google.dev/api/generate-content
