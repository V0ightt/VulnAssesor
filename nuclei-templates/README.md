# Nuclei Templates Directory

This directory contains pre-loaded Nuclei templates that are automatically imported into the database when the application is built or when you run the setup command.

## Included Templates

1. **security-headers.yaml** - Detects missing security headers
2. **server-disclosure.yaml** - Finds server information disclosure
3. **admin-panels.yaml** - Discovers common admin panel endpoints

## Adding Your Own Templates

Simply add your `.yaml` files to this directory. They will be automatically loaded when:
- The application is built with Docker
- You run: `python manage.py load_templates`

## Template Format

Each template must be a valid Nuclei YAML file with:
- `id`: Unique identifier
- `info`: Metadata (name, author, severity, description, tags)
- `requests`: The actual scan logic

## Example

```yaml
id: my-custom-template

info:
  name: My Custom Vulnerability Check
  author: Your Name
  severity: medium
  description: What this template detects
  tags: custom,example

requests:
  - method: GET
    path:
      - "{{BaseURL}}/endpoint"
    
    matchers:
      - type: word
        words:
          - "vulnerable pattern"
```

## Resources

- [Nuclei Template Guide](https://docs.projectdiscovery.io/templates/introduction)
- [Template Examples](https://github.com/projectdiscovery/nuclei-templates)

## Auto-Loading

Templates are loaded by the `load_templates` management command, which:
1. Scans this directory for `.yaml` files
2. Parses each template
3. Creates a `NucleiTemplate` entry for each file
4. Assigns them to the admin user (or creates a system user)

Templates are only loaded once (checked by template ID to avoid duplicates).

