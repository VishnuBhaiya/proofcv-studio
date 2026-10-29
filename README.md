# ProofCV Studio

An evidence-grounded AI application for building job-specific CVs, publishing reviewed portfolio websites and practising interviews. A React/TypeScript frontend connects to a Python agent runtime, Gemini, semantic job retrieval and revisioned SQLite workspaces.

Vishnu Bhaiya developed the original **CV Builder** and **Portfolio Studio**; **Interview Coach** is credited to teammate Tirth. Fictional demonstration profiles and illustrative project worlds are labelled throughout. See [portfolio scope and validation](docs/PORTFOLIO.md).

React/TypeScript with a Python/Gemini runtime agent, SQLite workspaces, MiniLM
retrieval across nine supplied jobs, confirmed-source CV generation and PDF export.

## Application modules

The confirmed-profile CV builder supports source-grounded generation, job matching,
version comparison and PDF export. Two integrated modules extend that workflow:

- **Interview Coach** (Tirth), under **Versions & comparison** in the sidebar: see
  [Interview Coach](#interview-coach) below.
- **Portfolio Studio** (Vishnu), after **CV studio** with the sparkle icon: a complete
  confirmed-CV website workflow, reviewed media, narrated 3D project tours, portfolio
  exports and an optional local recruiter website with a source-grounded AI guide.
  See [Portfolio Studio](#portfolio-studio) below.

### Shared Avery Morgan demo

New installations include the same detailed fictional Avery Morgan base used in
Vishnu's local demo: education, experience, achievements, 18 listed skills and four
projects—Smart Intersection Object Detection, Warehouse Safety Video Analytics,
Dataset Quality Review Toolkit and **SolarVision**. Both saved role-specific CVs
include all four projects in different priority orders. SolarVision is explicitly
a supplied demonstration case study, **not a claim of Avery's authorship**.
The supplied SolarVision demonstration recording is included under
`examples/portfolio/`, together with a small fictional portfolio fixture. No private
database, API key or personal CV is included.

Startup now preserves existing sample workspaces instead of resetting their
profiles, messages or saved CV history. If your existing Avery still has three
projects, stop your local server, pull the main update, then run:

```powershell
.\.venv\Scripts\python.exe -m server.update_avery_sample --apply
```

On macOS/Linux use `.venv/bin/python -m server.update_avery_sample --apply`.
This adds only SolarVision to the explicitly labelled Avery demo, preserving its
workspace ID, existing edits, messages and saved versions. Review and **Confirm
profile** in **My profile** afterwards; the current CV can then refresh from the
new facts. Previous saved CVs stay as historical snapshots. Conflicting SolarVision
content and pending proposals are not overwritten. Nothing is sent to an AI model.

Clone this repository into your own folder. On Windows, follow the setup and start
commands below. Each teammate must create their own `.env` from `.env.example` and
use their own authorised Gemini API key. The template keeps the existing primary
model and fallback order; actual availability depends on the provider account.
Never commit `.env`, personal CVs, uploaded resumes or `runtime/` databases.

For development, create a feature branch and open a pull request into `main`.
See [CONTRIBUTING.md](CONTRIBUTING.md) for the collaboration and verification steps.
The checked-in `dist/` is intentional so a fresh clone can run without Node.js.
Frontend changes must also rebuild and update `dist/` and `portfolio-runtime/` before merging.

Repository import verification (22 October 2026): all 61 offline Python unit tests
passed on the clean team checkout. These tests mock Gemini; this check did not
make live provider calls. No private workspace data was imported.

Integration verification (25 October 2026): 316 offline Python checks (315 in the
full suite plus the combined-module HTTP regression), 245 frontend checks, and
both production builds passed. Chrome verification confirmed both sidebar modules,
the four-project island and playback of the supplied 1280×720 SolarVision video.
Provider calls and fresh Whisper/Piper model downloads were not part of this run.

The four-project seed matches the working Avery demo profile field-for-field.
Existing-workspace updates, repeat runs, pending proposals and conflicting
SolarVision edits are covered by sample regression tests. Both integrated
modules share the confirmed profile and selected job; their practice records and
portfolio drafts remain separate.

## Run the connected app on this computer

```powershell
powershell -ExecutionPolicy Bypass -File .\start-proofcv.ps1
```

Open http://127.0.0.1:8000. The launcher uses only the `.venv` contained in this
project, so ProofCV Studio has no dependency on an older sibling project. Port 8000
must be available.

## Quick start (Node.js is not required)

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

Open `.env` and paste your own API key only after `GEMINI_API_KEY=`. The primary model
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

## Portfolio Studio

Open **Portfolio Studio** after **CV studio** in the sidebar. It uses the currently
selected workspace's confirmed profile; it does not replace Interview Coach.

1. **Story:** initialise from confirmed facts, request a model proposal if wanted,
   then review and accept or dismiss it. Accepted story proposals continue to media.
2. **Media:** upload a project image or video, inspect its analysis and approve the
   wording and annotations. Choose explicitly which reviewed assets may appear.
3. **Design:** choose Editorial, Technical or Minimal appearance, an abstract guide
   avatar, and contact disclosure settings. Save to continue to preview.
4. **Preview:** the purple floating island opens separate, project-specific 3D
   environments. Laptop touchpad gestures and keyboard controls work directly in
   the scene; fullscreen and a standard text view remain available. The project
   library uses full-width cards for projects 1 and 4, with 2 and 3 side by side.
5. **Approve & export:** review the exact public projection before creating an
   immutable snapshot. Download the static ZIP, or explicitly enable its local
   recruiter version. Editing a draft never silently changes an approved version.

Each project world has a guided tour with optional browser speech, three camera
views and local WebM recording. The 3D scenes are illustrations, not proof that the
projects were deployed. Browser speech depends on installed voices; exported WebM
scene recordings are labelled silent. SolarVision's supplied application video is
a separate native video player with reviewed chapter bookmarks.

### Load the complete shared Avery portfolio demo

After Python setup, stop the app and run this **once**, before initialising Avery's
Portfolio Studio yourself:

```powershell
.\.venv\Scripts\python.exe -m server.prepare_team_demo --apply
powershell -ExecutionPolicy Bypass -File .\start-proofcv.ps1
```

On macOS/Linux use `.venv/bin/python -m server.prepare_team_demo --apply` followed
by `.venv/bin/python -m server.http`. Select **Avery Morgan** and open **Portfolio
Studio**. This loads the labelled four-project demo, its three role views, Technical
theme and supplied SolarVision video. It makes no AI call. It does not approve or
publish a recruiter version. Repeating the helper preserves subsequent edits, and
it refuses to replace a separately created portfolio or a customised profile.

For an older three-project Avery, first run the explicit sample update described
above and reconfirm the profile. Existing custom portfolios can add the recording
through the Media step using `examples/portfolio/solarvision-demo.mp4`.

### Preview, recruiter website and AI guide

The owner preview on port **8000** lets you edit your draft. The recruiter website
on port **8001** displays only a saved, approved snapshot and exposes no profile
editing controls. Start that separate reader when needed:

```powershell
powershell -ExecutionPolicy Bypass -File .\start-reader.ps1
```

On macOS/Linux run `.venv/bin/python -m server.portfolio_reader`. Enable the
approved version inside Portfolio Studio and use its generated website link; old
snapshot URLs continue to show their historical content. Create and enable a new
snapshot when you want later projects or edits to appear for recruiters.

Both the owner preview and the connected recruiter website offer inline questions
once an approved snapshot is enabled. Answers use that approved snapshot's source
text and citations, not unreviewed draft changes. New answers require a working
server-side Gemini key and the local reader. Static ZIP exports keep the reviewed
content and 3D scenes; they cannot run a backend AI model by themselves.

No external hosting is enabled by these commands. `dist/` and
`portfolio-runtime/` are committed production builds, so normal Python-only setup
does not require Node. Frontend contributors should run `pnpm run build` and
`pnpm run test:portfolio` after installing the locked dependencies. Run the combined
Python checks with `.venv/bin/python -m unittest discover -v` (Windows:
`.\.venv\Scripts\python.exe -m unittest discover -v`).

## Interview Coach

Spoken interview practice for the job the user picked from their top matches. Every step
runs on this computer with local models or plain rules. The one exception is optional:
the user can choose **Gemini** for speech-to-text (see below).
Open it from **Interview Coach** in the sidebar after confirming a profile and choosing
a target job.

What it does, in order:

1. **Fit:** links each requirement of the job to the user's confirmed facts (exact
   keywords plus MiniLM similarity) and lists strengths, partial matches and gaps.
   Degrees and years of experience are never auto-judged.
2. **Questions:** picks self-introduction, behavioural, technical and motivation
   questions from a question bank, linked to the job's strengths and gaps.
3. **Spoken answers:** the browser records the answer; local Whisper (faster-whisper)
   transcribes it with word timings. Audio is never stored. The user can pick
   **Accurate** (`small.en`, better with accents) or **Fast** (`base.en`); only installed
   models are offered. When the server has a Gemini key, **Gemini** is also offered (and
   is the default): the recording is sent to Google as a 16 kHz WAV and Gemini writes the
   transcript, while local Whisper still measures pace, pauses and fillers. Gemini runs
   alongside Whisper, retries once on HTTP 503, and if it fails or takes over 35 seconds
   the Whisper transcript is used with a note. Measured: about 19 s per 20-second answer
   on `gemini-3.1-flash-lite`.
4. **Feedback:** pace, pauses, filler words and length; a STAR check for behavioural
   answers from our own trained classifier; key-point coverage for technical answers;
   and a fact check that flags numbers, tools or leadership claims the confirmed profile
   cannot back up.
5. **Corrections:** an example answer built only from confirmed facts, with
   [bracketed prompts] where the profile has no detail; retries are compared with the
   previous attempt.
6. **Self-introduction deck:** six slides with speaker notes from the strongest facts
   for the job, viewable full screen, downloadable as PDF, with a rehearsal mode that
   checks which slides were talked about.
7. **Interview-day cheat sheet:** one A4 page (Reports tab, also as PDF) with the best
   introduction, top three strengths with evidence, the best STAR stories from practice,
   honest answers for the two biggest gaps, questions to ask, and delivery reminders
   taken from the user's own numbers.
8. **Read aloud:** questions, follow-ups and example answers are read by Piper, a local
   neural voice (`en_US-lessac-medium`), with the browser's voice as the fallback.
9. **Countdown plan:** the user enters the interview date and gets a few questions a
   day: never-practised ones first, then weak answers, with strong ones refreshed every
   few days, a full mock interview the day before, and a light warm-up on the day.
   Tasks tick off automatically from practice; today's list stays fixed for the day.

**First run:** after `pip install -r requirements.txt` (which includes `faster-whisper`
and `piper-tts`), the first spoken answer downloads the Whisper `base.en` model (about
148 MB) into the Hugging Face cache, like MiniLM. Later runs work offline. The browser
asks for microphone access the first time.

**Optional models** (the app works without them and never downloads them itself):

```sh
# Accurate recognition: Whisper small.en, about 486 MB, into the Hugging Face cache
python -c "from faster_whisper import WhisperModel; WhisperModel('small.en', compute_type='int8')"
# Natural voice: Piper en_US-lessac-medium, about 63 MB, into runtime/models/piper/
mkdir -p runtime/models/piper && cd runtime/models/piper && \
  for f in en_US-lessac-medium.onnx en_US-lessac-medium.onnx.json; do \
  curl -fLO https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/$f; done
```

To compare the two Whisper models on the recorded evaluation scripts, run
`python -m server.interview.evaluate --model base.en` and `--model small.en`.

**Data it keeps:** each attempt's transcript and scores in `runtime/interview.sqlite3`
(never committed, like the other `runtime/` databases). Removing a workspace does not
yet remove its practice history.

**Files:**

| Path | Purpose |
| --- | --- |
| `server/interview/routes.py` | `/api/interview/...` endpoints (one hook in `server/http.py`) |
| `server/interview/fit.py` | Requirement-to-fact matching |
| `server/interview/questions.py` | Question picker |
| `server/interview/speech.py` | Whisper transcription and delivery checks |
| `server/interview/star.py`, `train_star.py` | STAR classifier and its training script |
| `server/interview/content.py`, `factcheck.py` | Key-point coverage and fact check |
| `server/interview/model_answer.py`, `attempts.py` | Example answers and attempt tracking |
| `server/interview/slides.py` | Self-introduction deck and PDF |
| `server/interview/cheatsheet.py` | Interview-day cheat sheet and PDF |
| `server/interview/voice.py` | Piper read-aloud voice |
| `server/interview/gemini_speech.py` | Optional Gemini speech-to-text |
| `server/interview/plan.py` | Countdown practice plan |
| `server/interview/data/` | Requirement map, question bank, STAR data, model and evaluation |
| `src/interview/` | Interview Coach screens |

**STAR classifier:** multinomial logistic regression on MiniLM sentence embeddings plus
sentence position, trained on 374 labelled sentences from 60 example answers. Splits
are by answer; 12 answers are held out. Held-out macro-F1 is 0.929 (cross-validation
0.855 ± 0.04), against 0.706 for keyword rules and 0.755 without the position feature.
Full results are in `server/interview/data/star_evaluation.json`. To retrain after
changing labels:

```sh
python -m server.interview.train_star
```

**Limitations:** the requirement map, question bank and STAR sentences were drafted with
AI assistance and still need human review (each file states its review status). The
STAR training data was written, not collected from real interviews, so real answers
will likely score lower than the evaluation suggests. Key-point scoring measures
coverage of expected ideas, not whether every statement is correct. Thresholds were
calibrated on the labelled sample profile.

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

Current repository verification (29 October 2026): 327 offline Python regression
checks passed on Windows, both production frontend builds completed and the portfolio
frontend check suite passed. Interview Coach tests use a fake transcriber, a fake voice
and small test embeddings, so they need none of the Whisper, Piper or MiniLM models.
See [release validation](docs/VALIDATION.md) for the checks and their limits.

An earlier CV-builder version has historical five-profile live
journeys and deterministic integration evidence. Those historical artifacts,
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
profiles for demonstration and testing. Only dist files are web-served, never .env or runtime.
Matched/missing checks are conservative text checks, not exhaustive qualification
assessment. Inspect full job requirements, especially seniority and experience.
Confirmation is user review, not independent verification. Provider failures retain
submitted messages and completed tool writes. Exclude .env, runtime databases,
node_modules, model weights, caches and personal data from any shared repository or release.
The supplied `dist/` is the intentional, verified production runtime frontend;
transient build caches remain excluded.
No billing changes or external deployment is automated.

API reference: https://ai.google.dev/api/generate-content
