# :coding: utf-8
# :copyright: Copyright (c) 2025 bro.tiger
import logging
import os
import json
import threading
from typing import Dict, Optional, List
import ftrack_api
import sys as _sys
import pathlib
_deps = pathlib.Path(__file__).resolve().parent.parent / 'dependencies'
if str(_deps) not in _sys.path:
    _sys.path.insert(0, str(_deps))
 
try:
    from excel_utils import (
        extract_original_images_by_row_from_xlsx,
        read_headers_all,
    )
except Exception:
    extract_original_images_by_row_from_xlsx = None

logger = logging.getLogger('batch_task_thumbnails_import')
from ui_utils import ui_log, get_dropped_excel_path, show_info, show_warn, qta_icon_pixmap, set_button_icon_qta


class BatchTaskThumbnailsImport:

    def _set_entity_thumbnail(self, session, entity, image_path: str) -> None:
        # Use entity.create_thumbnail to set thumbnail; no deprecated fallbacks.
        entity.create_thumbnail(image_path, data={'name': os.path.basename(image_path)})

    def _find_task_by_shots_sequence_shot_task(self, session, project_id: str,
                                               shots_name: str, sequence_name: str,
                                               shot_name: str, task_name: str) -> Optional[dict]:
        """Find Task by hierarchy: Shots > Sequence > Shot > Task (exact name)."""
        def esc(s: str) -> str:
            return s.replace('"', '\\"') if s is not None else ''

        base = (
            f'project_id is "{esc(project_id)}" '
            f'and parent.name is "{esc(shot_name)}" '
            f'and parent.parent.name is "{esc(sequence_name)}" '
            f'and parent.parent.parent.name is "{esc(shots_name)}"'
        )
        q = f'Task where {base} and name is "{esc(task_name)}"'
        res = session.query(q).all()
        if res:
            return res[0]
        return None

    def _find_task_by_chain(self, session, project_id: str, names_topdown: List[str]) -> Optional[dict]:
        """Find Task via a generic parent chain.

        names_topdown: e.g., ["Shots", "Sequence", "Shot", "Task"] or
        ["Assets", "AssetCategory", "Folder", "AssetBuild", "Task"].
        The last element is the Task name; preceding elements are parent names
        from top-level downwards.
        """
        def esc(s: str) -> str:
            return s.replace('"', '\\"') if s is not None else ''

        if not names_topdown or len(names_topdown) < 2:
            return None
        task_name = (names_topdown[-1] or '').strip()
        if not task_name:
            return None

        parents = [n.strip() for n in names_topdown[:-1]]
        if any(not p for p in parents):
            return None

        base = f'project_id is "{esc(project_id)}"'
        conds = []
        parents_count = len(parents)
        for t, pname in enumerate(parents):
            depth = parents_count - t  # number of parent hops from Task
            chain = 'parent.' * depth + 'name'
            conds.append(f'{chain} is "{esc(pname)}"')
        where = f'{base} and name is "{esc(task_name)}"'
        if conds:
            where += ' and ' + ' and '.join(conds)
        q = f'Task where {where}'
        res = session.query(q).all()
        if res:
            return res[0]
        return None

    def _import_thumbnails_by_hierarchy(self, session, project_id: str,
                                        excel_path: str, sheet_name: str = 'Sheet1',
                                        image_col_name: str = 'Thumbnail',
                                        shots_col_name: str = 'Shots', seq_col_name: str = 'Sequence', shot_col_name: str = 'Shot',
                                        task_col_name: str = 'Task') -> Dict[str, int]:
        from openpyxl import load_workbook
        updated = 0
        wb = None
        try:
            wb = load_workbook(excel_path, data_only=True, read_only=True)
            ws = wb[sheet_name]
            it = ws.iter_rows(values_only=True)
            first = next(it, None)
            if first is None:
                headers = []
                rows = []
            else:
                if isinstance(first, (list, tuple)):
                    headers = [str(h).strip() if h is not None else '' for h in first]
                else:
                    headers = [str(first).strip() if first is not None else '']
                rows = list(it)
            if not headers or not rows:
                raise RuntimeError('No data found in the sheet.')

            def col_idx(name: str) -> Optional[int]:
                try:
                    return headers.index(name)
                except ValueError:
                    return None

            idx_shots = col_idx(shots_col_name)
            idx_seq = col_idx(seq_col_name)
            idx_shot = col_idx(shot_col_name)
            idx_task = col_idx(task_col_name)
            missing = [n for n, i in [(shots_col_name, idx_shots), (seq_col_name, idx_seq), (shot_col_name, idx_shot), (task_col_name, idx_task)] if i is None]
            if missing:
                raise RuntimeError(f"Required columns not found: {missing}. Headers: {headers}")

            # Prefer original image extraction from xlsx structure to preserve resolution
            pic_map = extract_original_images_by_row_from_xlsx(
                excel_path=excel_path,
                sheet_name=sheet_name,
                image_col_name=image_col_name,
                headers=headers,
            )
            # Fallback to rendering the cell if native extraction failed or returned empty
            if not pic_map:
                pic_map = {}

            for i, row in enumerate(rows, start=2):
                try:
                    image_path = pic_map.get(i)
                    if not image_path:
                        continue
                    shots_name = (row[idx_shots] or '').strip() if idx_shots is not None else ''
                    seq_name = (row[idx_seq] or '').strip() if idx_seq is not None else ''
                    shot_name = (row[idx_shot] or '').strip() if idx_shot is not None else ''
                    task_name = (row[idx_task] or '').strip() if idx_task is not None else ''

                    task = self._find_task_by_shots_sequence_shot_task(session, project_id, shots_name, seq_name, shot_name, task_name)
                    if not task:
                        logger.warning(f'Row {i}: Task not found for Shots="{shots_name}", Sequence="{seq_name}", Shot="{shot_name}", Task="{task_name}"')
                        continue

                    self._set_entity_thumbnail(session, task, image_path)
                    updated += 1
                except Exception as e:
                    logger.error(f'Row {i}: failed to process - {e}')

            try:
                session.commit()
            except Exception as e:
                logger.error(f'Commit failed: {e}')
                raise
            return {'updated': updated, 'pictures': len(pic_map)}
        finally:
            try:
                if wb:
                    wb.close()
            except Exception:
                pass

    def _import_thumbnails_by_rule(self, session, project_id: str,
                                   excel_path: str,
                                   sheet_name: str,
                                   image_col_name: str,
                                   hierarchy_cols: List[str]) -> Dict[str, int]:
        """Import thumbnails using a dynamic hierarchy defined by column names.

        hierarchy_cols: a top-down list of column names, where the last
        element is the Task column. Example:
          ["Shots", "Sequence", "Shot", "Task"]
          ["Assets", "AssetCategory", "Folder", "AssetBuild", "Task"]
        """
        from openpyxl import load_workbook
        updated = 0
        wb = None
        try:
            wb = load_workbook(excel_path, data_only=True, read_only=True)
            ws = wb[sheet_name]
            it = ws.iter_rows(values_only=True)
            first = next(it, None)
            if first is None:
                headers = []
                rows = []
            else:
                if isinstance(first, (list, tuple)):
                    headers = [str(h).strip() if h is not None else '' for h in first]
                else:
                    headers = [str(first).strip() if first is not None else '']
                rows = list(it)
            if not headers or not rows:
                raise RuntimeError('No data found in the sheet.')

            def col_idx(name: str) -> Optional[int]:
                try:
                    return headers.index(name)
                except ValueError:
                    return None

            # validate required columns
            idx_map = [col_idx(n) for n in hierarchy_cols]
            missing_cols = [n for n, i in zip(hierarchy_cols, idx_map) if i is None]
            if missing_cols:
                raise RuntimeError(f"Required columns not found: {missing_cols}. Headers: {headers}")

            # Extract pictures per row
            pic_map = extract_original_images_by_row_from_xlsx(
                excel_path=excel_path,
                sheet_name=sheet_name,
                image_col_name=image_col_name,
                headers=headers,
            )
            if not pic_map:
                pic_map = {}

            for i, row in enumerate(rows, start=2):
                try:
                    image_path = pic_map.get(i)
                    if not image_path:
                        continue
                    # collect names from row according to hierarchy columns
                    names_topdown = []
                    for idx in idx_map:
                        value = (row[idx] or '').strip()
                        names_topdown.append(value)
                    if any(not v for v in names_topdown):
                        logger.warning(f'Row {i}: missing hierarchy values {names_topdown}')
                        continue

                    task = self._find_task_by_chain(session, project_id, names_topdown)
                    if not task:
                        logger.warning(f'Row {i}: Task not found for chain={names_topdown}')
                        continue

                    self._set_entity_thumbnail(session, task, image_path)
                    updated += 1
                except Exception as e:
                    logger.error(f'Row {i}: failed to process - {e}')

            try:
                session.commit()
            except Exception as e:
                logger.error(f'Commit failed: {e}')
                raise
            return {'updated': updated, 'pictures': len(pic_map)}
        finally:
            try:
                if wb:
                    wb.close()
            except Exception:
                pass

    def _create_job(self, event):
        try:
            user_id = event.get('source', {}).get('user', {}).get('id')
            job = self.session.create(
                'Job',
                {
                    'user': self.session.get('User', user_id) if user_id else None,
                    'status': 'running',
                    'data': json.dumps({'description': 'Task Thumbnail Import (processing)'})
                },
            )
            self.session.commit()
            return job
        except Exception:
            # If job creation fails, continue without job but log
            logger.warning('Failed to create Job for import; proceeding without job status updates.')
            return None

