# ProofCV Studio — connected app

React/TypeScript with a Python/Gemini runtime agent, SQLite workspaces, MiniLM
retrieval across nine supplied jobs, confirmed-source CV generation and PDF export.

## Team repository — Assignment 3 baseline

This repository starts from the final Assignment 1 CV builder. Its application
source, supplied datasets and production frontend were compared with the working
app before import. Assignment 3 adds two features, each in its own module: Interview
Coach (see [Interview Coach](#interview-coach-assignment-3) below) and the AI-generated
Portfolio website, which is still a placeholder page in `src/portfolio/`.

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

## Interview Coach (Assignment 3)

Spoken interview practice for the job the user picked from their top matches. It makes
**no Gemini calls**: every step runs on this computer with local models or plain rules.
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
   models are offered.
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

Interview Coach branch verification (24 October 2026): 201 offline tests passed on
macOS with Python 3.14. Interview Coach tests use a fake transcriber, a fake voice and
small test embeddings, so they need none of the Whisper, Piper or MiniLM models. Not yet
run on Windows.

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
