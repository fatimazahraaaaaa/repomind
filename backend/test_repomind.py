"""
Unit Tests for RepoMind
Tests for fetch_repo and analyze_repo functions
"""

import unittest
from unittest.mock import patch, MagicMock, mock_open
import tempfile
import os
import shutil
from pathlib import Path

# Import functions to test
from repo_handler import fetch_repo, _get_file_priority, _should_skip_directory, _should_skip_file
from analyzer import analyze_repo, _create_prompt, _call_watsonx_api


class TestFetchRepo(unittest.TestCase):
    """Test cases for fetch_repo function"""
    
    def test_fetch_repo_invalid_url(self):
        """Test 1: fetch_repo should handle invalid URLs gracefully"""
        # Test with empty string
        result = fetch_repo("")
        self.assertIn("error", result)
        self.assertEqual(result["error"], "Invalid GitHub URL provided")
        self.assertEqual(result["file_tree"], [])
        self.assertEqual(result["file_contents"], {})
        
        # Test with None
        result = fetch_repo(None)
        self.assertIn("error", result)
        self.assertEqual(result["error"], "Invalid GitHub URL provided")
    
    @patch('repo_handler.git.Repo.clone_from')
    def test_fetch_repo_repository_not_found(self, mock_clone):
        """Test 2: fetch_repo should handle repository not found errors"""
        # Mock GitCommandError for repository not found
        from git.exc import GitCommandError
        mock_clone.side_effect = GitCommandError(
            'git clone',
            128,
            stderr='fatal: repository not found'
        )
        
        result = fetch_repo("https://github.com/nonexistent/repo")
        
        self.assertIn("error", result)
        self.assertIn("not found", result["error"].lower())
        self.assertEqual(result["file_tree"], [])
        self.assertEqual(result["file_contents"], {})
    
    @patch('repo_handler.git.Repo.clone_from')
    @patch('repo_handler._collect_files')
    @patch('repo_handler._read_file_safely')
    @patch('repo_handler.tempfile.mkdtemp')
    @patch('repo_handler.shutil.rmtree')
    def test_fetch_repo_successful_clone(self, mock_rmtree, mock_mkdtemp, 
                                         mock_read_file, mock_collect, mock_clone):
        """Test 3: fetch_repo should successfully clone and analyze a repository"""
        # Setup mocks
        temp_dir = "/tmp/test_repo"
        mock_mkdtemp.return_value = temp_dir
        
        # Mock repository clone
        mock_repo = MagicMock()
        mock_clone.return_value = mock_repo
        
        # Mock file collection
        mock_collect.return_value = [
            ("README.md", 0),
            ("src/main.py", 2),
            ("requirements.txt", 1)
        ]
        
        # Mock file reading
        def read_file_side_effect(filepath):
            if "README.md" in filepath:
                return "# Test Repository\nThis is a test."
            elif "main.py" in filepath:
                return "def main():\n    pass"
            elif "requirements.txt" in filepath:
                return "fastapi\nuvicorn"
            return None
        
        mock_read_file.side_effect = read_file_side_effect
        
        # Execute
        result = fetch_repo("https://github.com/test/repo")
        
        # Assertions
        self.assertIsNone(result["error"])
        self.assertEqual(len(result["file_tree"]), 3)
        self.assertIn("README.md", result["file_tree"])
        self.assertIn("src/main.py", result["file_tree"])
        self.assertIn("requirements.txt", result["file_tree"])
        
        # Check file contents
        self.assertEqual(len(result["file_contents"]), 3)
        self.assertIn("README.md", result["file_contents"])
        self.assertIn("# Test Repository", result["file_contents"]["README.md"])
        
        # Verify cleanup was attempted (may be called in finally block)
        self.assertTrue(mock_rmtree.called)