def start_import(session, project_id, excel_path, sheet_name, rule_text, image_col_name):
    if not sheet_name.strip():
        return {'success': False, 'message': 'Sheet name is required. Example: Shots or Assets.'}
    if not image_col_name.strip():
        return {'success': False, 'message': 'Image Column is required. Example: Thumbnail.'}
    hierarchy_cols = [s.strip() for s in rule_text.split('/') if s.strip()]
    if len(hierarchy_cols) < 2:
        return {'success': False, 'message': 'Invalid Task Path. Provide at least two levels ending with Task, e.g., Shots/Sequence/Shot/Task.'}
    if hierarchy_cols[-1].lower() != 'task':
        logger.warning(f'Last level is not Task: {hierarchy_cols}')
    runner = BatchTaskThumbnailsImport()
    def _background_worker():
        try:
            bg_session = ftrack_api.Session()
        except Exception as se:
            logger.error(f'Failed to create background ftrack session: {se}')
            return
        job_id = None
        try:
            try:
                user = None
                try:
                    api_user = getattr(session, 'api_user', None) or os.getenv('FTRACK_API_USER')
                    if api_user:
                        user = bg_session.query(f'Select id from User where username is "{api_user}"').first()
                except Exception:
                    user = None
                job = bg_session.create('Job', {'user': user, 'status': 'running', 'data': json.dumps({'description': 'Task Thumbnail Import (processing)'})})
                bg_session.commit()
                job_id = job['id']
            except Exception:
                logger.warning('Failed to create Job for import; proceeding without job status updates.')
            stats = runner._import_thumbnails_by_rule(
                session=bg_session,
                project_id=project_id,
                excel_path=excel_path,
                sheet_name=sheet_name,
                image_col_name=image_col_name,
                hierarchy_cols=hierarchy_cols,
            )
            msg = f"Updated thumbnails: {stats['updated']}, Pictures mapped: {stats['pictures']}"
            if job_id:
                try:
                    job_entity = bg_session.get('Job', job_id)
                    job_entity['status'] = 'done'
                    job_entity['data'] = json.dumps({'description': msg})
                    bg_session.commit()
                except Exception:
                    logger.warning('Background: failed to update Job to done.')
        except Exception as e:
            if job_id:
                try:
                    job_entity = bg_session.get('Job', job_id)
                    job_entity['status'] = 'failed'
                    job_entity['data'] = json.dumps({'description': f'Import failed. Please verify sheet name, image column, and Task Path. Error: {e}'})
                    bg_session.commit()
                except Exception:
                    logger.warning('Background: failed to update Job to failed.')
            logger.error(f'Background import failed: {e}')
    threading.Thread(target=_background_worker, daemon=True).start()
    return {'success': True, 'message': 'Initializing import, please check Jobs for progress.'}

        

