# 🧠 RepoMind

**AI-Powered GitHub Repository Onboarding Copilot**

RepoMind is an intelligent tool that helps developers quickly understand and onboard to new GitHub repositories. By leveraging IBM's Granite AI model via watsonx.ai, it automatically analyzes repository structure, generates comprehensive documentation, and provides an interactive Q&A interface.

---

## 🎯 Problem Statement

Onboarding to a new codebase is time-consuming and challenging:
- **Information Overload**: Large repositories with hundreds of files are overwhelming
- **Lack of Documentation**: Many projects have outdated or incomplete documentation
- **Context Switching**: Developers spend hours navigating code to understand architecture
- **Knowledge Gaps**: Understanding key flows and module relationships takes significant time

**RepoMind solves this** by providing instant, AI-powered insights into any GitHub repository, reducing onboarding time from hours to minutes.

---

## ✨ Key Features

### 📊 **Architecture Summary**
Automatically generates a comprehensive overview of:
- Project purpose and type (web app, library, CLI tool, etc.)
- Primary programming languages and frameworks
- Complete tech stack (frontend, backend, database)
- Architecture patterns (MVC, microservices, monolithic)
- Key dependencies and technologies

### 📦 **Module Breakdown**
Provides detailed analysis of:
- Main directories and logical modules (5-8 key components)
- Purpose and contents of each module
- Inter-module relationships and dependencies
- Code organization patterns

### 🔄 **Key Flows Analysis**
Explains 2-3 critical workflows such as:
- Authentication/authorization flows
- API request handling
- Data processing pipelines
- User interaction patterns
- Build and deployment processes

### 💬 **Interactive Chat Q&A**
Ask questions about the repository and get instant AI-powered answers:
- "What is the main purpose of this repository?"
- "How does authentication work?"
- "What are the main API endpoints?"
- "Where is the database configuration?"

---

## 🛠️ Tech Stack

### Backend
- **FastAPI** - Modern, fast Python web framework
- **GitPython** - Repository cloning and file extraction
- **httpx** - Async HTTP client for API calls
- **python-dotenv** - Environment variable management

### AI/ML
- **IBM watsonx.ai** - Enterprise AI platform
- **IBM Granite 3 8B Instruct** - Advanced language model for code analysis
- **Model ID**: `ibm/granite-3-8b-instruct`

### Frontend
- **Vanilla JavaScript** - Lightweight, no framework overhead
- **Modern CSS** - Gradient backgrounds, glassmorphism effects
- **Responsive Design** - Mobile-friendly interface

---

## 🚀 Setup Instructions

### Prerequisites
- Python 3.8 or higher
- Git installed on your system
- IBM Cloud account with watsonx.ai access

### 1. Clone the Repository
```bash
git clone https://github.com/yourusername/repomind.git
cd repomind
```

### 2. Install Dependencies
```bash
cd backend
pip install -r requirements.txt
```

### 3. Configure Environment Variables
Create a `.env` file in the `backend` directory:

```env
WATSONX_API_KEY=your_ibm_cloud_api_key
WATSONX_PROJECT_ID=your_watsonx_project_id
WATSONX_URL=https://us-south.ml.cloud.ibm.com
```

**To get your credentials:**
1. Sign up for [IBM Cloud](https://cloud.ibm.com/)
2. Create a watsonx.ai project
3. Generate an API key from IBM Cloud IAM
4. Copy your project ID from watsonx.ai

### 4. Start the Backend Server
```bash
cd backend
python -m uvicorn main:app --reload --port 8000
```

The API will be available at `http://localhost:8000`

### 5. Open the Frontend
Open `frontend/index.html` in your web browser, or serve it with a local server:

```bash
# Using Python's built-in server
cd frontend
python -m http.server 3000
```

Then navigate to `http://localhost:3000`

---

## 📖 API Documentation

### Health Check
```http
GET /health
```
Returns API status.

### Analyze Repository
```http
POST /analyze
Content-Type: application/json

{
  "github_url": "https://github.com/user/repo"
}
```

**Response:**
```json
{
  "file_tree": ["README.md", "src/main.py", ...],
  "file_contents": {
    "README.md": "# Project Title\n..."
  },
  "architecture_summary": "This is a Python web application...",
  "module_breakdown": "Main modules include...",
  "key_flows": "Key flows: 1. Authentication...",
  "error": null
}
```

### Chat Q&A
```http
POST /chat
Content-Type: application/json

{
  "github_url": "https://github.com/user/repo",
  "question": "What is the main purpose of this repository?",
  "repo_data": {
    "file_tree": [...],
    "file_contents": {...}
  }
}
```

**Interactive API Documentation:** Visit `http://localhost:8000/docs` for Swagger UI

---

## 🤖 How IBM Bob Was Used in Development

RepoMind was built with the assistance of **IBM Bob**, an AI-powered development copilot. Bob helped accelerate development through:

### 1. **Architecture Planning**
- Designed the three-tier architecture (repo handler, analyzer, API)
- Planned the file prioritization system for efficient repository analysis
- Structured the watsonx.ai integration strategy

### 2. **Code Implementation**
- **repo_handler.py**: Bob implemented the complete repository cloning and file extraction logic with intelligent prioritization
- **analyzer.py**: Created the watsonx.ai integration with proper prompt engineering for three distinct analysis types
- **main.py**: Built the FastAPI backend with proper error handling, CORS configuration, and request/response models

### 3. **Best Practices**
- Implemented comprehensive error handling across all modules
- Added proper type hints and documentation
- Created modular, maintainable code structure
- Included example usage and testing code

### 4. **Problem Solving**
- Debugged PowerShell command syntax issues for Windows compatibility
- Fixed IAM token authentication for watsonx.ai API
- Optimized file reading with size limits and encoding fallbacks

### 5. **Documentation**
- Generated detailed docstrings for all functions
- Created this comprehensive README
- Documented API endpoints with examples

**Development Sessions:** All Bob interactions are documented in the `bob_sessions/` directory, providing a complete audit trail of the development process.

---

## 📁 Project Structure

```
repomind/
├── backend/
│   ├── main.py              # FastAPI application and endpoints
│   ├── repo_handler.py      # GitHub repository cloning and file extraction
│   ├── analyzer.py          # watsonx.ai integration and AI analysis
│   ├── requirements.txt     # Python dependencies
│   └── .env                 # Environment variables (not in git)
├── frontend/
│   └── index.html           # Single-page web application
├── bob_sessions/            # Development session logs with IBM Bob
└── README.md                # This file
```

---

## 🔒 Security Notes

- Never commit your `.env` file with API keys
- The `.bobignore` file prevents sensitive files from being shared with Bob
- API keys should be rotated regularly
- Consider implementing rate limiting for production use

---

## 🎨 Features in Action

1. **Paste any GitHub URL** into the input field
2. **Click Analyze** to start the AI-powered analysis
3. **View comprehensive insights** in three organized panels
4. **Ask questions** using the interactive chat interface
5. **Get instant answers** powered by IBM Granite AI

---

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

---

## 📄 License

This project is licensed under the MIT License.

---

## 🙏 Acknowledgments

- **IBM watsonx.ai** for providing the AI infrastructure
- **IBM Granite Model** for powerful code analysis capabilities
- **IBM Bob** for accelerating the development process
- **FastAPI** for the excellent web framework
- **GitPython** for seamless Git integration

---

## 📞 Support

For issues, questions, or suggestions, please open an issue on GitHub.

---

**Built with ❤️ using IBM watsonx.ai and IBM Bob**