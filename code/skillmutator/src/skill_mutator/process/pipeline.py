"""Pipeline that combines file reading with LLM calls."""

from pathlib import Path
from typing import Any, Callable

try:
    from ..llm import create_llm, BaseLLM
    from ..llm.chains import build_chain, build_graph
    from ..utils import read_folder, read_file, format_files_for_llm
except ImportError:
    from llm import create_llm, BaseLLM  # type: ignore[no-redef]
    from llm.chains import build_chain, build_graph  # type: ignore[no-redef]
    from utils import read_folder, read_file, format_files_for_llm  # type: ignore[no-redef]


class Pipeline:
    """Pipeline that chains folder/file reading into an LLM call.

    Example:
        >>> pipeline = Pipeline(provider="openai", model_name="gpt-4o")
        >>> result = pipeline.analyze_folder("./my_project", "Analyze this codebase")
        >>> print(result)
    """

    def __init__(self, provider: str | None = None, model_name: str = "gpt-4o", **llm_kwargs):
        self.llm: BaseLLM = create_llm(provider=provider, model_name=model_name, **llm_kwargs)

    # ------------------------------------------------------------------
    # Basic LLM calls
    # ------------------------------------------------------------------

    def call(self, prompt: str, **kwargs) -> str:
        """Simple prompt -> response."""
        return self.llm.call(prompt, **kwargs)

    def chat(self, messages: list[dict], **kwargs) -> str:
        """Messages list -> response."""
        return self.llm.chat(messages, **kwargs)

    # ------------------------------------------------------------------
    # File-based calls
    # ------------------------------------------------------------------

    def analyze_file(self, file_path: str | Path, instruction: str, **kwargs) -> str:
        """Send a single file's content to the LLM for analysis.

        Args:
            file_path: path of the file to analyze.
            instruction: instruction passed to the LLM.
            **kwargs: extra parameters for the LLM call.
        """
        file_info = read_file(file_path)
        prompt = (
            f"{instruction}\n\n"
            f"## file: {file_info['name']}\n"
            f"```{file_info['language']}\n{file_info['content']}\n```"
        )
        return self.llm.call(prompt, **kwargs)

    def analyze_folder(
        self,
        folder_path: str | Path,
        instruction: str,
        extensions: list[str] | None = None,
        recursive: bool = True,
        max_file_size_kb: int = 500,
        max_total_chars: int = 100_000,
        **kwargs,
    ) -> str:
        """Read the files in a folder and send them to the LLM for analysis.

        Args:
            folder_path: path of the folder to analyze.
            instruction: instruction passed to the LLM.
            extensions: file extensions to read.
            recursive: whether to descend into subfolders.
            max_file_size_kb: per-file size limit (KB).
            max_total_chars: max total context characters.
            **kwargs: extra parameters for the LLM call.
        """
        files = read_folder(
            folder_path,
            extensions=extensions,
            recursive=recursive,
            max_file_size_kb=max_file_size_kb,
        )
        formatted = format_files_for_llm(files, max_total_chars=max_total_chars)
        prompt = f"{instruction}\n\n{formatted}"
        return self.llm.call(prompt, **kwargs)

    # ------------------------------------------------------------------
    # Chain / graph based runs
    # ------------------------------------------------------------------

    def run_chain(self, prompt_template: str, inputs: dict, **kwargs) -> str:
        """Run a LangChain chain.

        Args:
            prompt_template: a {variable} format template.
            inputs: template-variable dict.
        """
        chain = build_chain(self.llm, prompt_template)
        return chain.invoke(inputs)

    def run_graph(
        self,
        nodes: dict[str, Callable],
        edges: list[tuple[str, str]],
        entry_point: str,
        initial_state: dict,
        state_schema: type | None = None,
    ) -> Any:
        """Run a LangGraph graph.

        Args:
            nodes: {"node_name": function} dict.
            edges: [("from", "to"), ...] edge list ("END" is allowed).
            entry_point: start node.
            initial_state: initial state.
            state_schema: TypedDict state schema.
        """
        graph = build_graph(
            self.llm,
            nodes=nodes,
            edges=edges,
            entry_point=entry_point,
            state_schema=state_schema,
        )
        return graph.invoke(initial_state)

    # ------------------------------------------------------------------
    # Batch processing
    # ------------------------------------------------------------------

    def batch_analyze_files(
        self,
        file_paths: list[str | Path],
        instruction: str,
        **kwargs,
    ) -> list[dict]:
        """Analyze several files individually.

        Returns:
            [{"file": filename, "result": LLM response}, ...]
        """
        results = []
        for path in file_paths:
            try:
                result = self.analyze_file(path, instruction, **kwargs)
                results.append({"file": str(path), "result": result, "error": None})
            except Exception as e:
                results.append({"file": str(path), "result": None, "error": str(e)})
        return results
