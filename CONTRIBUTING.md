# Team development

## First checkout

```powershell
git clone https://github.com/VishnuBhaiya/proofcv-studio.git
cd proofcv-studio
powershell -ExecutionPolicy Bypass -File .\setup-proofcv.ps1
```

Add your own Gemini API key to the locally created `.env`, then run:

```powershell
powershell -ExecutionPolicy Bypass -File .\start-proofcv.ps1
```

Open http://127.0.0.1:8000. Python 3.12 or 3.13 is required. Initial dependency
installation and the first MiniLM download need internet access and can take time.
The baseline requires no personal profile database: create your own workspace.

## Make a change

Start with a clean working tree. Replace the example branch name with your task.

```powershell
git switch main
git pull --ff-only origin main
git switch -c feature/your-task
```

Frontend development requires Node.js 22 and the pnpm version documented in the
README. Use `pnpm install --frozen-lockfile` to respect the committed lockfile,
then `pnpm run dev`. Run the Python server in a separate terminal; Vite proxies
API requests to it. Never place a provider key in a `VITE_` variable.

Before opening a pull request:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -v
# For frontend changes, also run:
pnpm run build
git status --short
git diff --check
```

Inspect the diff, including the updated `dist/` for frontend changes. Stage only
the files you intend to share, commit them, and push your feature branch:

```powershell
git add <changed-file-paths>
git commit -m "Describe the change"
git push -u origin feature/your-task
```

Open a pull request to `main` on GitHub. Ask another teammate to review it and
record what was tested. Branch review is a team convention, not an enforced
repository rule. Live connection/journey commands consume provider quota and are
not part of the offline unit-test command.

## Data and credentials

- Keep `.env`, virtual environments, dependencies and `runtime/` local.
- Use the labelled synthetic profiles for tests; do not upload private resumes,
  contact details, chat histories, PDFs or databases to the repository.
- Preserve existing confirmed-profile, proposal-review and provenance boundaries.
- Do not describe mocked tests as live Gemini runs.
- GitHub repository collaborators must be invited by the owner before they can
  clone this private repository or push branches.
