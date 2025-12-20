# Batch Task Thumbnails Import From Excel File

Import task thumbnails from Excel with a visual “Task Path” builder. Embedded images in the `Thumbnail` column are extracted and set as task thumbnails. ✨

## Highlights ✨

- 🎯 Companion to ftrack’s default task importer — bulk‑import task thumbnails in one go.
- 📄 Reuse your existing Excel task sheet; this action focuses on thumbnails only, no separate file needed.
- 🗂️ Allows users to choose which sheet to import thumbnails from.
- 🧩 Visual Rule Builder: drag chips to build your Task Path as your import rule.
- 🖼️ Original image extraction from `.xlsx` for best quality; Excel (xlwings) fallback.
- ⚙️ Fast header reading via `openpyxl` (no Excel launch when possible).
- ✅ Smart validation with helpful examples and hints.
- 📊 Clear result summary: updated thumbnails and pictures extracted.

## Usage 🧭

1. Prepare an Excel sheet with necessary columns for Thumbnail and Project Data
2. Place one picture per row anchored inside the `Thumbnail` cell.
3. In ftrack, trigger the action and select your Excel file.
4. Choose the sheet and set `Image Column` (default `Thumbnail`).
5. Build the `Task Path`:
   - Type with `/` as delimiter, or
   - Drag chips in the Visual Rule Builder.
6. Click OK to import and review the summary.

## Notes 🗒️

- 🖥️ Excel must be installed for the xlwings fallback to render cells.
- 🔤 Task Path column names must match Excel headers exactly.
- 📌 Pictures must be fully inside the `Thumbnail` cell (four corners within bounds).
- 🐢 Large workbooks may take longer; header reading prefers `openpyxl` for speed.
- 📦 Install dependencies: `pip install -r requirements.txt`.
- 📂 Location in repo: `env/ftrack-recipes/python/actions/batch-task-thumbnails-import-25.11.0/`.

## Troubleshooting 💡

- Task not found after submit:
  - Verify the Task Path matches your project’s hierarchy (e.g. `Shots/Sequence/Shot/Task`).
  - Ensure names in Excel exactly match ftrack object names.
- Columns not recognized:
  - Make sure the first row contains headers and they match your Task Path tokens.
  - Use the Visual Rule Builder to pick from detected headers.
- Images not extracted:
  - Confirm each picture is fully within the `Thumbnail` cell; embedded images are required.
  - If original extraction fails, xlwings fallback needs Excel installed.
- Headers appear empty or sheet not found:
  - Check the selected sheet name and that the workbook isn’t protected.
  - Try reopening the file and reselecting; header reading prefers `openpyxl`.
- Slow performance on large files:
  - Close other Excel instances; avoid volatile formulas in the sheet.
  - Prefer original extraction (no Excel launch) when possible.

## FAQ ❓

- Can I use it for Assets instead of Shots?
  - Yes. Example Task Path: `Assets/AssetCategory/Folder/AssetBuild/Task`.
- Do column names have to match exactly?
  - Yes. Task Path tokens must equal the header text (case‑sensitive).
- How are images matched to rows?
  - By the `Thumbnail` column: each embedded picture anchored inside a cell maps to that row.
- Can it work without Excel installed?
  - Partially. Original image extraction from `.xlsx` works, but the xlwings fallback (cell render) requires Excel.
- How do I reorder or remove columns in Task Path?
  - Drag chips to reorder; double‑click to remove (hint overlay appears when empty).
- What summary is shown after import?
  - Number of thumbnails updated and pictures successfully extracted.
