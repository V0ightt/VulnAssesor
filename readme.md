# VulnAssesor

>[!warning]
> **Work in Progress:** This project is in the very early stages of development. It is not yet functional and is subject to major changes.


## 🎯 Overview

**VulnAssesor** is an open-source, all-in-one web security and monitoring hub built with Django and HTMX. Sign in, add your website, and get comprehensive security analysis with real-time scanning powered by Nuclei and AI.

### Current Features (Phase 3 - Implemented)

* ✅ **DAST Scanning:** Live website vulnerability scanning using Nuclei
* ✅ **Custom Templates:** Create and manage your own Nuclei scan templates
* ✅ **Real-time Updates:** Watch scan progress with HTMX-powered live status updates
* ✅ **Detailed Reports:** Severity-based vulnerability breakdowns with JSON export
* ✅ **Configurable Scanner:** Web-based Nuclei configuration (no code changes needed)
* ✅ **Pre-loaded Templates:** Ready-to-use security checks included

### Coming Soon (Phase 4+)

* 🚀 **AI Integration:** Automatic vulnerability analysis with plain-English explanations and code-level fixes
* 🚀 **SAST:** Static code analysis for repositories
* 🚀 **24/7 Monitoring:** Continuous uptime and security checks
* 🚀 **Pentesting Agents:** Deployable agents for in-depth assessments
* 🚀 **Comprehensive Reporting:** PDF reports, compliance checks, and alerts


## 🚀 Quick Start

### Prerequisites
- Docker & Docker Compose
- Or: Python 3.14, PostgreSQL, Redis

### Setup (5/10 minutes)

**Windows, Linux, Mac:**
```bash
docker-compose build
docker-compose up -d
```

**Access:** http://localhost:8000

## 💻 Technology Stack

* **Backend:** Django 5.2 + Python 3.14
* **Frontend:** Django Templates + HTMX 1.9.10 + Alpine.js 3.13.3
* **Task Queue:** Celery + Redis
* **Database:** PostgreSQL (production) / SQLite (development)
* **Scanner:** Nuclei v3.4.10 by ProjectDiscovery
* **Deployment:** Docker with optimized layer caching (97% faster builds)

## 📖 Key Features Explained

### 1. Specialist Scanning
Run targeted vulnerability scans using custom Nuclei templates:
- Select multiple templates per scan
- Real-time status updates (PENDING → RUNNING → COMPLETED)
- Detailed results with severity breakdown (Critical, High, Medium, Low, Info)
- Export findings as JSON

### 2. Template Management
Full CRUD for Nuclei templates:
- Create custom YAML templates via web interface
- Pre-loaded templates included (security headers, server disclosure, admin panels)
- Auto-load templates from `nuclei-templates/` directory
- Share templates across your team

### 3. Configurable Scanner
Adjust Nuclei settings without touching code:
- Performance: timeout, rate limit, concurrency
- Network: retries, redirects
- Custom arguments support
- Live command preview

### 4. Modern UI
GitHub-inspired dark theme with:
- HTMX for real-time updates (no page reloads)
- Alpine.js for smooth interactions
- Responsive mobile-friendly design
- Intuitive navigation

## 📊 Performance

- **Build Speed:** 8 seconds for code changes (97% faster with Docker optimization)
- **Scan Speed:** 30 seconds to 10 minutes (depending on template complexity)
- **Real-time Updates:** Status polling every 3 seconds
- **Asynchronous:** Non-blocking background processing with Celery

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
1. Add a website via Dashboard
2. Go to Templates page (pre-loaded templates available)
3. Click ⚡ scan button next to website
4. Select templates and start scan
5. Watch real-time status updates
6. View detailed results with severity breakdown

## 🔒 Security Features

- **User Isolation:** Each user's data is completely isolated
- **CSRF Protection:** All forms protected
- **Staff-Only Config:** Scanner configuration restricted to staff users
- **Input Validation:** All user inputs validated
- **Secure Storage:** Credentials never stored in plain text

## 🧪 Testing

Comprehensive testing checklist included:
- Template CRUD operations
- Scan execution and status updates
- Real-time HTMX polling
- Result viewing and export
- User permissions and isolation

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

### ✅ Phase 3: Specialist Scan (Complete)
- Nuclei integration
- Template management
- Real-time scanning
- Configuration system

### 🚀 Phase 4: AI Integration (Next)
- AI-powered vulnerability analysis
- Plain-English explanations
- Code-level fix suggestions
- Automated severity assessment

### 🔮 Phase 5+: Advanced Features
- SAST engine for code repositories
- 24/7 uptime monitoring
- Alert notifications
- PDF report generation
- Compliance reports

## 📄 License

[Choose appropriate license - e.g., MIT, GPL, etc.]

## 🙏 Acknowledgments

- **Nuclei** by ProjectDiscovery - Vulnerability scanner
- **HTMX** - Dynamic HTML updates
- **Alpine.js** - Lightweight JavaScript framework
- **Django** - Web framework

## 📧 Contact

- **Issues:** [GitHub Issues](link-to-issues)
- **Discussions:** [GitHub Discussions](link-to-discussions)
- **Discord:** [your-email]
- **LinkedIn:** [your-email]

---

**Built with ❤️ by Momen Saeb**

*Making web security accessible to everyone.*

