# :coding: utf-8
# :copyright: Copyright (c) 2018 ftrack

import os
import functools
import logging

import ftrack_api
import ftrack_api.accessor.disk
import ftrack_api.structure.standard


# 此脚本的作用是注册一个自定义的 location 对象， 并给这个 location 添加一个 accessor 和 structure。
# 这里的 accessor 是 DiskAccessor， 它可以访问磁盘上的文件。
# 这里的 structure 是 StandardStructure， 它可以将文件按照标准的结构组织起来。
# 最后，我们设置 location 的优先级为 2， 低于 storage scenario 的优先级。
# 注册机制是 当 session 连通时，由于 'topic=ftrack.api.session.configure-location' 事件， 
# 继而触发了 configure_location() 函数， 该函数会注册 location。

logger = logging.getLogger('com.ftrack.recipes.location.custom_location_plugin')

# Name of the location plugin.
LOCATION_NAME = None

# Disk mount point.
DISK_PREFIX = None


def configure_location(session, event):
    '''Listen.'''
    location = session.ensure('Location', {'name': LOCATION_NAME})

    # 实例化一个类时所带的参数是传递给类的构造函数 __init__ 的参数。这里的 prefix 参数将被传递给 DiskAccessor 构造函数。
    location.accessor = ftrack_api.accessor.disk.DiskAccessor(prefix=DISK_PREFIX)

    # use the same structure as the storage scenario.
    location.structure = ftrack_api.structure.standard.StandardStructure()
    location.priority = 2  # lower than storage scenario

    logger.info('Registered location {0} at {1}.'.format(LOCATION_NAME, DISK_PREFIX))


def register(session, **kw):
    '''Register location with *session*.'''

    if not isinstance(session, ftrack_api.Session):
        return

    if not DISK_PREFIX:
        logger.error('No disk prefix configured for location.')
        return

    # 这种结合使用的方式可以确保在进行目录操作之前，路径是有效的并且确实是一个目录。
    if not os.path.exists(DISK_PREFIX) or not os.path.isdir(DISK_PREFIX):
        logger.error('Disk prefix location does not exist.')
        return

    session.event_hub.subscribe(
        # 该事件是同步的。由 session 发布以允许配置位置实例：
        # https://developer.ftrack.com/api-clients/python/event-list#ftrackapisessionconfigure-location
        'topic=ftrack.api.session.configure-location',
        
        # 该函数将在 session 发布该事件时被调用：
        # partial() 函数可以将 configure_location 函数的第一个参数固定为 session，
        # 这样就不需要在调用时传入 session 了。
        # functools.partial 会按照参数的位置顺序来固定参数。如果你提供了一个位置参数，它将默认固定第一个参数。
        # 这里的第一个参数是 session，所以它将被固定为 session。
        functools.partial(configure_location, session),
    )
