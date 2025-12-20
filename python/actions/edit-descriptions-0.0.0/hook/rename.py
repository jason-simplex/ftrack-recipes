#!/usr/bin/env python
# :coding: utf-8
# :copyright: Copyright (c) 2025 bigyellow

import logging

from ftrack_action_handler.action import BaseAction
import ftrack_api

'''
session = ftrack_api.Session()
list = session.get('List', '01908aa8-2d41-47df-a30d-f68099555b73')
print(list['system_type'])
'''


class Rename(BaseAction):

    label = 'Batch Rename Item Names'
    identifier = 'com.bigyellow.rename.item.names'
    description = 'Batch rename item names in a task list'
    icon = 'https://pipedream.com/s.v0/app_XKvhYR/logo/orig'   


    def discover(self, session, entities, event):
        

        if not entities:
            return False
        logging.info(f'所选数量: {len(entities)}')
        for entity_type, entity_id in entities:
            if entity_type == 'TypedContext':
                return True

        if len(entities) > 1:
           return False

        entity_type, entity_id = entities[0]
        if entity_type != 'List':
            return False
        my_list = session.get(entity_type, entity_id)
        if my_list['system_type'] != 'task':
            return False
        if not my_list['items']:
            return False
        
        return True
    
    def _get_items(self, entities):

        if len(entities) == 1 and entities[0][0] == 'List':
        # ['items'] 是TypedContextList对象的一个属性
            return self.session.get(*entities[0])['items']
    
        # 这里返回了一个生成器   
        return (
            self.session.get(*entity)
            for entity in entities
            if entity[0] == 'TypedContext'
        )

    def interface(self, session, entities, event):

        values = event['data'].get('values', {})
        if values:
            return
        items = self._get_items(entities)
        
        widgets = [
        # 添加查找和替换的功能
            {
                'label': '🔎 Find',
                'type': 'text',
                'value': '',
                'name': 'find',

            },
            {
                'label': '💊 Replace with',
                'type': 'text',
                'value': '',
                'name':'replace',
            },
            {
                'type': 'label',
                'value': '# Current Selection:', 
                'name': 'divider',
            }
        
            ] + [
            {
                'label':'🎈 Entity: '+'/'.join(link['name'] for link in item['link']),
                'type':'text',
                'value': item['name'],
                'name':item['id'],
            }
            for item in items
        ]

        return widgets

    def launch(self, session, entities, event):
        # 获取查找和替换的值
        find_value = event['data']['values'].get('find', '')
        replace_value = event['data']['values'].get('replace', '')
        logging.info(f'查找: {find_value}, 替换为: {replace_value}')

        #这里的id_, name_实际上对应的是 widgets 中的 name 和 value
        for id_, name_ in list(event['data']['values'].items()):
            if id_ == 'find' or id_ =='replace' or id_ == 'divider':
                continue
            new_name = name_.replace(find_value, replace_value)
            session.get('TypedContext', id_)['name'] = new_name
        session.commit()

        return {'success': True, 'message': 'item names have been renamed.'}

def register(session, **kw):
    if not isinstance(session, ftrack_api.Session):
        return

    action = Rename(session)
    action.register()

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    session = ftrack_api.Session(auto_connect_event_hub=True)
    register(session)
    logging.info('Registered actions and listening for event. Use Ctrl-C to abort.')
    session.event_hub.wait()



