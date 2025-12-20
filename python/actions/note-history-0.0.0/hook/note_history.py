#!/usr/bin/env python
# :coding: utf-8
# :copyright: Copyright (c) 2025 Bro.Tiger

import ftrack_api
import json
import logging
import arrow
import os
import datetime

from ftrack_action_handler.action import BaseAction

class NoteHistory(BaseAction):
    # 类属性 - 使用默认中文标签
    label = '备注变更历史查询'
    description = '查询关于所选实体的备注变更历史'
    identifier = 'com.bro.tiger.note.history'
    icon = 'https://pipedream.com/s.v0/app_vNh2lL/logo/orig'
    
    def __init__(self, session):
        super(NoteHistory, self).__init__(session)
        self.config = self._load_config()
        self.texts = self._load_language_texts()
        
        # 根据配置动态更新标签和描述
        self.label = self.texts['action']['label']
        self.description = self.texts['action']['description']
    
    def _load_config(self):
        """加载配置文件"""
        config_path = os.path.join(os.path.dirname(__file__), 'config.json')
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            self.logger.warning(f'Failed to load config file: {e}, using default config')
            return {'language': 'CN', 'available_languages': ['CN', 'EN']}
    
    def _load_language_texts(self):
        """根据配置加载对应语言文件"""
        language = self.config.get('language', 'CN').lower()
        lang_file = os.path.join(os.path.dirname(__file__), 'languages', f'{language}.json')
        
        try:
            with open(lang_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            self.logger.warning(f'Failed to load language file {lang_file}: {e}, using Chinese as fallback')
            # 如果加载失败，尝试加载中文文件作为后备
            try:
                fallback_file = os.path.join(os.path.dirname(__file__), 'languages', 'cn.json')
                with open(fallback_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                # 如果连中文文件都加载失败，返回默认文本
                return self._get_default_texts()
    
    def _get_default_texts(self):
        """返回默认的中文文本"""
        return {
            "action": {
                "label": "查询备注变更历史",
                "description": "查询所选实体的备注变更历史"
            },
            "interface": {
                "query_label": "查询关于 {entity_name} 的备注变更历史(不包含子节点上的备注)",
                "limit_label": "输入倒查记录数量上限 (默认10条)",
                "limit_placeholder": "输入一个数字, 默认倒查10条记录"
            },
            "launch": {
                "success_message": "成功获取 {limit} 条备注变更记录",
                "no_records": "暂无备注历史记录",
                "title": "备注变更历史",
                "export_success": "备注历史已成功导出到: {file_path}",
                "export_error": "导出失败: {error}",
                "export_button_label": "导出为Markdown文件"
            },
            "export": {
                "entity_label": "实体",
                "export_time_label": "导出时间",
                "record_count_label": "记录数量",
                "record_detail_title": "记录详情"
            },
            "operations": {
                 "create": "✏️创建",
                 "update": "💊更新",
                 "delete": "❌删除"
             },
             "content_display": {
                 "create_content": "# -创建内容: \n{content}",
                 "update_after": "# -更新后: \n{content}",
                 "update_before": "# -更新前: \n{content_old}",
                 "delete_content": "# -删除内容: \n{content}",
                 "unknown_event": "# 未知事件类型: \n{event_type}",
                 "result_format": "{time} -- 用户 {user} 在 {entity} 上 {operation} 了一条备注:\n{content_info}"
             },
            "logging": {
                "get_events_info": "_get_q_events() 接收有效限制数量: {limit}",
                "receive_limit_info": "接收有效限制数量: {limit}",
                "registered_info": "Registered actions and listening for event. Use Ctrl-C to abort."
            }
        }

    def _get_q_events(self, session, limit, entity_id=None):
        self.logger.info(self.texts['logging']['get_events_info'].format(limit=limit))
        if entity_id:
            # 查询特定实体的笔记事件
            # 由于笔记事件的复杂性，我们需要获取更多记录然后过滤，但要确保有足够的记录
            # 使用较大的倍数以确保能找到足够的相关记录
            sql = f"select action, user, insert, data, project, created_at from Event where action is 'db.all.note' and user is_not none order by created_at desc limit {limit * 50}"
        else:
            # 查询所有笔记事件（保持原有逻辑）
            sql = f"select action, user, insert, data, project, created_at from Event where action is 'db.all.note' and user is_not none order by created_at desc limit {limit}"
        q_events = session.query(sql).all()
        return q_events

    def _validate_insert_type(self, session, event_insert, q_event):
        event_data = json.loads(q_event['data'])
        if event_insert == 'insert':
            note_content = event_data.get('text', {}).get('new', '')
            note_content_old = None
            obj_id = event_data.get('parent_id').get('new', '')
            return note_content, note_content_old, obj_id, self.texts['operations']['create']
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
            return note_content, note_content_old, obj_id, self.texts['operations']['update']
        elif event_insert == 'delete':
            note_content = None
            note_content_old = event_data.get('text', {}).get('old', '')
            obj_id = event_data.get('parent_id').get('old', '')
            return note_content, note_content_old, obj_id, self.texts['operations']['delete']
        else:
            note_content = None
            note_content_old = None
            obj_id = None
            logging.info(f"事件类型为{event_insert}，不支持")
            return note_content, note_content_old, obj_id

    def _process_event(self, session, q_event, target_entity_id=None):
        if q_event['user'] is None or q_event['action'] != 'db.all.note':
            return None
            
        local_time = arrow.get(q_event['created_at']).to('local').format('YYYY-MM-DD HH:mm:ss')
        user_name = q_event['user']['username']
        note_content, note_content_old, obj_id, q_event_type = self._validate_insert_type(session, q_event['insert'], q_event)
        
        # 如果指定了目标实体ID，只处理该实体的笔记事件
        if target_entity_id and obj_id != target_entity_id:
            return None
        
        try:
            if session.get('Context', obj_id):
                entity = session.get('Context', obj_id)
                entity_link_name = '/'.join(link['name'] for link in entity['link'])
            else:
                asset_version = session.get('AssetVersion', obj_id)
                entity_link_name = '/'.join(link['name'] for link in asset_version['link'])
            
            if q_event_type == self.texts['operations']['create']:
                content_info = self.texts['content_display']['create_content'].format(content=note_content)
            elif q_event_type == self.texts['operations']['update']:
                update_after = self.texts['content_display']['update_after'].format(content=note_content)
                update_before = self.texts['content_display']['update_before'].format(content_old=note_content_old)
                content_info = f"{update_after}\n {update_before}"
            elif q_event_type == self.texts['operations']['delete']:
                content_info = self.texts['content_display']['delete_content'].format(content=note_content_old)
            else:
                content_info = self.texts['content_display']['unknown_event'].format(event_type=q_event_type)
            
            return self.texts['content_display']['result_format'].format(
                time=local_time,
                user=user_name,
                entity=entity_link_name,
                operation=q_event_type,
                content_info=content_info
            )
        except:
            return None

    def discover(self, session, entities, event):
        # 检查是否为指定用户（如果设置了限制）
        if hasattr(self, '_limit_to_user') and self._limit_to_user:
            current_user = event['source']['user']['username']
            if current_user != self._limit_to_user:
                return False
                
        if len(entities)!= 1:
            return False
        print(f"\n 当前所选: {event['data']['selection'][0]} \n")
        
        entity_type, entity_id = entities[0]

        if entity_type == 'User':
            return False

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

        if entity_type == 'AssetVersion':
            asset_version = session.get('AssetVersion', entity_id)
            entity_name = f"{asset_version['asset']['name']} v0{asset_version['version']}"

        else:
            entity_name = session.get(entity_type, entity_id)['name']
        
        widget = [
            {
                'type': 'label',
                'value': self.texts['interface']['query_label'].format(entity_name=entity_name),
            },
            {
                'label': self.texts['interface']['limit_label'],
                'type': 'number',
                'value': '10',
                'name': 'limit',
                'empty_text': self.texts['interface']['limit_placeholder'],
            },
        ]
        return widget
    
    def launch(self, session, entities, event):
        """主要的查询和显示方法"""
        entity_type, entity_id = entities[0]
        entity = session.get(entity_type, entity_id)
        
        # 获取entity_name，处理AssetVersion的特殊情况
        if entity_type == 'AssetVersion':
            asset_version = session.get('AssetVersion', entity_id)
            entity_name = f"{asset_version['asset']['name']} v0{asset_version['version']}"
        else:
            entity_name = entity['name']
        
        # 获取values数据
        values = event['data'].get('values', {})
        
        # 检查是否是导出请求
        if 'export_to_markdown' in values and values['export_to_markdown']:
            return self._handle_export_request(session, entity, entity_name, values)
        
        # 获取limit参数
        limit = 10  # 默认值
        if 'limit' in values:
            limit = int(values['limit'])
        
        self.logger.info(self.texts['logging']['receive_limit_info'].format(limit=limit))
        
        # 查询和处理事件
        processed_events = self._get_note_history(session, entity_id, limit)
        
        # 构建返回的表单项
        items = []
        
        # 添加结果显示项
        if processed_events:
            for i, result in enumerate(processed_events):
                # 添加分隔线
                items.append({
                    'type': 'label',
                    'value': '-----',
                })
                # 添加记录内容
                items.append({
                    'type': 'label',
                    'value': f'# {i+1} ⏰ -- ' + result,
                })
        else:
            items.append({
                'type': 'label',
                'value': self.texts['launch']['no_records'],
            })
        
        # 添加导出按钮
        items.append({
            'type': 'boolean',
            'name': 'export_to_markdown',
            'label': self.texts['launch']['export_button_label'],
            'value': False
        })
        
        return {
            'success': True,
            'message': self.texts['launch']['success_message'].format(limit=limit),
            'type': 'form',
            'items': items,
            'title': self.texts['launch']['title'],
            'width': 1000,
            'height': 1000,
        }
    
    def _get_note_history(self, session, entity_id, limit):
        """获取备注历史记录的独立方法"""
        # 查询当前选中实体的笔记历史
        q_events = self._get_q_events(session, limit, entity_id)
        
        # 处理事件并过滤出属于当前实体的笔记历史
        processed_events = []
        for q_event in q_events:
            result = self._process_event(session, q_event, entity_id)
            if result:
                processed_events.append(result)
                # 达到所需数量就停止处理
                if len(processed_events) >= int(limit):
                    break
        
        return processed_events
    
    def _handle_export_request(self, session, entity, entity_name, values):
        """处理导出请求"""
        # 获取limit参数
        limit = 10  # 默认值
        if 'limit' in values:
            limit = int(values['limit'])
        
        # 获取备注历史记录
        processed_events = self._get_note_history(session, entity['id'], limit)
        
        # 执行导出
        export_result = self._export_to_markdown(session, entity_name, processed_events)
        
        if export_result['success']:
            return {
                'success': True,
                'message': self.texts['launch']['export_success'].format(file_path=export_result['filepath'])
            }
        else:
            return {
                'success': False,
                'message': self.texts['launch']['export_error'].format(error=export_result['error'])
            }
    
    def _export_to_markdown(self, session, entity_name, processed_events):
        """导出为Markdown文件的独立方法"""
        try:
            # 生成文件名
            timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"note_history_{entity_name}_{timestamp}.md"
            filepath = os.path.join(os.path.expanduser('~/Desktop'), filename)
            
            # 生成Markdown内容
            markdown_content = f"# {self.texts['launch']['title']}\n\n"
            markdown_content += f"**{self.texts['export']['entity_label']}**: {entity_name}\n"
            markdown_content += f"**{self.texts['export']['export_time_label']}**: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            markdown_content += f"**{self.texts['export']['record_count_label']}**: {len(processed_events)}\n\n"
            markdown_content += "---\n\n"
            
            if processed_events:
                for i, result in enumerate(processed_events):
                    markdown_content += f"# {i+1}. {self.texts['export']['record_detail_title']}\n\n"
                    markdown_content += f"{result}\n\n"
                    markdown_content += "---\n\n"
            else:
                markdown_content += self.texts['launch']['no_records'] + "\n"
            
            # 写入文件
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(markdown_content)
            
            return {
                'success': True,
                'filepath': filepath
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }

def register(session, **kw):

    logger = logging.getLogger('note_history')

    if not isinstance(session, ftrack_api.Session):
        return

    # 注册NoteHistory action
    action = NoteHistory(session)
    # 获取当前用户名，如果api_user不存在则不限制用户
    current_user = getattr(session, 'api_user', None)
    if current_user:
        action._limit_to_user = current_user
        # 为action添加唯一标识符以避免冲突
        import uuid
        action.identifier = f"{action.identifier}_{str(uuid.uuid4())}"
    action.register()

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    session = ftrack_api.Session(auto_connect_event_hub=True)
    register(session)
    # 创建临时实例来获取日志文本
    temp_action = NoteHistory(session)
    logging.info(temp_action.texts['logging']['registered_info'])
    session.event_hub.wait()