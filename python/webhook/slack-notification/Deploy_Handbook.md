# 🚀 Deployment Handbook

This guide will walk you through the steps to deploy the ftrack-to-Slack notification service.

## Prerequisites

- **Google Cloud Platform (GCP) Account**: With a project created and billing enabled.
- **Slack Workspace**: Permission to create Apps or manage integrations.
- **ftrack Server**: Admin access to configure webhooks.

---

## Part 1: Slack Configuration (Get the Webhook URL) 💬

Before deploying the code, we need a destination for our messages.

1.  **Create a Slack App**:

    - Go to [Slack API: Your Apps](https://api.slack.com/apps).
    - Click **Create New App** -> **From scratch**.
    - Name it (e.g., "ftrack-notification") and select your workspace.

2.  **Enable Incoming Webhooks**:

    - In the sidebar, click **Incoming Webhooks**.
    - Toggle the "**Activate Incoming Webhooks**" switch to **On**.

3.  **Create a Webhook URL**:

    - Click **Add New Webhook to Workspace**.
    - Select the channel where you want notifications to appear (e.g., `#general` or a specific project channel).
    - Click **Allow**.

4.  **Copy the Webhook URL**:
    - You will see a URL starting with `https://hooks.slack.com/services/...`.
    - **Copy this URL**, you will need it for the configuration file.

---

## Part 2: Service Configuration (Prepare `config.json`) ⚙️

The service needs to know your ftrack credentials and where to send Slack messages.

1.  Locate the `config.json` file in the source code folder.
2.  Open it and update the following `<>` fields:

```json
{
  "server_url": "<https://your-ftrack-server.ftrackapp.com>",
  "api_user": "<your-api-username>",
  "api_key": "<your-long-api-key>",
  "ftrack_secret": "<your-chosen-secret-string>",
  "project_map": {
    "<ftrack-project1-id>": {
      "project_name": "<your-project1-name>",
      "webhook_url": "<https://hooks.slack.com/services/YOUR/SLACK/WEBHOOK_1>"
    },
    "<ftrack-project2-id>": {
      "project_name": "<your-project2-name>",
      "webhook_url": "<https://hooks.slack.com/services/YOUR/SLACK/WEBHOOK_2>"
    },
    ...
  }
}
```

- **server_url**: Your ftrack server URL.
- **api_user/api_key**: An API user from ftrack **My Account** -> **Username**, **My account** -> **API Keys**
- **ftrack_secret**: Create a secret password string (e.g., "my_super_secret_123"). You will enter this in ftrack later to verify requests.
- **project_map**: Map ftrack Project IDs to specific Slack Webhook URLs. This allows you to route different projects to different Slack channels.

---

## Part 3: Google Cloud Run Deployment ☁️

Now we deploy the code to Google Cloud Run.

### Option A: Using Google Cloud Console (Web UI)

1.  **Go to Cloud Run**: Navigate to the [Cloud Run Console](https://console.cloud.google.com/run).
2.  **Service**: Click **Write a function**.
3.  **Configuration**:
    - **Service name**: e.g., `ftrack-slack-notification`.
    - **Region**: Choose a region close to you (e.g., `asia-northeast1`).
    - **Authentication**: Select **Allow unauthenticated invocations**. (Security is handled via the `ftrack_secret` check in the code).
4.  **Source**:
    - Upload the files: `main.py`, `config.json`, `requirements.txt`, and `message_block.py`.
5.  **Build Configuration**:
    - **Function entry point**: Enter `message_push`. (Important! Default is often `hello_http`).
6.  **Create**: Click **Save and Deploy** and wait for the deployment to finish.
7.  **Get Service URL**: Once finished, copy the URL at the top (e.g., `https://ftrack-slack-notification-123456789.asia-northeast1.run.app`).

### Option B: Using Command Line (gcloud CLI)

Run this command in the project directory:

```bash
TBD
```

---

## Part 4: ftrack Webhook Setup 🔗

Finally, tell ftrack to send events to your deployed service.

1.  **Go to ftrack System Settings**:
    - Navigate to **System Settings** -> **Advanced** -> **Webhooks** -> **Add Webhook**
2.  **Configure this new Webhook**:

    - **Name**: e.g., "ftrack-to-slack"
    - **Endpoint Url**: Paste the **Cloud Run Service URL** from Part 3.
    - **Header** -> **Add headers** to create a new header: Name your header such as `X-Ftrack-Secret`, and use the value of `ftrack_secret` from `config.json`.
    - **Select events**: Check on the following events:

    ```
    AssetVersion -> Update on -> status_id
    Note -> Create
    Note -> Update on -> content
    Task -> Update on -> status_id
    ```

3.  **Save**: Your webhook is now active!

## ✅ Verification

1.  Change a Task status in ftrack.
2.  Check your Slack channel.
3.  You should see a nicely formatted notification!
