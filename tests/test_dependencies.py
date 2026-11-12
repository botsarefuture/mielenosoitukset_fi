"""
Test suite to prevent dependency hell by validating package integrity.

This module ensures:
- All declared dependencies can be imported
- No conflicting dependencies exist (via pip check)
- Core functionality packages are available
"""

import importlib
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


# Core production dependencies that must always be importable
CORE_IMPORTS = {
    "flask": "Flask",
    "flask_cors": "Flask_Cors",
    "flask_socketio": "flask_socketio",
    "pymongo": "pymongo",
    "boto3": "boto3",
    "requests": "Requests",
}

# All packages declared in requirements.txt mapped to their import names
# (import_name: pip_package_name)
DECLARED_IMPORTS = {
    "apscheduler": "APScheduler",
    "boto3": "boto3",
    "botocore": "botocore",
    "flask": "Flask",
    "flask_babel": "flask_babel",
    "flask_caching": "flask_caching",
    "flask_cors": "Flask_Cors",
    "flask_limiter": "Flask_Limiter",
    "flask_login": "Flask_Login",
    "flask_socketio": "flask_socketio",
    "itsdangerous": "itsdangerous",
    "jinja2": "Jinja2",
    "markdown": "Markdown",
    "PIL": "Pillow",
    "jwt": "PyJWT",
    "pymongo": "pymongo",
    "pyotp": "pyotp",
    "pyqrcode": "pyqrcode",
    "dateutil": "python_dateutil",
    "yaml": "PyYAML",
    "requests": "Requests",
    "tqdm": "tqdm",
    "werkzeug": "Werkzeug",
    "imgkit": "imgkit",
}


@pytest.mark.dependency
class TestDependencyIntegrity:
    """Tests to ensure all dependencies are properly installed and compatible."""

    def test_no_dependency_conflicts(self):
        """
        Verify no conflicting dependencies within our declared packages.

        This catches cases where two packages in our requirements.txt require 
        incompatible versions of a shared dependency. Only reports conflicts
        where BOTH packages involved are in our declared requirements.
        """
        result = subprocess.run(
            [sys.executable, "-m", "pip", "check"],
            capture_output=True,
            text=True,
        )

        # Only report conflicts where we declared both involved packages
        declared_package_names = set(DECLARED_IMPORTS.values())
        conflicts = []
        
        for line in result.stdout.split("\n"):
            if line.strip():
                # Count how many of our declared packages appear in this conflict
                matches_in_line = sum(
                    1 for pkg_name in declared_package_names
                    if pkg_name.lower() in line.lower()
                )
                # Only report if both sides of the conflict are our packages
                if matches_in_line >= 2:
                    conflicts.append(line)

        assert not conflicts, (
            f"Dependency conflicts detected between declared packages:\n" 
            + "\n".join(conflicts)
        )

    def test_core_dependencies_importable(self):
        """Verify all core production dependencies can be imported."""
        failed = []

        for import_name, package_name in CORE_IMPORTS.items():
            try:
                importlib.import_module(import_name)
            except ImportError as e:
                failed.append(f"{package_name}: {e}")

        assert not failed, (
            f"Failed to import core dependencies:\n" + "\n".join(failed)
        )

    def test_all_declared_dependencies_importable(self):
        """
        Verify all packages in requirements.txt can be imported.

        Note: Some packages have different import names than their pip package names.
        """
        failed = []

        for import_name, package_name in DECLARED_IMPORTS.items():
            try:
                importlib.import_module(import_name)
            except ImportError as e:
                failed.append(f"{package_name} (import: {import_name}): {e}")

        assert not failed, (
            f"Failed to import declared dependencies:\n" + "\n".join(failed)
        )

    def test_requirements_file_exists_and_pinned(self):
        """Verify requirements.txt exists and uses pinned versions."""
        req_file = ROOT / "requirements.txt"
        assert req_file.exists(), "requirements.txt not found"

        content = req_file.read_text()
        lines = [line.strip() for line in content.split("\n") if line.strip()]

        # Check all non-comment lines use pinned versions with ==
        unpinned = []
        for line in lines:
            if line.startswith("#"):
                continue
            if "==" not in line:
                unpinned.append(line)

        assert not unpinned, (
            f"Found unpinned dependencies. All should use ==X.Y.Z format:\n"
            + "\n".join(unpinned)
        )

    def test_dev_requirements_extends_base(self):
        """Verify requirements-dev.txt includes base requirements."""
        dev_req_file = ROOT / "requirements-dev.txt"
        content = dev_req_file.read_text()

        assert "-r requirements.txt" in content, (
            "requirements-dev.txt should start with '-r requirements.txt' "
            "to extend base requirements"
        )
