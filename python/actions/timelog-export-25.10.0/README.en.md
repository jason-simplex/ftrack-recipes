# Timelog Export ⏱️📊

An Action to export ftrack user timelog reports. It supports filtering by date range and projects, generates a downloadable `.xlsx` report, and can automatically save the current export settings locally per user — ideal for weekly/monthly reports and project accounting.

## Highlights ✨

- Filter by one or multiple projects, or simply check `All Projects` as the query scope ✅
- Selectable date range; leave blank to query `All Dates` 📅
- Semi-open date filter supported: only `From` or only `To` also works ⛓️
- Numeric columns use two decimal places (`0.00`) for consistent summaries 🧮
- Export to Excel with total and per-user breakdown 📊
- The exported Excel layout matches the ftrack timelog report page layout 🎨
- Automatically saves the current export settings locally, isolated by username 🔐
- Robust fallback: when historical settings are missing or invalid, it uses the current UI values 🛡️

## How to Use 🚀

1. Select one or more projects in ftrack.
2. Trigger the “Timelog Export” Action.
3. In the UI:
   - Choose `From` / `To` (format `YYYY-MM-DD`; leaving both blank means `All Dates`; you can also fill only one line).
   - Check `Current selection` (lists all currently selected project names).
   - Optionally check `All Projects` to ignore current selection and fetch timelogs from all projects.
   - Optionally check `Use My Last Settings` to ignore all current UI settings and reuse the last successful export configuration.
4. Click submit and wait a moment; in the popped Job panel, click to download the generated Excel file.

## Exported Excel Layout 📁

- Title area shows `Timelog report for <selected projects>` (or `All Projects`).
- Header area shows `Hours Tracked` (total tracked hours), `Projects` (number of related projects), `Users` (number of related users), and `Date Range`.
- User details area: lists each user’s `Total(Hours)`, with classification by `Billable` and `Non Billable`.
- Numeric display: hours values use two decimal places (`0.00`).

## Historical Settings & Isolation 🧩

- On each successful export, the tool automatically saves the current export configuration locally.
- Save path: `../config/users/<username>/last_setting.json` (isolated by username).
- The config file is plain text; you can directly edit it (e.g., date range, project names) as presets for the next export.
- When `Use My Last Settings` is checked and submitted:
  - Only valid field values will override (supports empty string for date to clear filters).
  - Invalid fields are skipped and the current UI input is kept (with logs recorded).

## Notes ⚠️

- The date control display format depends on browser/OS; submitted values follow `YYYY-MM-DD`.
- About date range:
  - Only `From` provided in the UI: `2025-11-01` → exported report `Date Range` shows `2025-11-01 - ∞`, meaning “from that day onwards”.
  - Only `To` provided in the UI: `2025-11-30` → exported report `Date Range` shows `∞ - 2025-11-30`, meaning “up to that day”.
  - Both left blank in the UI → exported report `Date Range` shows `All Dates`, meaning “all dates”.
- If the historical settings file is missing or corrupted while using `Use My Last Settings`, the tool automatically proceeds using the current UI values (fallback design).
- Required dependencies: see `requirement.txt`.

## Install Dependencies 🧰

In the action directory:

```bash
pip install -r requirement.txt
```

## Registration & Run 🧭

- This Action registers via `ftrack-python-api` and `ftrack-action-handler`.
- After successful registration, when a user selects one or more projects in the UI, the “Timelog Export” Action will appear in ftrack’s context menu or Actions list.

Happy exporting! 🙌