import logging
import os
import json
import threading
from typing import Dict, Optional, List

import ftrack_api
from ftrack_action_handler.action import BaseAction
try:
    # 优先使用包内相对导入（ftrack-connect 加载为包时）
    from .excel_utils import (
        read_table,
        export_pictures_by_row,
        extract_original_images_by_row_from_xlsx,
    )
except ImportError:
    # 当脚本被直接执行（无父包）时，回退到基于当前目录的本地导入
    import sys as _sys
    _sys.path.insert(0, os.path.dirname(__file__))
    from excel_utils import (
        read_table,
        export_pictures_by_row,
        extract_original_images_by_row_from_xlsx,
    )

logger = logging.getLogger('batch_task_thumbnails_import')


class BatchTaskThumbnailsImport(BaseAction):
    label = 'Batch Import Tasks Thumbnails from Excel File'
    identifier = 'bro.tiger.batch-task-thumbnails-import'
    description = 'Import tasks thumbnails from Excel embedded images.'
    icon = 'https://cdn-icons-png.flaticon.com/128/13406/13406972.png'

    def validate_selection(self, entities):
        '''Return True if the selection is valid.

        Utility method to check *entities* validity.

        '''
        if len(entities) != 1:
            return False

        entity_type, entity_id = entities[0]
        if entity_type == 'Project':
            return True

        return False

    def discover(self, session, entities, event):
        """Return True so this action is globally discoverable.

        This action does not depend on a specific selection; it operates on the
        provided Excel path entered by the user.
        """
        return self.validate_selection(entities)
    
    def _pick_excel_file_path(self) -> Optional[Dict[str, str]]:
        """Open a top-most, application-modal Qt dialog to select Excel file.

        Adds two inputs:
        - Import From Sheet (default: "Shots")
        - Hierarchy Rule (Use comma to separate) (default: "Shots,Sequence,Shot,Task")

        Also adds:
        - Image Column (default: "Thumbnail")

        Returns a dict with keys: path, sheet, rule, image_col. Returns None on cancel.
        """
        try:
            from Qt import QtWidgets, QtCore, QtGui
        except Exception as e:
            logger.error(f'无法导入 Qt 模块：{e}')
            return None

        # 在方法内定义对话框类，避免全局依赖
        class DropSelectDialog(QtWidgets.QDialog):
            def __init__(self, parent=None):
                super().__init__(parent)
                self.setWindowTitle('Select An Excel File')
                # 置顶 + 模态，保证可见性
                self.setWindowFlag(QtCore.Qt.WindowStaysOnTopHint, True)
                self.setWindowModality(QtCore.Qt.ApplicationModal)
                self.setAcceptDrops(True)
                self._headers = []
                # Widen the dialog to provide more space for long rules
                try:
                    self.resize(720, self.sizeHint().height())
                except Exception:
                    pass

                info = QtWidgets.QLabel('Drag and drop the Excel file here, or click "Browse…"')
                info.setAlignment(QtCore.Qt.AlignCenter)
                info.setStyleSheet('border: 2px dashed #888; padding: 24px; border-radius: 8px;')

                self.path_edit = QtWidgets.QLineEdit(self)
                self.path_edit.setPlaceholderText('Selected file path will appear here')

                browse_btn = QtWidgets.QPushButton('Browse…', self)
                browse_btn.clicked.connect(self._browse)

                # Sheet and hierarchy rule inputs
                form = QtWidgets.QFormLayout()
                # Image Column dropdown (editable)
                self.image_combo = QtWidgets.QComboBox(self)
                self.image_combo.setEditable(True)
                self.image_combo.addItem('Thumbnail')
                self.image_combo.setToolTip('Column header containing embedded images (default: Thumbnail).')
                form.addRow('Image Column:', self.image_combo)

                # Sheet dropdown (editable)
                self.sheet_combo = QtWidgets.QComboBox(self)
                self.sheet_combo.setEditable(True)
                self.sheet_combo.addItem('Shots')
                self.sheet_combo.setToolTip('Excel sheet name to read, e.g., Shots or Assets.')
                form.addRow('Import From Sheet:', self.sheet_combo)

                self.rule_edit = QtWidgets.QLineEdit(self)
                self.rule_edit.setText('Shots/Sequence/Shot/Task')
                self.rule_edit.setPlaceholderText('Use / to separate levels')
                self.rule_edit.setToolTip('Top-down hierarchy columns ending with Task, e.g., Shots/Sequence/Shot/Task.')
                # Make rule entry clearly left-aligned and wide
                try:
                    self.rule_edit.setAlignment(QtCore.Qt.AlignLeft)
                    self.rule_edit.setMinimumWidth(560)
                    self.rule_edit.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
                except Exception:
                    pass
                form.addRow('Task Path:', self.rule_edit)

                # Ensure labels and fields align to the left/top
                try:
                    form.setLabelAlignment(QtCore.Qt.AlignLeft)
                    form.setFormAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignTop)
                except Exception:
                    pass

                button_box = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
                button_box.accepted.connect(self.accept)
                button_box.rejected.connect(self.reject)
                # Keep reference for validation enable/disable
                self.ok_button = button_box.button(QtWidgets.QDialogButtonBox.Ok)

                layout = QtWidgets.QVBoxLayout(self)
                layout.addWidget(info)
                layout.addWidget(self.path_edit)
                layout.addWidget(browse_btn)
                layout.addLayout(form)
                try:
                    layout.setAlignment(form, QtCore.Qt.AlignLeft)
                except Exception:
                    pass
                # Visual rule builder: available columns list + selected chips area
                selector_group = QtWidgets.QGroupBox('Visual Rule Builder', self)
                selector_layout = QtWidgets.QVBoxLayout(selector_group)
                lists_row = QtWidgets.QHBoxLayout()

                # Left: Available columns
                avail_col_layout = QtWidgets.QVBoxLayout()
                avail_label = QtWidgets.QLabel('Available Columns', selector_group)
                self.available_list = QtWidgets.QListWidget(selector_group)
                self.available_list.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
                self.available_list.itemDoubleClicked.connect(self._add_available_item)
                avail_col_layout.addWidget(avail_label)
                avail_col_layout.addWidget(self.available_list)
                # Make available list take less horizontal space to free chips area
                lists_row.addLayout(avail_col_layout, 1)

                # Right: Selected hierarchy chips
                sel_col_layout = QtWidgets.QVBoxLayout()
                sel_label = QtWidgets.QLabel('Selected Columns', selector_group)
                self.selected_list = QtWidgets.QListWidget(selector_group)
                self.selected_list.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
                self.selected_list.setDragDropMode(QtWidgets.QAbstractItemView.InternalMove)
                self.selected_list.setDefaultDropAction(QtCore.Qt.MoveAction)
                try:
                    self.selected_list.setFlow(QtWidgets.QListView.LeftToRight)
                    self.selected_list.setWrapping(True)
                    # Chip styling: darker background for readability and white text
                    self.selected_list.setStyleSheet('QListWidget::item { border: 1px solid #ddd; border-radius: 12px; padding: 4px 8px; margin: 4px; background: #ABABAB; color: #FFFFFF; } QListWidget::item:selected { background: #ABABAB; color: #FFFFFF; }')
                except Exception:
                    pass
                # Overlay hint: show usage instructions in gray when empty
                try:
                    self.selected_hint = QtWidgets.QLabel(self.selected_list)
                    self.selected_hint.setText('Drag to reorder • Double-click to remove')
                    self.selected_hint.setAlignment(QtCore.Qt.AlignCenter)
                    self.selected_hint.setStyleSheet('color: #8a8a8a;')
                    self.selected_hint.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents, True)
                except Exception:
                    self.selected_hint = None
                self.selected_list.itemDoubleClicked.connect(self._remove_selected_item)
                try:
                    self.selected_list.model().rowsMoved.connect(lambda *args: (self._sync_rule_from_selected(), self._update_selected_hint_visibility()))
                    self.selected_list.model().rowsInserted.connect(lambda *args: (self._sync_rule_from_selected(), self._update_selected_hint_visibility()))
                    self.selected_list.model().rowsRemoved.connect(lambda *args: (self._sync_rule_from_selected(), self._update_selected_hint_visibility()))
                except Exception:
                    pass
                sel_col_layout.addWidget(sel_label)
                sel_col_layout.addWidget(self.selected_list)
                # Initialize hint visibility
                try:
                    self._update_selected_hint_visibility()
                except Exception:
                    pass
                # Give selected chips area more horizontal room
                lists_row.addLayout(sel_col_layout, 3)
                try:
                    lists_row.setStretch(0, 1)
                    lists_row.setStretch(1, 3)
                except Exception:
                    pass

                selector_layout.addLayout(lists_row)
                layout.addWidget(selector_group)
                # Validation message area
                self.validation_label = QtWidgets.QLabel('', self)
                self.validation_label.setStyleSheet('color: #b00020;')
                self.validation_label.setWordWrap(True)
                layout.addWidget(self.validation_label)
                layout.addWidget(button_box)

                # Autocomplete for hierarchy rule based on headers
                self._rule_completer = QtWidgets.QCompleter([], self)
                self._rule_completer.setCaseSensitivity(QtCore.Qt.CaseInsensitive)
                self.rule_edit.setCompleter(self._rule_completer)

                # Wire up live validation and dynamic population
                self.path_edit.textChanged.connect(self._on_path_changed)
                self.sheet_combo.currentTextChanged.connect(self._on_sheet_changed)
                self.image_combo.currentTextChanged.connect(self._validate_inputs)
                self.rule_edit.textChanged.connect(self._validate_inputs)
                self.rule_edit.textChanged.connect(self._on_rule_text_changed)

                # Left-align editable combo line edits
                try:
                    if self.image_combo.isEditable():
                        self.image_combo.lineEdit().setAlignment(QtCore.Qt.AlignLeft)
                    if self.sheet_combo.isEditable():
                        self.sheet_combo.lineEdit().setAlignment(QtCore.Qt.AlignLeft)
                except Exception:
                    pass

                # Guard to avoid recursive sync between rule text and chips
                self._syncing = False
                # Initial validation
                self._validate_inputs()

            def dragEnterEvent(self, e):
                if e.mimeData().hasUrls():
                    # 仅接受本地文件
                    for u in e.mimeData().urls():
                        if u.isLocalFile():
                            e.acceptProposedAction()
                            return
                e.ignore()

            def dropEvent(self, e):
                urls = [u for u in e.mimeData().urls() if u.isLocalFile()]
                if urls:
                    self.path_edit.setText(urls[0].toLocalFile())
                    e.acceptProposedAction()
                else:
                    e.ignore()

            def _browse(self):
                # 使用非原生对话框以更好控制窗口标志
                path, _ = QtWidgets.QFileDialog.getOpenFileName(
                    self,
                    'Select An Excel File',
                    os.path.expanduser('~'),
                    'Excel Files (*.xlsx *.xlsm *.xls);;All Files (*)'
                )
                if path:
                    self.path_edit.setText(path)
                    # Trigger sheet/header population
                    self._on_path_changed(path)

            def _on_path_changed(self, *_):
                path = self.path_edit.text().strip()
                if not path or not os.path.exists(path):
                    self.sheet_combo.clear()
                    self.sheet_combo.addItem('Shots')
                    self.image_combo.clear()
                    self.image_combo.addItem('Thumbnail')
                    self._headers = []
                    self._set_rule_headers([])
                    try:
                        self.available_list.clear()
                        self.selected_list.clear()
                    except Exception:
                        pass
                    self._validate_inputs()
                    return
                sheets = self._load_sheets_from_file(path)
                self.sheet_combo.blockSignals(True)
                self.sheet_combo.clear()
                for s in sheets or ['Shots']:
                    self.sheet_combo.addItem(s)
                # Prefer default if present
                if 'Shots' in sheets:
                    self.sheet_combo.setCurrentText('Shots')
                elif sheets:
                    self.sheet_combo.setCurrentText(sheets[0])
                self.sheet_combo.blockSignals(False)
                self._on_sheet_changed(self.sheet_combo.currentText())

            def _on_sheet_changed(self, *_):
                path = self.path_edit.text().strip()
                sheet = self.sheet_combo.currentText().strip() or 'Shots'
                headers = self._load_headers(path, sheet)
                self._headers = headers or []
                # Update image column choices
                self.image_combo.blockSignals(True)
                self.image_combo.clear()
                if self._headers:
                    for h in self._headers:
                        self.image_combo.addItem(h)
                else:
                    self.image_combo.addItem('Thumbnail')
                # prefer 'Thumbnail' if found
                if 'Thumbnail' in self._headers:
                    self.image_combo.setCurrentText('Thumbnail')
                self.image_combo.blockSignals(False)
                # Update completer for rule
                self._set_rule_headers(self._headers)
                # Auto-adjust default rule based on selected sheet (non-destructive)
                try:
                    default_shots = 'Shots/Sequence/Shot/Task'
                    default_assets = 'Assets/AssetCategory/Folder/AssetBuild/Task'
                    current_rule = (self.rule_edit.text() or '').strip()
                    if sheet.lower() == 'assets':
                        if current_rule in ('', default_shots):
                            self.rule_edit.setText(default_assets)
                    elif sheet.lower() == 'shots':
                        if current_rule in ('', default_assets):
                            self.rule_edit.setText(default_shots)
                except Exception:
                    pass
                # Populate visual builder lists
                try:
                    self._populate_available(self._headers)
                    self._apply_rule_to_selected(self.rule_edit.text().strip())
                except Exception:
                    pass
                self._validate_inputs()

            def _set_rule_headers(self, headers: List[str]):
                self._rule_completer.model().setStringList(headers)

            def _on_rule_text_changed(self, *_):
                if self._syncing:
                    return
                try:
                    self._syncing = True
                    self._apply_rule_to_selected(self.rule_edit.text().strip())
                finally:
                    self._syncing = False

            def _populate_available(self, headers: List[str]):
                try:
                    self.available_list.clear()
                    img_col = (self.image_combo.currentText() or '').strip()
                    for h in headers or []:
                        item = QtWidgets.QListWidgetItem(h)
                        if img_col and h == img_col:
                            try:
                                item.setForeground(QtGui.QColor('#666'))
                                item.setToolTip('Currently selected as Image Column')
                            except Exception:
                                pass
                        self.available_list.addItem(item)
                except Exception:
                    pass

            def _apply_rule_to_selected(self, rule_text: str):
                tokens = [s.strip() for s in (rule_text or '').split('/') if s.strip()]
                try:
                    self._syncing = True
                    self.selected_list.clear()
                    for t in tokens:
                        if self._headers and t not in self._headers:
                            continue
                        self.selected_list.addItem(QtWidgets.QListWidgetItem(t))
                finally:
                    self._syncing = False
                self._sync_rule_from_selected()

            def _sync_rule_from_selected(self):
                if self._syncing:
                    return
                try:
                    self._syncing = True
                    parts: List[str] = []
                    for i in range(self.selected_list.count()):
                        parts.append(self.selected_list.item(i).text().strip())
                    self.rule_edit.setText('/'.join([p for p in parts if p]))
                finally:
                    self._syncing = False
                self._validate_inputs()
                try:
                    self._update_selected_hint_visibility()
                except Exception:
                    pass

            def _add_available_item(self, item: QtWidgets.QListWidgetItem):
                text = (item.text() or '').strip()
                if not text:
                    return
                for i in range(self.selected_list.count()):
                    if self.selected_list.item(i).text().strip() == text:
                        return
                self.selected_list.addItem(QtWidgets.QListWidgetItem(text))
                self._sync_rule_from_selected()
                try:
                    self._update_selected_hint_visibility()
                except Exception:
                    pass

            def _remove_selected_item(self, item: QtWidgets.QListWidgetItem):
                row = self.selected_list.row(item)
                if row >= 0:
                    self.selected_list.takeItem(row)
                    self._sync_rule_from_selected()
                    try:
                        self._update_selected_hint_visibility()
                    except Exception:
                        pass

            def _update_selected_hint_visibility(self):
                try:
                    hint = getattr(self, 'selected_hint', None)
                    if hint is None:
                        return
                    count = self.selected_list.count()
                    hint.setVisible(count == 0)
                    # Fit the hint over the list's viewport
                    vp = self.selected_list.viewport()
                    r = vp.rect()
                    hint.setGeometry(r)
                except Exception:
                    pass

            def _load_sheets_from_file(self, path: str) -> List[str]:
                sheets: List[str] = []
                try:
                    import openpyxl
                    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
                    sheets = list(wb.sheetnames)
                    try:
                        wb.close()
                    except Exception:
                        pass
                    return sheets
                except Exception:
                    pass
                # Fallback to xlwings
                try:
                    import xlwings as xw
                    app = xw.App(visible=False)
                    book = xw.Book(path)
                    sheets = [s.name for s in book.sheets]
                except Exception:
                    sheets = []
                finally:
                    try:
                        book.close()
                    except Exception:
                        pass
                    try:
                        app.kill()
                    except Exception:
                        pass
                return sheets

            def _load_headers(self, path: str, sheet_name: str) -> List[str]:
                headers: List[str] = []
                if not path or not os.path.exists(path):
                    return headers
                # Try openpyxl first to avoid launching Excel
                try:
                    import openpyxl
                    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
                    if sheet_name in wb.sheetnames:
                        ws = wb[sheet_name]
                        # Read first row as headers
                        first_row = next(ws.iter_rows(min_row=1, max_row=1, values_only=True))
                        headers = [str(v).strip() if v is not None else '' for v in first_row]
                        headers = [h for h in headers if h]
                    try:
                        wb.close()
                    except Exception:
                        pass
                    return headers
                except Exception:
                    pass
                # Fallback to xlwings via excel_utils.read_table for consistent behavior
                try:
                    import xlwings as xw
                    app = xw.App(visible=False)
                    book = xw.Book(path)
                    sheet = book.sheets[sheet_name]
                    from .excel_utils import read_table as _rt
                except Exception:
                    try:
                        # When executed directly without package context
                        from excel_utils import read_table as _rt
                    except Exception:
                        _rt = None
                try:
                    if _rt is not None:
                        hdrs, _ = _rt(sheet)
                        headers = hdrs or []
                except Exception:
                    headers = []
                finally:
                    try:
                        book.close()
                    except Exception:
                        pass
                    try:
                        app.kill()
                    except Exception:
                        pass
                return headers

            def _validate_inputs(self):
                msgs: List[str] = []
                path = self.path_edit.text().strip()
                if not path:
                    msgs.append('Please select an Excel file.')
                elif not os.path.exists(path):
                    msgs.append('Selected file does not exist.')

                sheet = self.sheet_combo.currentText().strip()
                if not sheet:
                    msgs.append('Sheet name is required. Example: Shots or Assets.')
                elif self._headers == []:
                    msgs.append('Unable to read headers from the selected sheet.')

                image_col = self.image_combo.currentText().strip()
                if not image_col:
                    msgs.append('Image Column is required. Example: Thumbnail.')
                elif self._headers and image_col not in self._headers:
                    msgs.append(f'Image Column "{image_col}" not found in headers.')

                rule_text = self.rule_edit.text().strip()
                tokens = [s.strip() for s in rule_text.split('/') if s.strip()]
                if len(tokens) < 2:
                    msgs.append('Task Path must have at least two levels ending with Task.')
                elif tokens[-1].lower() != 'task':
                    msgs.append('Task Path must end with Task (e.g., Shots/Sequence/Shot/Task).')
                else:
                    # verify tokens exist in headers
                    missing = [t for t in tokens if self._headers and t not in self._headers]
                    if missing:
                        msgs.append(f'Selected columns not found in headers: {missing}.')

                # Update message and OK state
                self.validation_label.setText('\n'.join(msgs))
                if hasattr(self, 'ok_button') and self.ok_button:
                    self.ok_button.setEnabled(len(msgs) == 0)

        app = QtWidgets.QApplication.instance()
        created_app = False
        if app is None:
            try:
                app = QtWidgets.QApplication([])
                created_app = True
            except Exception as e:
                logger.error(f'创建 QApplication 失败：{e}')
                return None

        parent = None
        try:
            # 创建轻量级父窗口，确保对话框能在应用层激活
            parent = QtWidgets.QWidget()
            parent.setWindowTitle('File Selection')
            # Make the parent as unobtrusive as possible: tiny, frameless, transparent, tool window.
            parent.setWindowFlags(
                parent.windowFlags()
                | QtCore.Qt.WindowStaysOnTopHint
                | QtCore.Qt.Tool
                | QtCore.Qt.FramelessWindowHint
            )
            parent.setFixedSize(1, 1)
            parent.setWindowOpacity(0.01)
            parent.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents, True)
            parent.show()
            parent.raise_()
            parent.activateWindow()

            dlg = DropSelectDialog(parent)
            dlg.raise_()
            dlg.activateWindow()
            result = dlg.exec_() if hasattr(dlg, 'exec_') else dlg.exec()
            if result == QtWidgets.QDialog.Accepted:
                path = dlg.path_edit.text().strip()
                sheet = dlg.sheet_combo.currentText().strip() or 'Shots'
                rule = dlg.rule_edit.text().strip() or 'Shots/Sequence/Shot/Task'
                image_col = dlg.image_combo.currentText().strip() or 'Thumbnail'
                if not path:
                    return None
                return {'path': path, 'sheet': sheet, 'rule': rule, 'image_col': image_col}
            return None
        finally:
            try:
                if parent is not None:
                    parent.close()
            except Exception:
                pass
            if created_app:
                try:
                    app.quit()
                except Exception:
                    pass

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
        import xlwings as xw
        app = xw.App(visible=False)
        updated = 0
        book = None
        try:
            book = xw.Book(excel_path)
            sheet = book.sheets[sheet_name]
            headers, rows = read_table(sheet)
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
                pic_map = export_pictures_by_row(sheet, image_col_name=image_col_name)

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
                if book:
                    book.close()
            except Exception:
                pass
            try:
                app.kill()
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
        import xlwings as xw
        app = xw.App(visible=False)
        updated = 0
        book = None
        try:
            book = xw.Book(excel_path)
            sheet = book.sheets[sheet_name]
            headers, rows = read_table(sheet)
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
                pic_map = export_pictures_by_row(sheet, image_col_name=image_col_name)

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
                if book:
                    book.close()
            except Exception:
                pass
            try:
                app.kill()
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

    def launch(self, session, entities, event):
        # Always use the Qt picker to get path, sheet, and rule
        selection = self._pick_excel_file_path()
        if not selection:
            return {'success': False, 'message': 'No file selected. Action canceled.'}
        excel_path = selection['path']
        sheet_name = selection.get('sheet', 'Shots')
        rule_text = selection.get('rule', 'Shots/Sequence/Shot/Task')
        image_col_name = selection.get('image_col', 'Thumbnail')

        # Friendly pre-validations
        if not sheet_name.strip():
            return {'success': False, 'message': 'Sheet name is required. Example: Shots or Assets.'}
        if not image_col_name.strip():
            return {'success': False, 'message': 'Image Column is required. Example: Thumbnail.'}
        hierarchy_cols = [s.strip() for s in rule_text.split('/') if s.strip()]
        if len(hierarchy_cols) < 2:
            return {'success': False, 'message': 'Invalid Task Path. Provide at least two levels ending with Task, e.g., Shots/Sequence/Shot/Task.'}
        if hierarchy_cols[-1].lower() != 'task':
            return {'success': False, 'message': 'Task Path must end with Task. Example: Shots/Sequence/Shot/Task.'}
        # Optional: warn for duplicate levels (does not block)
        if len(set(hierarchy_cols)) != len(hierarchy_cols):
            # Keep running but inform the user
            logger.warning(f'Duplicate columns found in Task Path: {hierarchy_cols}')

        # 仅支持在 Project 上触发：直接从 entities 取项目ID。
        try:
            entity_type, project_id = entities[0]
        except Exception:
            return {'success': False, 'message': 'Please trigger this action on a Project.'}
        if str(entity_type).lower() != 'project' or not project_id:
            return {'success': False, 'message': 'Please trigger this action on a Project.'}

        # Create a running Job to reflect progress and avoid UI blocking
        job = self._create_job(event)
        job_id = job['id'] if job is not None else None

        def _background_worker():
            # Use a fresh session in background thread to avoid thread-safety issues.
            try:
                bg_session = ftrack_api.Session()
            except Exception as se:
                logger.error(f'Failed to create background ftrack session: {se}')
                return

            try:
                stats = self._import_thumbnails_by_rule(
                    session=bg_session,
                    project_id=project_id,
                    excel_path=excel_path,
                    sheet_name=sheet_name,
                    image_col_name=image_col_name,
                    hierarchy_cols=hierarchy_cols,
                )
                msg = (
                    f"Updated thumbnails: {stats['updated']}, Pictures mapped: {stats['pictures']}"
                )
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

        # Start background thread and return immediately so UI remains responsive
        threading.Thread(target=_background_worker, daemon=True).start()

        return {
            'success': True,
            'message': 'Initializing import, please check Jobs for progress.'
        }

def register(session, **kw):
    '''Register plugin.'''
    if not isinstance(session, ftrack_api.Session):
        return
    action = BatchTaskThumbnailsImport(session)
    action.register()

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    session = ftrack_api.Session(auto_connect_event_hub=True)
    register(session)
    # Dev-only: allow fast hard-exit when stopping the script to avoid
    # lingering Python processes. Enable with env FTRACK_DEV_AUTO_EXIT=1.
    if os.getenv('FTRACK_DEV_AUTO_EXIT') == '1':
        try:
            import signal

            def _dev_hard_exit(signum, frame):
                try:
                    session.event_hub.stop()
                except Exception:
                    pass
                # Force process termination to avoid leftovers.
                os._exit(0)

            signal.signal(signal.SIGINT, _dev_hard_exit)
            signal.signal(signal.SIGTERM, _dev_hard_exit)
        except Exception:
            # If signals cannot be registered (platform constraints), continue normally.
            pass

    session.event_hub.wait()