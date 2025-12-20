import ftrack_api

session = ftrack_api.Session()
# project_id = 'cc524fc3-76b9-429a-95bd-733c8d8ca690'
# review_sessions = session.query(f"select id, name, review_session_objects.annotations from ReviewSession where project_id is {project_id}").all()
# for review_session in review_sessions:
#     print(review_session['name'], review_session['id'])

# review_session_id = 'c03b16f6-f63f-4f45-8847-b3b1d73ceaa1'
# review_session_obj = session.query(f"select id, name, annotations from ReviewSessionObject where review_session_id is {review_session_id}").one()
# print(review_session_obj['id'])

note_content = 'BigYellow comment with Frame Annotation'
note = session.query(f"select id, note_components from Note where content is '{note_content}'").one()

print(note['id'])
print(len(note['note_components']))
print(note['note_components'][0]['component_id'])


note_id = '346b0a8a-8e5f-4af0-9377-cdf78d0e1830'
component_id = '29bd5b30-65ce-46ea-93f1-f67d38dc1eac'

# Query the annotation component by its ID (IDs must be quoted in ftrack queries).
# Note: Annotation data lives on the AnnotationComponent entity, not on the NoteComponent link.

note_annotation_component = session.query(
    f"select data from NoteAnnotationComponent where component_id is '{component_id}'"
).first()

if note_annotation_component:
    print(note_annotation_component['note'])
else:
    print(
        f"No NoteAnnotationComponent found for note_id='{note_id}' and component_id='{component_id}'."
    )

