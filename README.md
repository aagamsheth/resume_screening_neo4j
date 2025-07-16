# Resume Screening AI System

An intelligent resume screening system that leverages AI/LLM technology to analyze and match candidates with job requirements. The system provides comprehensive resume analysis, candidate search capabilities, and detailed matching reports for recruiters.

## 🚀 Features

### For Candidates
- **Resume Upload**: Upload resumes in PDF or DOCX format
- **Automatic Analysis**: AI-powered extraction and analysis of resume content
- **Secure Storage**: Resume files and extracted data stored securely on Dropbox

### For Recruiters
- **Advanced Search**: Search candidates using specific keywords and criteria
- **Similarity Matching**: AI-powered candidate matching with similarity scores
- **Detailed Analysis**: Get comprehensive analysis reports explaining why candidates match search criteria
- **Resume Download**: Download original resume files and analysis reports

## 🛠️ Technology Stack

- **Backend**: Django REST Framework
- **Database**: Neo4j Graph Database with vectorized storage
- **AI/LLM**: Flexible choice between Groq and OpenAI
- **MCP Server**: Model Context Protocol for tool calls
- **Search Enhancement**: Google Search integration via MCP
- **File Storage**: Dropbox integration
- **Frontend**: Simple HTML interface for API interaction

## 🏗️ System Architecture

### Core Components

1. **AI Processing Engine**
   - Supports both Groq and OpenAI LLMs
   - Configurable based on developer preference
   - Handles resume analysis and candidate matching

2. **Neo4j Graph Database**
   - Stores candidate information as nodes with properties
   - Vectorized data storage for efficient similarity search
   - Maintains relationships between skills, experience, and roles

3. **MCP Server**
   - Model Context Protocol implementation
   - Google Search tool for keyword enhancement
   - Extensible architecture for additional tools
   - Modular design for easy tool integration
   - Standalone deployment capabilities with Docker support
   - Reusable across multiple projects

4. **Storage System**
   - Dropbox integration for file storage
   - Maintains both original files (PDF/DOCX) and extracted JSON data
   - Secure and scalable storage solution

## 🔍 Search Capabilities

The system supports targeted searches using the following keywords and filters:

### Search Keywords:
- **Skills**: Technical and soft skills
- **Location**: Geographic preferences
- **Name**: Candidate name search
- **Email**: Contact information
- **Education**: Educational background
- **Role**: Job titles and positions

### Advanced Filters:
- **From Experience**: Minimum years of experience filter
- **To Experience**: Maximum years of experience filter
- **Experience Range**: Set both fields to 0 to disable experience filtering
- **Similarity Threshold**: Set minimum similarity score for candidate matching
  - Only candidates with similarity scores above this threshold will be returned
  - Customizable threshold value for precise candidate filtering

### Frontend Controls:
- Individual text boxes for experience range (from/to)
- Dedicated threshold input field
- Flexible filtering with optional constraints

## 📡 API Endpoints

### 1. Upload Endpoint (`/upload/`)
**Purpose**: For candidates to upload their resumes

**Process**:
- Accepts PDF or DOCX files
- Extracts and analyzes resume content using AI
- Stores original file on Dropbox
- Saves extracted data as JSON
- Creates vectorized entries in Neo4j database

### 2. Search Endpoint (`/search/`)
**Purpose**: For recruiters to find matching candidates

**Process**:
- Accepts search queries with specific keywords
- Performs database search and similarity matching
- Returns candidate results with:
  - Candidate name
  - Years of experience
  - Last designation
  - Similarity score

**Frontend Features**:
- Download button for original resumes
- Analyze button for detailed candidate analysis

### 3. Analyze Endpoint (`/analyze/`)
**Purpose**: Provides detailed candidate analysis

**Process**:
- Analyzes specific candidate resume using chosen LLM
- Generates comprehensive analysis report
- Explains why candidate matches search criteria
- Activates download button for analysis report PDF

## 🎯 Search Process Flow

1. **Recruiter Search**: Enter search criteria using supported keywords
2. **Database Query**: System searches Neo4j database with similarity matching
3. **Results Display**: Shows matching candidates with key information
4. **Resume Download**: Access original candidate resumes
5. **Analysis Generation**: Generate detailed matching analysis
6. **Report Download**: Download comprehensive analysis reports

## 💡 Key Benefits

