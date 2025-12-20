# :coding: utf-8
# :copyright: Copyright (c) 2018 ftrack

import functools
import logging

import ftrack_api


# logging.info()：用来直接向根日志记录器记录消息，方便简单用法。
# logger.info()：用来在自定义日志记录器上记录消息，提供更大的灵活性和控制能力。
logger = logging.getLogger('com.ftrack.recipes.cascade_status_change')

# 检查同项目下的 Shot 类型的 statuses 列表，
# 如果 shot 的 status 的 state 字段与传入 task 的 state 匹配，则返回 Shot 的 status
def get_status_by_state(project, state):
    '''Return a valid Status which matches *state*, for the given *project*.

    Raise an exception if the Shot Schema for *project* has no Status with the
    given *state*.
    '''
    # 从 project 实体中获取 project_schema 实体，然后获取 Shot 类型的 statuses 列表。
    # 利用 API 提供的实例方法 get_statuses() 来获取 statuses 列表。
    # 如果 status 的 state 字段与传入的 state 匹配，则返回该 status。
    # 如果没有找到匹配的状态，则抛出一个 ValueError 异常。
    for status in project['project_schema'].get_statuses('Shot'):
        if status['state']['short'] == state:
            return status

    raise ValueError(
        'No valid Shot status matching state {} for project {}'.format(
            state, project['full_name']
        )
    )

# 这个函数检查是否是 task 实体，action 是 add 或者 update，keys 中有 statusid，
# 最后 return 的是 True 或者 False，如果是 True 则表示状态发生了变化，需要更新。
def is_status_change(entity):
    '''Return if updated *entity* is a status change.'''
    is_task_entity = entity['entityType'] == 'task'
    is_add_update = entity.get('action') in ('add', 'update')
    is_status_change = 'statusid' in entity.get('keys', [])
    return is_task_entity and is_add_update and is_status_change

# 这个函数检查task的 status 的 state 字段状态，
# 返回 'BLOCKED', 'DONE', 'IN_PROGRESS', 'NOT_STARTED' 中的一个，如果没有状态，则返回 None。
def get_state_name(task):
    '''Return the short name of *task*'s state, if valid, othertwise None.'''
    try:
        state = task['status']['state']['short']
    except KeyError:
        logger.info(
            # 使用 ftrack_api.inspection.identity() 函数返回一个元组
            # (entity_type, entity_id) 用于标识一个 entity。
            # 类似 ('Task', ['00009810-1531-4db9-aab0-bf405294440d'])
            'Child {} has no status'.format(ftrack_api.inspection.identity(task))
        )
        return
    if state not in ('BLOCKED', 'DONE', 'IN_PROGRESS', 'NOT_STARTED'):
        logger.warning('Unknown state returned: {}'.format(state))
        return
    return state

# 检查传入的 shot 和 那些属于它的 tasks ，基于 task 的状态，返回 shot 的新状态 id
def get_new_shot_status(shot, tasks):
    '''Update *shot* based on status of *tasks*.

    Given a *shot* and a list of *tasks* belonging to that shot, determine
    the shots' status based on the task status'.
    '''
    logger.info('Current shot status: {}'.format(shot['status']['name']))

    # 把众多 tasks 的状态都取出来，并去重, 得到一个 set
    task_states = set(
        [get_state_name(task) for task in tasks],
    )
    # 去掉 None，因为 None 表示没有状态
    task_states.discard(None)
    project = shot['project']
    new_status = None

    if task_states == set(
        ['DONE'],
    ):
        new_status = get_status_by_state(project, 'DONE')
    elif task_states == set(
        ['NOT_STARTED'],
    ):
        new_status = get_status_by_state(project, 'NOT_STARTED')

    elif 'BLOCKED' in task_states:
        new_status = get_status_by_state(project, 'BLOCKED')
    elif 'IN_PROGRESS' in task_states:
        new_status = get_status_by_state(project, 'IN_PROGRESS')

    if new_status is None:
        logger.info('No appropriate state to set')
        return None
    logger.info(
        'New shot status is {} ({})'.format(new_status['name'], new_status['id'])
    )
    return new_status['id']

