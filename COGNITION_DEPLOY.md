# Cognition.run deployment notes

This project is now configured to run as a static jsPsych task on Cognition.run.

## What changed for Cognition compatibility

- Removed local path rewrite logic from `index.html`.
- Removed custom `fetch` submission flow from `experiment.js`.
- Added `index.js` as explicit Cognition source entrypoint bootstrap.
- Data is now recorded via normal jsPsych trial data only (Cognition captures runs automatically).
- Added explicit `final_status` metadata:
  - `"completed"` for participants who pass comprehension.
  - `"disqualified"` for participants who fail comprehension.

## Upload/deploy options

### Option A: Cognition code editor (manual, advanced)

1. Create a new task in Cognition.
2. Upload required files in the task assets/external files area:
   - `style.css`
   - `disqualified.html`
   - `plugin-causal-pair-scale.js`
   - `dist/` JS and CSS files used by `index.html`/experiment
   - `Stories/` PDFs
3. Mirror script/style loading from `index.html` in Cognition's source/external library setup.
4. Ensure file names/paths are unchanged.
5. Test with the task public link.

### Option B: GitHub integration (recommended)

1. Put this folder in a GitHub repository root.
2. Keep `index.js` and `index.html` at repo root.
3. Add repository secret `PERSONAL_ACCESS_TOKEN` in GitHub Actions secrets.
4. Set that secret value to your token from `https://www.cognition.run/account`.
5. Push your repo (or run the workflow manually).
6. Workflow logs print the deployed public task link.

This repository now includes:

- `.github/workflows/cognition-github-actions.yml`

## URL parameters supported by this experiment

- `participant_id` (or `PROLIFIC_PID`)
- `study_id` (or `STUDY_ID`)
- `session_id` (or `SESSION_ID`)
- `completion_url`
- `disqualify_url`
- `comprehension_min_correct` (default `1`)
- `comprehension_max_wrong` (default `2`)
- `debug=1` (forces data display at the end)

## Example participant link

```text
https://<your-task>.cognition.run/?participant_id=123&study_id=ABC&session_id=001&compl