# 🔔 ftrack to Slack Notification

Connect your ftrack workflow with Slack! This service automatically pushes updates from ftrack directly to your team's Slack channels, keeping everyone in sync without leaving the chat.

## Highlights ✨

- **Real-time Updates**: Get notified instantly when Task / AssetVersion statuses change or new Notes are added. 🚀
- **Beautifully Formatted**: Messages are presented in clean, rich cards with thumbnails and direct links. 🎨
- **Smart Routing**: Different ftrack projects can send notifications to different Slack channels (e.g., `#proj-a`, `#proj-b`). 🔀
- **Time Travel? No, just Local Time!**: Dates and times are automatically converted to your local time zone in Slack. 🌍
- **Context Aware**: Shows who made the change, what and when changed, and links back to the exact item in ftrack. 🔗

## Usage 🛠️

Once deployed, this service works silently in the background.

1.  **Status Updates**: Whenever someone changes a status (e.g., from "In Progress" to "Pending Review") on a **Task** or **Asset Version** in ftrack, a message pops up in the designated Slack channel.
2.  **New Notes**: When someone writes a note on a Task or Version, the content of the note (and the author) is posted to Slack.
3.  **Click & Go**: Click the project path or the "Related Task" link in the Slack message to jump straight to that item in ftrack.

### For Admins (Configuration)

To make it run, you need a `config.json` file with:

- **ftrack Credentials**: server_url, api_user, api_key, ftrack_secret.
- **Project Mapping**: Tell the bot which ftrack Project ID goes to which Slack Webhook URL.

## Notes 📝

- **Supported Events**: Currently supports **Status Changes** and **New Notes** on Tasks and Asset Versions.
- **Thumbnails**: If the asset or task has a thumbnail in ftrack, it will show up in the Slack message! 🖼️
- **Security**: The service checks for a valid "ftrack secret" to ensure requests are actually coming from your ftrack server. 🔒

## Troubleshooting 🔧

- **"I'm not getting any messages!"**
  - Check if the project you are working on is added to the `project_map` in `config.json`.
  - Ensure the Slack Webhook URL is valid and active.
- **"The time looks weird..."**
  - The time is displayed based on your Slack device's time zone settings. If your computer thinks it's in London, Slack will show London time! 🇬🇧
- **"Deploy failed?"**
  - Make sure all keys in `config.json` (like `api_key`, `server_url`) are lowercase and correct.

## FAQ ❓

**Q: Can I send notifications to a private channel?**
A: Yes! As long as the Slack Webhook URL you provide has permissions to post to that channel.

**Q: Does it support other entities like Shots or Sequences?**
A: Currently, it's optimized for Tasks and Asset Versions, but the code is flexible enough to be extended!

**Q: Why do I see a "Related Task" link?**
A: If an Asset Version is linked to a Task, we provide a handy shortcut to that Task so you can see the bigger picture.

---

_Made with ❤️ for better collaboration._
