# :coding: utf-8
# :copyright: Copyright (c) 2018 ftrack

import os
import sys
import logging

import ftrack_api

# 此脚本的作用是：无论是通过 action 还是通过 ftrack- connect 启动的 插件，都能自动加载  custom_location_plugin.py 插件。
# 核心方法 modify_application_launch(event): 把 location 插件的路径添加到环境变量中，event['data']['options']['env'] 中。







# os.path.dirname(__file__) 得到当前文件的绝对路径，作为connect 的插件在它运行时它在
# /Users/jason/Library/Application\ Support/ftrack-connect-plugins/migrate-components-24.6.0/hook
# 然后os.path.join() 里用 '..' 得到上级目录的绝对路径，再加上 'location' 得到 location 插件的绝对路径：
# /Users/jason/Library/Application\ Support/ftrack-connect-plugins/migrate-components-24.6.0/location
# 给它定义成全局变量，方便后面使用
# 最终这个全局变量表明的是 location 目录下 custom_location_plugin.py 插件的绝对路径
LOCATION_DIRECTORY = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..', 'location')
)

# 用 sys 方法添加 location 插件文件夹的路径到python解释器的搜索路径中，
# 这样connect 的 python解释器 发现并运行 hook 目录下的脚本同时
# 也能找到 custom_location_plugin.py 这个location 插件
sys.path.append(LOCATION_DIRECTORY)

# 定义了一个名为 com.ftrack.recipes.customise_structure.hook 的日志记录器
logger = logging.getLogger('com.ftrack.recipes.customise_structure.hook')



def append_path(path, key, environment):
    '''Append *path* to *key* in *environment*.'''
    # os.pathsep 是一个字符串，表示当前操作系统的路径分隔符。
    # os.pathsep.join() 的参数是一个数组（或列表），用于将多个路径组合成一个字符串
    # 不同操作系统的路径分隔符可能不同，所以这里使用 os.pathsep.join 方法来拼接路径
    try:
        environment[key] = (
            os.pathsep.join([
                environment[key], path
            ])
        )

    # 这种处理方式确保了即使在 environment 中没有 key 的情况下，
    # 也能正确地将 path 添加到 environment 中。
    except KeyError:
        environment[key] = path

    return environment


def modify_application_launch(event):
    '''Modify the application environment to include  our location plugin.'''
    # event['data'] 字典里原本没有 'options' 下的 'env' 键值对，所以这里需要先判断一下
    # 如果没有 'env' 键值对，则直接添加进去
    # 如果有 'env' 键值对，则需要先把它的值取出来，然后再把 location 插件的路径添加到它后面
    # 最后再把修改后的 'env' 键值对放回 event['data']['options'] 中
    # 所以这段代码到最后是给 event 做了一次修改
    # event['data'] 字典的结构如下：
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
    environment = event['data'].get('options', {}).get('env', {})

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

    logger.info('Connect plugin discovered.')

    # 因为顶部定义了 sys.path.append(LOCATION_DIRECTORY)，所以这里可以直接导入 custom_location_plugin 模块
    import custom_location_plugin
    # 在 custom_location_plugin.py 中定义了 register 函数， 所以可以直接调用它
    custom_location_plugin.register(session)


    # 订阅 ftrack.connect.application.launch 和 ftrack.action.launch 两个事件
    # 这两个事件会在用户启动 dcc 应用或者执行 action 时触发 modify_application_launch 函数
        # Location will be available from within the dcc applications.
    session.event_hub.subscribe(
        'topic=ftrack.connect.application.launch', modify_application_launch
    )

        # Location will be available from actions
    session.event_hub.subscribe(
        'topic=ftrack.action.launch', modify_application_launch
    )
