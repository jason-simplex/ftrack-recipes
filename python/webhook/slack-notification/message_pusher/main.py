# :coding: utf-8
# :copyright: Copyright (c) 2025 bro.tiger

import functions_framework
import requests
import json
import ftrack_api
from string import Template
from datetime import datetime, timezone
from message_block import STATUS_UPDATE_SLACK_BLOCK, NOTE_SLACK_BLOCK


session = None

# --- Configuration loading for project → Slack webhook routing ---
import os

def load_config():
    """Load routing config strictly from local config.json.
    """
    base_dir = os.path.dirname(__file__)
    file_path = os.path.join(base_dir, 'config.json')
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    server_url = data.get('server_url')
    return {
        'server_url': server_url,
        'api_user': data.get('api_user'),
        'api_key': data.get('api_key'),
        'ftrack_secret': data.get('ftrack_secret'),
        'project_map': data.get('project_map', {})
    }

CONFIG = load_config()

def get_session() -> ftrack_api.Session:
    global session
    if session is not None:
        return session
    server_url = CONFIG.get('server_url')
    api_user = CONFIG.get('api_user')
    api_key = CONFIG.get('api_key')
    kwargs = {}
    if server_url:
        kwargs['server_url'] = server_url
    if api_user:
        kwargs['api_user'] = api_user
    if api_key:
        kwargs['api_key'] = api_key
    session = ftrack_api.Session(**kwargs)
    return session
def select_webhook_url(project_id: str) -> str | None:
    """Return the webhook URL for a given project_id; strict dict schema."""
    val = CONFIG.get('project_map', {}).get(project_id)
    if isinstance(val, dict):
        url = val.get('webhook_url')
        return url if isinstance(url, str) and url.strip() else None
    return None

def extract_project_id(request_dict: dict, session: ftrack_api.Session) -> str | None:
    """Extract project_id from a request_dict.

    Args:
        request_dict (dict): The request dictionary.
        session (ftrack_api.Session): The ftrack session.

    Returns:
        str | None: The project_id if found, None otherwise.
    """
    try:
        entity = request_dict.get('entity', {})
        entity_type = entity.get('entity_type')
        new_obj = entity.get('new', {})
        entity_id = new_obj.get('id')
        if not entity_type or not entity_id:
            return None
        obj = session.get(entity_type, entity_id)
        if not obj:
            return None
        return obj.get('project_id')
    except Exception:
        return None

def get_utc_timestamp(value) -> str:
    """Convert a UTC datetime (ISO8601 string/epoch/datetime) to UTC unix timestamp string.

    Returns:
        str: timestamp as string (e.g. "1735689600")
    """
    dt: datetime
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, (int, float)):
        dt = datetime.fromtimestamp(value, tz=timezone.utc)
    elif isinstance(value, str):
        s = value.strip()
        # Support trailing 'Z' by converting to offset form
        if s.endswith('Z'):
            s = s[:-1] + '+00:00'
        try:
            dt = datetime.fromisoformat(s)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
        except ValueError:
            # Fallback: try a basic format without offset/microseconds
            try:
                dt = datetime.strptime(s, '%Y-%m-%dT%H:%M:%S').replace(tzinfo=timezone.utc)
            except ValueError:
                # Last resort: return 0 if parse fails, or maybe current time
                return str(int(datetime.now(timezone.utc).timestamp()))
    else:
        return str(int(datetime.now(timezone.utc).timestamp()))
    
    return str(int(dt.timestamp()))

def safe_get_thumbnail_url(obj) -> str:
    """Safely get thumbnail url from an entity-like object/dict."""
    try:
        return obj.get('thumbnail_url', {}).get('url', '')
    except Exception:
        return ''

def build_entity_path(entity) -> str:
    """Return entity path built from link; fallback to name."""
    try:
        return '/'.join(link['name'] for link in entity['link'])
    except Exception:
        return entity.get('name', '')

