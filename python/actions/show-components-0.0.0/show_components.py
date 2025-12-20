#!/usr/bin/env python
# :coding: utf-8
# :copyright: Copyright (c) 2025 bigyellow

import logging

from ftrack_action_handler.action import BaseAction
import ftrack_api

UNWANTED_COMPONENTS = ['ftrackreview-image','ftrackreview-image-high','thumbnail', 'ftrackreview-mp4','ftrackreview-mp4-1080','ftrackreview-mp4-1440','ftrackreview-mp4-2160']

class ShowComponents(BaseAction):
    '''Action to allow showing components on AssetVersion Objects.'''

    label = '显示 🎬版本 所包含的 📦组件 和 📂路径'
    identifier = 'com.ftrack.recipes.show_components'
    description = '显示每个版本所包含的所有组件和路径'
    icon = 'https://pipedream.com/s.v0/app_Oz6hvk/logo/96'



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
        
        if len(entities) == 1 and entities[0][0] == 'List':
            return self.session.get(*entities[0])['items']
        return [
            self.session.get(*entity)
            for entity in entities
            if entity[0] == 'AssetVersion'
        ]

    def _resolve_names(self, version):
        components = version['components']
        filtered_components = [component for component in components if component['name'] not in UNWANTED_COMPONENTS]
        return '\n'.join('📦 '+component['name']+component['file_type']+f" # {component['size']/1024/1024:.2f}"+'MB' for component in filtered_components)

    def _resolve_paths(self, version):
        location = self.session.pick_location()
        components = version['components']
        filtered_components = [component for component in components if component['name'] not in UNWANTED_COMPONENTS]
        try: 

            paths = location.get_filesystem_paths(filtered_components)
            paths_without_spaces = [f'📂 {path.replace(" ", "")}' for path in paths]
            return '\n'.join(paths_without_spaces)
        
        except ftrack_api.exception.ComponentNotInLocationError:

            invalid_paths = [f"这批组件不在 {location['name']} 位置上" ]
            return '\n'.join(invalid_paths) 


    def launch(self, session, entities, event):
  
        values = event['data'].get('values', {})
        if values:
            return {
            'success': True,
            'message': '无事发生',
            }    

        versions = self._get_versions(entities)
        for version in versions:
            try:
                components_info =self._resolve_names(version)+'\n'+self._resolve_paths(version)
                print(components_info)
            except Exception as e:
                print(f"处理版本 {version['id']} 出错：{e}")

        # for id_, comment in list(event['data']['values'].items()):
        #     if id_ == 'test1' or id_ =='test2':
        #         continue
        #     session.get('AssetVersion', id_)['comment'] = comment
        # session.commit()

        return {
            'success': True,
            'message': '无事发生',
    		'items': [
            {

                'type': 'label',
                'value': '🎬 AssetVersion:'+' / '.join(link['name'] for link in version['link'])+'\n'+components_info,
                'name': version['id'],

            } for version in versions          
            ],
    		'title': 'Show All Components',
    		'submit_button_label': '知道了',
            'width': 800,
            'height': 1000
		}
  


def register(session, **kw):

    logger = logging.getLogger('show_components')

    if not isinstance(session, ftrack_api.Session):
        return

    action = ShowComponents(session)
    action.register()


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    session = ftrack_api.Session(auto_connect_event_hub=True)
    register(session)
    logging.info('Registered actions and listening for event. Use Ctrl-C to abort.')
    session.event_hub.wait()