from ftrack_connect.qt import QtWidgets, QtCore, QtGui
import ftrack_connect.ui.application
try:
    import qtawesome as qta
except Exception:
    qta = None

class DropLineEdit(QtWidgets.QLineEdit):
    def __init__(self, on_file_selected=None, *args, **kwargs):
        super(DropLineEdit, self).__init__(*args, **kwargs)
        self._on_file_selected = on_file_selected
        self.setAcceptDrops(True)
    def dragEnterEvent(self, e):
        p = get_dropped_excel_path(e.mimeData())
        if p:
            ui_log(f'dnd_enter {p}')
            try:
                e.setDropAction(QtCore.Qt.CopyAction)
            except Exception:
                pass
            e.accept()
            e.acceptProposedAction()
        else:
            e.ignore()
    def dragMoveEvent(self, e):
        p = get_dropped_excel_path(e.mimeData())
        if p:
            try:
                e.setDropAction(QtCore.Qt.CopyAction)
            except Exception:
                pass
            e.accept()
            e.acceptProposedAction()
        else:
            e.ignore()
    def dropEvent(self, e):
        p = get_dropped_excel_path(e.mimeData())
        if p:
            ui_log(f'dnd_drop {p}')
            self.setText(p)
            if callable(self._on_file_selected):
                self._on_file_selected()
            try:
                e.setDropAction(QtCore.Qt.CopyAction)
            except Exception:
                pass
            e.acceptProposedAction()
        else:
            e.ignore()

