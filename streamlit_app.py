"""
RepoMind Streamlit App
A clean, professional interface for analyzing GitHub repositories
"""

import streamlit as st
import sys
from pathlib import Path

# Add backend directory to Python path
backend_path = Path(__file__).parent / "backend"
sys.path.insert(0, str(backend_path))

# Import backend functions directly
from repo_handler import fetch_repo
from analyzer import analyze_repo, _call_watsonx_api

# Page configuration
st.set_page_config(
    page_title="RepoMind - GitHub Repository Analyzer",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Custom CSS for professional dark theme
st.markdown("""
    <style>
    .main {
        padding: 2rem;
    }
    .stTextInput > div > div > input {
        font-size: 16px;
    }
    .stButton > button {
        width: 100%;
        background-color: #0066cc;
        color: white;
        font-weight: 600;
        padding: 0.75rem 1rem;
        border-radius: 8px;
        border: none;
        font-size: 16px;
    }
    .stButton > button:hover {
        background-color: #0052a3;
    }
    .stExpander {
        border: 1px solid #333;
        border-radius: 8px;
        margin-bottom: 1rem;
    }
    h1 {
        color: #0066cc;
        font-size: 2.5rem;
        margin-bottom: 0.5rem;
    }
    h2 {
        font-size: 1.5rem;
        margin-top: 2rem;
        margin-bottom: 1rem;
    }
    .subtitle {
        color: #888;
        font-size: 1.1rem;
        margin-bottom: 2rem;
    }
    </style>
""", unsafe_allow_html=True)

# Initialize session state
if "repo_data" not in st.session_state:
    st.session_state.repo_data = None
if "analysis" not in st.session_state:
    st.session_state.analysis = None
if "github_url" not in st.session_state:
    st.session_state.github_url = ""
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# Header
st.title("🧠 RepoMind")
st.markdown('<p class="subtitle">AI-Powered GitHub Repository Analysis</p>', unsafe_allow_html=True)

# Main input section
col1, col2 = st.columns([4, 1])

with col1:
    github_url = st.text_input(
        "GitHub Repository URL",
        placeholder="https://github.com/username/repository",
        value=st.session_state.github_url,
        label_visibility="collapsed"
    )

with col2:
    analyze_button = st.button("🔍 Analyze", use_container_width=True)

# Analysis logic
if analyze_button and github_url:
    # Validate URL
    if not github_url.startswith(("https://github.com/", "http://github.com/")):
        st.error("❌ Invalid GitHub URL. Must start with https://github.com/")
    else:
        st.session_state.github_url = github_url
        st.session_state.chat_history = []  # Clear chat history on new analysis
        
        # Fetch repository
        with st.spinner("🔄 Cloning repository..."):
            repo_data = fetch_repo(github_url)
        
        if repo_data.get("error"):
            st.error(f"❌ Error: {repo_data['error']}")
        else:
            st.session_state.repo_data = repo_data
            st.success(f"✅ Repository cloned successfully! Found {len(repo_data['file_tree'])} files.")
            
            # Analyze repository
            with st.spinner("🤖 Analyzing repository with AI..."):
                analysis = analyze_repo(repo_data)
            
            if analysis.get("error"):
                st.warning(f"⚠️ Analysis completed with warnings: {analysis['error']}")
            else:
                st.success("✅ Analysis complete!")
            
            st.session_state.analysis = analysis

# Display results if available
if st.session_state.analysis and st.session_state.repo_data:
    st.markdown("---")
    st.markdown("## 📊 Analysis Results")
    
    analysis = st.session_state.analysis
    repo_data = st.session_state.repo_data
    
    # Architecture Summary
    with st.expander("🏗️ Architecture Summary", expanded=True):
        if analysis.get("architecture_summary"):
            st.markdown(analysis["architecture_summary"])
        else:
            st.info("No architecture summary available.")
    
    # Module Breakdown
    with st.expander("📦 Module Breakdown", expanded=False):
        if analysis.get("module_breakdown"):
            st.markdown(analysis["module_breakdown"])
        else:
            st.info("No module breakdown available.")
    
    # Key Flows
    with st.expander("🔄 Key Flows", expanded=False):
        if analysis.get("key_flows"):
            st.markdown(analysis["key_flows"])
        else:
            st.info("No key flows analysis available.")
    
    # File Tree
    with st.expander("📁 File Tree", expanded=False):
        if repo_data.get("file_tree"):
            # Display file tree in a scrollable container
            file_tree_text = "\n".join(f"- {path}" for path in repo_data["file_tree"])
            st.text_area(
                "Repository Files",
                value=file_tree_text,
                height=400,
                label_visibility="collapsed"
            )
            st.caption(f"Total files: {len(repo_data['file_tree'])}")
        else:
            st.info("No file tree available.")
    
    # Chat Section
    st.markdown("---")
    st.markdown("## 💬 Ask Questions About This Repository")
    
    # Display chat history
    for i, (question, answer) in enumerate(st.session_state.chat_history):
        with st.container():
            st.markdown(f"**You:** {question}")
            st.markdown(f"**RepoMind:** {answer}")
            if i < len(st.session_state.chat_history) - 1:
                st.markdown("---")
    
    # Chat input
    question = st.chat_input("Ask a question about this repository...")
    
    if question:
        with st.spinner("🤖 Thinking..."):
            # Create a summary of the repository structure
            file_tree = repo_data.get("file_tree", [])
            file_contents = repo_data.get("file_contents", {})
            
            tree_summary = "\n".join(f"- {path}" for path in file_tree[:50])
            if len(file_tree) > 50:
                tree_summary += f"\n... and {len(file_tree) - 50} more files"
            
            # Include key file contents
            key_files = []
            for path, content in list(file_contents.items())[:5]:
                truncated_content = content[:1000] + "..." if len(content) > 1000 else content
                key_files.append(f"\n### {path}\n```\n{truncated_content}\n```")
            
            key_files_text = "\n".join(key_files)
            
            # Create prompt
            prompt = f"""You are a helpful AI assistant analyzing a GitHub repository.

Repository: {st.session_state.github_url}

Repository File Structure:
{tree_summary}

Key Files:
{key_files_text}

User Question: {question}

Please provide a clear, concise, and helpful answer based on the repository structure and contents shown above. If the information needed to answer the question is not available in the provided data, say so."""
            
            # Get answer from AI
            answer = _call_watsonx_api(prompt)
            
            if answer:
                # Add to chat history
                st.session_state.chat_history.append((question, answer))
                st.rerun()
            else:
                st.error("❌ Failed to generate answer. Please try again.")

elif not st.session_state.repo_data:
    # Show welcome message
    st.info("👆 Enter a GitHub repository URL above and click Analyze to get started!")
    
    st.markdown("### ✨ Features")
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("""
        - 🏗️ **Architecture Analysis**: Understand the overall structure and tech stack
        - 📦 **Module Breakdown**: Explore main components and their purposes
        """)
    
    with col2:
        st.markdown("""
        - 🔄 **Key Flows**: Learn about important processes and workflows
        - 💬 **Interactive Chat**: Ask questions about the repository
        """)
    
    st.markdown("### 📝 Example Repositories")
    st.markdown("""
    Try analyzing these popular repositories:
    - `https://github.com/octocat/Hello-World`
    - `https://github.com/microsoft/vscode`
    - `https://github.com/facebook/react`
    """)

# Footer
st.markdown("---")
st.markdown(
    '<p style="text-align: center; color: #666; font-size: 0.9rem;">Powered by IBM Granite via watsonx.ai</p>',
    unsafe_allow_html=True
)

# Made with Bob
