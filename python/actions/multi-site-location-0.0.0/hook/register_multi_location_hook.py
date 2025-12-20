# :coding: utf-8
# :copyright: Copyright (c) 2019 ftrack

import os
import sys
import logging
import json
import ftrack_api

logger = logging.getLogger('com.ftrack.recipes.multi_site_location.hook')

# 基于当前 register_multi_location_hook.py 的目录定位到 location 插件 custom_location_plugin.py
# 所在的目录 并添加到环境变量 LOCATION_DIRECTORY 中
# 这样connect 的 python解释器 就可以找到 custom_location_plugin.py 这个location 插件
# /Users/jason/Library/Application\ Support/ftrack-connect-plugins/migrate-components-24.6.0/location
CWD = os.path.dirname(__file__)
LOCATION_DIRECTORY = os.path.abspath(os.path.join(CWD, '..', 'location'))

# 用 sys 方法添加 location 插件文件夹的路径到python解释器的搜索路径中，
# 这样connect 的 python解释器 发现并运行 hook 目录下的脚本同时
# 也能找到 custom_location_plugin.py 这个location 插件
sys.path.append(LOCATION_DIRECTORY)

# config 文件是个 .json, 它在当前目录下
# 这个操作是为了可以拿到 locations.json 文件的绝对路径，作为connect的插件在运行时，
# /Users/jason/Library/Application\ Support/ftrack-connect-plugins/multi-site-location-24.6.0/hook/locations.json
LOCATIONS_CONFIG_FILE_PATH = os.path.abspath(os.path.join(CWD, 'locations.json'))


def append_path(path, key, environment):
    '''Append *path* to *key* in *environment*.'''

    # 如果 environment[key] 已经存在，使用 os.pathsep.join() 连接路径
    # 也就是说在保留原来路径的同时，再追加新的路径
    # 两个路径之间用 os.pathsep 分隔
    # 这也是向一个空字典直接添加键值对的过程
    try:
        environment[key] = (
            os.pathsep.join([
                environment[key], path
            ])
        )
    # 如果 environment[key] 不存在，直接赋值
    # 这也是向一个空字典直接添加键值对的过程
    except KeyError:
        environment[key] = path

    return environment


# with 语句用于确保文件在使用完毕后被正确关闭，
# 即使在处理文件过程中发生错误。这种写法利用了上下文管理，简化了文件的操作。
# 这两行代码是从指定的 JSON 文件中读取数据并解析为 Python 对象，以便在代码中使用这些数据。
with open(LOCATIONS_CONFIG_FILE_PATH) as json_file:
    LOCATIONS_DATA = json.load(json_file)


def modify_application_launch(event):
    '''Modify the application environment to include  our location plugin.'''
    # event['data'] 字典里原本没有 'options' 下的 'env' 键值对
    # 因为没有 'env' 键值对，所以直接创建一个空字典
    # 所以这段代码到最后是给 event 做了一次修改
    # 最后要实现的 event['data'] 字典的结构如下：
    # {
    # 'options' :
    #     {
    #     'env' :
    #         {
    #         'FTRACK_EVENT_PLUGIN_PATH': LOCATION_DIRECTORY,
    #         'PYTHONPATH': LOCATION_DIRECTORY
    #         }
    #     }
    # }    

    if 'options' not in event['data']:
        event['data']['options'] = {'env': {}}

    environment = event['data']['options']['env']

    append_path(
        LOCATION_DIRECTORY, 'FTRACK_EVENT_PLUGIN_PATH', environment
    )
    append_path(LOCATION_DIRECTORY, 'PYTHONPATH', environment)
    logger.info('Connect plugin modified launch hook to register location plugin.')


def register(session, **kw):
    '''Register plugin to session.'''

    # Validate that session is an instance of ftrack_api.Session. If not,
    # assume that register is being called from an incompatible API
    # and return without doing anything.
    if not isinstance(session, ftrack_api.Session):
        # Exit to avoid registering this plugin again.
        return
    
    # 因为顶部定义了 sys.path.append(LOCATION_DIRECTORY)，所以这里可以直接导入 custom_location_plugin 模块
    import custom_location_plugin

    custom_location_plugin.register(session, location_setup=LOCATIONS_DATA)

    # Location will be available from within the dcc applications.
    session.event_hub.subscribe(
        'topic=ftrack.connect.application.launch', modify_application_launch
    )

    # Location will be available from actions
    session.event_hub.subscribe(
        'topic=ftrack.action.launch', modify_application_launch
    )
