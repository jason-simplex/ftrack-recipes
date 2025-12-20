import logging
import datetime
import json
from ftrack_action_handler.action import BaseAction
import ftrack_api
import arrow

SUPPORTED_ENTITY_TYPES = ('ReviewSession', 'ReviewSessionFolder',)
LABEL_OF_SYNC = 'Synced feedback'
EXCLUDE_NOTE_WITH_LABELS = ('Client feedback', LABEL_OF_SYNC)

class SyncNotesToClientReviews(BaseAction):
    label = 'Sync Notes to Client Review Sessions'
    identifier = 'bro.tiger.sync-internal-notes'
    description = 'Syncing internal AssetVersions\' notes to the Client Review Sessions'
    icon = 'https://cdn-icons-png.flaticon.com/128/3043/3043508.png'

    def _format_local_date(self, value):
        '''Return local time string from UTC date/time value.'''
        if not value:
            return None
        try:
            return arrow.get(value).to('local').format('YYYY-MM-DD HH:mm:ss')
        except Exception:
            try:
                if isinstance(value, datetime.datetime):
                    dt = value
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=datetime.timezone.utc)
                    return dt.astimezone().strftime('%Y-%m-%d %H:%M:%S')
                elif isinstance(value, datetime.date):
                    return value.strftime('%Y-%m-%d')
                elif isinstance(value, str):
                    # Best effort parse
                    try:
                        return arrow.get(value).to('local').format('YYYY-MM-DD HH:mm:ss')
                    except Exception:
                        return value
            except Exception:
                return str(value)
        return None

    def _get_deduplicated_review_session_objs(self, entities):
        '''Return unique review session objects deduped by asset_version.'''
        unique_rsos = []
        seen_asset_versions = set()
        review_sessions = []

        def _refresh_review_session_objects(review_session):
            try:
                if 'review_session_objects' in review_session:
                    del review_session['review_session_objects']
                self.session.populate(review_session, 'review_session_objects')
            except Exception as e:
                self.logger.debug(f"Refresh review_session_objects failed: {e}")

        def _refresh_review_sessions_in_folder(review_session_folder):
            try:
                if 'review_sessions' in review_session_folder:
                    del review_session_folder['review_sessions']
                self.session.populate(review_session_folder, 'review_sessions')
            except Exception as e:
                self.logger.debug(f"Refresh review_sessions in folder failed: {e}")

        def _ensure_asset_version_on_rso(rso):
            try:
                # Ensure asset_version relation is loaded fresh
                if 'asset_version' in rso:
                    # Clear cached field to force populate
                    av = rso['asset_version']
                    if not av:
                        del rso['asset_version']
                self.session.populate(rso, 'asset_version')
            except Exception:
                pass

        def _asset_version_id(rso):
            # Prefer explicit id field if present, fallback to entity reference
            try:
                av_id = rso['asset_version_id']
                if av_id:
                    return av_id
            except Exception:
                pass
            try:
                av = rso['asset_version']
                if av and 'id' in av:
                    return av['id']
            except Exception:
                pass
            return None

        for entity_type, entity_id in entities:
            if entity_type == 'ReviewSession':
                review_session = self.session.get(entity_type, entity_id)
                _refresh_review_session_objects(review_session)
                for rso in (review_session.get('review_session_objects') or []):
                    _ensure_asset_version_on_rso(rso)
                    av_id = _asset_version_id(rso)
                    if av_id is None or av_id not in seen_asset_versions:
                        if av_id is not None:
                            seen_asset_versions.add(av_id)
                        unique_rsos.append(rso)
            elif entity_type == 'ReviewSessionFolder':
                review_session_folder = self.session.get(entity_type, entity_id)
                _refresh_review_sessions_in_folder(review_session_folder)
                review_sessions.extend(review_session_folder['review_sessions'] or [])
        for review_session in review_sessions:
            _refresh_review_session_objects(review_session)
            for rso in (review_session['review_session_objects'] or []):
                _ensure_asset_version_on_rso(rso)
                av_id = _asset_version_id(rso)
                if av_id is None or av_id not in seen_asset_versions:
                    if av_id is not None:
                        seen_asset_versions.add(av_id)
                    unique_rsos.append(rso)

        return unique_rsos

    def _get_note_label_names(self, note):
        '''Return list of label names from note_label_links.'''
        try:
            # Ensure links are present; rely on lazy-loading of label entity fields.
            if 'note_label_links' not in note:
                self.session.populate(note, 'note_label_links')

            names = []
            for link in (note['note_label_links'] or []):
                try:
                    label = link['label']
                    if label:
                        # Accessing label['name'] triggers lazy load if needed.
                        names.append(label['name'])
                except Exception:
                    continue
            return names
        except Exception as e:
            # Keep UI resilient; if anything fails, show N/A without breaking.
            self.logger.debug(f"Get note label names failed: {e}")
            return []

    def _filter_notes(self, notes):
        '''Return notes excluding those having any label in EXCLUDE_NOTE_WITH_LABELS.
        Safely handles missing links or name fields.'''
        try:
            return [
                n for n in (notes or [])
                if not any(
                    (ln in EXCLUDE_NOTE_WITH_LABELS) for ln in self._get_note_label_names(n)
                )
            ]
        except Exception as e:
            self.logger.debug(f"Filter notes failed: {e}")
            return notes or []

    def _refresh_note_fields(self, note):
        '''Refresh label links for a Note entity.'''
        try:
            if 'note_label_links' in note:
                del note['note_label_links']
            self.session.populate(note, 'note_label_links')
        except Exception:
            pass

    def _refresh_asset_version_notes(self, asset_version):
        '''Refresh notes list and each note's fields for an AssetVersion.'''
        try:
            if 'notes' in asset_version:
                del asset_version['notes']
            self.session.populate(asset_version, 'notes')
            for note in asset_version['notes'] or []:
                self._refresh_note_fields(note)
        except Exception as e:
            self.logger.debug(f"Refresh asset version notes failed: {e}")

    def _refresh_rso_notes(self, rso):
        '''Refresh notes list for a ReviewSessionObject.'''
        try:
            if 'notes' in rso:
                del rso['notes']
            self.session.populate(rso, 'notes')
            for note in rso['notes'] or []:
                self._refresh_note_fields(note)
        except Exception as e:
            self.logger.debug(f"Refresh RSO notes failed: {e}")

    def _get_note_label_by_name(self, label_name):
        '''Return NoteLabel entity by name, create if missing.'''
        try:
            labels = list(self.session.query(f"NoteLabel where name is '{label_name}'"))
            if labels:
                return labels[0]
            label = self.session.create('NoteLabel', {'name': label_name})
            return label
        except Exception as e:
            self.logger.debug(f"Get/create NoteLabel failed: {e}")
            return None

    def _note_has_label(self, note, label_name):
        '''Return True if note already has label_name.'''
        try:
            return label_name in self._get_note_label_names(note)
        except Exception:
            return False

    def _ensure_note_has_label(self, note, label_name):
        '''Ensure note has a NoteLabelLink to label_name.'''
        try:
            if self._note_has_label(note, label_name):
                return
            label = self._get_note_label_by_name(label_name)
            if not label:
                return
            # Prefer relation-based creation
            try:
                link = self.session.create('NoteLabelLink', {
                    'note': note,
                    'label': label,
                })
            except Exception:
                link = None
            # Fallback to id-based creation if relation fails
            if not link:
                try:
                    link = self.session.create('NoteLabelLink', {
                        'note_id': note['id'],
                        'label_id': label['id'],
                    })
                except Exception:
                    link = None
        except Exception as e:
            self.logger.debug(f"Ensure note has label failed: {e}")

    def _copy_note_labels(self, src_note, dst_note):
        '''Copy all labels from src_note to dst_note.'''
        try:
            # Ensure we read latest labels from source
            self._refresh_note_fields(src_note)
        except Exception:
            pass
        try:
            for name in self._get_note_label_names(src_note):
                try:
                    self._ensure_note_has_label(dst_note, name)
                except Exception:
                    pass
        except Exception as e:
            self.logger.debug(f"Copy note labels failed: {e}")

    def _copy_note_components(self, src_note, dst_note):
        '''Copy attached components from src_note to dst_note by linking existing Component instances.'''
        try:
            # Ensure source note components are available
            if 'note_components' in src_note:
                # clear to force fresh populate of links list if needed
                pass
            try:
                self.session.populate(src_note, 'note_components')
            except Exception:
                pass
            for ncl in (src_note['note_components'] or []):
                try:
                    comp = ncl['component']
                    if comp:
                        try:
                            self.session.create('NoteComponent', {
                                'note': dst_note,
                                'component': comp,
                            })
                        except Exception:
                            self.session.create('NoteComponent', {
                                'note_id': dst_note['id'],
                                'component_id': comp['id'],
                            })
                except Exception:
                    continue
        except Exception as e:
            self.logger.debug(f"Copy note components failed: {e}")

    def _merge_metadata_with_source_id(self, src_md, source_note_id):
        '''Merge existing metadata with sync_source_note_id without overwriting non-dict types.'''
        try:
            base = {}
            if isinstance(src_md, dict):
                base = dict(src_md)
            base['sync_source_note_id'] = source_note_id
            return base
        except Exception:
            return {'sync_source_note_id': source_note_id}

    def _should_sync_and_content(self, migrate_all, note, values, source_synced_note_ids):
        '''Return (should_sync, content_text) for a note under current selection rules.'''
        try:
            # Skip if this source note is already labeled as synced
            try:
                if note['id'] in source_synced_note_ids:
                    return False, ''
            except Exception:
                pass
            enum_name = f"internal_note_{note['id']}"
            selection = values.get(enum_name)
            # Prefer user selection text if present (including edited enumerator value)
            if selection is False:
                return False, ''
            if isinstance(selection, str):
                if not selection.strip():
                    return False, ''
                return True, selection
            # Fall back to migrate_all toggle
            if migrate_all:
                return True, (note['content'] or '')
            # Otherwise skip when no explicit selection
            return False, ''
        except Exception:
            return migrate_all, (note['content'] or '')

    def _migrate_notes_for_rso(self, rso, values):
        '''Apply migration rules for a single ReviewSessionObject based on UI values.'''
        # Refresh client and internal notes
        try:
            self._refresh_rso_notes(rso)
        except Exception as e:
            self.logger.debug(f"Failed to refresh rso notes: {e}")

        try:
            asset_version = rso['asset_version']
            if not asset_version:
                return
            self._refresh_asset_version_notes(asset_version)
        except Exception as e:
            self.logger.debug(f"Failed to refresh asset version notes: {e}")
            return

        # Decide migration set
        boolean_name = f"asset_version_{asset_version['id']}"
        migrate_all = bool(values.get(boolean_name))
        filtered_notes = self._filter_notes(asset_version['notes'])

        # Build set of source notes already marked with synced label to avoid re-copying
        source_synced_note_ids = set()
        try:
            for sn in filtered_notes:
                try:
                    names = self._get_note_label_names(sn)
                    if LABEL_OF_SYNC in names:
                        source_synced_note_ids.add(sn['id'])
                except Exception:
                    pass
        except Exception:
            pass

        to_migrate = []
        contents_map = {}
        for note in filtered_notes:
            should_sync, content_text = self._should_sync_and_content(migrate_all, note, values, source_synced_note_ids)
            if should_sync:
                to_migrate.append(note)
                contents_map[note['id']] = content_text

        # Deduplicate by source-id when available; fallback to content
        existing_synced_source_ids = set()
        existing_synced_contents = set()
        try:
            for cn in (rso['notes'] or []):
                try:
                    md = cn.get('metadata') or {}
                    if isinstance(md, dict) and 'sync_source_note_id' in md:
                        existing_synced_source_ids.add(md['sync_source_note_id'])
                except Exception:
                    pass
                try:
                    if LABEL_OF_SYNC in self._get_note_label_names(cn):
                        c = (cn.get('content') or '').strip()
                        existing_synced_contents.add(c)
                except Exception:
                    pass
        except Exception as e:
            self.logger.debug(f"Build existing synced id/content sets failed: {e}")

        # Create copies on RSO to avoid moving the original note off AssetVersion
        for note in to_migrate:
            try:
                # Skip if source-id already synced
                if note['id'] in existing_synced_source_ids:
                    continue
                content_text = contents_map.get(note['id'], note.get('content') or '')
                if (content_text or '').strip() in existing_synced_contents:
                    continue

                # Create client copy
                new_note_data = {'content': content_text, 'parent': rso}
                try:
                    new_note_data['author'] = note['author']
                except Exception:
                    pass
                try:
                    new_note_data['frame_number'] = note['frame_number']
                except Exception:
                    pass
                try:
                    new_note_data['metadata'] = self._merge_metadata_with_source_id(note.get('metadata'), note['id'])
                except Exception:
                    new_note_data['metadata'] = {'sync_source_note_id': note['id']}

                new_note = self.session.create('Note', new_note_data)
                try:
                    rso['notes'].append(new_note)
                except Exception:
                    pass
                try:
                    self._copy_note_labels(note, new_note)
                except Exception:
                    pass
                # Copy attached components from source note to the new note
                try:
                    self._copy_note_components(note, new_note)
                except Exception:
                    pass
                try:
                    self._ensure_note_has_label(new_note, LABEL_OF_SYNC)
                except Exception:
                    pass
                # Also mark source note as synced to avoid future re-copying
                try:
                    # Use a fresh note entity from server to avoid stale cache issues
                    try:
                        fresh_note = self.session.get('Note', note['id'])
                    except Exception:
                        fresh_note = note
                    # Ensure label on the source
                    self._ensure_note_has_label(fresh_note, LABEL_OF_SYNC)
                except Exception:
                    pass
                try:
                    target_note = fresh_note if 'fresh_note' in locals() and fresh_note else note
                    if 'note_label_links' in target_note:
                        del target_note['note_label_links']
                    self.session.populate(target_note, 'note_label_links')
                except Exception:
                    pass
                try:
                    if 'note_label_links' in new_note:
                        del new_note['note_label_links']
                    self.session.populate(new_note, 'note_label_links')
                except Exception:
                    pass
                try:
                    if 'note_components' in new_note:
                        del new_note['note_components']
                    self.session.populate(new_note, 'note_components')
                except Exception:
                    pass
            except Exception as e:
                self.logger.debug(f"Create note copy failed: {e}")

    def _create_internal_review_notes_widget(self, review_session_objects):
        '''Return widgets to display internal review notes.'''
        asset_versions = [rso['asset_version'] for rso in review_session_objects if rso['asset_version']]

        def _label_for_note(note):
            label_names = self._get_note_label_names(note)
            labels_part = f"🏷️ {', 🏷️ '.join(label_names)}" if label_names else "🏷️ N/A"

            # Frame may be missing when notes are added directly on AssetVersion
            raw_frame = note['frame_number']
            frame = None
            if isinstance(raw_frame, int):
                frame = raw_frame + 1
            elif isinstance(raw_frame, str):
                try:
                    frame = int(raw_frame) + 1
                except Exception:
                    frame = None
            frame_part = f"🎞️ frame {frame}" if frame is not None else "🎞️ frame N/A"

            author_entity = note['author']
            author_name = None
            if author_entity:
                first_name = author_entity['first_name']
                last_name = author_entity['last_name']
                author_name = f"{first_name} {last_name}" if first_name and last_name else first_name or last_name
            author_part = f"👤 {author_name}" if author_name else "👤 Anonymous"

            date_local = self._format_local_date(note['date'])
            date = f"🗓️ {date_local}" if date_local else "🗓️ N/A"

            return f"{frame_part} • {author_part} • {labels_part} • {date}"

        # Group notes by asset version with a descriptive title built from link
        internal_review_notes_widget = []
        for av in asset_versions:
            # Title: breadcrumb from asset_version['link']
            try:
                link_parts = [link['name'] for link in (av['link'] or []) if link and 'name' in link]
            except Exception:
                link_parts = []
            title_value = '/'.join(link_parts) if link_parts else (av['asset']['name'] or 'Asset Version')

            # Notes for this asset version (exclude labels from EXCLUDE_NOTE_WITH_LABELS)
            filtered_notes = self._filter_notes(av['notes'])
            if not filtered_notes:
                # Skip creating the boolean title widget when no notes to show
                continue

            # Divider before each asset version group
            internal_review_notes_widget.append({
                'name': f"devider_{av['id']}",
                'type': 'label',
                'value': '---',
            })

            # Group boolean toggle for this asset version
            internal_review_notes_widget.append({
                'type': 'boolean',
                'value': True,
                'label': f"Sync all internal notes for Version: ♦️ {title_value} ",
                'name': f"asset_version_{av['id']}",
            })



            for note in filtered_notes:
                opts = [
                    {'label': note['content'], 'value': note['content']},
                    {'label': 'Don\'t sync', 'value': False},
                    ]
                internal_review_notes_widget.append({
                    'label': _label_for_note(note),
                    'type': 'enumerator',
                    'name': f"internal_note_{note['id']}",
                    'value': opts[0]['value'],
                    'data': opts,
                })
                # Omit debug metadata printing for a leaner UI

        return internal_review_notes_widget

    def _compute_header_message(self, entities, review_session_objects, internal_review_notes_widget):
        '''Return header message string with selection counters.
        - When there are no eligible notes, show the synced-complete message.
        - Otherwise, show two-line counters for selected sessions, internal notes, and asset versions.
        '''
        # No eligible internal notes: keep the original message
        if not internal_review_notes_widget:
            return '# - All internal notes have been synced already. #'

        try:
            # Count selected ReviewSessions (including those from folders) with deduplication
            selected_review_session_ids = set()
            for entity_type, entity_id in entities:
                if entity_type == 'ReviewSession':
                    selected_review_session_ids.add(entity_id)
                elif entity_type == 'ReviewSessionFolder':
                    try:
                        folder = self.session.get(entity_type, entity_id)
                        # Ensure fresh review_sessions list on folder
                        try:
                            if 'review_sessions' in folder:
                                del folder['review_sessions']
                            self.session.populate(folder, 'review_sessions')
                        except Exception:
                            pass
                        for rs in folder['review_sessions']:
                            try:
                                selected_review_session_ids.add(rs['id'])
                            except Exception:
                                continue
                    except Exception:
                        continue
            selected_review_sessions_count = len(selected_review_session_ids)

            # Count unique AssetVersions present in the deduped RSO list
            asset_versions = [
                rso['asset_version'] for rso in review_session_objects if rso['asset_version']
            ]
            asset_versions_count = len({av['id'] for av in asset_versions if av and av['id']})

            # Count internal notes (excluding labels in EXCLUDE_NOTE_WITH_LABELS)
            internal_notes_count = 0
            for av in asset_versions:
                try:
                    notes_for_av = av['notes'] or []
                    filtered_notes = self._filter_notes(notes_for_av)
                    internal_notes_count += len(filtered_notes)
                except Exception:
                    continue
        except Exception as e:
            self.logger.debug(f"Compute header counters failed: {e}")
            selected_review_sessions_count = 0
            asset_versions_count = 0
            internal_notes_count = 0

        # Pluralization for better readability
        rs_word = 'ReviewSession' if selected_review_sessions_count == 1 else 'ReviewSessions'
        note_word = 'Internal Note' if internal_notes_count == 1 else 'Internal Notes'
        av_word = 'AssetVersion' if asset_versions_count == 1 else 'AssetVersions'
        be_verb = 'is' if internal_notes_count == 1 else 'are'

        return (
            f" # - You've selected {selected_review_sessions_count} {rs_word} #\n"
            f" # - There {be_verb} {internal_notes_count} {note_word} on {asset_versions_count} {av_word} #\n"
        )

    def validate_entities(self, entities):
        '''Return if *entities* is valid.'''
        if len(entities) >= 1 and all(
            [entity_type in SUPPORTED_ENTITY_TYPES for entity_type, _ in entities]
        ):
            self.logger.info('Selection is valid')
            return True
        else:
            self.logger.info('Selection is _not_ valid')
            return False

    def discover(self, session, entities, event):
        '''Return True if action is valid.'''
        return self.validate_entities(entities)

    def interface(self, session, entities, event):
        '''Return interface for action.'''
        values = event['data'].get('values', {})
        if values:
            return
        print(event['source']['user']['username'])
        
        review_session_objects = self._get_deduplicated_review_session_objs(entities)

        # Ensure latest notes are fetched from server (avoid stale cache)
        for rso in review_session_objects:
            try:
                self._refresh_rso_notes(rso)
            except Exception as e:
                self.logger.debug(f"Failed to refresh rso notes: {e}")

            # Refresh internal notes on the related asset version
            try:
                asset_version = rso['asset_version']
                if asset_version:
                    self._refresh_asset_version_notes(asset_version)
            except Exception as e:
                self.logger.debug(f"Failed to refresh asset version notes: {e}")

        for rso in review_session_objects:
            self.logger.info(f"Current review session object: {rso['name']}")
            asset_version = rso['asset_version']
            for internal_note in asset_version['notes']:
                self.logger.info(f"内部注释: {internal_note['content'], internal_note['id']}")
                
            for client_note in rso['notes']:
                self.logger.info(f"客户注释: {client_note['content'], client_note['id']}")

        # Build widgets for internal review notes
        internal_review_notes_widget = self._create_internal_review_notes_widget(review_session_objects)

        # Header message with counters (refactored for maintainability)
        header_message = self._compute_header_message(
            entities,
            review_session_objects,
            internal_review_notes_widget,
        )

        widgets = [
            {
                'name': 'header00',
                'value': header_message,
                'type': 'label',
            }
        ] + internal_review_notes_widget

        return widgets

    def launch(self, session, entities, event):
        # Execute migration based on UI values, referencing notes and tagging synced label
        values = event['data'].get('values', {})

        review_session_objects = self._get_deduplicated_review_session_objs(entities)

        # If no eligible filtered notes exist on the executed Review Sessions,
        # return "Bye" on submit without performing migration.
        try:
            has_filtered_notes = False
            for rso in review_session_objects:
                try:
                    av = rso['asset_version']
                    if not av:
                        continue
                    try:
                        self._refresh_asset_version_notes(av)
                    except Exception:
                        pass
                    filtered = self._filter_notes(av['notes'] or [])
                    if filtered:
                        has_filtered_notes = True
                        break
                except Exception:
                    pass
            if not has_filtered_notes:
                return {'success': True, 'message': 'Bye'}
        except Exception:
            pass

        for rso in review_session_objects:
            try:
                self._migrate_notes_for_rso(rso, values)
            except Exception as e:
                self.logger.debug(f"Migrate notes for rso failed: {e}")

        try:
            self.session.commit()
        except Exception as e:
            self.logger.debug(f"Commit failed: {e}")
            return {'success': False, 'message': f'Failed to commit changes: {e}'}

        # Omit post-commit debug verification logs for a leaner implementation

        return {'success': True, 'message': 'Success: All selected internal notes have been synced to client review sessions.'}


def register(session, **kw):
    '''Register plugin.'''
    if not isinstance(session, ftrack_api.Session):
        return
    action = SyncNotesToClientReviews(session)
    action.register()


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    session = ftrack_api.Session(auto_connect_event_hub=True)
    register(session)

    session.event_hub.wait()