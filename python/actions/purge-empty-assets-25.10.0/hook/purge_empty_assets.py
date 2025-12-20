import datetime
import logging

from ftrack_action_handler.action import BaseAction
import ftrack_api


class PurgeEmptyAssets(BaseAction):

    label = 'Purge Empty Assets'
    identifier = 'broTiger.purge_empty_assets'
    description = 'Purge empty assets in the selected project.'
    icon = 'https://cdn-icons-png.flaticon.com/128/12782/12782267.png'

    def discover(self, session, entities, event):

        if len(entities)==1 and entities[0][0]=='Project':
            return True
        else:
            return False

    def _fetch_all_assets_in_project(self, session, project_id):
        # 仅查询资产（不在QL中做聚合排序）
        assets = session.query(
            f'select id, name, type.name from Asset where project.id = "{project_id}"'
        ).all()

        # 在 Python 侧按版本数量升序排序，并缓存类型名
        version_counts = {a['id']: len(a['versions']) for a in assets}
        type_names = {a['id']: a['type']['name'] for a in assets}
        assets_sorted = sorted(assets, key=lambda a: version_counts[a['id']])
        # self.logger.info(f"assets(sorted by versions): {[(a['name'], version_counts[a['id']]) for a in assets_sorted]}")
        return assets_sorted, version_counts, type_names


    def interface(self, session, entities, event):
        if event['data'].get('values', {}):
            return

        project_type, project_id = entities[0]

        assets_sorted, version_counts, type_names = self._fetch_all_assets_in_project(session, project_id)
        versioned_assets_enum = [
            {
                'label': f"📦[ {versioned_asset_enum['name']} ] has {version_counts[versioned_asset_enum['id']]} version{'s' if version_counts[versioned_asset_enum['id']] != 1 else ''} - Type: {type_names[versioned_asset_enum['id']]} ",
                'value': versioned_asset_enum['id'],
            }
            for versioned_asset_enum in assets_sorted if version_counts[versioned_asset_enum['id']] > 0
        ]

        empty_assets = [empty_asset for empty_asset in assets_sorted if version_counts[empty_asset['id']] == 0]
        empty_asset_widgets = [
            {
                'type': 'boolean',
                'name': f"{empty_asset_opt['id']}",   # 唯一键：asset_<id>
                'label': f"📦[ {empty_asset_opt['name']} ] has 0 versions - Type: {type_names[empty_asset_opt['id']]}",   # 显示名称 + 版本数
                'value': True,               # 默认选中
            }
            for empty_asset_opt in empty_assets
        ]

        widgets = [
            {
            'type': 'label', 
            'name': 'caution',
            'value': f'⚠️ CAUTION: \n- This action will delete the selected assets. \n- This action is NOT REVERSIBLE!'
            },
            {
            'type': 'label', 
            'name': 'versioned_assets_label',
            'value': f'⚠️ {len(assets_sorted) - len(empty_assets)}/{len(assets_sorted)} Assets are NOT EMPTY'
            },
            {
            'label': 'But I still want to delete... ', 
            'type': 'enumerator', 
            'name': 'versioned_aseet_to_delete',
            # 'value': all_assets[0]['value'],
            'data': versioned_assets_enum,
            },
            {
            'type': 'label', 
            'name': 'devider',
            'value': '---'
            },
            {
            'type': 'label', 
            'name': 'empty_assets_label',
            'value': f'✅ {len(empty_assets)}/{len(assets_sorted)} Assets are EMPTY'
            },         
        ] + empty_asset_widgets
        
        return widgets

    def launch(self, session, entities, event):
        
        if 'values' in event['data']:
            values = event['data']['values']
            self.logger.info('Got values: {0}'.format(values))

            # 获取枚举选择的（有版本的）资产
            selected_versioned_asset_id = values.get('versioned_aseet_to_delete')
            selected_versioned_asset = (
                session.get('Asset', selected_versioned_asset_id)
                if selected_versioned_asset_id
                else None
            )

            # 解析布尔项：被勾选的空资产
            selected_empty_asset_ids = []
            for name, flag in values.items():
                if name == 'versioned_aseet_to_delete':
                    continue
                if flag is True:
                    # 兼容两种命名：asset_<id> 或直接 <id>
                    if isinstance(name, str) and name.startswith('asset_'):
                        selected_empty_asset_ids.append(name.split('_', 1)[1])
                    else:
                        selected_empty_asset_ids.append(name)

            selected_empty_assets = [
                session.get('Asset', asset_id) for asset_id in selected_empty_asset_ids
            ]


            # 汇总目标（过滤掉 None）
            targets = [
                a for a in (
                    ([selected_versioned_asset] if selected_versioned_asset else [])
                    + selected_empty_assets
                ) if a is not None
            ]

            for target in targets:
                session.delete(target)
            session.commit()

            return {
                'success': True,
                'message': f"🗑️ Successfully deleted {len(targets)} asset(s)"
            }


def register(session, **kw):
    '''Register plugin.'''
    if not isinstance(session, ftrack_api.Session):
        return
    action = PurgeEmptyAssets(session)
    action.register()


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    session = ftrack_api.Session(auto_connect_event_hub=True)
    register(session)

    session.event_hub.wait()

