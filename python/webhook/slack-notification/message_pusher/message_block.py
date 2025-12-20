# :coding: utf-8
# :copyright: Copyright (c) 2025 bro.tiger

# Unified Slack Block Kit template with dynamic header and entity-agnostic variables
STATUS_UPDATE_SLACK_BLOCK = """{
  "blocks": [
    {
      "type": "divider"
    },
    {
      "type": "header",
      "text": {
        "type": "plain_text",
        "text": "$header_text"
      }
    },
    {
      "type": "section",
      "text": {
        "type": "mrkdwn",
        "text": 
"
*<$entity_url|$entity_path>* 
- Current Status: *$new_status*
- Last Status: *$old_status* 
- Updated By: *$fname $lname* 
- When: *<!date^$status_change_time^{date_num} {time_secs}|$status_change_time>*
$related_task_line
"
      },
      "accessory": {
        "type": "image",
        "image_url": "$entity_thumbnail_url",
        "alt_text": "thumbnail"
      }
    }
  ]
}"""

NOTE_SLACK_BLOCK = """{
	"blocks": [
		{
			"type": "divider"
		},
		{
			"type": "header",
			"text": {
				"type": "plain_text",
				"text": "$header_text"
			}
		},
		{
			"type": "section",
			"text": {
				"type": "mrkdwn",
				"text": 
"
*<$entity_url|$entity_path>*
- Content: *$content* $frame_line 
- Author: *$fanme $lname* 
- When: *<!date^$date^{date_num} {time_secs}|$date>*
$related_task_line
"
			},
			"accessory": {
				"type": "image",
				"image_url": "$entity_thumbnail_url",
				"alt_text": "thumbnail"
			}
		}
	]
}"""
