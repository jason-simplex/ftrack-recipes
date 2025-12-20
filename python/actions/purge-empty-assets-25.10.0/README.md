# Purge Empty Assets (Action)

Delete selected assets in a project, focusing on empty assets. Use with care — deletions are irreversible.

## Features

- 🧭 Scope: Appears when a single Project is selected.
- 🧹 Purpose: Purge empty assets; optionally purge one versioned asset.
- 📊 UI: Shows non‑empty/empty counts, an enumerator to pick a versioned asset, and per‑asset boolean toggles for empty assets.
- 🧠 Performance: Caches version counts and type names; sorts assets by version count (ascending) for clarity.
- 🗑️ Deletion: Deletes selected targets via `session.delete(...)` and commits; logs a summary.

## How It Works

1. Select a Project in ftrack.
2. Open “Purge Empty Assets”.
3. (Optional) Pick a versioned asset to purge from the enumerator.
4. Toggle empty assets you want to purge.
5. Run the action — selected assets are deleted and the session is committed.

## Notes

- Labels show asset name, type, and version count for safer decisions.
- The action logs chosen targets and returns a brief success message.
