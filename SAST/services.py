import os
from pathlib import Path
import shutil
import zipfile
import git
from git import RemoteProgress
from git.exc import GitError
from django.conf import settings
from .models import Project

class ProjectManager:
    def __init__(self, project: Project):
        self.project = project
        self.workspace_root = Path(settings.MEDIA_ROOT) / 'projects' / str(project.id)

    def prepare_workspace(self):
        """Creates the workspace directory if it doesn't exist."""
        self.workspace_root.mkdir(parents=True, exist_ok=True)
        return str(self.workspace_root)

    def resolve_path(self, relative_path=''):
        """Resolves a workspace-relative path and prevents path traversal."""
        normalized = (relative_path or '').replace('\\', '/').strip('/')
        target = (self.workspace_root / normalized).resolve()
        workspace_root = self.workspace_root.resolve()
        if workspace_root != target and workspace_root not in target.parents:
            raise ValueError("Invalid file path.")
        return target

    def get_relative_path(self, path: Path):
        return path.resolve().relative_to(self.workspace_root.resolve()).as_posix()

    def clone_repository(self, progress_callback=None):
        """Clones the git repository into the workspace."""
        if not self.project.repository_url:
            raise ValueError("No repository URL provided.")
        
        self.prepare_workspace()
        
        # If directory is not empty, we might want to pull or clear it.
        if (self.workspace_root / '.git').exists():
            repo = git.Repo(str(self.workspace_root))
            origin = repo.remotes.origin
            if progress_callback:
                progress_callback('pull_started', 'Updating existing checkout', {'repository_url': self.project.repository_url})
            origin.pull()
            if progress_callback:
                progress_callback('pull_completed', 'Existing checkout updated', {})
            return repo
        else:
            # Clear directory just in case
            if self.workspace_root.exists():
                shutil.rmtree(self.workspace_root)
                self.workspace_root.mkdir(parents=True, exist_ok=True)
                 
            if progress_callback:
                progress_callback('clone_started', 'Cloning repository', {'repository_url': self.project.repository_url})
            repo = git.Repo.clone_from(
                self.project.repository_url,
                str(self.workspace_root),
                progress=_ProgressAdapter(progress_callback) if progress_callback else None,
            )
            if progress_callback:
                progress_callback('clone_completed', 'Repository clone completed', {})
            return repo

    def extract_zip(self, progress_callback=None):
        """Extracts the uploaded zip file into the workspace."""
        if not self.project.source_zip:
            raise ValueError("No source zip provided.")
        
        self.prepare_workspace()
        
        # Clear workspace for zip extraction
        for entry in self.workspace_root.iterdir():
            if entry.is_file() or entry.is_symlink():
                entry.unlink()
            elif entry.is_dir():
                shutil.rmtree(entry)

        with zipfile.ZipFile(self.project.source_zip.path, 'r') as zip_ref:
            members = zip_ref.infolist()
            total = len(members)
            if progress_callback:
                progress_callback('extract_started', 'Extracting ZIP archive', {'file_count': total})
            for index, member in enumerate(members, start=1):
                zip_ref.extract(member, self.workspace_root)
                if progress_callback and (index == 1 or index == total or index % 25 == 0):
                    progress_callback(
                        'extract_progress',
                        f'Extracted {index} of {total} archive entries',
                        {'processed': index, 'total': total, 'name': member.filename},
                    )
            if progress_callback:
                progress_callback('extract_completed', 'ZIP extraction completed', {'file_count': total})

    def get_file_content(self, relative_path):
        """Reads a file from the workspace."""
        full_path = self.resolve_path(relative_path)
        with full_path.open('r', encoding='utf-8', errors='ignore') as f:
            return f.read()

    def get_file_lines(self, relative_path, start_line=1, end_line=None, max_lines=None):
        """Reads a bounded line range from a file in the workspace."""
        full_path = self.resolve_path(relative_path)
        with full_path.open('r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()

        total_lines = len(lines)
        actual_start = max(1, int(start_line or 1))
        actual_end = total_lines if end_line is None else max(actual_start, int(end_line))
        truncated = False

        if max_lines and (actual_end - actual_start + 1) > max_lines:
            actual_end = actual_start + max_lines - 1
            truncated = True

        actual_end = min(actual_end, total_lines)
        if actual_end < actual_start:
            return {
                'content': '',
                'start_line': actual_start,
                'end_line': actual_start - 1,
                'truncated': truncated,
                'total_lines': total_lines,
            }

        content = ''.join(lines[actual_start - 1:actual_end])
        if end_line is not None and int(end_line) > actual_end:
            truncated = True

        return {
            'content': content,
            'start_line': actual_start,
            'end_line': actual_end,
            'truncated': truncated,
            'total_lines': total_lines,
        }

    def get_directory_structure(self, relative_path='', ignored_directories=None, max_entries=None):
        """Returns a list of files and directories in the given path."""
        full_path = self.resolve_path(relative_path)
        if not full_path.exists() or not full_path.is_dir():
            return []

        ignored = set(ignored_directories or {'.git'})
        items = []
        for entry in full_path.iterdir():
            if entry.name in ignored:
                continue

            is_dir = entry.is_dir()
            items.append({
                'name': entry.name,
                'path': self.get_relative_path(entry),
                'is_dir': is_dir
            })
            if max_entries is not None and len(items) >= max_entries:
                break

        # Sort directories first, then files
        items.sort(key=lambda x: (not x['is_dir'], x['name']))
        return items

    def iter_workspace_files(self, ignored_directories=None, allowed_extensions=None):
        ignored = set(ignored_directories or [])
        allowed = {ext.lower() for ext in (allowed_extensions or [])}

        for root, dirs, filenames in os.walk(self.workspace_root):
            dirs[:] = [
                directory for directory in dirs
                if directory not in ignored and not directory.startswith('.')
            ]

            for filename in filenames:
                full_path = Path(root) / filename
                if allowed and full_path.suffix.lower() not in allowed:
                    continue
                yield self.get_relative_path(full_path)

    def push_changes(self, commit_message="Applied SAST fixes"):
        """Commits and pushes changes to the remote repository."""
        if not self.project.repository_url:
            raise ValueError("No repository URL provided.")
        
        repo = git.Repo(str(self.workspace_root))
        if repo.is_dirty(untracked_files=True):
            repo.git.add(A=True)
            repo.index.commit(commit_message)
            origin = repo.remotes.origin
            origin.push()
            return True
        return False

    def get_repository_head_commit(self):
        git_dir = self.workspace_root / '.git'
        if not git_dir.exists():
            return None
        try:
            repo = git.Repo(str(self.workspace_root))
            return repo.head.commit.hexsha
        except (GitError, OSError, ValueError):
            return None

    def delete_workspace(self):
        """Deletes the workspace directory."""
        if self.workspace_root.exists():
            shutil.rmtree(self.workspace_root)


class _ProgressAdapter(RemoteProgress):
    def __init__(self, callback):
        super().__init__()
        self.callback = callback
        self._last_percent = -1

    def update(self, op_code, cur_count, max_count=None, message=''):
        if not self.callback or not max_count:
            return
        percent = int((cur_count / max_count) * 100)
        if percent == self._last_percent or percent % 20 != 0:
            return
        self._last_percent = percent
        self.callback(
            'clone_progress',
            f'Git transfer {percent}% complete',
            {'percent': percent, 'message': message or ''},
        )
