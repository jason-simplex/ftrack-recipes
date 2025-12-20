# :coding: utf-8
# :copyright: Copyright (c) 2019 ftrack

import os
import sys
import functools
import logging

import ftrack_api
import ftrack_api.accessor.disk
import ftrack_api.structure.standard

logger = logging.getLogger(
    'com.ftrack.recipes.multi_site_location.custom_location_plugin'
)

# retrieve current location from the environment variables
# 这个环境变量 FTRACK_LOCATION 需要预先配置一下

current_location = os.environ.get('FTRACK_LOCATION')


def configure_location(session, location_setup, event):
    
    '''Configure location based on *location_setup*.'''
    # dict.items(), 
    # dict.keys(), 
    # dict.values() 返回的都是视图对象,不能直接遍历,需要先转换成列表
    # 用 list(location_setup.items()) 转换成列表,由于列表里每一个元素都是元组,所以可以解包成键和值
    '''比如：
    原本这是个字典 location_setup =   
    {
	'custom.location1': {
		'linux2': '/remote/location/one', 
		'win32': 'Z:\\ftrack\\project_loc1', 
		'darwin': '/net/remote/location/one'
		}, 
	'custom.location2': {
		'linux2': '/remote/location/two', 
		'win32': 'Z:\\ftrack\\project_loc2', 
		'darwin': '/net/remote/location/two'
		}
    }

    那么 location_setup.items() 就是视图对象 , 列表里的元素是元组。
    每个元组的第一个元素是原来字典的键,第二个元素是原来字典的值
    dict_items(
	[
	('custom.location1', {'linux2': '/remote/location/one', 'win32': 'Z:\\ftrack\\project_loc1', 'darwin': '/net/remote/location/one'}), 
	('custom.location2', {'linux2': '/remote/location/two', 'win32': 'Z:\\ftrack\\project_loc2', 'darwin': '/net/remote/location/two'})
	]
)

    只有在 list(location_setup.items()) 之后才是列表,才可以被遍历
    [
    ('custom.location1', {'linux2': '/remote/location/one', 'win32': 'Z:\\ftrack\\project_loc1', 'darwin': '/net/remote/location/one'}), 
    ('custom.location2', {'linux2': '/remote/location/two', 'win32': 'Z:\\ftrack\\project_loc2', 'darwin': '/net/remote/location/two'})
    ]
           
    sys.platform 是 Python 标准库中的一个模块 sys 提供的属性,
        用于获取当前运行 Python 解释器的操作系统平台标识符。
        这个标识符可以帮助你编写跨平台的代码,根据不同的操作系统执行不同的操作。
        常见的 sys.platform 返回值包括：
        'linux': Linux 系统
        'win32': Windows 系统（无论是 32 位还是 64 位）
        'darwin': macOS 系统
        'cygwin': Cygwin 环境(Windows 上的类 Unix 环境)
        'freebsd': FreeBSD 系统
    ''' 

    for location_name, disk_prefixes in list(location_setup.items()):
        '''Get mount point for the correct os in use'''
        '''
        解包之后  disk_prefixes 依然是个字典,包含多个操作系统的盘符前缀
        所以要选择当前 os 的盘符前缀,需要用get()从字典里提取当前的操作系统 
        而当前的 os 由 sys.platform 表示
        '''
        disk_prefix = disk_prefixes.get(sys.platform)

        # 如果disk_prefix为空,那么就不配置这个location,并跳转回for循环继续下一个location
        if not disk_prefix:
            logger.error(
                'No disk prefix configured for location {0}'.format(location_name)
            )
            continue

        # 如果disk_prefix不存在或者不是个目录,那么就不配置这个location,并记录到报错日志
        # 并跳转回for循环继续下一个location
        if not os.path.exists(disk_prefix) or not os.path.isdir(disk_prefix):
            logger.error(
                'Disk prefix for location {} does not exist.'.format(location_name)
            )
            continue
        
        # 遇到符合条件的location,就配置这个location
        # session.ensure()可以在创建之前先判断是否存在,如果存在,则不再创建
        location = session.ensure('Location', {'name': location_name})

        # 配置 location 的访问器和结构,盘符前缀是必须参数,用上面获取到的disk_prefix
        location.accessor = ftrack_api.accessor.disk.DiskAccessor(prefix=disk_prefix)
        location.structure = ftrack_api.structure.standard.StandardStructure()

        # current_location 获取自环境变量,如果当前location是这个,则优先级设为1,否则为10
        # 也就是保持当前的 location 优先级为高,其他的 location 优先级为低
        if location_name == current_location:
            location.priority = 1  # lower value == higher priority !
        else:
            location.priority = 10

        logger.warning(
            'Registered location {0} at {1} with priority {2}'.format(
                location_name, disk_prefix, location.priority
            )
        )


def register(session, location_setup=None):
    '''Register location with *session*.'''

    # Validate that session is an instance of ftrack_api.Session. If not,
    # assume that register is being called from an incompatible API
    # and return without doing anything.
    if not isinstance(session, ftrack_api.Session):
        return

    session.event_hub.subscribe(
        'topic=ftrack.api.session.configure-location',
        functools.partial(configure_location, session, location_setup),
    )
