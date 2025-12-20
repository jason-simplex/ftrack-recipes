

import logging
from ftrack_action_handler.action import BaseAction
import ftrack_api


class StartDueDate(BaseAction):

    label = '🗓️ 批量编辑 开始、截止 日期'
    identifier = 'bro.tiger.start_due_override'
    description = '日期可设置到非工作日'
    icon = 'https://pipedream.com/s.v0/app_13Gh2V/logo/orig'

    def _filtered_entities(self, session, entities):
        '''Filter entities to only include Tasks and Milestones.'''
        return [
            session.get(entity_type, entity_id)
            for entity_type, entity_id in entities
            if session.get(entity_type, entity_id).entity_type in ['Task', 'Milestone']
        ]

    def _get_smart_date_value(self, filtered_entities, date_field):
        """
        Get smart date value for the given date field from filtered entities.
        Returns:
        - Specific date string if all entities have the same date
        - '...' if entities have different dates (mixed values)
        - 'null' if no entities have dates
        """
        if not filtered_entities:
            return 
        
        # Collect all non-empty date values
        date_values = []
        for entity in filtered_entities:
            # For Milestone's start_date, since it's immutable, we skip collecting it
            # This avoids displaying Milestone's start_date in the interface since users cannot modify it
            if date_field == 'start_date' and entity.entity_type == 'Milestone':
                continue
                
            date_value = entity.get(date_field)
            if date_value:
                # Handle Arrow object conversion to string
                if hasattr(date_value, 'format'):
                    date_value = date_value.format('YYYY-MM-DD')
                elif not isinstance(date_value, str):
                    date_value = str(date_value)[:10]
                date_values.append(date_value)
        
        if not date_values:
            return 'null'
        
        # Check if all values are the same
        unique_values = set(date_values)
        
        if len(unique_values) == 1:
            # All values are the same, return that value
            return list(unique_values)[0]
        else:
            # Multiple different values, return placeholder format to prompt user input
            return '...'

    def discover(self, session, entities, event):

        # Check if the selected entities contain Task or Milestone
        for entity_type, entity_id in entities:
            entity = session.get(entity_type, entity_id)
            # Check the actual type of the entity
            if entity.entity_type in ['Task', 'Milestone']:
                return True
        
        # If no Task or Milestone is found, return False
        return False

    def interface(self, session, entities, event):
        # Check if this is a form submission (has values) before clearing
        is_form_submission = bool(event['data'].get('values', {}))
        
        # Skip interface during form submission processing
        if is_form_submission:
            return
        
        # For fresh action launches, clear any residual values to prevent form caching
        if 'values' in event['data']:
            event['data']['values'] = {}

        # Get filtered entities
        filtered_entities = self._filtered_entities(session, entities)
        print(f"过滤后实体:{filtered_entities}")
        
        # Always recalculate values for fresh interface display
        # This ensures no residual values from previous submissions
        start_date_value = self._get_smart_date_value(filtered_entities, 'start_date')
        end_date_value = self._get_smart_date_value(filtered_entities, 'end_date')

        # Convert special values to appropriate display values
        # '...' means mixed values - show empty to prompt user input
        # 'null' means no values - show empty
        # Actual date values should be displayed to show current common value
        def get_display_value(smart_value):
            if smart_value in ['...', 'null', None]:
                return ''  # Use empty string for form compatibility
            else:
                return smart_value  # Show the common date value

        widgets = [
            {
                'label': '开始日期',
                'type': 'date',
                'name': 'start_date',
                'value': get_display_value(start_date_value),
            },
            {
                'label': '截止日期',
                'type': 'date',
                'name': 'end_date',
                'value': get_display_value(end_date_value),
            },
        ]

        print(f"start_date_value:{get_display_value(start_date_value)}")
        print("="*20)
        print(f"end_date_value:{get_display_value(end_date_value)}")
        print("="*20)

        return widgets

    def _clamp_dates(self, filtered_entities, start_date, end_date):
        """
        Clamp date values within the project's date range
        If the passed date value is 'null' or '...', it means the user doesn't want to assign a value, keep it as is
        
        Args:
            filtered_entities: List of filtered entities
            start_date: User input start date
            end_date: User input end date
            
        Returns:
            tuple: (clamped_start_date, clamped_end_date)
        """
        if not filtered_entities:
            return start_date, end_date
        
        # Check null value cases - if 'null' or '...' then return directly, indicating user doesn't want to assign value
        def is_null_or_skip_value(value):
            return value == 'null' or value == '...'
        
        # If start date is 'null' or '...', keep it as is
        if is_null_or_skip_value(start_date):
            clamped_start_date = start_date
        else:
            # Get project's date range
            project_start_date = filtered_entities[0]['project']['start_date']
            project_end_date = filtered_entities[0]['project']['end_date']
            
            # Handle Arrow object conversion to string
            if hasattr(project_start_date, 'format'):
                project_start_date = project_start_date.format('YYYY-MM-DD')
            elif not isinstance(project_start_date, str):
                project_start_date = str(project_start_date)[:10]
                
            if hasattr(project_end_date, 'format'):
                project_end_date = project_end_date.format('YYYY-MM-DD')
            elif not isinstance(project_end_date, str):
                project_end_date = str(project_end_date)[:10]
            
            # Clamp start_date within project range
            clamped_start_date = start_date
            if start_date and start_date < project_start_date:
                clamped_start_date = project_start_date
                self.logger.info(f"开始日期 {start_date} 早于项目开始日期，已调整为 {project_start_date}")
            elif start_date and start_date > project_end_date:
                clamped_start_date = project_end_date
                self.logger.info(f"开始日期 {start_date} 晚于项目结束日期，已调整为 {project_end_date}")
        
        # If end date is 'null' or '...', keep it as is
        if is_null_or_skip_value(end_date):
            clamped_end_date = end_date
        else:
            # If project date range hasn't been retrieved yet (when start_date is 'null' or '...')
            if is_null_or_skip_value(start_date):
                project_start_date = filtered_entities[0]['project']['start_date']
                project_end_date = filtered_entities[0]['project']['end_date']
                
                # Handle Arrow object conversion to string
                if hasattr(project_start_date, 'format'):
                    project_start_date = project_start_date.format('YYYY-MM-DD')
                elif not isinstance(project_start_date, str):
                    project_start_date = str(project_start_date)[:10]
                    
                if hasattr(project_end_date, 'format'):
                    project_end_date = project_end_date.format('YYYY-MM-DD')
                elif not isinstance(project_end_date, str):
                    project_end_date = str(project_end_date)[:10]
            
            # Clamp end_date within project range
            clamped_end_date = end_date
            if end_date and end_date < project_start_date:
                clamped_end_date = project_start_date
                self.logger.info(f"结束日期 {end_date} 早于项目开始日期，已调整为 {project_start_date}")
            elif end_date and end_date > project_end_date:
                clamped_end_date = project_end_date
                self.logger.info(f"结束日期 {end_date} 晚于项目结束日期，已调整为 {project_end_date}")
            
        return clamped_start_date, clamped_end_date

    def launch(self, session, entities, event):
        if 'values' in event['data']:
            values = event['data']['values']
            print(f"values:{values}")
                
        filtered_entities = self._filtered_entities(session, entities)
        
        # Use _clamp_dates method to clamp date values within project range
        clamped_start_date, clamped_end_date = self._clamp_dates(
            filtered_entities, 
            values.get('start_date'), 
            values.get('end_date')
        )
        
        for entity in filtered_entities:
            # Check if it's a Milestone - Milestone's start_date is immutable and automatically equals end_date
            is_milestone = entity.entity_type == 'Milestone'
            
            # For Milestone, ignore start_date assignment because it's immutable
            # Skip assignment if value is '...' (user didn't input anything)
            if not is_milestone and clamped_start_date and clamped_start_date != 'yyyy-mm-dd' and clamped_start_date != 'null' and clamped_start_date != '...':
                entity['start_date'] = clamped_start_date
                
            # end_date can be assigned for all entity types
            # Skip assignment if value is '...' (user didn't input anything)
            if clamped_end_date and clamped_end_date != 'yyyy-mm-dd' and clamped_end_date != 'null' and clamped_end_date != '...':
                entity['end_date'] = clamped_end_date
        session.commit()
        session.reset()
    
        return {'success': True, 'message': f"开始日期为: 🗓️{clamped_start_date}，截止日期为: 🗓️{clamped_end_date}"}

def register(session, **kw):
    '''Register plugin.'''
    if not isinstance(session, ftrack_api.Session):
        return
    action = StartDueDate(session)
    action.register()

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    session = ftrack_api.Session(auto_connect_event_hub=True)
    register(session)

    session.event_hub.wait()
