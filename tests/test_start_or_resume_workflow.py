from pathlib import Path
from unittest import TestCase
from unittest.mock import MagicMock, patch

from poi_scraper.utils import start_or_resume_workflow


class TestStartOrResumeWorkflow(TestCase):
    def setUp(self) -> None:
        """Set up test environment before each test."""
        self.db_path = Path("test_workflow.db")
        # Ensure clean state
        if self.db_path.exists():
            self.db_path.unlink()

    def tearDown(self) -> None:
        """Clean up after tests."""
        if self.db_path.exists():
            self.db_path.unlink()

    @patch("poi_scraper.utils.get_all_workflows")
    def test_resume_workflow(self, mock_get_all_workflows: MagicMock) -> None:
        """Test resuming an existing workflow.

        This simulates when there are incomplete workflows and user chooses to resume one.
        """
        # Setup test data
        mock_get_all_workflows.return_value = [
            {"name": "workflow1", "base_url": "https://www.example.com"},
            {"name": "workflow2", "base_url": "https://www.example.com"},
        ]

        # Create mock UI with expected behavior
        mock_ui = MagicMock()

        # Configure mock to return "Yes" for first multiple_choice (want to resume?)
        # and "workflow1" for second multiple_choice (which workflow to resume?)
        mock_ui.multiple_choice.side_effect = ["Yes", "workflow2"]

        # Run the function with our mock
        result = start_or_resume_workflow(mock_ui, self.db_path)

        # Verify the results
        assert result == ("workflow2", "https://www.example.com")
        assert mock_ui.multiple_choice.call_count == 2
        mock_get_all_workflows.assert_called_once()

    @patch("poi_scraper.utils.get_all_workflows")
    @patch("poi_scraper.utils.get_name_for_workflow")
    @patch("poi_scraper.utils.get_base_url")
    def test_new_workflow_no_incomplete(
        self,
        mock_get_base_url: MagicMock,
        mock_get_name: MagicMock,
        mock_get_all_workflows: MagicMock,
    ) -> None:
        """Test starting a new workflow when no incomplete workflows exist.

        Tests the direct path to creating a new workflow when there's nothing to resume.
        """
        # Setup mocks
        mock_get_all_workflows.return_value = []
        mock_get_name.return_value = "new_workflow"
        mock_get_base_url.return_value = "https://www.example.com"

        # Create mock UI (shouldn't be used in this case)
        mock_ui = MagicMock()

        # Run the function
        result = start_or_resume_workflow(mock_ui, self.db_path)

        # Verify results
        assert result == ("new_workflow", "https://www.example.com")
        assert mock_ui.multiple_choice.call_count == 0  # Should never be called
        mock_get_name.assert_called_once_with(mock_ui, self.db_path)
        mock_get_base_url.assert_called_once_with(mock_ui)
        mock_get_all_workflows.assert_called_once()

    @patch("poi_scraper.utils.get_all_workflows")
    @patch("poi_scraper.utils.get_name_for_workflow")
    @patch("poi_scraper.utils.get_base_url")
    def test_new_workflow_with_existing_incomplete(
        self,
        mock_get_base_url: MagicMock,
        mock_get_name: MagicMock,
        mock_get_all_workflows: MagicMock,
    ) -> None:
        """Test creating a new workflow when incomplete workflows exist.

        Tests the scenario where the user chooses to start fresh despite having
        incomplete workflows available.
        """
        # Setup mocks
        mock_get_all_workflows.return_value = [{"name": "existing_workflow"}]
        mock_get_name.return_value = "unique_workflow"
        mock_get_base_url.return_value = "https://www.example.com"

        # Create mock UI
        mock_ui = MagicMock()
        mock_ui.multiple_choice.return_value = "No"  # Don't want to resume

        # Run the function
        result = start_or_resume_workflow(mock_ui, self.db_path)

        # Verify results
        assert result == ("unique_workflow", "https://www.example.com")
        assert mock_ui.multiple_choice.call_count == 1
        mock_get_name.assert_called_once_with(mock_ui, self.db_path)
        mock_get_base_url.assert_called_once_with(mock_ui)
        mock_get_all_workflows.assert_called_once()

    @patch("poi_scraper.utils.get_name_for_workflow")
    @patch("poi_scraper.utils.get_base_url")
    def test_first_time_no_database(
        self, mock_get_base_url: MagicMock, mock_get_name: MagicMock
    ) -> None:
        """Test first-time workflow creation when database doesn't exist.

        Tests the simplest path where there's no database yet, so we go straight
        to creating a new workflow.
        """
        # Setup mocks
        mock_get_name.return_value = "first_workflow"
        mock_get_base_url.return_value = "https://www.example.com"

        # Create mock UI (shouldn't need to use multiple_choice)
        mock_ui = MagicMock()

        # Run the function
        result = start_or_resume_workflow(mock_ui, self.db_path)

        # Verify results
        assert result == ("first_workflow", "https://www.example.com")
        assert mock_ui.multiple_choice.call_count == 0
        mock_get_name.assert_called_once_with(mock_ui, self.db_path)
        mock_get_base_url.assert_called_once_with(mock_ui)

    @patch("poi_scraper.utils.get_all_workflows")
    @patch("poi_scraper.utils.get_name_for_workflow")
    @patch("poi_scraper.utils.is_valid_url")
    def test_new_workflow_invalid_url_handling(
        self,
        mock_is_valid_url: MagicMock,
        mock_get_name: MagicMock,
        mock_get_all_workflows: MagicMock,
    ) -> None:
        """Test handling of invalid URLs when creating a new workflow.

        Tests the scenario where:
        1. User provides an invalid URL first
        2. System asks for URL again
        3. User provides a valid URL
        4. Workflow creation succeeds
        """
        # Setup mocks for workflow state
        mock_get_all_workflows.return_value = []
        mock_get_name.return_value = "new_workflow"

        # Setup URL validation to fail once then succeed
        mock_is_valid_url.side_effect = [False, True]

        # Create mock UI
        mock_ui = MagicMock()
        # Mock user providing invalid URL then valid URL
        mock_ui.text_input.side_effect = [
            "invalid-url",  # First attempt - invalid
            "https://www.example.com",  # Second attempt - valid
        ]

        # Run the function
        result = start_or_resume_workflow(mock_ui, self.db_path)

        # Verify results
        assert result == ("new_workflow", "https://www.example.com")
        mock_get_name.assert_called_once_with(mock_ui, self.db_path)
        assert mock_ui.text_input.call_count == 2  # Should be called twice for URLs
        assert mock_is_valid_url.call_count == 2  # Should validate URL twice
        mock_get_all_workflows.assert_called_once()
