# Sync Internal Notes to Client Review Sessions

Share selected internal notes with your collaborators in their Review Sessions — quickly, safely, and with full control.

## Highlights ✨

- 🚚 Sync internal notes to Client Review Sessions; originals remain on Asset Versions.
- ✍️ Edit note text inline before syncing, or choose to skip items.
- 🔄 One‑click “Sync all” per Asset Version for batch operations.
- 🏷️ Note Labels and 🧩 internal review annoations/attachments are copied to Client Review Sessions.
- 🛡️ Smart deduplication prevents copying the same note twice.
- 👀 Clear UI context: shows 🏷️ note labels, 🎞️ frame number, 👤 author, and 🗓️ creation date.
- 🧮 Header counters: shows selected ReviewSessions, eligible Internal Notes, and AssetVersions (with correct singular/plural forms).
- ♻️ Data freshness: automatically refreshes Review Sessions and notes, detecting newly added AssetVersions/notes without restarting the action.

## How to Use 🧭

Prerequisites:

- Make sure that you have both `Client feedback` and `Synced feedback` labels in your ftrack System Settings > Workflow > Note Labels. Create them if they don't exist.

1. In ftrack, select one or more `ReviewSession` or `ReviewSessionFolder`.
2. Trigger the action: `Sync Internal Notes to Client Review Sessions`.
3. In the UI, for each Asset Version:
   - Use the switch `Sync all internal notes for Version: ♦️ <breadcrumb>` to copy all notes for that version.
   - For each note, use the selector (enumerator):
     - Choose the note text (default). You can edit this text inline to tailor it for the Client Review Sessions.
     - Or select `Don't sync` to skip.
4. Click `Submit` to start syncing.

What happens next:

- The action refreshes review session objects and notes to avoid stale data.
- It respects your per‑note selections and the per‑version “Sync all” toggle.
- It creates new notes on the Review Session, copies labels and review annoations/attachments, and marks synced notes with `Synced feedback`.

## Tips & FAQ 💡❓

- Tips:

  - Edit text inline to keep client‑facing notes clear and concise.
  - Use `Don't sync` for internal‑only or sensitive comments.
  - Prefer the `Sync all` toggle when all notes are safe to share.

- FAQ:
  - Why do labels show “N/A”? — The note has no labels at all.
  - Why do frames show “N/A”? — The note is not attached to a frame.
  - Where do synced notes appear? — In the selected Review Session(s) with a note label `Synced feedback`
  - Will my original notes be moved? — No, originals stay on the Asset Version; the action creates copies.

## Notes 🗒️

- Notes tagged with `Client feedback` or `Synced feedback` are excluded from syncing.

### Data freshness details

- The action proactively refreshes cached fields to ensure current data:
  - On `ReviewSession`: refreshes `review_session_objects`.
  - On `ReviewSessionFolder`: refreshes `review_sessions` before expanding contained sessions.
  - On each `ReviewSessionObject`: refreshes `asset_version` and `notes`.
  - On `AssetVersion` notes: refreshes `notes` and each note’s `note_label_links`.
- This avoids the ftrack session cache from hiding newly added AssetVersions or notes; changes made while the action UI is open are detected on submit.

## Requirements 📦

- Python 3.11+
- Install dependencies:

```
pip install -r requirements.txt
```

Location in repository:

```
env/ftrack-recipes/python/actions/sync-notes-to-client-reviews-25.10.0/hook/sync_notes_to_client_reviews.py
```
