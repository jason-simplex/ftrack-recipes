# :coding: utf-8
# :copyright: Copyright (c) 2014-2022 ftrack


import logging
import ftrack_api
import functools


logger = logging.getLogger("com.ftrack.recipes.cascade_thumbnails_to_parent")

def send_message_to_user(session, user_id):
    '''Send a success message to the active user.

    Use the event hub of *session* to pop up a message for the user with
    *user_id*. (Functionality new in ftrack 3.3.31.)
    '''
    # event 结构体 参考：
    # https://developer.ftrack.com/websocket-events/event-list#ftrackactiontrigger-user-interface
    session.event_hub.publish(
        ftrack_api.event.base.Event(
            topic='ftrack.update',
            data=dict(
                type='message',
                success=True,
                message=(
                    '缩略图更新啦！'
                ),
            ),
            target='applicationId=ftrack.client.web and user.id="{0}"'.format(user_id),
        ),
        on_error='ignore',
    )

def send_broadcast_message(session):
    '''Send a broadcast message to all web clients.'''
    session.event_hub.publish(
        ftrack_api.event.base.Event(
            topic='ftrack.update',
            data=dict(
                type='message',
                success=True,
                message='缩略图已自动更新！'
            ),
            target='applicationId=ftrack.client.web'
        ),
        on_error='ignore',
    )

def cascade_thumbnail(session, event):
    """Handle *event* and cascade thumbnail changes on versions."""
    user_id = event['source'].get('user', {}).get('id', None)
    for entity in event["data"].get("entities", []):
        asset_version = None
        entity_id = None

        # Handle new or updated versions.
        if (
            entity.get("entityType") == "assetversion"
            and entity.get("action") in ("add", "update")
            and entity.get("keys", None)
            and "thumbid" in entity.get("keys", [])
        ):
            entity_id = entity["entityId"]

        # Handle encoded versions.
        if (
            entity.get("action") in ("encoded",)
            and entity.get("entityType") == "assetversion"
        ):
            entity_id = entity["entityId"]

        # If entity was found, try to get it.
        if entity_id:

            # Get asset version and preload data for performance and to avoid
            # caching issues.
            asset_version = session.query(
                "select thumbnail_id, asset, asset.parent, task "
                "from AssetVersion where id is {0}".format(entity["entityId"])
            ).first()
            logger.info(f'using asset version : {asset_version["version"]}')

        if asset_version and asset_version["thumbnail_id"]:
            # Update parent and related task if the thumbnail is set.
            task = asset_version["task"]

            # NOTE: uncomment these lines to also update the parent (shot/sequence/etc...), rather than just the task
            # parent = asset_version["asset"]["parent"]
            # parent["thumbnail_id"] = asset_version["thumbnail_id"]
            # logger.info(f'updating parent : {parent["name"]}')

            if task:
                logger.info(f'updating task: {task["name"]}')
                # 更新 task 的 thumbnail_id
                old_thumbnail_id = task["thumbnail_id"]
                task["thumbnail_id"] = asset_version["thumbnail_id"]
                
                try:
                    session.commit()
                    # 调试：打印user_id信息
                    logger.info(f'User ID from event: {user_id}')
                    
                    if user_id:
                        send_message_to_user(session, user_id)
                        logger.info(f'Message sent to user: {user_id}')
                    else:
                        # 如果没有特定用户，发送广播消息
                        send_broadcast_message(session)
                        logger.info('Broadcast message sent to all web clients')
                        
                except Exception:
                    logger.exception('Failed to update task thumbnail')
                    # Since we failed to synchronize our changes with the server, revert
                    # our state to match what was on the server when we started.
                    session.rollback()
                    raise


    

    


def register(session, **kw):
    """Register event listener."""

    # Validate that session is an instance of ftrack_api.Session. If not,
    # assume that register is being called from an incompatible API
    # and return without doing anything.
    if not isinstance(session, ftrack_api.Session):
        return

    # Register the event handler
    handle_event = functools.partial(cascade_thumbnail, session)
    session.event_hub.subscribe("topic=ftrack.update", handle_event)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    session = ftrack_api.Session(auto_connect_event_hub=True)
    register(session)
    logging.info("Registered actions and listening for events. Use Ctrl-C to abort.")
    session.event_hub.wait()
