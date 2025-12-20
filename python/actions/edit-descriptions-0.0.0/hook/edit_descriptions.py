#!/usr/bin/env python
# :coding: utf-8
# :copyright: Copyright (c) 2019 ftrack

import logging

from ftrack_action_handler.action import BaseAction
import ftrack_api


class EditDescriptions(BaseAction):
    '''Action to allow updating the descriptions on AssetVersion Objects.'''

    label = 'Edit Description'
    identifier = 'com.ftrack.recipes.edit_descriptions'
    description = 'Edit descriptions for AssetVersions'

    def discover(self, session, entities, event):

        if not entities:
            return False

        for entity_type, entity_id in entities:
            if entity_type == 'AssetVersion':
                return True

        if len(entities) > 1:
            return False

        entity_type, entity_id = entities[0]
        if entity_type != 'List':
            return False
        my_list = session.get(entity_type, entity_id)
        if my_list['system_type'] != 'assetversion':
            return False
        if not my_list['items']:
            return False

        return True

    def _get_versions(self, entities):
        
        # entities数量为1且类型为List时，返回List中的AssetVersion对象
        # 否则，遍历entities，当类型为AssetVersion时，返回AssetVersion对象
        if len(entities) == 1 and entities[0][0] == 'List':
            return self.session.get(*entities[0])['items']
        return (
            self.session.get(*entity)
            for entity in entities
            if entity[0] == 'AssetVersion'
        )
    

    def interface(self, session, entities, event):

        values = event['data'].get('values', {})
        # 如果values 被填入数值了，说明已经点击了保存按钮，直接关闭窗口
        # 否则，说明是第一次打开窗口，需要展示窗口
        if values:
            return 

        # 这里的的 versions 是个集合  <ftrack_api.collection.Collection object at 0x10ab00790>
        versions = self._get_versions(entities)

        '''
        version['link'] 是个列表,每个元素是字典, 包含了该AssetVersion的上下级关系
        例如：
        [
        {'id': '33d65c60-a077-11ed-ae11-52eecb693950', 'name': 'tatata', 'type': 'Project'}, 
        {'id': '3f14c760-a077-11ed-ae11-52eecb693950', 'name': 'sh01', 'type': 'TypedContext'}, 
        {'id': '57b740de-a9a5-4e06-b659-aa9eaee59a87', 'name': 'cloud v001', 'type': 'AssetVersion'}
        ]
        '''
        # [] 里是个列表推导式
        widgets = [
            {
                # separator.join(iterable) 将iterable中的元素用separator连接起来
                # link['name'] for link in version['link'] 是一个生成器表达式，
                # 用于从 version['link'] 列表中的每个字典提取 name 值
                'label': ' / '.join(link['name'] for link in version['link']),
                'type': 'text',
                'value': version['comment'],
                'name': version['id'],
            }
            for version in versions
        ]
        return widgets

    def launch(self, session, entities, event):
        print(event['data']['values'])

        for id_, comment in list(event['data']['values'].items()):
            session.get('AssetVersion', id_)['comment'] = comment
        session.commit()

        return {'success': True, 'message': 'Description(s) updated.'}


def register(session, **kw):

    if not isinstance(session, ftrack_api.Session):
        return

    action = EditDescriptions(session)
    action.register()


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    session = ftrack_api.Session(auto_connect_event_hub=True)
    register(session)
    logging.info('Registered actions and listening for event. Use Ctrl-C to abort.')
    session.event_hub.wait()
