#!/usr/bin/env python
# :coding: utf-8
# :copyright: Copyright (c) 2019 ftrack

import logging

from ftrack_action_handler.action import BaseAction
import ftrack_api

UNWANTED_COMPONENTS = ['ftrackreview-image','ftrackreview-image-high','thumbnail', 'ftrackreview-mp4','ftrackreview-mp4-1080','ftrackreview-mp4-1440','ftrackreview-mp4-2160']

class ShowComponents(BaseAction):
    '''Action to allow showing components on AssetVersion Objects.'''

    label = '显示版本所包含的组件'
    identifier = 'com.ftrack.recipes.show_components'
    description = '显示每个版本所包含的所有组件'
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
        paths = location.get_filesystem_paths(filtered_components)
        paths_without_spaces = [f'📂 {path.replace(" ", "")}' for path in paths]
        return '\n'.join(paths_without_spaces)


    # def interface(self, session, entities, event):

    #     values = event['data'].get('values', {})
    #     if values:
    #         return 

    #     versions = self._get_versions(entities)
    #     for version in versions:
    #         components_info =self._resolve_names(version)+'\n'+self._resolve_paths(version)
    #         print(components_info)

    #     widgets = [
    #         {
    #             'label': '开关',
    #             'type': 'boolean',
    #             'value': False,
    #             'name': 'test1',

    #         }
    #     ]+[
    #         {

    #             'label': '🎬 资产版本：'+' / '.join(link['name'] for link in version['link']),
    #             'type': 'textarea',
    #             'value': components_info,
    #             'name': version['id'],
    #         }
    #         for version in versions
    #     ]+[
    #         {
    #             'label': '测试2',
    #             'type': 'textarea',
    #             'value': '测试2',
    #             'name': 'test2',
    #         }]
    #     return widgets

    def launch(self, session, entities, event):
  
        values = event['data'].get('values', {})
        if values:
            return    

        versions = self._get_versions(entities)
        for version in versions:
            components_info =self._resolve_names(version)+'\n'+self._resolve_paths(version)
            print(components_info) 

        for id_, comment in list(event['data']['values'].items()):
            if id_ == 'test1' or id_ =='test2':
                continue
            session.get('AssetVersion', id_)['comment'] = comment
        session.commit()

        return {
            'success': True,
            'message': 'Description(s) updated.',
    		'type': 'form',
    		'items': [
            {

                'label': '🎬 资产版本：'+' / '.join(link['name'] for link in version['link']),
                'type': 'textarea',
                'value': components_info,
                'name': version['id'],
            }
            for version in versions             
            ],
    		'title': '显示版本所包含的组件',
    		'submit_button_label': '保存',
            'width': 1280,
            'height': 800
		}
  


def register(session, **kw):

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