class AvailListWidget(QtWidgets.QListWidget):
    def startDrag(self, supportedActions):
        it = self.currentItem()
        if not it:
            return
        drag = QtGui.QDrag(self)
        mime = QtCore.QMimeData()
        mime.setText(it.text())
        drag.setMimeData(mime)
        drag.exec_(QtCore.Qt.CopyAction)

class PathListWidget(QtWidgets.QListWidget):
    def __init__(self, on_change=None, *args, **kwargs):
        super(PathListWidget, self).__init__(*args, **kwargs)
        self._on_change = on_change
    def dropEvent(self, e):
        md = e.mimeData()
        if md.hasText() and e.source() is not self:
            t = md.text().strip()
            if t:
                self.addItem(t)
                e.acceptProposedAction()
                if callable(self._on_change):
                    self._on_change()
                return
        super(PathListWidget, self).dropEvent(e)
        if callable(self._on_change):
            self._on_change()

class BatchThumbsWidget(ftrack_connect.ui.application.ConnectWidget):
    try:
        icon = qta.icon('mdi6.file-image-plus', color='#03DAC5', scale_factor=1) if qta is not None else QtGui.QIcon()
    except Exception:
        icon = QtGui.QIcon()
    def __init__(self, session, parent=None):
        super(BatchThumbsWidget, self).__init__(session, parent=parent)
        self._session = session
        self._sheet_headers = {}
        self._sheets = []
        self._build_ui()

    def _build_ui(self):
        self.setObjectName('BatchThumbsWidget')
        self.setAcceptDrops(True)
        layout = QtWidgets.QVBoxLayout()
        self.setLayout(layout)
        title_row = QtWidgets.QHBoxLayout()
        title_icon = QtWidgets.QLabel()
        pm = qta_icon_pixmap('mdi6:image-multiple', 24)
        if pm is not None:
            title_icon.setPixmap(pm)
        title = QtWidgets.QLabel('Batch Import Task Thumbnails From Excel')
        title.setStyleSheet('font-size:18px; font-weight:600;')
        title_row.addWidget(title_icon)
        title_row.addWidget(title)
        title_row.addStretch(1)
        path_row = QtWidgets.QHBoxLayout()
        self.path_edit = DropLineEdit(self._populate_sheets_and_headers)
        self.path_edit.setPlaceholderText('Select Excel file')
        browse = QtWidgets.QPushButton('Browse')
        browse.setStyleSheet(
            'QPushButton{padding:8px 16px; border-radius:4px; background:#1976D2; color:#fff;}'
            'QPushButton:hover{background:#1E88E5;}'
            'QPushButton:pressed{background:#1565C0;}'
        )
        set_button_icon_qta(browse, 'mdi6:file-excel')
        browse.clicked.connect(self._browse)
        path_row.addWidget(self.path_edit)
        path_row.addWidget(browse)
        form = QtWidgets.QFormLayout()
        self.project_combo = QtWidgets.QComboBox()
        self.sheet_combo = QtWidgets.QComboBox()
        self.image_combo = QtWidgets.QComboBox()
        self.rule_edit = QtWidgets.QLineEdit()
        self.rule_edit.setPlaceholderText('Shots/Sequence/Shot/Task')
        self.rule_edit.setReadOnly(True)
        form.addRow('Project', self.project_combo)
        form.addRow('Sheet', self.sheet_combo)
        form.addRow('Image Column', self.image_combo)
        form.addRow('Task Path', self.rule_edit)
        lists_row = QtWidgets.QHBoxLayout()
        left_col = QtWidgets.QVBoxLayout()
        right_col = QtWidgets.QVBoxLayout()
        left_label = QtWidgets.QLabel('Available Columns')
        right_label = QtWidgets.QLabel('Task Path Builder')
        self.avail_list = AvailListWidget()
        self.avail_list.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.avail_list.setDragEnabled(True)
        self.avail_list.setDragDropMode(QtWidgets.QAbstractItemView.DragOnly)
        self.path_list = PathListWidget(self._sync_rule_text)
        self.path_list.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.path_list.setAcceptDrops(True)
        self.path_list.setDragEnabled(True)
        self.path_list.setDragDropMode(QtWidgets.QAbstractItemView.InternalMove)
        self.path_list.setDefaultDropAction(QtCore.Qt.MoveAction)
        self.path_list.setDropIndicatorShown(True)
        btns = QtWidgets.QHBoxLayout()
        add_btn = QtWidgets.QPushButton('Add →')
        rem_btn = QtWidgets.QPushButton('← Remove')
        add_btn.setStyleSheet(
            'QPushButton{padding:6px 12px; border-radius:4px; background:#2196F3; color:#fff;}'
            'QPushButton:hover{background:#42A5F5;}'
            'QPushButton:pressed{background:#1E88E5;}'
        )
        rem_btn.setStyleSheet(
            'QPushButton{padding:6px 12px; border-radius:4px; background:#9E9E9E; color:#fff;}'
            'QPushButton:hover{background:#B0B0B0;}'
            'QPushButton:pressed{background:#7E7E7E;}'
        )
        set_button_icon_qta(add_btn, 'mdi6:plus')
        set_button_icon_qta(rem_btn, 'mdi6:minus')
        add_btn.clicked.connect(self._on_add_column)
        rem_btn.clicked.connect(self._on_remove_column)
        btns.addWidget(add_btn)
        btns.addWidget(rem_btn)
        left_col.addWidget(left_label)
        left_col.addWidget(self.avail_list)
        right_col.addWidget(right_label)
        right_col.addWidget(self.path_list)
        right_col.addLayout(btns)
        lists_row.addLayout(left_col)
        lists_row.addLayout(right_col)
        run = QtWidgets.QPushButton('Import')
        run.setStyleSheet(
            'QPushButton{padding:10px 18px; border-radius:6px; background:#388E3C; color:#fff;}'
            'QPushButton:hover{background:#43A047;}'
            'QPushButton:pressed{background:#2E7D32;}'
        )
        set_button_icon_qta(run, 'mdi6:cloud-upload')
        run.clicked.connect(self._run_import)
        self.run_btn = run
        layout.addLayout(title_row)
        layout.addLayout(path_row)
        layout.addLayout(form)
        layout.addLayout(lists_row)
        self.task_warn = QtWidgets.QLabel()
        self.task_warn.setStyleSheet('color:#D32F2F; padding:4px 0;')
        layout.addWidget(self.task_warn)
        layout.addWidget(run)
        layout.addStretch(1)
        self._populate_projects()
        self.sheet_combo.currentIndexChanged.connect(self._update_headers_for_selected_sheet)
        self.path_list.model().rowsMoved.connect(self._sync_rule_text)
        self.path_list.model().rowsInserted.connect(self._sync_rule_text)
        self.path_list.model().rowsRemoved.connect(self._sync_rule_text)
        self.avail_list.itemDoubleClicked.connect(self._on_add_column)

    def _browse(self):
        p, _ = QtWidgets.QFileDialog.getOpenFileName(self, 'Select Excel File', os.path.expanduser('~'), 'Excel Files (*.xlsx *.xlsm *.xls);;All Files (*)')
        if p:
            self.path_edit.setText(p)
            self._populate_sheets_and_headers()

    def _populate_sheets_and_headers(self):
        path = self.path_edit.text().strip()
        sheets, headers_map = read_headers_all(path)
        self._sheets = sheets
        self._sheet_headers = headers_map or {}
        self.sheet_combo.clear()
        for s in (sheets or ['Shots']):
            self.sheet_combo.addItem(s)
        self.image_combo.clear()
        first_headers = headers_map.get(sheets[0], []) if sheets else []
        if first_headers:
            for h in first_headers:
                self.image_combo.addItem(h)
        else:
            self.image_combo.addItem('Thumbnail')
        self._populate_available_columns(first_headers)
        self._apply_default_task_path(self.sheet_combo.currentText(), first_headers)
        self._sync_rule_text()

    def _update_headers_for_selected_sheet(self):
        path = self.path_edit.text().strip()
        sheet = self.sheet_combo.currentText().strip()
        headers = []
        if not path or not sheet:
            return
        if not self._sheet_headers or sheet not in self._sheet_headers:
            sheets, headers_map = read_headers_all(path)
            self._sheets = sheets
            self._sheet_headers = headers_map or {}
        headers = list(self._sheet_headers.get(sheet, []))
        self.image_combo.clear()
        if headers:
            for h in headers:
                self.image_combo.addItem(h)
        else:
            self.image_combo.addItem('Thumbnail')
        self._populate_available_columns(headers)
        self._apply_default_task_path(sheet, headers)
        self._sync_rule_text()

    

    def _populate_available_columns(self, headers):
        self.avail_list.clear()
        for h in headers:
            if h:
                self.avail_list.addItem(h)

    def _apply_default_task_path(self, sheet, headers):
        self.path_list.clear()
        preset = []
        n = (sheet or '').strip().lower()
        if n == 'shots':
            preset = ['Shots', 'Sequence', 'Shot', 'Task']
        elif n == 'assets':
            preset = ['Assets', 'AssetCategory', 'Folder', 'AssetBuild', 'Task']
        if not preset:
            for h in headers:
                if h:
                    self.path_list.addItem(h)
        else:
            for x in preset:
                self.path_list.addItem(x)

    def _on_add_column(self):
        it = self.avail_list.currentItem()
        if it:
            self.path_list.addItem(it.text())
            self._sync_rule_text()

    def _on_remove_column(self):
        r = self.path_list.currentRow()
        if r >= 0:
            self.path_list.takeItem(r)
            self._sync_rule_text()

    def _sync_rule_text(self):
        cols = []
        for i in range(self.path_list.count()):
            t = self.path_list.item(i).text().strip()
            if t:
                cols.append(t)
        if cols:
            self.rule_edit.setText('/'.join(cols))
        else:
            self.rule_edit.setText('')
        warn = ''
        if cols and cols[-1].lower() != 'task':
            warn = 'Warning: Task must be the last level in Task Path.'
        self.task_warn.setText(warn)

    def dragEnterEvent(self, e):
        p = get_dropped_excel_path(e.mimeData())
        if p:
            try:
                e.setDropAction(QtCore.Qt.CopyAction)
            except Exception:
                pass
            e.accept()
            e.acceptProposedAction()
        else:
            e.ignore()

    def dragMoveEvent(self, e):
        p = get_dropped_excel_path(e.mimeData())
        if p:
            ui_log(f'dnd_move_widget {p}')
            try:
                e.setDropAction(QtCore.Qt.CopyAction)
            except Exception:
                pass
            e.accept()
            e.acceptProposedAction()
        else:
            e.ignore()

    def dropEvent(self, e):
        p = get_dropped_excel_path(e.mimeData())
        if p:
            ui_log(f'dnd_drop_widget {p}')
            self.path_edit.setText(p)
            self._populate_sheets_and_headers()
            try:
                e.setDropAction(QtCore.Qt.CopyAction)
            except Exception:
                pass
            e.acceptProposedAction()
        else:
            e.ignore()

    def _run_import(self):
        path = self.path_edit.text().strip()
        if not path:
            return
        sheet = self.sheet_combo.currentText() or 'Shots'
        cols = []
        for i in range(self.path_list.count()):
            t = self.path_list.item(i).text().strip()
            if t:
                cols.append(t)
        if not cols:
            rule = self.rule_edit.text().strip() or 'Shots/Sequence/Shot/Task'
            cols = [x.strip() for x in rule.split('/') if x.strip()]
        if not cols:
            return
        # Do not auto-append Task; instead show warning and continue.
        rule = '/'.join(cols)
        image_col = self.image_combo.currentText().strip() or 'Thumbnail'
        proj_id = self.project_combo.currentData()
        if not proj_id:
            return
        try:
            res = start_import(self._session, proj_id, path, sheet, rule, image_col)
            if isinstance(res, dict) and res.get('success'):
                show_info(self, 'Import started', 'Job has been created. Please check Jobs in ftrack to monitor progress.')
            else:
                show_warn(self, 'Import', res.get('message') if isinstance(res, dict) else 'Import request failed.')
        except Exception:
            pass

    def _populate_projects(self):
        self.project_combo.clear()
        try:
            items = list(self._session.query('select id, name from Project'))
            for p in items:
                self.project_combo.addItem(p['name'], p['id'])
        except Exception:
            pass

def register(session, **kw):
    if not isinstance(session, ftrack_api.session.Session):
        logger.debug(
        'Not subscribing plugin as passed argument {0!r} is not an '
        'ftrack_api.Session instance.'.format(session)
        )
        return
    plugin = ftrack_connect.ui.application.ConnectWidgetPlugin(BatchThumbsWidget)
    plugin.register(session, priority=10)
