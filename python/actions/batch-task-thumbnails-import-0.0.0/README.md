<!--
Copyright (c) 2025 bro.tiger
All rights reserved.
-->

# Batch Import Task Thumbnails From Excel 📸

Batch-import thumbnails for ftrack tasks — simple, visual, and fast.

## Highlights ✨

- (New) Integrates with ftrack-connect as a tab widget 🔌
- Batch set thumbnails for tasks in one go ⚡️
- Use Excel (.xlsx) to match task paths and images 🧩
- Pick sheet and columns; works with your spreadsheet 🗂️
- Extract native embedded images 🛟
- Only updates thumbnails; leaves other task data untouched 🔒
- See results instantly in ftrack ✅

## Usage 🚀

1. Prepare an Excel (.xlsx) file with embedded picture objects in Excel 📊
2. Launch this tool in the ftrack-connect and load your `.xlsx` file 📂
3. Select the sheet; pick the Image column ("Thumbnail" by default) from the dropdowns 🗂️➡️🖼️
4. Configure the “Task Path” rule in "Task Path Builder" to match your project hierarchy (e.g., Shots/Sequence/Shot/Task) 🧭
5. Click “Import” to update thumbnails in bulk ▶️
6. Review the summary (success/skipped/failed) and check results in ftrack 👀

## Notes 📝

- Prefer `.xlsx`; CSV does not contain embedded images and cannot be used for image extraction.
- Very large files/many images may run slower; consider splitting the import or lowering image resolution.
- Ensure you have edit permissions on target tasks; only thumbnails are updated.

## Troubleshooting 💡

- Task not found:
  - Check the “Task Path” rule matches your project hierarchy (e.g., Shots/Sequence/Shot/Task).
  - Adjust columns or rules if needed.
- Unrecognized columns:
  - Make sure headers exist and are on the first row; reselect sheet and columns.
- Images not imported or empty:
  - Confirm images are embedded picture objects in Excel;
- Slow performance:
  - Reduce batch size, compress images, and close heavy background apps.
- Unexpected errors:
  - Update to the latest version; check logs and share a sample file for diagnosis.

## FAQ ❓

- Do I need Excel installed?
  - No. This tool can read your Excel sheets and columns directly; no need to have Excel installed.
- Which image sources are supported?
  - Embedded images in Excel are supported; plain file path columns are not automatically loaded — insert images to ensure detection.
- Can I import across multiple sheets at once?
  - Import one sheet per run; run multiple passes for additional sheets.
- Does the column order in my Excel sheet matter?
  - No. Once you've selected the sheet and columns, you can re-order them in the UI to define your "Task Path" rule.
- Is there an import summary?
  - Yes. You’ll see success/skipped/failed counts and detailed logs.
- Can I roll back?
  - Re-import to overwrite thumbnails. No automatic rollback — test on a small subset first.

Happy importing!
