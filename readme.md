# VulnAssesor
>[!warning]
> **Work in Progress:** This project is in the very early stages of development. It is not yet functional and is subject to major changes.


## 🎯 Overview & Goal

**VulnAssesor** is an open-source, all-in-one web security and monitoring hub built with Django and HTMX. Sign in, add your website, and get comprehensive security analysis with real-time scanning powered by Nuclei and AI-powered code analysis.

### Current Features (Phase 4 - Implemented)

* ✅ **SAST (Static Application Security Testing):** AI-powered code vulnerability scanning with automated fix generation
* ✅ **DAST (Dynamic Application Security Testing):** Live website vulnerability scanning using Nuclei
* ✅ **AI Integration:** OpenAI GPT-4o analyzes vulnerabilities, provides plain-English explanations, and generates code fixes
* ✅ **Custom Templates:** Create and manage your own Nuclei scan templates
* ✅ **Real-time Updates:** Watch scan progress with HTMX-powered live status updates
* ✅ **Detailed Reports:** Severity-based vulnerability breakdowns with JSON export
* ✅ **Configurable Scanner:** Web-based Nuclei configuration (no code changes needed)
* ✅ **Pre-loaded Templates:** Ready-to-use security checks included

### Coming Soon (Phase 5+)

* 🚀 **Fix Application:** Apply AI-generated fixes directly to repositories
* 🚀 **Pull Request Automation:** Automatic branch creation and PR generation
* 🚀 **AI-Enhanced DAST:** AI analysis for Nuclei findings
* 🚀 **Comprehensive Reporting:** PDF reports, compliance checks, and alerts


## 🚀 Quick Start

### Prerequisites
- Docker & Docker Compose
- OpenAI API Key (for SAST functionality)

### Setup (5-10 minutes)

**Windows, Linux, Mac:**
```bash
docker-compose build
docker-compose up -d
```

**Access:** http://localhost:8000

### Environment Variables
For SAST to work, set your OpenAI API key:
```bash
# Add to docker-compose.yaml or set as environment variable
OPENAI_API_KEY=your-api-key-here
```

## 💻 Technology Stack

* **Backend:** Django 5.2 + Python 3.14
* **Frontend:** Django Templates + HTMX 1.9.10 + Alpine.js 3.13.3
* **Task Queue:** Celery + Redis
* **Database:** PostgreSQL (production) / SQLite (development)
* **DAST Scanner:** Nuclei v3.4.10 by ProjectDiscovery
* **SAST Engine:** Custom AI agent with OpenAI GPT-4o
* **AI Integration:** OpenAI GPT-4o with Pydantic structured outputs
* **Code Management:** GitPython for repository handling
* **Deployment:** Docker with optimized layer caching (97% faster builds)

## 📖 Key Features Explained

### 1. AI-Powered SAST (NEW - Phase 4)
Scan source code repositories with AI intelligence:
- **Project Management:** Import from Git or upload ZIP files
- **AI Analysis:** OpenAI GPT-4o analyzes code for vulnerabilities
- **Multi-Language Support:** Python, JavaScript, TypeScript, Java, C, C++, Go, Rust, PHP, HTML, CSS
- **Automated Fixes:** AI generates complete code fixes with explanations
- **Fix Verification:** AI verifies fixes don't introduce new issues
- **Context-Aware:** Reads project documentation for better recommendations
- **Real-time Updates:** HTMX polling for live scan progress

### 2. Specialist Scanning (DAST)
Run targeted vulnerability scans using custom Nuclei templates:
- Select multiple templates per scan
- Real-time status updates (PENDING → RUNNING → COMPLETED)
- Detailed results with severity breakdown (Critical, High, Medium, Low, Info)
- Export findings as JSON

### 3. Template Management
Full CRUD for Nuclei templates:
- Create custom YAML templates via web interface
- Pre-loaded templates included (security headers, server disclosure, admin panels)
- Auto-load templates from `nuclei-templates/` directory
- Share templates across your team

### 4. Configurable Scanner
Adjust Nuclei settings without touching code:
- Performance: timeout, rate limit, concurrency
- Network: retries, redirects
- Custom arguments support
- Live command preview

### 5. Modern UI
GitHub-inspired dark theme with:
- HTMX for real-time updates 
- Alpine.js for smooth interactions
- Responsive mobile-friendly design
- Intuitive navigation
- Syntax highlighting for code

## 📊 Performance

- **Build Speed:** 8 seconds for code changes (97% faster with Docker optimization)
- **DAST Scan Speed:** 30 seconds to 10 minutes (depending on template complexity)
- **SAST Scan Speed:** 1 minute to 30 minutes (depending on project size)
- **Real-time Updates:** Status polling every 3 seconds
- **Asynchronous:** Non-blocking background processing with Celery
- **AI Response Time:** 2-10 seconds per file for vulnerability analysis

## 📚 Documentation

Comprehensive documentation available:
- **[agents.md](agents.md)** - Complete project specification
- **[SAMPLE_NUCLEI_TEMPLATES.md](SAMPLE_NUCLEI_TEMPLATES.md)** - Template examples

## 🛠️ Development

### Run Locally
```bash
# Build Docker image
docker-compose build
# Start services
docker-compose up
# Access at http://localhost:8000
```

### Run a Scan

