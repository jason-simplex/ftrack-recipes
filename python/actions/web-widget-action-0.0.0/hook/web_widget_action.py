# :coding: utf-8
# :copyright: Copyright (c) 2024 ftrack

import logging
import ftrack_api
from ftrack_action_handler.action import BaseAction


class MyWebWidgetAction(BaseAction):
    identifier = 'my.webwidget.action'
    label = 'My Web Widget Action'
    description = 'This is an example action'
    icon = 'https://pipedream.com/s.v0/app_1w0hvd/logo/orig'

    def discover(self, session, entities, event):
        """
        Method that responds to the discovery message.

        This will always return the action in any context.
        """
        return True
    
    def launch(self, session, entities, event):
        """
        Method that responds to messages to launch the action.

        This will simply just return a web widget with the specified URL.
        """
        print(event['topic'])
        return {
          
            'success': True,
            'message': 'success', # Required
            'type': 'widget',
            'url': 'https://chinateam.ftrackapp.cn/#entityId=33d65c60-a077-11ed-ae11-52eecb693950&entityType=show&itemId=projects&view=tasks',
            'title': 'My Web Widget Action',
            'width': 1280,
            'height': 720
        }


def register(session, **kw):
    '''Register plugin.'''
    if not isinstance(session, ftrack_api.Session):
        return

    action = MyWebWidgetAction(session)
    action.register()


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    session = ftrack_api.Session(auto_connect_event_hub=True)
    register(session)

    session.event_hub.wait()



