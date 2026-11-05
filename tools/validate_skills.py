"""Repository validation preserves the user's Chinese skill name intentionally."""

from pathlib import Path
import re

import yaml


def validate(root: Path) -> list[str]:
    errors = []
    for skill in sorted((root / "skills").iterdir()):
        if not skill.is_dir():
            continue
        text = (skill / "SKILL.md").read_text(encoding="utf-8")
        match = re.match(r"^---\r?\n(.*?)\r?\n---\r?\n", text, re.DOTALL)
        if not match:
            errors.append(f"Invalid frontmatter: {skill.name}")
            continue
        meta = yaml.safe_load(match.group(1))
        if meta.get("name") != skill.name or not re.fullmatch(r"[a-z0-9\-\u4e00-\u9fff]{1,63}", meta.get("name", "")):
            errors.append(f"Invalid name: {skill.name}")
        if not isinstance(meta.get("description"), str) or not meta["description"].strip():
            errors.append(f"Missing description: {skill.name}")
        interface = yaml.safe_load((skill / "agents" / "openai.yaml").read_text(encoding="utf-8"))["interface"]
        if not 25 <= len(interface["short_description"]) <= 64:
            errors.append(f"UI description needs 25-64 characters: {skill.name}")
        if "$" + skill.name not in interface["default_prompt"]:
            errors.append(f"Missing explicit invocation in prompt: {skill.name}")
        for link in re.findall(r"\]\((references/[^)]+)\)", text):
            if not (skill / link).is_file():
                errors.append(f"Missing reference: {skill.name}/{link}")
        if re.search(r"[A-Z]:[\\/]Users[\\/]", text):
            errors.append(f"Personal absolute path: {skill.name}")
    return errors


if __name__ == "__main__":
    problems = validate(Path(__file__).resolve().parents[1])
    for problem in problems:
        print(problem)
    if problems:
        raise SystemExit(1)
    print("Validated both language skills (including the intentional Chinese name).")
