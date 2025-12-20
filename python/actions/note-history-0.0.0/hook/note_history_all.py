#!/usr/bin/env python
# :coding: utf-8
# :copyright: Copyright (c) 525 Bro.Tiger

import ftrack_api
import json
import logging
import arrow

from ftrack_action_handler.action import BaseAction

class NoteHistory(BaseAction):
    label = '谁动了备注？'
    identifier = 'com.bro.tiger.note.history'
    description = '何时何人如何动了备注'
    icon = 'https://pipedream.com/s.v0/app_5ghAg9/logo/orig'

    def _get_q_events(self, session, limit):
        self.logger.info('_get_q_events() 接收有效限制数量: {0}'.format(limit))
        sql = f"select action, user, insert, data, project, created_at from Event where action is 'db.all.note' and user is_not none order by created_at desc limit {limit}"
        q_events = session.query(sql).all()
        return q_events

    def _validate_insert_type(self, event_insert, q_event):
        event_data = json.loads(q_event['data'])
        if event_insert == 'insert':
            note_content = event_data.get('text', {}).get('new', '')
            note_content_old = None
            obj_id = event_data.get('parent_id').get('new', '')
            return note_content, note_content_old, obj_id, "✏️创建"
        elif event_insert == 'update':
            # API 缺陷，更新 note 的 event['parent_id'] 其实是 note 数组的 id, 而不是 note 所在父级对象的 id 
            # 且在更新 note 时， event['data'] 中没有包含 note 所在父级对象的 id， 所以 event['data'].get('parent_id') 这个键不存在
            # event['data'] 只有 'text' 这个键，下面包含 'new' 和 'old' 两个键，然后啥也没有
            # 所以需要通过 note 数组的 id 去查询 note 数组所在父级对象的 id
            event_data = json.loads(q_event['data'])
            note_content = event_data.get('text', {}).get('new', '')
            note_content_old = event_data.get('text', {}).get('old', '')
            note_root_id = q_event['parent_id']
            obj_id = session.get('Note', note_root_id)['parent_id']
            return note_content, note_content_old, obj_id, "💊更新"
        elif event_insert == 'delete':
            note_content = None
            note_content_old = event_data.get('text', {}).get('old', '')
            obj_id = event_data.get('parent_id').get('old', '')
            return note_content, note_content_old, obj_id, "❌删除"
        else:
            note_content = None
            note_content_old = None
            obj_id = None
            logging.info(f"事件类型为{event_insert}，不支持")
            return note_content, note_content_old, obj_id

    def _process_event(self, session, q_event):
        if q_event['user'] is None or q_event['action'] != 'db.all.note':
            return None
            
        local_time = arrow.get(q_event['created_at']).to('local').format('YYYY-MM-DD HH:mm:ss')
        user_name = q_event['user']['username']
        note_content, note_content_old, obj_id, q_event_type = self._validate_insert_type(q_event['insert'], q_event)
        
        try:
            if session.get('Context', obj_id):
                entity = session.get('Context', obj_id)
                entity_link_name = '/'.join(link['name'] for link in entity['link'])
            else:
                asset_version = session.get('AssetVersion', obj_id)
                entity_link_name = '/'.join(link['name'] for link in asset_version['link'])
            
            if q_event_type == "✏️创建":
                content_info = f"-创建内容: {note_content}"
            elif q_event_type == "💊更新":
                content_info = f"-更新后: {note_content}\n-更新前: {note_content_old}"
            elif q_event_type == "❌删除":
                content_info = f"-删除内容: {note_content_old}"
            else:
                content_info = f"未知事件类型: {q_event_type}"
            
            return f"{local_time} -- 用户 {user_name} 在 {entity_link_name} 上 {q_event_type} 了一条笔记:\n{content_info}"
        except:
            return None

    def discover(self, session, entities, event):        
        if len(entities)!= 1:
            return False
        print(f"当前所选: {event['data']['selection'][0]} \n")
        
        entity_type, entity_id = entities[0]
        print(f"解包实体: {entity_type}, id: {entity_id} \n")
        print(f"当前所选实体: {session.get(entity_type, entity_id)} \n")
        return True

    def interface(self, session, entities, event):
        values = event['data'].get('values', {})
        # 如果values 被填入数值了，说明已经点击了保存按钮，直接关闭窗口
        # 否则，说明是第一次打开窗口，需要展示窗口
        if values:
            return
        entity_type, entity_id = entities[0]

        entity_name = session.get(entity_type, entity_id)['name']
        widget = [
            {
                'type': 'label',
                'value': f'查询关于 {entity_name} 的笔记变更历史',
            },
            {
                'label': '输入所需的倒查数量',
                'type': 'number',
                'value': '5',
                'name': 'limit',
                'empty_text': '输入一个数字, 默认5条, 最多100条',
            },
        ]
        return widget
    
    def launch(self, session, entities, event):
        entity_type, entity_id = entities[0]
        print(f"launch接收到的实体: {session.get(entity_type, entity_id)} \n")
        
        # 获取limit参数
        if 'values' in event['data']:
            limit = event['data']['values'].get('limit', 5)
            self.logger.info('接收有效限制数量: {0}'.format(limit))
            # 当有values时，同时打印到终端
            should_print = True
        else:
            limit = 5
            should_print = False
        
        q_events = self._get_q_events(session, limit)
        
        # 如果需要打印到终端，先处理打印
        if should_print:
            for q_event in q_events:
                result = self._process_event(session, q_event)
                if result:
                    print(result)
        
        return {
            'success': True, 
            'message': 'Ran my custom action successfully!',
            'type': 'form',
            'items': [
                {
                    'type': 'label',
                    'value': f'# 🕒 {i+1} -- ' + self._process_event(session, q_event),

                }
                for i, q_event in enumerate(q_events) 
                if self._process_event(session, q_event) is not None
            ] or [
                {
                    'type': 'label',
                    'value': '暂无笔记历史记录',

                }
            ],
            'title': '笔记历史记录',
            'width': 1000,
            'height': 1000,
            'submit_button_label': '关闭',
        }

def register(session, **kw):

    logger = logging.getLogger('note_history')

    if not isinstance(session, ftrack_api.Session):
        return

    action = NoteHistory(session) 
    action.register()

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    session = ftrack_api.Session(auto_connect_event_hub=True)
    register(session)
    logging.info('Registered actions and listening for event. Use Ctrl-C to abort.')
    session.event_hub.wait()