#### DAST (Dynamic Scanning):
1. Add a website via Dashboard
2. Go to Templates page (pre-loaded templates available)
3. Click ⚡ scan button next to website
4. Select templates and start scan
5. Watch real-time status updates
6. View detailed results with severity breakdown

#### SAST (Static Code Analysis):
1. Navigate to SAST menu
2. Create new project:
   - Enter Git repository URL, OR
   - Upload ZIP file with source code
3. Wait for project ingestion (CLONING → READY)
4. Click "Start SAST Scan"
5. Watch AI analyze your code (PENDING → SCANNING → COMPLETED)
6. Review findings with:
   - AI explanations in plain English
   - Proposed code fixes
   - Fix verification status
7. (Phase 5) Accept/Reject fixes and apply to repository

## 🤖 AI Integration

### OpenAI GPT-4o Setup
1. Get API key from [OpenAI Platform](https://platform.openai.com/)
2. Set environment variable:
   ```bash
   # Windows PowerShell
   $env:OPENAI_API_KEY="your-api-key-here"
   
   # Linux/Mac
   export OPENAI_API_KEY="your-api-key-here"
   ```
3. Or add to docker-compose.yaml:
   ```yaml
   environment:
     - OPENAI_API_KEY=your-api-key-here
   ```

### What AI Does:
- **Scans Code:** Analyzes files for security vulnerabilities
- **Explains Issues:** Provides plain-English explanations
- **Generates Fixes:** Creates complete code fixes
- **Verifies Fixes:** Confirms fixes resolve issues without introducing bugs
- **Context-Aware:** Reads your project's README and agents.md for better recommendations

### Supported Languages:
Python, JavaScript, TypeScript, Java, C, C++, Go, Rust, PHP, HTML, CSS

## ⚠️ Important Notes

### Cost Considerations:
- **OpenAI API Usage:** SAST scans use GPT-4o, which incurs costs
- **Pricing:** Varies by project size (typically $0.01-$0.50 per scan)
- **Monitor Usage:** Check your OpenAI dashboard for consumption

### Performance Tips:
- **SAST:** Scan duration depends on project size (1-30 minutes)
- **DAST:** Scan duration depends on templates and target size (30s-10min)
- **Concurrent Scans:** Limited by Celery worker count
- **AI Response:** GPT-4o responds in 2-10 seconds per file

### Limitations:
- One active scan per project/website at a time
- AI context limited to 2000 chars for README/agents.md
- Fix application not yet implemented (Phase 5)
- YAML template validation is basic

## 🔒 Security Features

- **User Isolation:** Each user's data is completely isolated
- **CSRF Protection:** All forms protected
- **Input Validation:** All user inputs validated
- **Secure Storage:** Credentials never stored in plain text
- **Path Traversal Protection:** SAST file operations secured
- **API Key Security:** OpenAI keys stored as environment variables

## 🧪 Testing

If you want to help the project and find bugs/errors check the testing checklist:
- Template CRUD operations
- Scan execution and status updates
- Real-time HTMX polling
- Result viewing and export
- User permissions and isolation
- Project creation (Git and ZIP)
- SAST scan execution
- AI vulnerability detection
- Fix generation and verification
- File explorer and code viewer

See [TESTING_CHECKLIST.md](TESTING_CHECKLIST.md) for details.

## 🤝 Contributing

This project is now ready for contributions!

### How to Contribute
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests
5. Submit a pull request

### Development Guidelines
- Follow Django best practices
- Use HTMX for dynamic updates
- Maintain dark theme consistency
- Add tests for new features
- Update documentation

## 📋 Roadmap

### ✅ Phase 1-3: Foundation & DAST (Complete)
- User authentication and website management
- Nuclei integration and template management
- Real-time scanning with HTMX
- Configuration system

### ✅ Phase 4: AI-Powered SAST (Complete)
- OpenAI GPT-4o integration
- Automated vulnerability detection
- AI-generated fixes with verification
- Context-aware code analysis

### 🚀 Phase 5: Advanced SAST Features (Next)
- Apply fixes directly to repositories
- Automated branch creation
- Pull request generation
- Batch fix application

### 🔮 Phase 6: AI-Enhanced DAST
- AI analysis for Nuclei findings
- Plain-English explanations for DAST results
- DAST-specific fix recommendations

### 🔮 Phase 7: Monitoring Engine
- 24/7 uptime monitoring
- SSL certificate checks
- Alert notifications
- Historical data analytics

### 🔮 Phase 8: Advanced Reporting
- PDF report generation
- Compliance reports (OWASP Top 10, PCI-DSS)
- Vulnerability trend analysis
- Executive dashboards 
## 📄 License

[Choose appropriate license - e.g., MIT, GPL, etc.]

## 🙏 Acknowledgments

- **Nuclei** by ProjectDiscovery - Vulnerability scanner
- **OpenAI** - GPT-4o for AI-powered analysis
- **HTMX** - Dynamic HTML updates
- **Alpine.js** - Lightweight JavaScript framework
- **Django** - Web framework
- **Pygments** - Syntax highlighting

## 📧 Contact

- **Issues:** [GitHub Issues](https://github.com/V0ightt/VulnAssesor/issues)
- **Discord:** v0ight_
- **LinkedIn:** [Momen Saeb](https://www.linkedin.com/in/momen-saeb-b88183283/)

---

**Built with ❤️ by Momen Saeb**

*Making web security accessible to everyone.*

