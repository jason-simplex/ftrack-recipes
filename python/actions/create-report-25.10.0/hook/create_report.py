#!/usr/bin/env python
# :coding: utf-8
# :copyright: Copyright (c) 2018 ftrack

import io
import urllib3
import os
import tempfile
import logging
import json

import ftrack_api
import xlsxwriter

from ftrack_action_handler.action import BaseAction


class CreateReportAction(BaseAction):
    '''Create report action class.'''

    label = 'Create Report Action'
    identifier = 'com.ftrack.recipes.create_report'
    description = 'Create example report from selected Project'
    icon = 'https://pipedream.com/s.v0/app_lxhDLL/logo/orig'


    @property
    def session(self):
        '''Return convenient exposure of the self._session reference.'''
        return self._session

    @property
    def ftrack_server_location(self):
        '''Return the ftrack.server location.'''
        return self.session.query("Location where name is 'ftrack.server'").one()

    def validate_selection(self, entities):
        '''Return True if the selection is valid.

        Utility method to check *entities* validity.

        '''
        if not entities:
            return False

        entity_type, entity_id = entities[0]
        if entity_type == 'Project':
            return True

        return False

    def discover(self, session, entities, event):
        '''Return True if the action can be discovered.

        Check if the current selection can discover this action.

        '''
        return self.validate_selection(entities)

    def launch(self, session, entities, event):
        '''Return result of running action.'''

        self.logger.info('Launching action with selection {0}'.format(entities))

        # 由于 interface() 提交了数据， 因此现在event['data']['values'] 是带着 {'project_name': 'xxx'} 的字典
        values = event['data'].get('values', {})

        # If there's no value coming from the ui, we can bail out.
        if not values:
            return

        # Create a new running Job.
        job = self._create_job(event)

        # .name 属性获取这个临时文件的路径，并将其赋值给 file_path 变量
        file_path = tempfile.NamedTemporaryFile(
            prefix='example_utilization_report', suffix='.xlsx', delete=False
        ).name

        # 这里调用了 create_excel_file() 方法，并传入了 project_name 和 file_path 作为参数。
        try:
            self.logger.info('Invoking crate_excel_file method.')
            self.create_excel_file(values['project_name'], file_path)
        except Exception as error:
            # If an exception happens in the document generation
            # mark the job as failed.
            job['status'] = 'failed'
            job['data'] = json.dumps({'description': str(error)})
            # Commit job status changes and description.
            self.session.commit()

            # Return an error message to the user.
            return {
                'success': False,
                'message': 'An error occured during the document generation.',
            }

        # Create component on the server, name it and attach it the job.
        # os.path.basename() 返回路径中的基本名称部分，即去掉了目录路径后的文件名本身
        # 同时又去掉了 .xlsx 后缀. job_file 就成了 ‘example_utilization_report’
        # session.create_component(path, data=None, location='auto') 是session的接口方法，用于创建组件
        # path 也可以是序列 ， 比如 '/path/to/file.%04d.ext [1-5, 7, 8, 50-20]'
        # self.ftrack_server_location 是把上方一个实例方法转化成了一个实例属性
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
        return {'success': True, 'message': 'Successfully generated project report.'}

    def interface(self, session, entities, event):
        '''Return interface for *entities*.'''
        values = event['data'].get('values', {})
        # Interface will be raised as long as there's no value set.
        # here is a good place where to put validations.
        if values:
            return

        # Get the project object.
        # entities[0]确保是单选一个 entity
        # entities[0][1]获取entity id
        # 据此得到一个 project 对象
        project = self.session.get('Project', entities[0][1])

        # Populate ui with the project name.
        widgets = [
            {
                'label': 'Project',
                'value': project['name'],
                'name': 'project_name',
                'type': 'text',
            }
        ]

        return widgets

    def _create_job(self, event):
        '''Return new job from *event*.

        ..note::

            This function will auto-commit the session.

        '''

        user_id = event['source']['user']['id']
        job = self.session.create(
            'Job',
            {
                'user': self.session.get('User', user_id),
                'status': 'running',
                'data': json.dumps(
                    {'description': str('Project Report Export (click to download)')}
                ),
            },
        )
        self.session.commit()
        return job

    def create_excel_file(self, project_name, file_path):
        '''Generate excel file from *project_name* and output *file_path*.'''
        # 当前定义的 create_excel_file 方法会在 launch()方法里被调用
        # xlsxwriter.Workbook() 方法创建一个新的工作簿对象，参数是要创建的 Excel 文件的文件名（包括路径）。
        #  file_path 是一个文件路径字符串，表示要创建的 Excel 文件的文件名（包括路径）。如果该文件已存在，则会覆盖它。
        #  file_path 在函数定义这里不需要赋值，等到被launch()调用时才赋值。
        xlsFile = xlsxwriter.Workbook(file_path)

        # Define bold style.
        # add_format()的参数是一个字典，表示格式的属性。
        bold16 = xlsFile.add_format(
            {
                'bold': True,
                'font_size': 16,
            }
        )

        # add_format() 来定义一个蓝色的格式。参数是个字典 {}，表示格式的属性。
        # 更多 format : https://xlsxwriter.readthedocs.io/format.html#format-methods-and-format-properties:~:text=your%20host%20OS.-,Format%20methods%20and%20Format%20properties,-%23
        # set_bg_color() 的参数是一个颜色代码，表示单元格背景色。
        blue = xlsFile.add_format({'bold': True})
        blue.set_bg_color('dbedf3')

        # Create worksheet.
        # add_worksheet() 方法创建一个新的工作表，参数是工作表的名称。
        sheet = xlsFile.add_worksheet('Report')
        sheet.set_landscape()  # 设置朝向
        sheet.set_paper(9)  # 设置纸张大小

        # 找到一个 project
        project = self.session.query(
            'Project where name is "{0}"'.format(project_name)
        ).one()

        # 找到该 project 下的所有 shots
        shots = self.session.query(
            'select name, description, thumbnail_url, status.name, link from Shot where project.id is "{0}" order by name asc'.format(project['id'])
        ).all()

        # Start populating excel file.
        # write(row, col, string[, cell_format])
        # https://xlsxwriter.readthedocs.io/worksheet.html#worksheet-write:~:text=write_string(row%2C%20col%2C%20string%5B%2C%20cell_format%5D)
        # 这里的行、列都是从 0 开始的。
        # 这里的样式是通过 add_format() 方法创建的。 
        # set_column(first_col, last_col, width, cell_format, options)
        sheet.write(0, 1, 'Project report for {0}'.format(project['name']), bold16)


        
        
        # 为表头设置样式
        sheet.write(2, 1, 'Thumbnails', bold16)
        sheet.set_column(2, 1, 13) 

        sheet.write(2, 2, 'Shot Links', bold16)
        sheet.set_column(2, 2, 50)        

        sheet.write(2, 3, 'Shot Names', bold16)
        sheet.set_column(2, 3, 50)

        sheet.write(2, 4, 'Description', bold16)
        sheet.set_column(2, 4, 50)

        sheet.write(2, 5, 'Status', bold16)
        sheet.set_column(2, 5, 13)

        http = urllib3.PoolManager()

        # Write shot data into cells.
        # sorted() 是 Python 内置的一个函数，用于返回一个新的已排序的列表。它不会修改原始列表，而是生成一个新的列表
        # enumerate(sorted(shots)) 的作用是遍历排序后的 shots 列表，并为每个元素提供一个索引。
        # 这样你就可以在循环中同时访问每个 shot 及其对应的索引。
        # enumerate(sorted(shots)) 会生成一个枚举对象，每次迭代时返回一个包含两个元素的元组：索引和 shot 对象。
        # 索引从 0 开始，shot 对象是 shots 列表中的一个元素。
        for idx, shot in enumerate(shots):

            # Get shot status color from server.
            status_color = shot['status']['color']
            xls_shot_status = xlsFile.add_format({'bold': True, 'font_size': 10})
            xls_shot_status.set_bg_color(status_color)
            '''
            用生成器提取shot的link列表里的每一个link字典元素的name属性, 
            用'/'分隔得到一个字符串作为shot_link, 以下是 shot['link'] 的完整形态
            [
                {'id': '323f7664-acc5-4d8a-9a82-c4ff6d6605ce', 'name': 'xxxxxx', 'type': 'Project'}, 
                {'id': 'b07eb79d-bd96-42cc-8159-9f41df39f97f', 'name': 'seq02', 'type': 'TypedContext'}, 
                {'id': '0243701c-5463-405b-a87b-6d18069914ea', 'name': 'shot01', 'type': 'TypedContext'}
            ]
            '''
            shot_link = ' / '.join(link['name'] for link in shot['link'])
            thumb_url = shot['thumbnail_url']['url']
            # print(thumb_url)
            image_data = io.BytesIO(http.request('GET', thumb_url).data)
            # print(image_data)


            
            sheet.set_column(idx + 3, 1, 13)
            sheet.embed_image(idx + 3, 1, "img.jpeg", {'image_data': image_data})
            
            sheet.write(idx + 3, 2, shot_link, blue)
            sheet.set_column(idx + 3, 2, 50)
                         
            sheet.write(idx + 3, 3, shot['name'], blue)
            sheet.set_column(idx + 3, 3, 50)

            sheet.write(idx + 3, 4, shot['description'])
            sheet.set_column(idx + 3, 4, 50)

            sheet.write(idx + 3, 5, shot['status']['name'], xls_shot_status)
            sheet.set_column(idx + 3, 5, 13)

            sheet.set_row(idx + 3, 40)


        xlsFile.close()


def register(api_object, **kw):
    '''Register hook with provided *api_object*.'''

    # Validate that session is an instance of ftrack_api.Session. If not,
    # assume that register is being called from an old or incompatible API and
    # return without doing anything.
    if not isinstance(api_object, ftrack_api.session.Session):
        return

    action = CreateReportAction(api_object)
    action.register()


if __name__ == '__main__':
    # To be run as standalone code.
    logging.basicConfig(level=logging.INFO)
    session = ftrack_api.Session(auto_connect_event_hub=True)
    register(session)

    # Wait for events
    logging.info('Registered actions and listening for events. Use Ctrl-C to abort.')
    session.event_hub.wait()
