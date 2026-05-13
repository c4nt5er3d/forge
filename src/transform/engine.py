import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import yaml

from src.schema.document import Document


class TemplateEngine:
    def __init__(self, template_dirs: Optional[List[Path]] = None):
        builtin_dir = Path(__file__).parent / "templates"
        user_dir = Path.home() / ".forge" / "templates"
        self.template_dirs = template_dirs or [builtin_dir, user_dir]

    def list_templates(self) -> List[str]:
        names = []
        for directory in self.template_dirs:
            if not directory.exists():
                continue
            names.extend(path.stem for path in directory.glob("*.yaml"))
        return sorted(set(names))

    def load_template(self, name: str) -> Dict[str, Any]:
        for directory in self.template_dirs:
            path = directory / f"{name}.yaml"
            if path.exists():
                return yaml.safe_load(path.read_text(encoding="utf-8"))
        raise FileNotFoundError(f"Template not found: {name}")

    def render_prompt(self, template: Dict[str, Any], document: Document) -> str:
        prompt = template.get("prompt", "")
        replacements = {
            "content": document.content,
            "filename": document.filename,
            "source_path": document.source_path,
        }
        for key, value in replacements.items():
            prompt = prompt.replace(f"{{{key}}}", str(value))
        for key, value in document.metadata.items():
            prompt = prompt.replace(f"{{metadata.{key}}}", json.dumps(value) if isinstance(value, list) else str(value))
        return prompt

    def transform(
        self,
        documents: Iterable[Document],
        template_name: str,
        use_ollama: bool = False,
        model: str = "llama3.2",
    ) -> List[Dict[str, Any]]:
        template = self.load_template(template_name)
        results = []
        for document in documents:
            prompt = self.render_prompt(template, document)
            output = self._run_local_llm(prompt, model) if use_ollama else prompt
            results.append({
                "template": template.get("name", template_name),
                "filename": document.filename,
                "source_path": document.source_path,
                "output_format": template.get("output_format", "text"),
                "output": self._post_process(output, template.get("post_process")),
            })
        return results

    def _run_local_llm(self, prompt: str, model: str) -> str:
        try:
            import ollama
        except ImportError as exc:
            raise RuntimeError("ollama is required for --local template transforms") from exc

        response = ollama.chat(model=model, messages=[{"role": "user", "content": prompt}])
        return response.get("message", {}).get("content", "").strip()

    def _post_process(self, output: str, post_process: Optional[str]):
        if post_process == "json_parse":
            try:
                return json.loads(output)
            except json.JSONDecodeError:
                return output
        return output