def build_entity_url(server_url: str, entity_id: str, entity_type: str) -> str:
    """Return ftrack web URL for an entity id/type using slide view."""
    slide_type_map = {'Task': 'task', 'AssetVersion': 'assetversion', 'Note': 'note'}
    slide_type = slide_type_map.get(entity_type, entity_type.lower())
    return f"{server_url}#slideEntityId={entity_id}&slideEntityType={slide_type}&itemId=home"

def build_task_link(session: ftrack_api.Session, task_id, server_url: str) -> tuple[str, str]:
    """Return (task_url, task_path) for a given task_id; empty strings if unavailable."""
    if not task_id:
        return '', ''
    try:
        task = session.get('Task', task_id)
        try:
            task_path = '/'.join(link['name'] for link in task['link'])
        except Exception:
            task_path = task.get('name', '')
        task_url = f"{server_url}#slideEntityId={task_id}&slideEntityType=task&itemId=home"
        return task_url, task_path
    except Exception:
        return '', ''

def build_status_update_context(request_dict: dict, session: ftrack_api.Session) -> dict:
    """Build a unified context dict for Slack Status Update block from payload.

    Returns keys that match the unified template:
    - header_text, entity_url, entity_path, entity_thumbnail_url
    - new_status, old_status, username, status_change_time
    """
    entity_type = request_dict['entity']['entity_type']
    server_url = request_dict['metadata']['server_url']
    entity_id = request_dict['entity']['new']['id']
    entity = session.get(entity_type, entity_id)

    entity_thumbnail_url = safe_get_thumbnail_url(entity)
    entity_url = build_entity_url(server_url, entity_id, entity_type)
    entity_path = build_entity_path(entity)
    new_status = session.get('Status', request_dict['entity']['new']['status_id'])['name']
    old_status = session.get('Status', request_dict['entity']['old']['status_id'])['name']
    fname = session.get('User', request_dict['metadata']['resource_id'])['first_name']
    lname = session.get('User', request_dict['metadata']['resource_id'])['last_name']
    status_change_time = get_utc_timestamp(request_dict['metadata']['date'])
    header_text = ':traffic_light: Status Updates on :clipboard: Task' if entity_type == 'Task' else (
        ':traffic_light: Status Updates on :clapper: Asset Version' if entity_type == 'AssetVersion' else f'{entity_type} Status Updates'
    )

    # Optional related task line: only for AssetVersion linked to a Task
    related_task_line = ''
    if entity_type == 'AssetVersion':
        task_id = request_dict['entity']['new'].get('task_id') if isinstance(request_dict.get('entity', {}).get('new', {}), dict) else None
        task_url, task_path = build_task_link(session, task_id, server_url)
        if task_url and task_path:
            related_task_line = f"- Related Task: *<{task_url}|{task_path}>*"

    return {
        'header_text': header_text,
        'entity_url': entity_url,
        'entity_path': entity_path,
        'new_status': new_status,
        'old_status': old_status,
        'fname': fname,
        'lname': lname,
        'status_change_time': status_change_time,
        'entity_thumbnail_url': entity_thumbnail_url,
        'related_task_line': related_task_line,
    }

