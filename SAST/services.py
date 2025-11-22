import os
import shutil
import zipfile
import git
from django.conf import settings
from .models import Project

class ProjectManager:
    def __init__(self, project: Project):
        self.project = project
        self.workspace_root = os.path.join(settings.MEDIA_ROOT, 'projects', str(project.id))

    def prepare_workspace(self):
        """Creates the workspace directory if it doesn't exist."""
        if not os.path.exists(self.workspace_root):
            os.makedirs(self.workspace_root)
        return self.workspace_root

    def clone_repository(self):
        """Clones the git repository into the workspace."""
        if not self.project.repository_url:
            raise ValueError("No repository URL provided.")
        
        self.prepare_workspace()
        
        # If directory is not empty, we might want to pull or clear it.
        if os.path.exists(os.path.join(self.workspace_root, '.git')):
            repo = git.Repo(self.workspace_root)
            origin = repo.remotes.origin
            origin.pull()
            return repo
        else:
            # Clear directory just in case
            if os.path.exists(self.workspace_root):
                shutil.rmtree(self.workspace_root)
                os.makedirs(self.workspace_root)
                
            return git.Repo.clone_from(self.project.repository_url, self.workspace_root)

    def extract_zip(self):
        """Extracts the uploaded zip file into the workspace."""
        if not self.project.source_zip:
            raise ValueError("No source zip provided.")
        
        self.prepare_workspace()
        
        # Clear workspace for zip extraction
        for filename in os.listdir(self.workspace_root):
            file_path = os.path.join(self.workspace_root, filename)
            if os.path.isfile(file_path) or os.path.islink(file_path):
                os.unlink(file_path)
            elif os.path.isdir(file_path):
                shutil.rmtree(file_path)

        with zipfile.ZipFile(self.project.source_zip.path, 'r') as zip_ref:
            zip_ref.extractall(self.workspace_root)

    def get_file_content(self, relative_path):
        """Reads a file from the workspace."""
        full_path = os.path.join(self.workspace_root, relative_path)
        # Security check to prevent path traversal
        if not os.path.abspath(full_path).startswith(os.path.abspath(self.workspace_root)):
            raise ValueError("Invalid file path.")
        
        with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
            return f.read()

    def get_directory_structure(self, relative_path=''):
        """Returns a list of files and directories in the given path."""
        full_path = os.path.join(self.workspace_root, relative_path)
        if not os.path.exists(full_path):
            return []
        
        items = []
        for name in os.listdir(full_path):
            if name == '.git':
                continue
            
            item_path = os.path.join(full_path, name)
            is_dir = os.path.isdir(item_path)
            items.append({
                'name': name,
                'path': os.path.join(relative_path, name).replace('\\', '/'),
                'is_dir': is_dir
            })
        
        # Sort directories first, then files
        items.sort(key=lambda x: (not x['is_dir'], x['name']))
        return items

    def push_changes(self, commit_message="Applied SAST fixes"):
        """Commits and pushes changes to the remote repository."""
        if not self.project.repository_url:
            raise ValueError("No repository URL provided.")
        
        repo = git.Repo(self.workspace_root)
        if repo.is_dirty(untracked_files=True):
            repo.git.add(A=True)
            repo.index.commit(commit_message)
            origin = repo.remotes.origin
            origin.push()
            return True
        return False