- **Intelligent Matching**: AI-powered candidate-job matching
- **Flexible LLM Support**: Choose between Groq and OpenAI
- **Comprehensive Analysis**: Detailed explanations for matching decisions
- **Scalable Architecture**: Graph database for efficient data relationships
- **Enhanced Search**: Google integration for keyword enrichment
- **User-Friendly**: Simple HTML interface for easy interaction

## 🔧 MCP Server Details

The MCP (Model Context Protocol) server is designed as a standalone, reusable component with the following features:

### Architecture
- **Modular Design**: Adding new tools is straightforward and developer-friendly
- **Extensible Framework**: Easy integration of additional functionality
- **Standalone Operation**: Can be deployed independently
- **Cross-Project Compatibility**: Reusable across different projects

### Current Tools
- **Google Search Tool**: Enhances keyword understanding by retrieving detailed information

### Deployment Options
- **Docker Support**: Includes Dockerfile for containerized deployment
- **Heroku Ready**: Procfile included for easy Heroku deployment
- **Independent Requirements**: Separate requirements.txt for isolated dependencies

### Benefits
- **Scalable**: Can handle multiple concurrent requests
- **Maintainable**: Clear separation of concerns
- **Portable**: Deploy anywhere with minimal configuration
- **Extensible**: Add new tools without affecting existing functionality

## 🔧 Configuration

The system allows developers to configure:
- LLM provider (Groq or OpenAI)
- Search parameters and thresholds
- Database connection settings
- Dropbox storage configuration

## 📋 Usage Workflow

### For Candidates:
1. Access the upload interface
2. Upload resume (PDF/DOCX format)
3. System automatically processes and stores resume data

### For Recruiters:
1. Use search interface with specific keywords
2. Review candidate matches with similarity scores
3. Download original resumes for detailed review
4. Generate AI analysis for candidate fit assessment
5. Download comprehensive analysis reports

## 🚦 Getting Started

### Prerequisites
- Python 3.8 or higher
- Neo4j database
- Dropbox account for file storage
- Google API key for search functionality
- OpenAI or Groq API key

### Setup Instructions

1. **Clone the Repository**
   ```bash
   git clone [repository-url]
   cd resume-screening-project
   ```

2. **Create Environment Files**
   
   Create two `.env` files:
   
   **In the `resumes` project folder:**
   ```env
   GROQ_API_KEY=your_groq_api_key
   GROQ_MODEL=your_groq_model
   OPENAI_API_KEY=your_openai_api_key
   OPENAI_API_MODEL=your_openai_model
   DJANGO_SECRET_KEY=your_django_secret_key
   DJANGO_DEBUG=True
   DROPBOX_ACCESS_TOKEN=your_dropbox_token
   NEO4jURI=your_neo4j_uri
   NEO4jUSER=your_neo4j_username
   NEO4jPASSWORD=your_neo4j_password
   ```
   
   **In the `mcp_server` folder:**
   ```env
   GOOGLE_API_KEY=your_google_api_key
   GOOGLE_SEARCH_ENGINE_ID=your_search_engine_id
   ```

3. **Configure LLM Provider**
   - Navigate to `analyse_resume.py` and `extract_keys.py`
   - Follow the instructions in these files to configure your preferred LLM (Groq or OpenAI)

4. **Install Dependencies**
   ```bash
   # In the root folder
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

5. **Start the MCP Server**
   ```bash
   # Navigate to mcp_server folder
   cd mcp_server
   # Ensure virtual environment is activated
   python server.py
   ```

6. **Start the Django Application**
   ```bash
   # Open a new terminal, navigate to resume folder
   cd resumes
   # Ensure virtual environment is activated
   uvicorn resume.asgi:application --host 0.0.0.0 --port 8000
   ```

### Important Notes
- Ensure both terminals have the virtual environment activated
- The MCP server must be running before starting the Django application
- The Neo4j Database is active
- Both servers need to be running simultaneously for full functionality
- Check all the ip access point and ports in mcp_server, index.html, extract_keys.py and analyse_resume.py and make changes as per your ip configuration.

### Accessing the Application
- Open your browser and navigate to `http://localhost:8000`
- Use the HTML interface to interact with the API endpoints

## 🤝 Contributing

This project is designed with extensibility in mind. The MCP server architecture allows for easy addition of new tools and capabilities.

---

*This system revolutionizes the recruitment process by combining AI intelligence with graph database efficiency, providing recruiters with powerful tools to find the perfect candidates while offering candidates a streamlined application process.*# resume_screening_neo4j