class TestAnalyzeRepo(unittest.TestCase):
    """Test cases for analyze_repo function"""
    
    def test_analyze_repo_with_error_in_repo_data(self):
        """Test 4: analyze_repo should handle errors from fetch_repo"""
        repo_data = {
            "file_tree": [],
            "file_contents": {},
            "error": "Repository not found"
        }
        
        result = analyze_repo(repo_data)
        
        self.assertIn("error", result)
        self.assertIn("Cannot analyze repository", result["error"])
        self.assertEqual(result["architecture_summary"], "")
        self.assertEqual(result["module_breakdown"], "")
        self.assertEqual(result["key_flows"], "")
    
    def test_analyze_repo_with_empty_data(self):
        """Test 5: analyze_repo should handle empty repository data"""
        repo_data = {
            "file_tree": [],
            "file_contents": {},
            "error": None
        }
        
        result = analyze_repo(repo_data)
        
        self.assertIn("error", result)
        self.assertEqual(result["error"], "No repository data to analyze")
        self.assertEqual(result["architecture_summary"], "")
        self.assertEqual(result["module_breakdown"], "")
        self.assertEqual(result["key_flows"], "")
    
    @patch('analyzer._call_watsonx_api')
    def test_analyze_repo_successful_analysis(self, mock_watsonx):
        """Test 6: analyze_repo should successfully generate all three analyses"""
        # Setup mock repository data
        repo_data = {
            "file_tree": [
                "README.md",
                "src/main.py",
                "src/utils.py",
                "requirements.txt",
                "tests/test_main.py"
            ],
            "file_contents": {
                "README.md": "# Test Project\nA Python web application",
                "requirements.txt": "fastapi\nuvicorn\npydantic",
                "src/main.py": "from fastapi import FastAPI\napp = FastAPI()"
            },
            "error": None
        }
        
        # Mock watsonx API responses
        mock_responses = [
            "This is a Python web application built with FastAPI framework. It follows a modular architecture with separate source and test directories.",
            "Main modules:\n1. src/ - Contains application source code\n2. tests/ - Contains unit tests\n3. Root configuration files",
            "Key flows:\n1. API Request Flow: Client -> FastAPI -> Handler -> Response\n2. Testing Flow: pytest -> test files -> assertions"
        ]
        mock_watsonx.side_effect = mock_responses
        
        # Execute
        result = analyze_repo(repo_data)
        
        # Assertions
        self.assertIsNone(result["error"])
        self.assertIn("Python web application", result["architecture_summary"])
        self.assertIn("Main modules", result["module_breakdown"])
        self.assertIn("Key flows", result["key_flows"])
        
        # Verify watsonx was called 3 times
        self.assertEqual(mock_watsonx.call_count, 3)


class TestHelperFunctions(unittest.TestCase):
    """Test cases for helper functions"""
    
    def test_get_file_priority(self):
        """Test 7: _get_file_priority should correctly prioritize files"""
        # Critical files (priority 0)
        self.assertEqual(_get_file_priority("README.md"), 0)
        self.assertEqual(_get_file_priority("main.py"), 0)
        self.assertEqual(_get_file_priority("LICENSE"), 0)
        
        # Config files (priority 1)
        self.assertEqual(_get_file_priority("requirements.txt"), 1)
        self.assertEqual(_get_file_priority("package.json"), 1)
        self.assertEqual(_get_file_priority("Dockerfile"), 1)
        
        # Source files in src/ (priority 2)
        self.assertEqual(_get_file_priority("src/app.py"), 2)
        
        # Other files (priority 3 or 4)
        priority = _get_file_priority("tests/test_app.py")
        self.assertIn(priority, [2, 3, 4])
    
    def test_should_skip_directory(self):
        """Test 8: _should_skip_directory should correctly identify excluded directories"""
        # Should skip
        self.assertTrue(_should_skip_directory("node_modules"))
        self.assertTrue(_should_skip_directory(".git"))
        self.assertTrue(_should_skip_directory("__pycache__"))
        self.assertTrue(_should_skip_directory("venv"))
        self.assertTrue(_should_skip_directory(".cache"))
        
        # Should not skip
        self.assertFalse(_should_skip_directory("src"))
        self.assertFalse(_should_skip_directory("tests"))
        self.assertFalse(_should_skip_directory(".github"))  # Special case
    
    def test_should_skip_file(self):
        """Test 9: _should_skip_file should correctly identify excluded files"""
        # Should skip
        self.assertTrue(_should_skip_file(".env"))
        self.assertTrue(_should_skip_file("test.pyc"))
        self.assertTrue(_should_skip_file("package-lock.json"))
        self.assertTrue(_should_skip_file("yarn.lock"))
        self.assertTrue(_should_skip_file(".DS_Store"))
        
        # Should not skip
        self.assertFalse(_should_skip_file("main.py"))
        self.assertFalse(_should_skip_file("README.md"))
        self.assertFalse(_should_skip_file("config.json"))


