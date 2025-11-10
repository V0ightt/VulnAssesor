
requests:
  - method: GET
    path:
      - "{{BaseURL}}"
    headers:
      Origin: "https://evil.com"
    
    matchers:
      - type: word
        part: header
        words:
          - "Access-Control-Allow-Origin: https://evil.com"
          - "Access-Control-Allow-Origin: *"
        condition: or
```

## 8. HTTP Methods Allowed

```yaml
id: http-methods-allowed
info:
  name: Dangerous HTTP Methods Enabled
  author: VulnAssesor
  severity: medium
  description: Detects dangerous HTTP methods like PUT, DELETE, TRACE
  tags: http,methods,misconfiguration

requests:
  - method: OPTIONS
    path:
      - "{{BaseURL}}"
    
    matchers:
      - type: word
        part: header
        words:
          - "PUT"
          - "DELETE"
          - "TRACE"
          - "CONNECT"
        condition: or
```

## How to Use These Templates

1. **Copy the YAML content** from any template above
2. **Navigate to Templates** in VulnAssesor
3. **Click "Create Template"**
4. **Paste the YAML** into the "Template Content" field
5. **Fill in a name** (e.g., "Security Headers Check")
6. **Add a description** (optional)
7. **Save the template**
8. **Run a scan** using this template

## Template Structure Explanation

```yaml
id: unique-template-identifier
info:
  name: Human-readable name
  author: Your name
  severity: critical|high|medium|low|info
  description: What this template detects
  tags: comma,separated,tags

requests:
  - method: GET|POST|PUT|DELETE|etc
    path:
      - "{{BaseURL}}/endpoint"
    
    headers:  # Optional
      Custom-Header: value
    
    matchers:
      - type: status|word|regex|dsl
        # Matching conditions here
```

## Best Practices

1. **Start Simple**: Begin with basic templates and expand
2. **Test Locally**: Test templates on test sites first
3. **Use Appropriate Severity**: Don't mark everything as critical
4. **Add Good Descriptions**: Help others understand what you're detecting
5. **Tag Properly**: Makes templates easier to organize
6. **Handle False Positives**: Use precise matchers to avoid false alerts

## Resources

- [Official Nuclei Documentation](https://docs.projectdiscovery.io/templates/introduction)
- [Nuclei Template Examples](https://github.com/projectdiscovery/nuclei-templates)
- [Template Editor](https://templates.nuclei.sh/)

## Severity Guidelines

- **Critical**: Remote code execution, SQL injection, authentication bypass
- **High**: XSS, SSRF, sensitive data exposure, CORS misconfiguration
- **Medium**: Missing security headers, outdated libraries, directory listing
- **Low**: Information disclosure, server version leakage
- **Info**: Generic findings, reconnaissance data
# Sample Nuclei Templates

## 1. Missing Security Headers

```yaml
id: missing-security-headers
info:
  name: Missing Security Headers Detection
  author: VulnAssesor
  severity: medium
  description: Detects missing security headers that could expose the application to attacks
  tags: security,headers,misconfiguration

requests:
  - method: GET
    path:
      - "{{BaseURL}}"
    
    matchers-condition: or
    matchers:
      - type: dsl
        name: missing-x-frame-options
        dsl:
          - '!contains(tolower(header), "x-frame-options")'
          - 'status_code == 200'
        condition: and

      - type: dsl
        name: missing-csp
        dsl:
          - '!contains(tolower(header), "content-security-policy")'
          - 'status_code == 200'
        condition: and

      - type: dsl
        name: missing-xss-protection
        dsl:
          - '!contains(tolower(header), "x-xss-protection")'
          - 'status_code == 200'
        condition: and
```

## 2. Server Information Disclosure

```yaml
id: server-information-disclosure
info:
  name: Server Information Disclosure
  author: VulnAssesor
  severity: low
  description: Detects server version information in response headers
  tags: disclosure,headers,info

requests:
  - method: GET
    path:
      - "{{BaseURL}}"
    
    matchers:
      - type: regex
        part: header
        regex:
          - "Server: .+"
          - "X-Powered-By: .+"
        condition: or
```

## 3. Directory Listing Enabled

```yaml
id: directory-listing-enabled
info:
  name: Directory Listing Enabled
  author: VulnAssesor
  severity: medium
  description: Detects if directory listing is enabled on the web server
  tags: misconfiguration,directory-listing

requests:
  - method: GET
    path:
      - "{{BaseURL}}/assets/"
      - "{{BaseURL}}/uploads/"
      - "{{BaseURL}}/images/"
      - "{{BaseURL}}/files/"
    
    matchers-condition: or
    matchers:
      - type: word
        words:
          - "Index of /"
          - "Directory listing for"
          - "<title>Index of"
        part: body
        condition: or

      - type: regex
        regex:
          - "<h1>Index of"
          - "Parent Directory"
        part: body
```

## 4. Common Admin Panels

```yaml
id: common-admin-panels
info:
  name: Common Admin Panel Detection
  author: VulnAssesor
  severity: info
  description: Detects common admin panel endpoints
  tags: admin,discovery,exposure

requests:
  - method: GET
    path:
      - "{{BaseURL}}/admin"
      - "{{BaseURL}}/admin/"
      - "{{BaseURL}}/administrator"
      - "{{BaseURL}}/wp-admin"
      - "{{BaseURL}}/phpmyadmin"
      - "{{BaseURL}}/cpanel"
    
    matchers:
      - type: status
        status:
          - 200
          - 301
          - 302
```

## 5. Outdated jQuery Detection

```yaml
id: outdated-jquery-detection
info:
  name: Outdated jQuery Library Detection
  author: VulnAssesor
  severity: medium
  description: Detects usage of outdated jQuery versions with known vulnerabilities
  tags: javascript,jquery,cve

requests:
  - method: GET
    path:
      - "{{BaseURL}}"
    
    extractors:
      - type: regex
        part: body
        regex:
          - 'jquery[/-]([0-9.]+)(.min)?.js'
        group: 1

    matchers:
      - type: regex
        regex:
          - 'jquery[/-](1\.[0-7]\.|2\.[0-2]\.|3\.[0-4]\.).*\.js'
        part: body
```

## 6. Sensitive File Exposure

```yaml
id: sensitive-file-exposure
info:
  name: Sensitive File Exposure
  author: VulnAssesor
  severity: high
  description: Detects exposed sensitive configuration or backup files
  tags: exposure,files,config

requests:
  - method: GET
    path:
      - "{{BaseURL}}/.env"
      - "{{BaseURL}}/.git/config"
      - "{{BaseURL}}/config.php.bak"
      - "{{BaseURL}}/database.yml"
      - "{{BaseURL}}/wp-config.php.bak"
      - "{{BaseURL}}/.htaccess"
      - "{{BaseURL}}/web.config"
    
    matchers:
      - type: status
        status:
          - 200
```

## 7. CORS Misconfiguration

```yaml
id: cors-misconfiguration
info:
  name: CORS Misconfiguration Detection
  author: VulnAssesor
  severity: high
  description: Detects CORS misconfigurations that allow unauthorized domains
  tags: cors,misconfiguration,security

