# :coding: utf-8
# :copyright: Copyright (c) 2025 ftrack

import functools
import logging

import ftrack_api


logger = logging.getLogger('bro.tiger.cascade_status_update')


def is_status_change(entity):
    '''Return if updated *entity* is a status change on an AssetVersion.'''
    is_version_entity = entity['entityType'] == 'assetversion'
    is_add_update = entity.get('action') in ('add', 'update')
    
    # Handle case where keys might be None
    keys = entity.get('keys') or []
    is_status_change = 'statusid' in keys
    
    return is_version_entity and is_add_update and is_status_change


def send_message_to_user(session, user_id, message, success=True):
    '''Send a message to the active user.

    Use the event hub of *session* to pop up a message for the user with
    *user_id*.
    '''
    session.event_hub.publish(
        ftrack_api.event.base.Event(
            topic='ftrack.action.trigger-user-interface',
            data=dict(
                type='message',
                success=success,
                message=message,
            ),
            target=f'applicationId=ftrack.client.web and user.id="{user_id}"',
        ),
        on_error='ignore',
    )


def cascade_asset_version_to_task_event_listener(session, event):
    '''Handle *event*. Cascade AssetVersion status changes to the associated Task.'''
    user_id = event['source'].get('user', {}).get('id', None)
    status_changed = False
    
    # Keep track of failed entities to report to user
    failed_entities = []

    entities = event['data'].get('entities', [])

    for entity in entities:
        if not is_status_change(entity):
            continue
        
        entity_id = entity['entityId']
        
        # Query the AssetVersion and associated Task
        # We directly query status_id to sync it
        version = session.query(
            f'select status_id, status.name, task_id, task.status_id, task.name '
            f'from AssetVersion where id is "{entity_id}"'
        ).first()
        
        if not version:
            continue
            
        # Check if the AssetVersion is attached to a Task
        if not version['task_id']:
            logger.info(f'AssetVersion {entity_id} is not attached to a Task. Ignoring.')
            continue
            
        task = version['task']
        target_status_id = version['status_id']
        
        # Update Task status if it's different
        if task['status_id'] != target_status_id:
            task['status_id'] = target_status_id
            status_changed = True
            logger.info(f'Cascading status_id {target_status_id} from AssetVersion {entity_id} to Task {task["id"]}')
        else:
            logger.info(f'Task {task["id"]} is already in status_id "{target_status_id}". Skipping.')

    if not status_changed:
        return

    # Persist changes
    try:
        session.commit()
    except ftrack_api.exception.ServerError as e:
        # Handle specific validation error: "Object "Task" cannot have status..."
        error_msg = str(e)
        if 'cannot have status' in error_msg:
            logger.warning(f'Validation failed: {error_msg}')
            session.rollback()
            
            if user_id:
                send_message_to_user(
                    session, 
                    user_id, 
                    message='Task missing target status. Please ensure AssetVersion and Task share the same status schema.',
                    success=False
                )
            return
            
        logger.exception('Failed to update Task status')
        session.rollback()
        raise
    except Exception:
        logger.exception('Failed to update Task status')
        session.rollback()
        raise
    
    if not user_id:
        return

    send_message_to_user(
        session, 
        user_id, 
        message='Cascade Status Update: AssetVersion >> Task',
        success=True
    )


def register(session, **kw):
    '''Register event listener.'''

    if not isinstance(session, ftrack_api.Session):
        return

    # Register the event handler
    handle_event = functools.partial(cascade_asset_version_to_task_event_listener, session)
    session.event_hub.subscribe('topic=ftrack.update', handle_event)


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    session = ftrack_api.Session(auto_connect_event_hub=True)
    register(session)
    logging.info('Registered actions and listening for events. Use Ctrl-C to abort.')
    session.event_hub.wait()
