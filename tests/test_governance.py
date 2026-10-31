"""Unit tests for repository open-source governance documents."""

import os
import unittest


class TestGovernanceDocuments(unittest.TestCase):
    """Verifies mandatory open-source community health documents."""

    def setUp(self):
        self.root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def test_contributing_guide_exists(self):
        """Verifies that CONTRIBUTING.md exists and provides setup instructions."""
        contrib_path = os.path.join(self.root_dir, "CONTRIBUTING.md")
        self.assertTrue(os.path.exists(contrib_path), "CONTRIBUTING.md must exist in root.")
        with open(contrib_path, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("Quickstart Development Setup", content)
        self.assertIn("Running the Test Suite", content)

    def test_code_of_conduct_exists(self):
        """Verifies that CODE_OF_CONDUCT.md exists."""
        coc_path = os.path.join(self.root_dir, "CODE_OF_CONDUCT.md")
        self.assertTrue(os.path.exists(coc_path), "CODE_OF_CONDUCT.md must exist in root.")
        with open(coc_path, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("Contributor Covenant", content)
        self.assertIn("Our Pledge", content)

    def test_license_exists(self):
        """Verifies MIT LICENSE exists."""
        license_path = os.path.join(self.root_dir, "LICENSE")
        self.assertTrue(os.path.exists(license_path), "LICENSE must exist in root.")
        with open(license_path, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("MIT License", content)


if __name__ == "__main__":
    unittest.main()
