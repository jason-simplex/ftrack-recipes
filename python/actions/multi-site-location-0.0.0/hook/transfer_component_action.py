# :coding: utf-8
# :copyright: Copyright (c) 2019 ftrack

import json
import sys
import argparse
import logging
import threading
import collections

import ftrack_api
import ftrack_api.exception
from ftrack_action_handler.action import BaseAction

SUPPORTED_ENTITY_TYPES = ('AssetVersion', 'TypedContext', 'Project', 'Component')

# _async 装饰器用于将传入的函数 fn 包装为异步执行。
# 它通过创建一个新的线程来运行该函数，允许程序在函数运行的同时继续执行后续代码。
def _async(fn):
    '''Run *fn* asynchronously.'''

    def wrapper(*args, **kwargs):
        thread = threading.Thread(target=fn, args=args, kwargs=kwargs)
        thread.start()

    return wrapper


def get_filter_string(entity_ids):
    '''Return a comma separated string of quoted ids from *entity_ids* list.'''
    # 这个方法最后生成的字符串类似："722c847a-eb79-48bc-a98a-a3f52ff52def", "da96cec2-3825-43e4-a829-b5ebeeef1546" , "e8a0acee-755c-480d-a0b6-1adf0e218aa6"
    # 用 “” 包裹 entity_ids 列表中的每一个元素，并用逗号分隔起来，以便于在 SQL 语句中使用。
    return ', '.join('"{0}"'.format(entity_id) for entity_id in entity_ids)


