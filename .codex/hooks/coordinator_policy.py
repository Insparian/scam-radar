"""Create and enforce the optional Goal Router thin-coordinator policy."""
import argparse
import json
import os
import re
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path


SPAWN_TOOLS = {'Agent', 'spawn_agent', 'collaborationspawn_agent'}
FOLLOWUP_TOOLS = {'followup_task', 'collaborationfollowup_task'}
SHELL_TOOLS = {'Bash', 'exec_command'}
READ_TOOLS = {'Read', 'read_file'}
SEARCH_TOOLS = {'Glob', 'Grep', 'search_files'}
WRITE_TOOLS = {'Write', 'Edit', 'MultiEdit', 'apply_patch'}
DEFAULT_CHECKPOINTS = ['.goal-router/STATE.json', '.goal-router/EVIDENCE.md',
                       '.goal-router/ROUTES.jsonl', 'docs/PROGRESS.md', 'docs/BLOCKED.md']


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def read_policy(path):
    value = json.loads(Path(path).read_text())
    if not isinstance(value, dict) or value.get('schema_version') != 1:
        raise ValueError('invalid coordinator policy')
    return value


def write_policy(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.tmp')
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')
    os.replace(str(temporary), str(path))


@contextmanager
def policy_lock(path):
    lock = Path(path).with_name(Path(path).name + '.lock')
    lock.parent.mkdir(parents=True, exist_ok=True)
    handle = lock.open('a+b')
    if handle.tell() == 0:
        handle.write(b'0')
        handle.flush()
    deadline = time.monotonic() + 2.0
    acquired = False
    try:
        while not acquired:
            try:
                if os.name == 'nt':
                    import msvcrt
                    handle.seek(0)
                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                acquired = True
            except (BlockingIOError, OSError):
                if time.monotonic() >= deadline:
                    raise OSError('coordinator policy lock timed out')
                time.sleep(0.01)
        yield
    finally:
        if acquired:
            if os.name == 'nt':
                import msvcrt
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        handle.close()


def create_policy(path, checkpoint_paths=None, max_active_workers=1):
    if max_active_workers not in (1, 2):
        raise ValueError('max_active_workers must be one or two')
    with policy_lock(path):
        value = {
            'schema_version': 1,
            'enabled': True,
            'coordinator_models': ['gpt-5.6-sol'],
            'coordinator_session_id': None,
            'max_active_workers': max_active_workers,
            'checkpoint_paths': checkpoint_paths or list(DEFAULT_CHECKPOINTS),
            'frontier_agent_types': ['goal-frontier'],
            'frontier_models': ['gpt-6-astra'],
            'active_agents': {},
            'pending_starts': {},
            'created_at': utc_now(),
        }
        write_policy(path, value)
    return value


def _deny(reason):
    return {
        'hookSpecificOutput': {
            'hookEventName': 'PreToolUse',
            'permissionDecision': 'deny',
            'permissionDecisionReason': reason,
        }
    }


def _patch_paths(command):
    if not isinstance(command, str):
        return []
    return re.findall(r'^\*\*\* (?:(?:Add|Update|Delete) File:|Move to:) (.+)$',
                      command, re.MULTILINE)


def _tool_paths(tool, tool_input):
    if tool == 'apply_patch':
        return _patch_paths(tool_input.get('command'))
    values = []
    for key in ('file_path', 'path'):
        value = tool_input.get(key)
        if isinstance(value, str) and value:
            values.append(value)
    edits = tool_input.get('edits')
    if isinstance(edits, list):
        values.extend(item['file_path'] for item in edits
                      if isinstance(item, dict) and isinstance(item.get('file_path'), str))
    return values


def _allowed_path(raw_path, root, allowed):
    path = Path(raw_path)
    try:
        relative = path.resolve().relative_to(root.resolve()) if path.is_absolute() else Path(os.path.normpath(str(path)))
    except ValueError:
        return False
    if '..' in relative.parts:
        return False
    text = relative.as_posix()
    return any(text == entry.rstrip('/') or text.startswith(entry.rstrip('/') + '/') for entry in allowed)


def _is_policy_path(raw_path, root, policy_path):
    candidate = Path(raw_path)
    if not candidate.is_absolute():
        candidate = Path(root) / candidate
    return candidate.resolve() == Path(policy_path).resolve()


def update_lifecycle(payload, policy_path):
    path = Path(policy_path)
    if not path.is_file():
        return
    event = payload.get('hook_event_name')
    if event not in ('SubagentStart', 'SubagentStop'):
        return
    agent_id = payload.get('agent_id')
    if not isinstance(agent_id, str) or not agent_id:
        return
    with policy_lock(path):
        policy = read_policy(path)
        bound = policy.get('coordinator_session_id')
        if bound is None or payload.get('session_id') != bound:
            return
        active = policy.setdefault('active_agents', {})
        pending = policy.setdefault('pending_starts', {})
        if event == 'SubagentStart':
            if pending:
                pending.pop(next(iter(pending)), None)
            active[agent_id] = {'agent_type': payload.get('agent_type'), 'model': payload.get('model')}
        else:
            active.pop(agent_id, None)
        policy['last_lifecycle_at'] = utc_now()
        write_policy(path, policy)


def release_failed_start(payload, policy_path):
    path = Path(policy_path)
    if not path.is_file() or payload.get('hook_event_name') != 'PostToolUse':
        return
    tool = payload.get('tool_name')
    is_start = (tool in SPAWN_TOOLS or tool in FOLLOWUP_TOOLS or
                (isinstance(tool, str) and
                 (tool.endswith('spawn_agent') or tool.endswith('followup_task'))))
    response = payload.get('tool_response')
    failed = (payload.get('tool_error') is not None or
              isinstance(response, dict) and
              (response.get('isError') is True or response.get('is_error') is True or
               response.get('error') is not None))
    if not is_start or not failed:
        return
    tool_use_id = payload.get('tool_use_id')
    if not isinstance(tool_use_id, str) or not tool_use_id:
        return
    with policy_lock(path):
        policy = read_policy(path)
        if (policy.get('coordinator_session_id') is None or
                payload.get('session_id') != policy.get('coordinator_session_id')):
            return
        policy.setdefault('pending_starts', {}).pop(tool_use_id, None)
        policy['last_lifecycle_at'] = utc_now()
        write_policy(path, policy)


def guard_pre_tool(payload, policy_path, root):
    path = Path(policy_path)
    if payload.get('hook_event_name') != 'PreToolUse' or not path.is_file():
        return None
    with policy_lock(path):
        return _guard_pre_tool_locked(payload, path, root)


def _guard_pre_tool_locked(payload, path, root):
    policy = read_policy(path)
    if not policy.get('enabled') or payload.get('model') not in policy.get('coordinator_models', []):
        return None
    session_id = payload.get('session_id')
    bound = policy.get('coordinator_session_id')
    if bound is None:
        if not isinstance(session_id, str) or not session_id:
            return _deny('Goal Router coordinator guard could not bind this task session. Stop and repair the guard.')
        policy['coordinator_session_id'] = session_id
        policy['bound_at'] = utc_now()
        write_policy(path, policy)
    elif session_id != bound:
        return None

    tool = payload.get('tool_name')
    tool_input = payload.get('tool_input') if isinstance(payload.get('tool_input'), dict) else {}
    is_spawn = tool in SPAWN_TOOLS or (isinstance(tool, str) and tool.endswith('spawn_agent'))
    is_followup = tool in FOLLOWUP_TOOLS or (isinstance(tool, str) and tool.endswith('followup_task'))
    if is_spawn or is_followup:
        active = policy.get('active_agents', {})
        pending = policy.setdefault('pending_starts', {})
        if pending:
            return _deny('A worker start is pending. Wait for its lifecycle event before dispatching another worker.')
        if is_followup and active:
            return _deny('Wait for the active worker before waking another existing worker. Use a typed spawn only for an approved second parallel slice.')
        requested_type = tool_input.get('agent_type')
        requested_model = tool_input.get('model')
        frontier = set(policy.get('frontier_agent_types', []))
        frontier_models = set(policy.get('frontier_models', []))
        active_types = {item.get('agent_type') for item in active.values() if isinstance(item, dict)}
        active_models = {item.get('model') for item in active.values() if isinstance(item, dict)}
        pending_types = {item.get('agent_type') for item in pending.values() if isinstance(item, dict)}
        pending_models = {item.get('model') for item in pending.values() if isinstance(item, dict)}
        requested_frontier = requested_type in frontier or requested_model in frontier_models
        if requested_frontier and (active or pending):
            return _deny('FRONTIER must run alone. Wait for every active worker to stop.')
        if (active_types & frontier or active_models & frontier_models or
                pending_types & frontier or pending_models & frontier_models):
            return _deny('A FRONTIER worker is active. Do not start another worker.')
        if len(active) + len(pending) >= policy.get('max_active_workers', 1):
            return _deny('Goal Router worker limit reached. Wait for the active worker instead of fanning out.')
        tool_use_id = payload.get('tool_use_id')
        if not isinstance(tool_use_id, str) or not tool_use_id:
            return _deny('Goal Router cannot reserve this worker start without a tool-call identity.')
        pending[tool_use_id] = {
            'agent_type': requested_type,
            'model': requested_model,
            'exclusive': is_followup or requested_frontier,
            'reserved_at': utc_now(),
        }
        write_policy(path, policy)
        return None
    if tool in SHELL_TOOLS:
        return _deny('Sol is the thin coordinator. Delegate shell work, implementation, repair and verification to a worker.')
    if tool in SEARCH_TOOLS:
        return _deny('Sol is the thin coordinator. Delegate repository search and reconnaissance to a worker.')
    if tool in READ_TOOLS:
        paths = _tool_paths(tool, tool_input)
        if paths and all(not _is_policy_path(item, root, path) and
                         _allowed_path(item, Path(root), policy.get('checkpoint_paths', []))
                         for item in paths):
            return None
        return _deny('Sol may read only approved Goal Router checkpoint files after guard activation.')
    if tool in WRITE_TOOLS:
        paths = _tool_paths(tool, tool_input)
        if paths and all(not _is_policy_path(item, root, path) and
                         _allowed_path(item, Path(root), policy.get('checkpoint_paths', []))
                         for item in paths):
            return None
        return _deny('Sol may edit only approved Goal Router checkpoint files. Delegate product-file changes to a worker.')
    return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest='command', required=True)
    init = subparsers.add_parser('init')
    init.add_argument('--policy', default='.goal-router/coordinator-policy.json')
    init.add_argument('--checkpoint', action='append', dest='checkpoints')
    init.add_argument('--max-active-workers', type=int, default=1)
    args = parser.parse_args()
    if args.command == 'init':
        policy = Path(args.policy)
        if not policy.is_absolute():
            current = Path.cwd().resolve()
            roots = [current, *current.parents]
            git_root = next((item for item in roots if (item / '.git').exists()), None)
            if git_root is None:
                parser.exit(2, 'relative policy path requires a Git working tree\n')
            policy = git_root / policy
        create_policy(policy, args.checkpoints, args.max_active_workers)
        print('Coordinator policy initialized at ' + str(policy))


if __name__ == '__main__':
    main()
