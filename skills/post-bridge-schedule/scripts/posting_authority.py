"""Fail closed on posting writes; never infer a client workspace from default credentials."""
import hashlib
import json
import os
from pathlib import Path


class PostingAuthorityError(RuntimeError):
    pass


def context(required=False):
    path = os.environ.get('AIA_POSTING_CONTEXT')
    if not path:
        if required: raise PostingAuthorityError('Posting disabled: explicit client posting context is required')
        return None
    data = json.loads(Path(path).read_text())
    if not isinstance(data, dict): raise PostingAuthorityError('Invalid posting context')
    return data


def credential(data):
    source = data.get('credential', {})
    if source.get('type') == 'env' and source.get('name'):
        key = os.environ.get(source['name'])
    elif source.get('type') == 'file' and source.get('path') and Path(source['path']).is_absolute():
        key = json.loads(Path(source['path']).read_text()).get(source.get('key_field', 'apiKey'))
    else:
        raise PostingAuthorityError('Explicit credential source required; global fallback is forbidden')
    if not isinstance(key, str) or not key:
        raise PostingAuthorityError('Declared posting credential is unavailable')
    fingerprint = hashlib.sha256(key.encode()).hexdigest()
    if data.get('destination', {}).get('credential_sha256') != fingerprint:
        raise PostingAuthorityError('Credential does not match the verified destination workspace')
    return key


def required_operations(path, method, body):
    body = body or {}
    if path == '/media/create-upload-url' and method == 'POST': return {'upload'}
    if path == '/posts' and method == 'POST':
        return {'draft' if body.get('is_draft') is True else 'schedule' if body.get('scheduled_at') else 'publish'}
    if path.startswith('/posts/') and '/' not in path[len('/posts/'):]:
        if method == 'DELETE': return {'delete'}
        if method in ('PATCH', 'PUT'):
            operations = {'patch'}
            if body.get('scheduled_at') or body.get('status') == 'scheduled': operations.add('schedule')
            if body.get('status') in ('published', 'publishing'): operations.add('publish')
            if body.get('is_draft') is False and not body.get('scheduled_at'): operations.add('publish')
            return operations
    raise PostingAuthorityError('Unsupported posting write endpoint; no unguarded transport fallback')


def account_ids(record):
    ids = set()
    for value in record.get('social_accounts', []):
        ids.add(str(value.get('id')) if isinstance(value, dict) else str(value))
    configurations = record.get('account_configurations', {})
    if isinstance(configurations, dict): configurations = configurations.get('account_configurations', [])
    if configurations is None: configurations = []
    for item in configurations:
        if item.get('account_id') is not None: ids.add(str(item['account_id']))
    return ids


def authorize(data, path, method, body, read):
    """`read` is GET-only and already bound to this context's exact credential."""
    owner = data.get('content_owner')
    destination = data.get('destination', {})
    auth = data.get('authorization', {})
    if not owner or not destination.get('owner') or destination.get('kind') not in ('client', 'personal'):
        raise PostingAuthorityError('Content owner and destination owner/kind must be explicit')
    if auth.get('source') != 'user' or auth.get('explicit') is not True or not auth.get('reference'):
        raise PostingAuthorityError('Explicit user posting authorization required; media generation is not posting authority')
    operations = required_operations(path, method, body)
    if not operations.issubset(set(auth.get('operations', []))):
        raise PostingAuthorityError('User authorization does not cover this posting operation')
    if destination['owner'] != owner:
        if destination['kind'] != 'personal' or auth.get('scope') != 'personal-sample':
            raise PostingAuthorityError('Client content cannot enter another owner workspace')
        if auth.get('sample_content_owner') != owner or auth.get('sample_destination_owner') != destination['owner']:
            raise PostingAuthorityError('Personal sample authorization must identify both content and destination owners')
    elif auth.get('scope') not in ('client-posting', 'owner-posting', 'personal-sample'):
        raise PostingAuthorityError('Explicit posting scope required')
    if destination.get('ownership_verified_by') != 'user' or not destination.get('ownership_reference'):
        raise PostingAuthorityError('Destination ownership needs explicit user verification, not a guessed account match')
    configured = destination.get('account_ids', [])
    approved = {str(value) for value in configured}
    if not configured or len(configured) != len(approved):
        raise PostingAuthorityError('Verified destination account roster must be nonempty and unique')
    records, offset = [], 0
    while True:
        page = read(f'/social-accounts?limit=100&offset={offset}')
        if not isinstance(page.get('data'), list): raise PostingAuthorityError('Live account roster unavailable')
        records.extend(page['data'])
        if not (page.get('meta') or {}).get('next'): break
        offset += 100
        if offset > 10000: raise PostingAuthorityError('Live account pagination did not finish')
    # Verify workspace identity separately from authorized publishing destinations.
    roster = destination.get('workspace_account_ids', configured)
    verified_roster = {str(value) for value in roster}
    if not roster or len(roster) != len(verified_roster) or not approved.issubset(verified_roster):
        raise PostingAuthorityError('Verified workspace roster must be unique and contain authorized destinations')
    live = {str(item['id']) for item in records}
    if live != verified_roster:
        raise PostingAuthorityError('Live account roster differs from verified destination; refresh identity before writing')
    workspace_id = destination.get('workspace_id')
    if workspace_id and any(item.get('workspace_id') is not None and str(item['workspace_id']) != str(workspace_id) for item in records):
        raise PostingAuthorityError('API workspace identity differs from verified destination')
    if path.startswith('/posts/'):
        current = read(path)
        current = current.get('data', current)
        current_ids = account_ids(current)
        if not current_ids or not current_ids.issubset(approved):
            raise PostingAuthorityError('Existing post is not bound to authorized destination accounts')
    if path == '/posts' or (body and ('social_accounts' in body or 'account_configurations' in body)):
        requested = account_ids(body or {})
        if not requested or not requested.issubset(approved):
            raise PostingAuthorityError('Post destinations are missing or outside authorized client roster')
    return approved