class TransferComponentsAction(BaseAction):
    '''Action to transfer components between locations.'''

    #: Action identifier.
    identifier = 'transfer-components'

    #: Action label.
    label = 'Transfer component(s)'

    #: Action description.
    description = 'Transfer component(s) between locations.'

    #: Excluded Locations
    excluded_locations = ['ftrack.origin', 'ftrack.connect']

    '''如果被允许的可执行实体有很多种，用这个方法判读当前选择的实体是否合法。'''
    def validate_entities(self, entities):
        '''Return if *entities* is valid.'''
        # all(iterable)
        # iterable：一个可迭代对象（如列表、元组、集合等），其中的元素将被检查是否都为真。
        # all() 函数用于确保 entities 中的所有实体类型都在支持的类型列表中。
        if len(entities) >= 1 and all(
            # 先 for entity_type, _ in entities 从 entities 中取出 entity_type 再判断是否在 SUPPORTED_ENTITY_TYPES 中。
            # 每一次遍历都返回一个布尔值，如果所有遍历结果为真，则会创建一个列表 类似[ True, True, True]
            # 再由 all() 函数判断列表中是否有 False，如果有 False，则返回 False，否则返回 True。
            [entity_type in SUPPORTED_ENTITY_TYPES for entity_type, _ in entities]
        ):
            self.logger.info('Selection is valid')
            return True
        else:
            self.logger.info('Selection is _not_ valid')
            return False

    def discover(self, session, entities, event):
        '''Return True if action is valid.'''
        self.logger.info('Discovering action with entities: {0}'.format(entities))
        return self.validate_entities(entities)

    def get_components_in_location(self, session, entities, location):
        '''Return list of components in *entities*.'''
        component_queries = []
        # collections.defaultdict创建了一个字典，其默认值为 list
        # 这意味着当你访问 entity_groups 中的一个不存在的键时，
        # 它会自动创建该键，并将其值初始化为一个空列表。
        # 比如 entity_groups['Project'] 这样的访问方式，
        # 即使之前没有过 'Project' ,'TypedContext' 等等这类键，也会自动创建它并返回一个空列表 [] 
        
        entity_groups = collections.defaultdict(list)
        
        # entity_groups 用于将不同类型的实体分组存储。
        # 具体来说，它会将相同类型的实体 ID 存储在同一个列表中。
        for entity_type, entity_id in entities:
            entity_groups[entity_type].append(entity_id)
        
        ''' 可以创建出类似这样的 entity_group 字典：
        {
        'Project': ['722c847a-eb79-48bc-a98a-a3f52ff52def','da96cec2-3825-43e4-a829-b5ebeeef1546',], 
        'TypedContext': ['e778a9dc-ac91-4acb-a37b-4e7bbb0f01e6','dc3b7110-ba93-416a-9bc8-d5ddfd6562ae',], 
        'AssetVersion': ['e8a0acee-755c-480d-a0b6-1adf0e218aa6','e8a0acee-755c-480d-a0b6-1adf0e218aa6',], 
        'Component': ['5f622178-b301-4b55-8825-ec6887e4235b','50890d05-e823-4645-93fb-f3743673a860',]
        }
        '''

        # 可以把 entity_groups 字典中的值['Project']取出，并用逗号分隔，生成一个字符串，比如：
        # "722c847a-eb79-48bc-a98a-a3f52ff52def", "da96cec2-3825-43e4-a829-b5ebeeef1546"
         
        '''最后得到 component_queries 这个列表类似:
        ['Component where (version.asset.parent.project.id in 
         ("722c847a-eb79-48bc-a98a-a3f52ff52def", "da96cec2-3825-43e4-a829-b5ebeeef1546")
         or version.asset.parent.id in
          ("722c847a-eb79-48bc-a98a-a3f52ff52def", "da96cec2-3825-43e4-a829-b5ebeeef1546"))'
           ]
           '''
        if entity_groups['Project']:
            component_queries.append(
                'Component where (version.asset.parent.project.id in ({0}) or '
                'version.asset.parent.id in ({0}))'.format(
                    get_filter_string(entity_groups['Project'])
                )
            )

        # 可以把 entity_groups 字典中的值['TypedContext']取出，并用逗号分隔，生成一个字符串，比如：
        # "e778a9dc-ac91-4acb-a37b-4e7bbb0f01e6", "dc3b7110-ba93-416a-9bc8-d5ddfd6562ae"
        '''最后得到 component_queries 这个列表类似: 
        ['Component where (version.asset.parent.ancestors.id in
         ("e778a9dc-ac91-4acb-a37b-4e7bbb0f01e6", "dc3b7110-ba93-416a-9bc8-d5ddfd6562ae")
          or version.asset.parent.id in
           ("e778a9dc-ac91-4acb-a37b-4e7bbb0f01e6", "dc3b7110-ba93-416a-9bc8-d5ddfd6562ae"))',
            ]
        '''
        if entity_groups['TypedContext']:
            component_queries.append(
                'Component where (version.asset.parent.ancestors.id in ({0}) or '
                'version.asset.parent.id in ({0}))'.format(
                    get_filter_string(entity_groups['TypedContext'])
                )
            )

        # 可以把 entity_groups 字典中的值['AssetVersion']取出，并用逗号分隔，生成一个字符串，比如：
        # "e8a0acee-755c-480d-a0b6-1adf0e218aa6", "e8a0acee-755c-480d-a0b6-1adf0e218aa6"
        '''最后得到 component_queries 这个列表类似: 
        ['Component where version_id in
         ("e8a0acee-755c-480d-a0b6-1adf0e218aa6", "e8a0acee-755c-480d-a0b6-1adf0e218aa6")'
         ]
        '''
        if entity_groups['AssetVersion']:
            component_queries.append(
                'Component where version_id in ({0})'.format(
                    get_filter_string(entity_groups['AssetVersion'])
                )
            )

        # 可以把 entity_groups 字典中的值['Component']取出，并用逗号分隔，生成一个字符串，比如：
        # "5f622178-b301-4b55-8825-ec6887e4235b", "50890d05-e823-4645-93fb-f3743673a860"
        '''最后得到 component_queries 这个列表类似: 
        ['Component where id in
         ("5f622178-b301-4b55-8825-ec6887e4235b", "50890d05-e823-4645-93fb-f3743673a860")'
         ]
         '''
        if entity_groups['Component']:
            component_queries.append(
                'Component where id in ({0})'.format(
                    get_filter_string(entity_groups['Component'])
                )
            )
        
        '''到此 component_queries 这个大列表，里面包含了所有符合条件的 components 的查询 SQL 语句
        id的 “” 以及分隔用的 , 都是来自于 get_filter_string() 方法：

        ['Component where (version.asset.parent.project.id in 
         ("722c847a-eb79-48bc-a98a-a3f52ff52def", "da96cec2-3825-43e4-a829-b5ebeeef1546")
         or version.asset.parent.id in
          ("722c847a-eb79-48bc-a98a-a3f52ff52def", "da96cec2-3825-43e4-a829-b5ebeeef1546"))',

        'Component where (version.asset.parent.ancestors.id in
         ("e778a9dc-ac91-4acb-a37b-4e7bbb0f01e6", "dc3b7110-ba93-416a-9bc8-d5ddfd6562ae")
          or version.asset.parent.id in
           ("e778a9dc-ac91-4acb-a37b-4e7bbb0f01e6", "dc3b7110-ba93-416a-9bc8-d5ddfd6562ae"))',

        'Component where version_id in
         ("e8a0acee-755c-480d-a0b6-1adf0e218aa6", "e8a0acee-755c-480d-a0b6-1adf0e218aa6")',

        'Component where id in
         ("5f622178-b301-4b55-8825-ec6887e4235b", "50890d05-e823-4645-93fb-f3743673a860")'
         ]
         '''       
        # 创建一个 set 集合，特性是无序的，不重复的元素集合作为 components 的容器。
        components = set()
        for query_string in component_queries:
            # set.update（iterable1, iterable2, ...）是 set 对象的一个方法，
            # 用于将一个或多个可迭代对象中的元素添加到当前集合中。它没有返回值，直接修改当前集合。
            # 遍历 component_queries 列表，每一个元素都是一个 SQL 语句，配合location_id 进行查询。
            # 每遍历一次就向 components 集合中添加一批 components 对象。
            components.update(
                session.query(
                    '{0} and component_locations.location_id is "{1}"'.format(
                        query_string, location['id']
                    )
                ).all()
            )

        self.logger.info('Found {0} components in selection'.format(len(components)))
        # 转换集合称为列表，并返回。
        return list(components)

    @_async
    def transfer_components(
        self,
        entities,
        source_location,
        target_location,
        user_id=None,
        ignore_component_not_in_location=False,
        ignore_location_errors=False,):
        
        '''Transfer components in *entities* from *source_location*.

        if *ignore_component_not_in_location*, ignore components missing in
        source location. If *ignore_location_errors* is specified, ignore all
        locations-related errors.

        Reports progress back to *user_id* using a job.

        '''
        '''这个方法的作用是异步执行，并将结果返回给调用者。
        代码结构上总的来说可以被分解为 3 个部分：
        1. 创建 job 对象，并设置状态为 running。提示用户正在进行数据传输。
        2. 在 try 块中，用 for 遍历有效的 components, 
        每次遍历都通过 job 提示用户正在传输第几个 component。并在 try 中进行传输， except 处理异常
        3. 在 except 块中，抛出基础异常，并设置 job 状态为 failed。并回滚事务。
        
        
        '''
        session = ftrack_api.Session(auto_connect_event_hub=False)
        job = session.create(
            'Job',
            {
                'user_id': user_id,
                'status': 'running',
                # 在当前的 api 版本里 'data' 需要被 json 序列化。
                'data': json.dumps(
                    {'description': 'Transfer components (Gathering...)'}
                ),
            },
        )
        session.commit()
        try:
            components = self.get_components_in_location(
                session, entities, source_location
            )
            amount = len(components)
            self.logger.info('Transferring {0} components'.format(amount))

            for index, component in enumerate(components, start=1):
                self.logger.info(
                    'Transferring component ({0} of {1})'.format(index, amount)
                )
                job['data'] = json.dumps(
                    {
                        'description': 'Transfer components ({0} of {1})'.format(
                            index, amount
                        )
                    }
                )
                session.commit()

                try:
                    target_location.add_component(component, source=source_location)
                except ftrack_api.exception.ComponentInLocationError:
                    self.logger.info(
                        'Component ({}) already in target location'.format(component)
                    )
                except ftrack_api.exception.ComponentNotInLocationError:
                    if ignore_component_not_in_location or ignore_location_errors:
                        self.logger.exception('Failed to add component to location')
                    else:
                        raise
                except ftrack_api.exception.LocationError:
                    if ignore_location_errors:
                        self.logger.exception('Failed to add component to location')
                    else:
                        raise

            job['status'] = 'done'
            session.commit()

            self.logger.info('Transfer complete ({0} components)'.format(amount))

        except BaseException:
            self.logger.exception('Transfer failed')
            session.rollback()
            job['status'] = 'failed'
            session.commit()

    def launch(self, session, entities, event):
        '''Launch edit meta data action.'''
        self.logger.info('Launching action with selection: {0}'.format(entities))
        values = event['data']['values']
        self.logger.info('Received values: {0}'.format(values))

        # values 的这 2 个键值来自interface()方法捕捉到的用户输入。
        source_location = session.get('Location', values['from_location'])
        target_location = session.get('Location', values['to_location'])
        if source_location == target_location:
            return {
                'success': False,
                'message': 'Source and target locations are the same.',
            }
        # 括号里在做真伪判断，并把最后判断出来的的结果给 左边的变量。
        ignore_component_not_in_location = (
            values.get('ignore_component_not_in_location') == 'true'
        )
        ignore_location_errors = values.get('ignore_location_errors') == 'true'

        self.logger.info(
            'Transferring components from {0} to {1}'.format(
                source_location, target_location
            )
        )
        user_id = event['source']['user']['id']
        self.transfer_components(
            entities,
            source_location,
            target_location,
            user_id=user_id,
            ignore_component_not_in_location=ignore_component_not_in_location,
            ignore_location_errors=ignore_location_errors,
        )
        return {'success': True, 'message': 'Transferring components...'}




    # 这个在用户提交选项后，event['data']['values'] 会被赋值类似于:
    # {
    # 'from_location':'ID', 'to_location':'ID', 
    # 'ignore_component_not_in_location':'true', 
    # 'ignore_location_errors':'true'
    # }
    def interface(self, session, entities, event):
        '''Return interface.'''
        values = event['data'].get('values', {})
        # 当 event['data']['values'] 为空时，查询所有带有 accessor 的 location
        # 遍历所有 location，并把所有带有 accessor 的 location 放入一个列表 locations
        if not values:
            locations = [
                location
                for location in session.query('select name, label from Location').all()
                if location.accessor
            ]
            # 按照 priority 排序
            # Sort by priority.
            # `lambda arguments: expression`` 使用匿名函数，返回一个可调用对象。
            # 这里的 lambda 函数接收一个 location 对象，返回 location.priority 值。
            locations = sorted(locations, key=lambda location: location.priority)

            # Remove built in locations
            locations = [
                location
                for location in locations
                if location['name'] not in self.excluded_locations
            ]
            self.logger.info(locations)

            # 这个列表中的每一个元素都是一个字典，包含 label 和 value 两个键值对。
            # 未来会作为 enumerator 类型的 data 多选项提供给用户。
            locations_options = [
                {
                    'label': location['label'] or location['name'],
                    'value': location['id'],
                }
                for location in locations
            ]
            return [
                {'value': 'Transfer components between locations', 'type': 'label'},
                {
                    'label': 'Source location',
                    'type': 'enumerator',
                    'name': 'from_location',
                    'value': locations_options[0]['value'],
                    'data': locations_options,
                },
                {
                    'label': 'Target location',
                    'type': 'enumerator',
                    'name': 'to_location',
                    'value': locations_options[1]['value'],
                    'data': locations_options,
                },
                {'value': '---', 'type': 'label'},
                {
                    'label': 'Ignore missing',
                    'type': 'enumerator',
                    'name': 'ignore_component_not_in_location',
                    'value': 'false',
                    'data': [
                        {'label': 'Yes', 'value': 'true'},
                        {'label': 'No', 'value': 'false'},
                    ],
                },
                {
                    'label': 'Ignore errors',
                    'type': 'enumerator',
                    'name': 'ignore_location_errors',
                    'value': 'false',
                    'data': [
                        {'label': 'Yes', 'value': 'true'},
                        {'label': 'No', 'value': 'false'},
                    ],
                },
            ]


