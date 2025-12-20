# :coding: utf-8
import logging

import ftrack_api

from ftrack_action_handler.action import BaseAction


class FindAndReplace(BaseAction):
    '''Example action with interface to find and replace in text attributes.'''
    label = 'find and replace'
    identifier = 'ftrack.test.find_and_replace'

    def discover(self, session, entities, event):
        if not self.validate_selection(entities):
            return super(FindAndReplace, self).discover(
                session, entities,  event
            )

        return True

    def launch(self, session, entities, event):
        '''Callback method for action.'''
        self.logger.info(
            u'Launching action with selection {0}'.format(entities)
        )

        # Validate selection and abort if not valid
        if not self.validate_selection(entities):
            self.logger.warning(
                'Selection is not valid, aborting action'
            )

            return

        values = event['data'].get('values',{})

        attribute = values.get('attribute')
        find = values.get('find')
        replace = values.get('replace')

        self.find_and_replace(
            session, entities, attribute, find, replace
        )

        try:
            session.commit()
        except:
            # Commit failed, rollback session and re-raise.
            session.rollback()
            raise

        return {
            'success': True,
            'message': 'Find and replace "{0}" with "{1}" on attribute "{2}"'.format(
                str(find), str(replace), attribute
            )
        }

    def find_and_replace(self, session, entities, attribute, find, replace):
        '''Find and replace *find* and *replace* in *attribute* for *selection*.'''
        for entity_type, entity_id in entities:
            entity = session.get(entity_type, entity_id)

            if entity:
                value = entity.get(attribute)
                if not isinstance(value, basestring):
                    self.logger.info(
                        'Ignoring attribute {0!r} with non-string value'.format(attribute)
                    )
                    continue

                entity.update({
                    attribute: value.replace(find, replace)
                })

    def validate_selection(self, entities):
        '''Return True if *entities* is valid'''
        # Replace with custom logic for validating selection.
        # For example check the length or entityType of items in selection.
        return True

    def interface(self, session, entities, event):
        values = event['data'].get('values', {})

        if (
            not values or not (
                values.get('attribute') and
                values.get('find') and
                values.get('replace')
            )
        ):

            # Valid attributes to update.
            attributes = [{
                'label': 'Name',
                'value': 'name'
            }, {
                'label': 'Description',
                'value': 'description'
            }]

            return [
                {
                    'label': 'Attribute',
                    'type': 'enumerator',
                    'name': 'attribute',
                    'value': attributes[0]['value'],
                    'data': attributes
                }, {
                    'type': 'text',
                    'label': 'Find',
                    'name': 'find'
                }, {
                    'type': 'text',
                    'label': 'Replace',
                    'name': 'replace'
                }
            ]

def register(session, **kw):
    if not isinstance(session, ftrack_api.Session):
        return

    action = FindAndReplace(session)
    action.register()

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    session = ftrack_api.Session(auto_connect_event_hub=True)
    register(session)
    logging.info('Registered actions and listening for event. Use Ctrl-C to abort.')
    session.event_hub.wait()