def build_note_context(request_dict: dict, session: ftrack_api.Session) -> dict:
    """Build context dict for Slack Note block from payload."""
    parent_type = request_dict['entity']['new']['parent_type']  # 'task' or 'asset_version'
    server_url = request_dict['metadata']['server_url']
    parent_id = request_dict['entity']['new']['parent_id']

    # Map to canonical entity type names
    if parent_type == 'task':
        entity_type = 'Task'
    elif parent_type == 'asset_version':
        entity_type = 'AssetVersion'
    else:
        entity_type = parent_type.title()

    entity = session.get(entity_type, parent_id)
    entity_thumbnail_url = safe_get_thumbnail_url(entity)
    entity_url = build_entity_url(server_url, parent_id, entity_type)
    entity_path = build_entity_path(entity)

    # Header text by target entity
    header_text = ':memo: New Note on :clipboard: Task' if entity_type == 'Task' else (
        ':memo: New Note on :clapper: Asset Version' if entity_type == 'AssetVersion' else f':memo: New Note on {entity_type}'
    )

    new_obj = request_dict['entity']['new']
    content = new_obj.get('content', '')
    # Frame can be 'frame' or 'frame_number' depending on payload
    frame = new_obj.get('frame')
    if frame is None:
        frame = new_obj.get('frame_number')
    # Build conditional frame line: future payload guarantees None or numeric
    if frame is None:
        frame_line = ''
    else:
        frame_line = f"\n - FrameNum: *{int(frame) + 1}*"

    fanme = session.get('User', request_dict['metadata']['resource_id'])['first_name']
    lname = session.get('User', request_dict['metadata']['resource_id'])['last_name']
    date = get_utc_timestamp(request_dict['metadata']['date'])

    # Optional related task line: show only when note is on AssetVersion and that version links to a Task
    related_task_line = ''
    if entity_type == 'AssetVersion':
        task_id = entity.get('task_id') if isinstance(entity, dict) else None
        # Some API objects expose attributes via dict-like access; fallback using session.get if needed
        if not task_id:
            try:
                task_id = entity['task_id']
            except Exception:
                task_id = None
        task_url, task_path = build_task_link(session, task_id, server_url)
        if task_url and task_path:
            related_task_line = f"- Related Task: *<{task_url}|{task_path}>*"

    return {
        'header_text': header_text,
        'entity_url': entity_url,
        'entity_path': entity_path,
        'content': content,
        'frame': frame,
        'frame_line': frame_line,
        'fanme': fanme,
        'lname': lname,
        'date': date,
        'entity_thumbnail_url': entity_thumbnail_url,
        'related_task_line': related_task_line,
    }


@functions_framework.http
def message_push(request):
    # Cloud Run（Functions Framework）：read request body and headers
    request_dict = request.get_json(silent=True)
    headers = dict(request.headers)

    if not check_validity(request_dict, headers):
        return 'Invalid request', 400
    if check_validity(request_dict, headers):
        s = get_session()
        entity_type = request_dict.get('entity', {}).get('entity_type')
        if entity_type == 'Note':
            ctx = build_note_context(request_dict, s)
            message = Template(NOTE_SLACK_BLOCK).substitute(**ctx)
        else:
            ctx = build_status_update_context(request_dict, s)
            message = Template(STATUS_UPDATE_SLACK_BLOCK).substitute(**ctx)
        project_id = extract_project_id(request_dict, s)
        webhook_url = select_webhook_url(project_id)
        if not webhook_url:
            return 'Webhook not configured for project', 400
        push_message_to_slack(message, webhook_url)
        return 'Success', 200

def check_validity(request_dict, headers: dict | None = None) -> bool:
    # Validate server URL and standardized X-Ftrack-Secret header against config
    try:
        srv_req = str(request_dict['metadata']['server_url']).rstrip('/')
        srv_cfg = str(CONFIG.get('server_url')).rstrip('/')
        server_ok = srv_req == srv_cfg
    except Exception:
        server_ok = False

    secret_expected = CONFIG.get('ftrack_secret')
    if secret_expected is None:
        # If no secret configured, require only server match
        secret_ok = True
    else:
        provided = None
        if headers:
            # Case-insensitive lookup for the X-Ftrack-Secret header
            provided = headers.get('X-Ftrack-Secret') or headers.get('x-ftrack-secret')
        secret_ok = provided is not None and str(provided) == str(secret_expected)

    return bool(server_ok and secret_ok)

def push_message_to_slack(message, webhook_url: str):
    try:
        response = requests.post(webhook_url, headers={'Content-Type': 'application/json'}, data=message)
        if response.status_code == 200:
            print("Message sent successfully!")
        else:
            print(f"Error: {response.status_code} - {response.text}")
    except requests.exceptions.RequestException as e:
        print(f"Error: {e}")