def register(session, **kw):
    '''Register plugin. Called when used as an plugin.'''

    # Validate that session is an instance of ftrack_api.Session. If not,
    # assume that register is being called from an old or incompatible API and
    # return without doing anything.
    if not isinstance(session, ftrack_api.session.Session):
        return

    action_handler = TransferComponentsAction(session)
    action_handler.register()


def main(arguments=None):
    '''Set up logging and register action.'''
    if arguments is None:
        arguments = []

    parser = argparse.ArgumentParser()
    # Allow setting of logging level from arguments.
    loggingLevels = {}
    for level in (
        logging.NOTSET,
        logging.DEBUG,
        logging.INFO,
        logging.WARNING,
        logging.ERROR,
        logging.CRITICAL,
    ):
        loggingLevels[logging.getLevelName(level).lower()] = level

    parser.add_argument(
        '-v',
        '--verbosity',
        help='Set the logging output verbosity.',
        choices=list(loggingLevels.keys()),
        default='info',
    )
    namespace = parser.parse_args(arguments)

    # Set up basic logging
    logging.basicConfig(level=loggingLevels[namespace.verbosity])

    session = ftrack_api.Session(auto_connect_event_hub=True)
    register(session)

    # Wait for events
    logging.info('Registered actions and listening for events. Use Ctrl-C to abort.')
    session.event_hub.wait()


# sys.argv 是 Python 的标准库 sys 模块中的一个列表，它保存了命令行参数。
# 第一个参数 sys.argv[0] 保存了脚本的名称，所以我们从 sys.argv[1:] 开始解析参数。

if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