# 成功执行时，给用户发送一条消息
def send_message_to_user(session, user_id):
    '''Send a success message to the active user.

    Use the event hub of *session* to pop up a message for the user with
    *user_id*. (Functionality new in ftrack 3.3.31.)
    '''
    # event 结构体 参考：
    # https://developer.ftrack.com/websocket-events/event-list#ftrackactiontrigger-user-interface
    session.event_hub.publish(
        ftrack_api.event.base.Event(
            topic='ftrack.action.trigger-user-interface',
            data=dict(
                type='message',
                success=True,
                message=(
                    'cascade_status_changes: ' 'Shot status updated automatically'
                ),
            ),
            target='applicationId=ftrack.client.web and user.id="{0}"'.format(user_id),
        ),
        on_error='ignore',
    )


# 监听的主函数，监听 ftrack.update 事件，如果有状态变化，则更新 shot 状态。
def cascade_status_changes_event_listener(session, event):
    '''Handle *event*.'''
    user_id = event['source'].get('user', {}).get('id', None)
    status_changed = False

    entities = event['data'].get('entities', [])

    for entity in entities:
        # 先看是不是 task 实体，action 是 add 或者 update，keys 中有 statusid
        # 如果不是，返回 for 循环继续下一个 entity
        if not is_status_change(entity):
            continue
        
        # 接着在遍历中取 ['entityId'] 字段，得到 task 的 id
        entity_id = entity['entityId']
        # 然后根据 task 的 id，查询出其父级的 shot 实体
        shot = session.query(
            'select status_id, status.name from Shot '
            'where children any (id is "{0}")'.format(entity_id)
        ).first()
        
        if shot:
            # 如果成功取到 shot 实体，则根据shot 找到其下方所有的 tasks
            tasks = session.query(
                'select type.name, status.state.short from Task '
                'where parent_id is "{}"'.format(shot['id'])
            )
            # 检查传入的 shot 和 那些属于它的 tasks ，基于 task 的状态，返回 shot 的新状态 id
            new_shot_status_id = get_new_shot_status(shot, tasks)
            if shot['status_id'] == new_shot_status_id:
                # 如果 shot 的状态没有变化，则返回 for 循环继续下一个 entity
                logger.info('Status is unchanged.')
                continue
            if new_shot_status_id is None:
                # 如果 shot 的状态是空，则返回 for 循环继续下一个 entity
                continue

            # 如果确实是有效的 shot 新状态，那么就把 Shot 的状态 id 更新掉
            # 同时把 status_changed 置为 True
            shot['status_id'] = new_shot_status_id
            status_changed = True

        else:
            logger.info('No shot found, ignoring update')

    # 如果 status_changed 为 True，那么条件 not status_changed 将为 False，
    # 代码将不会执行 return 语句，从而继续往下执行。
    # 也就是说，如果状态有改变，则执行 session.commit() 语句，
    # 否则，直接返回。
    if not status_changed:
        return

    # Persist changes
    try:
        session.commit()
    except Exception:
        logger.exception('Failed to update status')
        # Since we failed to synchronize our changes with the server, revert
        # our state to match what was on the server when we started.
        session.rollback()
        raise
    
    # 如果用户 id 存在，则发送一条成功消息到用户的消息中心
    # 否则，什么也不做
    if not user_id:
        return

    send_message_to_user(session, user_id)

# 因为 **kw 是可选的。当你没有提供任何额外的参数时，kw 将会是一个空字典 ({})。
def register(session, **kw):
    '''Register event listener.'''

    # Validate that session is an instance of ftrack_api.Session. If not,
    # assume that register is being called from an incompatible API
    # and return without doing anything.
    if not isinstance(session, ftrack_api.Session):
        return

    # Register the event handler
    # 通过使用 functools.partial，你可以将 session 绑定到 handle_event，
    # 使得在事件发生时，只传递 event 参数即可：
    # 这正好符合 def callback(event): 这个函数的定义要求 
    handle_event = functools.partial(cascade_status_changes_event_listener, session)
    session.event_hub.subscribe('topic=ftrack.update', handle_event)


if __name__ == '__main__':
    # 设置日志记录级别：level=logging.INFO 指定了日志记录的最低级别为 INFO。
    # 这意味着所有级别高于或等于 INFO 的日志消息将被处理和显示。
    # basicConfig 会创建一个默认的日志处理器并将其附加到根日志记录器上。
    # 这样，你可以直接使用 logging.info(), logging.warning() 等函数来记录消息，而不用手动设置处理器。
    logging.basicConfig(level=logging.INFO)
    # Remember, in version version 2.0 of the ftrack-python-api the default
    # behavior will change from True to False.
    session = ftrack_api.Session(auto_connect_event_hub=True)
    register(session)
    logging.info('Registered actions and listening for events. Use Ctrl-C to abort.')
    session.event_hub.wait()
