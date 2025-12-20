#!/usr/bin/env python
# :coding: utf-8
# :copyright: Copyright (c) 2025 bigyellow

import logging
import arrow

from ftrack_action_handler.action import BaseAction
import ftrack_api



class ShowStatusTransition(BaseAction):

    label = 'Show Status Progression'
    identifier = 'com.bigyellow.show.status.progression'
    description = 'Show Status Progression for Current Selection'
    icon = 'https://pipedream.com/s.v0/app_OQYhMa/logo/orig'   


    def discover(self, session, entities, event):

        
        logging.info(f"Discovering entities: {len(entities)}")

        if not entities:
            return False

        for entity_type, entity_id in entities:
            if entity_type == 'AssetVersion' or entity_type == 'TypedContext':
                return True

        entity_type, entity_id = entities[0]
        if entity_type != 'List':
            return False

        return True

    def _get_selections(self, entities):
        
        if len(entities) == 1 and entities[0][0] == 'List':
            return self.session.get(*entities[0])['items']
        return [
            self.session.get(*entity)
            for entity in entities
        ]

    def _show_status_transition(self,selection):
        sorted_status_changes = sorted(selection['status_changes'], key=lambda x: x['date'].to('local').naive)
        output_lines = []
        for statusChange in sorted_status_changes:
            if statusChange['from_status'] != None:                
                output_lines.append(f"- {statusChange['date'].to('local').naive} | - [{statusChange['from_status']['name']}]  ==>>  [{statusChange['status']['name']}]   👨‍💻 {statusChange['user']['username']}")
            if statusChange['from_status'] == None:                
                output_lines.append(f"- {statusChange['date'].to('local').naive} | - [{statusChange['status']['name']}]   👨‍💻 {statusChange['user']['username']}")
        return '\n'.join(output_lines)  # 将所有行连接成一个单一的字符串，并用换行符分隔

    def launch(self, session, entities, event):
 
        values = event['data'].get('values', {})
        if values:
            return {
            'success': True,
            'message': 'Bye',
            }

        selections = self._get_selections(entities) 


        return {
            'success': True,
            'message': 'Bye',
        
    		'items': 
            [
            {
                'type': 'label',
                'value': 'You have selected '+ str(len(selections))+ ' items. You can view the status progression below:'
            }
            ]+
            [
            {
                'type': 'label',
                'value': '🔻 '+' / '.join(link['name'] for link in selection['link'])+':\n'+ self._show_status_transition(selection),
            } for selection in selections                      
            ],
    		'title': '🚥 Show Status Progression',
    		'submit_button_label': '👌 OK',
            'width': 600,
            'height': 1000
		}
  


def register(session, **kw):

    logger = logging.getLogger('show_status_transition')

    if not isinstance(session, ftrack_api.Session):
        return

    action = ShowStatusTransition(session)
    action.register()


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    session = ftrack_api.Session(auto_connect_event_hub=True)
    register(session)
    logging.info('Registered actions and listening for event. Use Ctrl-C to abort.')
    session.event_hub.wait()


