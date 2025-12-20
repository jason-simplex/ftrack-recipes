#!/usr/bin/env python
# :coding: utf-8
# :copyright: Copyright (c) 2025 Bro.Tiger

import ftrack_api
import json
import logging
import arrow

from ftrack_action_handler.action import BaseAction

session = ftrack_api.Session()
task_id = '62b6f02a-1039-4da8-95c8-4d8cbad2ba9d'
latest_versions = session.query(f"select id from AssetVersion where task_id is {task_id} and is_latest_version is true").all()
for version in latest_versions:
    print(version['id'])
