import os
import json
from openai import OpenAI
from pydantic import BaseModel, Field
from typing import List, Optional
from .sast_tools import read_file, list_project_files

# --- Structured Outputs (Pydantic) ---
class Vulnerability(BaseModel):
    line_number: int
    severity: str = Field(..., pattern="^(LOW|MEDIUM|HIGH|CRITICAL)$")
    title: str
    description: str
    code_snippet: str
    confidence_score: float
    ai_explanation: str # Added field for detailed explanation

class ScanResult(BaseModel):
    findings: List[Vulnerability]

class FixResult(BaseModel):
    fixed_code: str
    explanation: str

class VerificationResult(BaseModel):
    is_true_positive: bool
    reasoning: str

class SASTAgent:
    def __init__(self, project):
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable is not set.")
            
        self.client = OpenAI(api_key=api_key)
        self.project = project
        self.system_context = self._load_project_context()

    def _load_project_context(self):
        """
        Reads agents.md and README.md from the TARGET PROJECT to build the System Prompt.
        """
        context = "You are an expert Application Security Engineer."
        
        # Try to read agents.md
        try:
            agents_md = read_file(self.project, 'agents.md')
            context += f"\n\nProject Specification (agents.md):\n{agents_md[:2000]}..." # Truncate to avoid overflow
        except:
            pass
            
        # Try to read README.md
        try:
            readme_md = read_file(self.project, 'README.md')
            context += f"\n\nProject Readme:\n{readme_md[:2000]}..."
        except:
            pass
            
        return context

    def scan_code(self, file_path, file_content):
        """
        Analyzes code for vulnerabilities using OpenAI.
        """
        prompt = f"""
        Analyze the following file: {file_path}
        
        ```{file_path.split('.')[-1]}
        {file_content}
        ```
        
        Return a JSON list of vulnerabilities. If none are found, return an empty list.
        Only report issues that are exploitable. Ignore style issues.
        """
        
        try:
            completion = self.client.beta.chat.completions.parse(
                model="gpt-4o-2024-08-06",
                messages=[
                    {"role": "system", "content": self.system_context},
                    {"role": "user", "content": prompt},
                ],
                response_format=ScanResult,
            )
            
            findings = [v.model_dump() for v in completion.choices[0].message.parsed.findings]
            print(f"DEBUG: Scanned {file_path}, found {len(findings)} issues.")
            return findings
        except Exception as e:
            print(f"Error scanning {file_path}: {e}")
            return []

    def verify_fix(self, original_content, fixed_content, vulnerability_title):
        """
        Verifies if the fix resolves the issue using OpenAI.
        """
        prompt = f"""
        I have applied a fix for '{vulnerability_title}'.
        
        Original Code:
        ```
        {original_content}
        ```
        
        Fixed Code:
        ```
        {fixed_content}
        ```
        
        Does the fix resolve the vulnerability without introducing syntax errors or new bugs?
        """
        
        try:
            completion = self.client.beta.chat.completions.parse(
                model="gpt-4o-2024-08-06",
                messages=[
                    {"role": "system", "content": "You are a QA Engineer verifying security fixes."},
                    {"role": "user", "content": prompt},
                ],
                response_format=VerificationResult,
            )
            
            result = completion.choices[0].message.parsed
            return {
                "verified": result.is_true_positive, # Reusing field for verification status
                "reason": result.reasoning
            }
        except Exception as e:
            print(f"Error verifying fix: {e}")
            return {"verified": False, "reason": str(e)}

    def generate_fix(self, finding, file_content):
        """
        Generates a fix for a finding using OpenAI.
        """
        prompt = f"""
        The following code has a '{finding['title']}' at line {finding['line_number']}.
        
        Vulnerable Code:
        ```
        {finding['code_snippet']}
        ```
        
        Full File Context:
        ```
        {file_content}
        ```
        
        Generate a secure fix. Return the COMPLETE fixed code block for the snippet (or the whole file if necessary context requires it, but prefer the snippet).
        """
        
        try:
            completion = self.client.beta.chat.completions.parse(
                model="gpt-4o-2024-08-06",
                messages=[
                    {"role": "system", "content": self.system_context},
                    {"role": "user", "content": prompt},
                ],
                response_format=FixResult,
            )
            
            return completion.choices[0].message.parsed.model_dump()
        except Exception as e:
            print(f"Error generating fix: {e}")
            return {"fixed_code": "", "explanation": f"Error: {str(e)}"}

