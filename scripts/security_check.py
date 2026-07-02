#!/usr/bin/env python3
import ast
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXCLUDED_PARTS = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    "docs_cache",
}
FORBIDDEN_FILES = {
    ".env",
    "secrets.toml",
}
ALLOWED_LOCAL_SECRET_FILES = {
    ROOT / ".env",
    ROOT / ".streamlit" / "secrets.toml",
}
SENSITIVE_NAME = re.compile(
    r"(api_?key|secret|token|password|credential)",
    re.IGNORECASE,
)
PLACEHOLDER_WORDS = {
    "",
    "none",
    "replace_me",
    "replace_with_your_rotated_key",
    "replace_with_a_long_random_password",
    "replace_with_a_different_random_value",
}


def included(path: Path) -> bool:
    return not EXCLUDED_PARTS.intersection(path.relative_to(ROOT).parts)


def check_forbidden_files():
    findings = []
    for path in ROOT.rglob("*"):
        if (
            path.is_file()
            and included(path)
            and path.name in FORBIDDEN_FILES
            and path not in ALLOWED_LOCAL_SECRET_FILES
        ):
            findings.append(f"{path.relative_to(ROOT)}: local secret file")
    return findings


def check_python_literals():
    findings = []
    for path in ROOT.rglob("*.py"):
        if not included(path):
            continue

        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError) as error:
            findings.append(f"{path.relative_to(ROOT)}: cannot scan ({error})")
            continue

        for node in ast.walk(tree):
            if not isinstance(node, (ast.Assign, ast.AnnAssign)):
                continue

            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            value = node.value
            if not isinstance(value, ast.Constant) or not isinstance(value.value, str):
                continue

            for target in targets:
                if not isinstance(target, ast.Name):
                    continue
                if not SENSITIVE_NAME.search(target.id):
                    continue
                if value.value.lower() not in PLACEHOLDER_WORDS:
                    findings.append(
                        f"{path.relative_to(ROOT)}:{node.lineno}: "
                        f"hardcoded sensitive variable {target.id}"
                    )
    return findings


def main():
    findings = check_forbidden_files() + check_python_literals()
    if findings:
        print("Security check failed:")
        for finding in findings:
            print(f"- {finding}")
        return 1

    print("Security check passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
