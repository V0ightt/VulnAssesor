import os
from .models import SASTFinding, SASTFix
from .services import ProjectManager

def modify_code(project, file_path, new_content):
    """Modifies a file in the project workspace."""
    manager = ProjectManager(project)
    full_path = os.path.join(manager.workspace_root, file_path)
    
    # Security check
    if not os.path.abspath(full_path).startswith(os.path.abspath(manager.workspace_root)):
        raise ValueError("Invalid file path.")
        
    with open(full_path, 'w', encoding='utf-8') as f:
        f.write(new_content)
    
    return True

def report_vulnerability(scan_job, file_path, line_number, severity, title, description, code_snippet):
    """Creates a new SASTFinding."""
    finding = SASTFinding.objects.create(
        scan_job=scan_job,
        file_path=file_path,
        line_number=line_number,
        severity=severity,
        title=title,
        description=description,
        code_snippet=code_snippet
    )
    return finding

def get_vulnerability_context(finding_id):
    """Returns context for a finding."""
    finding = SASTFinding.objects.get(id=finding_id)
    manager = ProjectManager(finding.scan_job.project)
    
    # Read file content around the line
    content = manager.get_file_content(finding.file_path)
    lines = content.splitlines()
    
    start_line = max(0, finding.line_number - 5)
    end_line = min(len(lines), finding.line_number + 5)
    
    context_lines = lines[start_line:end_line]
    return "\n".join(context_lines)

def apply_fix(finding_id, proposed_code, explanation):
    """Creates a SASTFix for a finding."""
    finding = SASTFinding.objects.get(id=finding_id)
    fix = SASTFix.objects.create(
        finding=finding,
        proposed_code=proposed_code,
        explanation=explanation
    )
    return fix

def push_fixes(project, commit_message="Applied SAST fixes"):
    """Pushes changes to the remote repository."""
    manager = ProjectManager(project)
    return manager.push_changes(commit_message)

def list_project_files(project):
    """Returns a list of all scannable files in the project."""
    manager = ProjectManager(project)
    files = []
    
    # Extensions to scan
    ALLOWED_EXTENSIONS = {'.py', '.js', '.ts', '.html', '.css', '.java', '.c', '.cpp', '.go', '.rs', '.php'}
    
    for root, dirs, filenames in os.walk(manager.workspace_root):
        # Skip hidden directories (like .git)
        dirs[:] = [d for d in dirs if not d.startswith('.')]
        
        for filename in filenames:
            _, ext = os.path.splitext(filename)
            if ext.lower() in ALLOWED_EXTENSIONS:
                # Get relative path
                full_path = os.path.join(root, filename)
                rel_path = os.path.relpath(full_path, manager.workspace_root)
                files.append(rel_path.replace('\\', '/'))
                
    return files

def read_file(project, file_path):
    """Reads a file from the project workspace."""
    manager = ProjectManager(project)
    return manager.get_file_content(file_path)
