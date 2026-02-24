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
    - Go to [https://api.slack.com/apps](https://api.slack.com/apps).
    - Click **Create New App - From a manifest - Pick a workspace - Name it in the manifest (e.g., "ftrack-notification")**.
    - Click this new app in the list to go to its settings, in **Settings - Basic Information - Display Information** section, You can rename your app and update its icon. You can use this [icon](https://github.com/jason-simplex/ftrack-recipes/blob/jason/workbench/python/webhook/slack-notification/integratoin-hero-ftrack.png) for your App.
<img width="2880" height="1480" alt="image" src="https://github.com/user-attachments/assets/bb8dc6c7-3c98-434b-b71f-309c7e153744" />
<img width="1134" height="1132" alt="image" src="https://github.com/user-attachments/assets/b905ca8c-2ece-4e8e-9a9d-a13b453a74e3" />
<img width="3336" height="1996" alt="image" src="https://github.com/user-attachments/assets/a53caa3e-7c16-4331-a2ab-5595df40d7bb" />



2.  **Enable Incoming Webhooks**:
    - In the sidebar, click **Incoming Webhooks**.
    - Toggle the "**Activate Incoming Webhooks**" switch to **On**.
<img width="1119" height="762" alt="image" src="https://github.com/user-attachments/assets/0813c56c-1b01-4378-aa7a-6685357bca68" />



3.  **Create a Webhook URL**:

    - Click **Add New Webhook to Workspace**.
    - Select the channel where you want notifications to appear (e.g., a specific project channel).
    - Click **Allow**.
<img width="2880" height="1515" alt="image" src="https://github.com/user-attachments/assets/171d67eb-355a-4910-94ac-a96317043345" />


4.  **Copy the Webhook URL**:
    - You will see a URL starting with `https://hooks.slack.com/services/...`.
    - **Copy this URL**, you will need it for the configuration file.
<img width="1104" height="711" alt="image" src="https://github.com/user-attachments/assets/ad5e2274-168f-4443-b217-36309457ae51" />


---

## Part 2: Service Configuration (Prepare `config.json`) ⚙️

There are 4 files which you need to download from [slack-notification/message_pusher](https://github.com/jason-simplex/ftrack-recipes/tree/jason/workbench/python/webhook/slack-notification/message_pusher) repository, because you'll need to add them to your Google Cloud Run service later:

- `config.json`: The main configuration file. (Need to update with your ftrack credentials and Slack webhook URL)
- `main.py`: The main script to run the service. (No need to modify)
- `message_block.py`: The script to build the Slack message blocks. (No need to modify)
- `requirements.txt`: Python dependencies. (No need to modify)

Ok, so let's update the `config.json` file before we deploy the service.

1.  Locate the `config.json` file.
2.  Open it with a text editor and update the following `<>` fields:

A sample of `config.json`:
```json
{
  "server_url": "https://chinateam.ftrackapp.cn/",
  "api_user": "__automation_service__",
  "api_key": "NTY1********************************************************************************DE",
  "ftrack_secret": 123456,
  "project_map": {
    "4b7cee18-2608-4682-94a3-c904d960a403": {
      "project_name": "my-alpha",
      "webhook_url": "https://hooks.slack.com/services/T********C/B********9/d********************J"
    },
    "d4a562bb-6dce-41e5-b16b-d6de005e67b3": {
      "project_name": "proj12",
      "webhook_url": "https://hooks.slack.com/services/T********C/B********9/d********************J"
    }
  }
}
```
- **server_url**: Your ftrack server URL.
- **api_user**: You can use `__automation_service__`, as it's a built-in Webhook Service user in ftrack.
- **api_key**: Create a Global API Key in ftrack **System Settings** -> **Security** -> **API Keys**. (This key will only show once, make sure to copy it right after creating it.) For more info, go check: [Global API keys](https://help.ftrack-studio.backlight.co/hc/en-us/articles/13129926642327-API-Keys)
- **ftrack_secret**: Create a secret password string to protect your service.  (e.g., "my_super_secret_123"). You will enter this in ftrack later to verify requests.
- **project_map**: Map ftrack Project IDs to specific Slack Webhook URLs. This allows you to route different projects to different Slack channels. There are only 2 projects in the sample `config.json` above, but in fact you can add as many projects as you need. To get a Project ID, click a project name in ftrack, then copy the ID from its **info** tab in Sidebar (e.g., `4b7cee18-2608-4682-94a3-c904d960a403`).

<img width="514" height="791" alt="image" src="https://github.com/user-attachments/assets/40050b75-036c-4059-a73a-492b417fb227" />

---

## Part 3: Google Cloud Run Deployment ☁️

Now we deploy the code to Google Cloud Run.

### Option A: Using Google Cloud Console (Web UI)

1.  **Go to Cloud Run**: Navigate to the [Cloud Run Console](https://console.cloud.google.com/run).
2.  **Service**: Click **Write a function**.
<img width="1119" height="773" alt="image" src="https://github.com/user-attachments/assets/083186de-c219-47cf-bcc7-036127296637" />

3.  **Configuration**:
    - **Service name**: e.g., `ftrack-slack-notification`.
    - **Region**: Choose a region close to you (e.g., `asia-northeast1`).
    - **Authentication**: Select **Allow Public Access**. (Don't worry, Security is handled via the `ftrack_secret` check in the code).
<img width="1120" height="672" alt="image" src="https://github.com/user-attachments/assets/1ebf1fed-fba5-4ed2-ae42-1c321f25e3bd" />

4.  **Source**:
    - Add the files: `main.py`, `config.json`, `requirements.txt`, and `message_block.py` in the **Source** section. It doesn't support uploading files directly via web UI, you need to create each file and paste its content into the editor accordingly.
<img width="1125" height="672" alt="image" src="https://github.com/user-attachments/assets/99e08b9e-ccee-4c13-bec6-165c13a1d41e" />


5.  **Build Configuration**:
    - **Function entry point**: Enter `message_push`. (Important! Default is often `hello_http`).
6.  **Create**: Click **Save and Deploy** and wait for the deployment to finish.
7.  **Get Service URL**: Once finished, copy the URL at the top (e.g., `https://ftrack-slack-notification-123456789.asia-northeast1.run.app`).
<img width="1140" height="680" alt="image" src="https://github.com/user-attachments/assets/c7a149ae-4734-4063-b97d-c71c91edc613" />

### Option B: Using Command Line (gcloud CLI)

TBD

```bash
TBD
```

---

## Part 4: ftrack Webhook Setup 🔗

Finally, tell ftrack to send events to your deployed service.

1.  **Go to ftrack System Settings**:
    - Navigate to **System Settings** -> **Advanced** -> **Webhooks** -> **Add Webhook**
<img width="1103" height="666" alt="image" src="https://github.com/user-attachments/assets/ac5d5e5b-ee22-4cbc-a5d7-0a7ff93230a2" />



2.  **Configure this new Webhook**:
    - **Name**: Name your webhook, e.g., "ftrack-to-slack"
    - **Endpoint Url**: Paste the **Cloud Run Service URL** from Part 3. (e.g., `https://ftrack-slack-notification-123456789.asia-northeast1.run.app`).
    - **Header** -> **Add headers** to create a new header: Name your header such as `X-Ftrack-Secret`, and use the value of `ftrack_secret` from `config.json`.
    - **Select events**: Check on the following events:

```
    AssetVersion -> Update on -> status_id
    Note -> Create
    Note -> Update on -> content
    Task -> Update on -> status_id
```

3.  **Save**: Your webhook is now active!
<img width="1112" height="667" alt="image" src="https://github.com/user-attachments/assets/50220f15-1e8f-468a-81fe-c52357770d60" />



## ✅ Verification

1.  Make some changes in ftrack. This tool supports the following events currently:
    - Messaging to Slack when a Task's status is updated in ftrack.
    - Messaging to Slack when an AssetVersion's status is updated in ftrack.
    - Messaging to Slack when a Note is created in ftrack.
    - Messaging to Slack when a Note's content is updated in ftrack.
2.  Check your Slack channel.
3.  You should see nicely formatted notifications!

<img width="1051" height="1417" alt="image" src="https://github.com/user-attachments/assets/06681ae4-767b-4f83-bcf2-b6c7f6d4ef4b" />

