# 🔄 Cascade Status: AssetVersion to Task

This event listener automatically syncs status changes from an **AssetVersion** to its associated **Task**. When you update a version's status (e.g., "Approved"), the linked task's status will update to match.

## ✨ Highlights

- **Auto-Sync**: Keeps Task status in sync with AssetVersion effortlessly.
- **Validation**: Checks if the target status exists on the Task before updating.
- **User Feedback**: Sends instant notifications (success ✅ or error ❌) to the user in the web UI.
- **Safe**: Rolls back changes if the status schema doesn't match, preventing data corruption.

## 🚀 Usage

1.  **Deploy**: You can install it as a standard ftrack-connect plugin.
2.  **Action**: Change the status of an AssetVersion in the ftrack web UI.
3.  **Result**: The related Task status updates automatically! 🎉

## 📝 Notes

- **One-way Sync**: Only syncs from AssetVersion ➡️ Task.
- **Status Matching**: The sync relies on `status_id`. The Task must have the exact same status available in its schema.

## 🛠️ Troubleshooting

**Issue**: The Task status didn't change.

- **Check 1**: Is the AssetVersion linked to a Task? (Look for `task_id`)
- **Check 2**: Do both entities share the same status schema? If the Task doesn't support the new status, you'll see an error notification.

## ❓ FAQ

**Q: What if the Task doesn't have the "Approved" status?**
A: The script will block the update and show a red error message: "Task missing target status". You need to add that status to the Task's schema in System Settings.

**Q: Does this work for Shots or Sequences?**
A: No, this specific hook is designed only for the **AssetVersion ↔️ Task** relationship.