class TestPromptCreation(unittest.TestCase):
    """Test cases for prompt creation"""
    
    def test_create_prompt_architecture(self):
        """Test 10: _create_prompt should generate proper architecture prompts"""
        repo_data = {
            "file_tree": ["README.md", "src/main.py"],
            "file_contents": {
                "README.md": "# Test Project",
                "src/main.py": "print('hello')"
            }
        }
        
        prompt = _create_prompt(repo_data, "architecture")
        
        self.assertIn("architecture summary", prompt.lower())
        self.assertIn("README.md", prompt)
        self.assertIn("tech stack", prompt.lower())
        self.assertIn("programming language", prompt.lower())
    
    def test_create_prompt_modules(self):
        """Test 11: _create_prompt should generate proper module breakdown prompts"""
        repo_data = {
            "file_tree": ["src/main.py", "tests/test.py"],
            "file_contents": {}
        }
        
        prompt = _create_prompt(repo_data, "modules")
        
        self.assertIn("modules", prompt.lower())
        self.assertIn("directories", prompt.lower())
        self.assertIn("src/main.py", prompt)
    
    def test_create_prompt_flows(self):
        """Test 12: _create_prompt should generate proper key flows prompts"""
        repo_data = {
            "file_tree": ["api/routes.py"],
            "file_contents": {}
        }
        
        prompt = _create_prompt(repo_data, "flows")
        
        self.assertIn("flows", prompt.lower())
        self.assertIn("authentication", prompt.lower())
        self.assertIn("api", prompt.lower())


class TestWatsonxIntegration(unittest.TestCase):
    """Test cases for watsonx.ai integration"""
    
    @patch.dict(os.environ, {
        'WATSONX_API_KEY': '',
        'WATSONX_PROJECT_ID': ''
    })
    def test_call_watsonx_api_missing_credentials(self):
        """Test 13: _call_watsonx_api should handle missing credentials"""
        with self.assertRaises(ValueError) as context:
            _call_watsonx_api("test prompt")
        
        self.assertIn("WATSONX_API_KEY", str(context.exception))
    
    @patch.dict(os.environ, {
        'WATSONX_API_KEY': 'test_key',
        'WATSONX_PROJECT_ID': 'test_project'
    })
    @patch('analyzer._get_iam_token')
    @patch('analyzer.httpx.Client')
    def test_call_watsonx_api_successful_call(self, mock_client, mock_get_token):
        """Test 14: _call_watsonx_api should successfully call the API"""
        # Mock IAM token
        mock_get_token.return_value = "test_iam_token"
        
        # Mock HTTP response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "results": [
                {"generated_text": "This is a test response from Granite model"}
            ]
        }
        mock_response.raise_for_status = MagicMock()
        
        # Mock client context manager
        mock_client_instance = MagicMock()
        mock_client_instance.post.return_value = mock_response
        mock_client.return_value.__enter__.return_value = mock_client_instance
        
        # Execute
        result = _call_watsonx_api("Analyze this code")
        
        # Assertions
        self.assertIsNotNone(result)
        self.assertIn("test response", result)
        mock_get_token.assert_called_once()
        mock_client_instance.post.assert_called_once()
    
    @patch.dict(os.environ, {
        'WATSONX_API_KEY': 'test_key',
        'WATSONX_PROJECT_ID': 'test_project'
    })
    @patch('analyzer._get_iam_token')
    @patch('analyzer.httpx.Client')
    def test_call_watsonx_api_http_error(self, mock_client, mock_get_token):
        """Test 15: _call_watsonx_api should handle HTTP errors gracefully"""
        # Mock IAM token
        mock_get_token.return_value = "test_iam_token"
        
        # Mock HTTP error
        import httpx
        mock_client_instance = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"
        mock_client_instance.post.side_effect = httpx.HTTPStatusError(
            "Unauthorized",
            request=MagicMock(),
            response=mock_response
        )
        mock_client.return_value.__enter__.return_value = mock_client_instance
        
        # Execute
        result = _call_watsonx_api("Test prompt")
        
        # Should return None on error
        self.assertIsNone(result)


def run_tests():
    """Run all tests and display results"""
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add all test classes
    suite.addTests(loader.loadTestsFromTestCase(TestFetchRepo))
    suite.addTests(loader.loadTestsFromTestCase(TestAnalyzeRepo))
    suite.addTests(loader.loadTestsFromTestCase(TestHelperFunctions))
    suite.addTests(loader.loadTestsFromTestCase(TestPromptCreation))
    suite.addTests(loader.loadTestsFromTestCase(TestWatsonxIntegration))
    
    # Run tests with verbose output
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Print summary
    print("\n" + "="*70)
    print(f"Tests run: {result.testsRun}")
    print(f"Successes: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print("="*70)
    
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_tests()
    exit(0 if success else 1)

# Made with Bob
