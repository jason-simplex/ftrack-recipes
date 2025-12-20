import os
import tempfile
import logging
import json
import datetime
import unicodedata



import ftrack_api
import xlsxwriter

from ftrack_action_handler.action import BaseAction

SUPPORTED_ENTITY_TYPES = ('Project',)

class timelogExport(BaseAction):

    label = 'Timelog Export'
    identifier = 'bro.tiger.timelog_export'
    description = 'Export user timelogged hours to an .xlsx file'
    icon = 'https://cdn-icons-png.flaticon.com/128/15465/15465638.png'   

    @property
    def session(self):
        return self._session

    @property
    def ftrack_server_location(self):
        if getattr(self, '_server_location', None) is None:
            self._server_location = self.session.query("Location where name is 'ftrack.server'").one()
        return self._server_location

    def validate_entities(self, entities):
        if len(entities) >= 1 and all(
            [entity_type in SUPPORTED_ENTITY_TYPES for entity_type, _ in entities]
        ):
            self.logger.info('Selection is valid')
            return True
        else:
            self.logger.info('Selection is _not_ valid')
            return False

    def discover(self, session, entities, event):
        return self.validate_entities(entities)

    def interface(self, session, entities, event):
        values = event['data'].get('values', {})
        if values:
            return

        project_names = [session.get('Project', entity[1])['full_name'] for entity in entities]


        # Build a display string like '项目名', '项目名', '项目名' (supports Chinese)
        selection_value = "'" + "', '".join(project_names) + "'"

        # Populate ui with the project name.
        widgets = [
            {
                'type': 'label', 
                'name': 'devider',
                'value': '---'
            },
            {
                'type': 'label', 
                'name': 'Date_Range',
                'value': '- *Note: If no date range is selected, "All Dates" will be used.*'
            },
            {
                'label': 'From',
                'type': 'date',
                'name': 'start_date',
                'value': '',
            },
            {
                'label': 'To',
                'type': 'date',
                'name': 'end_date',
                'value': '',
            },
            {
                'type': 'label', 
                'name': 'devider',
                'value': '---'
            },
            {
                'label': 'Selection',
                'type': 'label',
                'name': 'selection',
                'value': f"*Current selection: {selection_value}*",
            },
            {
                'type': 'label', 
                'name': 'devider',
                'value': '---'
            },
            {
                'type':'hidden',
                'name': 'project_names',
                'value': project_names,
            },
            {
                'label': 'All Projects ( Ignore current projects selection )',
                'type': 'boolean',
                'name': 'is_all_projects',
                'value': False,
            },
            {
                'label': 'Use My Last Settings',
                'type': 'boolean',
                'name': 'use_last_settings',
                'value': False,
            }

        ]
        return widgets

    def _create_job(self, event):
        user_id = event['source']['user']['id']
        job = self.session.create(
            'Job',
            {
                'user': self.session.get('User', user_id),
                'status': 'running',
                'data': json.dumps(
                    {'description': str('Timelog Export (click to download)')}
                ),
            },
        )
        self.session.commit()
        return job

    def _parse_date_range(self, start_date_str: str | None, end_date_str: str | None):
        start_dt = None
        end_dt = None
        # Treat incoming dates as LOCAL calendar days, convert bounds to UTC
        local_tz = datetime.datetime.now().astimezone().tzinfo
        if start_date_str:
            try:
                d = datetime.date.fromisoformat(start_date_str)
                start_local = datetime.datetime(d.year, d.month, d.day, 0, 0, 0, tzinfo=local_tz)
                start_dt = start_local.astimezone(datetime.timezone.utc)
            except ValueError:
                pass
        if end_date_str:
            try:
                d = datetime.date.fromisoformat(end_date_str)
                end_local = datetime.datetime(d.year, d.month, d.day, 23, 59, 59, 999999, tzinfo=local_tz)
                end_dt = end_local.astimezone(datetime.timezone.utc)
            except ValueError:
                pass
        return start_dt, end_dt

    def create_excel_file(self, project_names, file_path, start_date=None, end_date=None, is_all_projects=True):
        '''Generate excel file from *project_names* and output *file_path*.'''

        # Prepare excel file.
        xlsFile = xlsxwriter.Workbook(file_path)

        # Define book_title.
        book_title = xlsFile.add_format(
            {
                'bold': True,
                'font_size': 20,
            }
        )

        # Define book_header.
        book_header = xlsFile.add_format(
            {
                'bold': True,
                'font_size': 16,
            }
        )
        book_header.set_bg_color('DEEDF2')
        # Define book_body.
        book_body = xlsFile.add_format(
            {
                'bold': True,
                'font_size': 12,
            }
        )
        
        # Numeric format for 2-decimal numbers
        book_body_num = xlsFile.add_format({'bold': True, 'font_size': 12, 'num_format': '0.00'})
       
        # Define blue bold style.

        # Create worksheet.
        sheet = xlsFile.add_worksheet('Timelog')
        sheet.set_landscape()  # Set orientation
        sheet.set_paper(9)  # Set print size

        # Server-side query with optional filters to reduce data volume
        base = 'select id, start, duration, user.username, user.first_name, user.last_name, context.project.full_name from Timelog'
        conditions = []
        if not is_all_projects and project_names:
            quoted = ', '.join([f'"{p}"' for p in project_names])
            conditions.append(f'context.project.full_name in ({quoted})')
        # Apply date filters when provided (start-only, end-only, or both)
        start_dt, end_dt = self._parse_date_range(start_date, end_date)
        if start_dt:
            conditions.append(f'start >= "{start_dt.isoformat()}"')
        if end_dt:
            conditions.append(f'start <= "{end_dt.isoformat()}"')
        expr = base if not conditions else f'{base} where ' + ' and '.join(conditions)
        timelogs = self.session.query(expr).all()

        
        hours_tracked = sum([t['duration'] for t in timelogs]) / 3600
        project_count = len(set([t['context']['project']['full_name'] for t in timelogs]))
        user_count = len(set([t['user']['username'] for t in timelogs]))

        self.logger.info(f"hours_tracked: {hours_tracked}")
        self.logger.info(f"project_count: {project_count}")
        self.logger.info(f"user_count: {user_count}")



        # Wrtite header section
        # Write Title
        report_scope = 'All Projects' if is_all_projects else ', '.join(project_names)
        sheet.write(0, 1, f"Timelog report for {report_scope}", book_title)
        # Write hours_tracked
        sheet.write(1, 1, 'Hours Tracked', book_header)
        sheet.set_column(1, 1, 20)
        sheet.write_number(2, 1, float(hours_tracked), book_body_num)
        # Write Project_count
        sheet.write(1, 2, 'Projects', book_header)
        sheet.set_column(1, 2, 20)
        sheet.write(2, 2, project_count, book_body)
        # Write user_count
        sheet.write(1, 3, 'Users', book_header)
        sheet.set_column(1, 3, 20)
        sheet.write(2, 3, user_count, book_body)
        # Write Date Range
        sheet.write(1, 4, 'Date Range', book_header)
        sheet.set_column(1, 4, 20)
        if start_date and end_date:
            date_range = f"{start_date} - {end_date}"
        elif start_date and not end_date:
            date_range = f"{start_date} - ∞"
        elif end_date and not start_date:
            date_range = f"∞ - {end_date}"
        else:
            date_range = 'All Dates'
        sheet.write(2, 4, date_range, book_body)



        # Set styles on cells (User Breakdown)
        sheet.write(3, 1, 'User', book_header)
        sheet.set_column(3, 1, 20)

        sheet.write(3, 2, 'Total (Hours)', book_header)
        sheet.set_column(3, 2, 20)

        sheet.write(3, 3, 'Billable', book_header)
        sheet.set_column(3, 3, 20)

        sheet.write(3, 4, 'Non Billable', book_header)
        sheet.set_column(3, 4, 20)

        # Write user data into cells.
        users = set([t['user'] for t in timelogs])
        # Case-insensitive, accent-insensitive sort by first_name then last_name
        def _norm(s):
            return unicodedata.normalize('NFKD', (s or '')).casefold()
        sorted_users = sorted(users, key=lambda u: (_norm(u.get('first_name')), _norm(u.get('last_name'))))
        for idx, sorted_user in enumerate(sorted_users):
            sheet.write(idx + 4, 1, f"{sorted_user['first_name']} {sorted_user['last_name']}", book_body)

            # Write total hours for this user.
            total_hours = sum([t['duration'] for t in timelogs if t['user'] == sorted_user]) / 3600
            sheet.write_number(idx + 4, 2, float(total_hours), book_body_num)

            # Write billable hours for this user.
            billable_hours = sum([t['duration'] for t in timelogs if t['user'] == sorted_user and t['context']['type']['is_billable'] is True]) / 3600
            sheet.write_number(idx + 4, 3, float(billable_hours), book_body_num)

            # Write non-billable hours for this user.
            non_billable_hours = total_hours - billable_hours
            sheet.write_number(idx + 4, 4, float(non_billable_hours), book_body_num)

        xlsFile.close()

    def _settings_path(self, username: str | None = None):
        # Save to a repo-local config folder parallel to 'hook'
        base_dir = os.path.dirname(__file__)
        if username:
            # sanitize username for filesystem
            safe = ''.join(c if (c.isalnum() or c in ('-', '_')) else '_' for c in str(username))
            config_dir = os.path.abspath(os.path.join(base_dir, '..', 'config', 'users', safe))
        else:
            config_dir = os.path.abspath(os.path.join(base_dir, '..', 'config'))
        os.makedirs(config_dir, exist_ok=True)
        path = os.path.join(config_dir, 'last_setting.json')
        try:
            self.logger.debug(f"Settings path resolved for '{username}': {path}")
        except Exception:
            pass
        return path

    def _load_last_settings(self, username: str | None = None):
        try:
            path = self._settings_path(username)
            if not os.path.exists(path):
                return None
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            self.logger.warning(f"Failed to load last settings: {e}")
            return None

    def _save_last_settings(self, values: dict, username: str | None = None):
        try:
            picks = {k: values.get(k) for k in ['start_date', 'end_date', 'project_names', 'is_all_projects']}
            path = self._settings_path(username)
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(picks, f, ensure_ascii=False)
            try:
                self.logger.info(f"Saved last settings for user '{username}' at {path}")
            except Exception:
                pass
        except Exception as e:
            self.logger.warning(f"Failed to save last settings: {e}")

    def launch(self, session, entities, event):

        # self.logger.info(f'current Selections: {entities}')

        values = event['data'].get('values', {})
        if not values:
            return

        # self.logger.info(f'values: {values}')

        # If user opts to use last settings, override current values
        if values.get('use_last_settings'):
            last = self._load_last_settings(self._current_username(event))
            if last:
                self.logger.info('Using last settings to override current input')
                # Override selectively with validation
                for date_key in ['start_date', 'end_date']:
                    v = last.get(date_key)
                    if v is None:
                        continue
                    if isinstance(v, str):
                        if v == '':
                            values[date_key] = ''
                        else:
                            try:
                                datetime.date.fromisoformat(v)
                                values[date_key] = v
                            except ValueError:
                                self.logger.warning(f"Last settings invalid {date_key} format '{v}', keeping UI value")
                pn = last.get('project_names')
                if pn is not None:
                    if isinstance(pn, list) and all(isinstance(x, str) for x in pn):
                        values['project_names'] = pn
                    else:
                        self.logger.warning('Last settings invalid project_names, keeping UI value')
                ap = last.get('is_all_projects')
                if ap is not None:
                    if isinstance(ap, bool):
                        values['is_all_projects'] = ap
                    else:
                        self.logger.warning('Last settings invalid is_all_projects, keeping UI value')
            else:
                self.logger.info('No last settings found, proceeding with current input')

        # Validate date range if provided
        start_str = values.get('start_date') or ''
        end_str = values.get('end_date') or ''
        if start_str and end_str:
            try:
                start_date = datetime.date.fromisoformat(start_str)
                end_date = datetime.date.fromisoformat(end_str)
            except ValueError:
                return {'success': False, 'message': '日期格式不正确，应为 YYYY-MM-DD'}
            if start_date > end_date:
                return {'success': False, 'message': '开始日期必须小于等于结束日期'}

        # Create a new running Job.
        job = self._create_job(event)

        file_path = tempfile.NamedTemporaryFile(
            prefix='timelog_', suffix='.xlsx', delete=False
        ).name

        try:
            # Pass filters via values
            self.create_excel_file(
                values['project_names'],
                file_path,
                start_date=values.get('start_date') or None,
                end_date=values.get('end_date') or None,
                is_all_projects=bool(values.get('is_all_projects'))
            )

            # Persist current values as last settings after successful generation
            self._save_last_settings(values, self._current_username(event))

        except Exception as error:
            job['status'] = 'failed'
            job['data'] = json.dumps({'description': str(error)})
            self.session.commit()
            return {
                'success': False,
                'message': 'An error occured during the document generation.',
            }


        # Create component on the server, name it and attach it the job.
        job_file = os.path.basename(file_path).replace('.xlsx', '')
        component = self.session.create_component(
            file_path, data={'name': job_file}, location=self.ftrack_server_location
        )
        self.session.commit()

        # Create job component.
        self.session.create(
            'JobComponent', {'component_id': component['id'], 'job_id': job['id']}
        )
        # Set job status as done.
        job['status'] = 'done'
        self.session.commit()

        # Return the successful status to the user.
        return {'success': True, 'message': 'Successfully generated timelog report.'}

    def _current_username(self, event) -> str | None:
        try:
            src = event.get('source', {}) if isinstance(event, dict) else {}
            user = src.get('user', {}) if isinstance(src, dict) else {}
            username = user.get('username') or user.get('id')
            if not username:
                username = getattr(self.session, 'api_user', None)
            return str(username) if username else None
        except Exception:
            # Fallback to session api_user if event structure is unexpected
            return getattr(self.session, 'api_user', None)

def register(api_object, **kw):
    '''Register hook with provided *api_object*.'''

    # Validate that session is an instance of ftrack_api.Session. If not,
    # assume that register is being called from an old or incompatible API and
    # return without doing anything.
    if not isinstance(api_object, ftrack_api.session.Session):
        return

    action = timelogExport(api_object)
    action.register()


if __name__ == '__main__':
    # To be run as standalone code.
    logging.basicConfig(level=logging.INFO)
    session = ftrack_api.Session(auto_connect_event_hub=True)
    register(session)

    # Wait for events
    logging.info('Registered actions and listening for events. Use Ctrl-C to abort.')
    session.event_hub.wait()