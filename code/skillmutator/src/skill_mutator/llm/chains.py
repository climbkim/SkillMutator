"""LangChain / LangGraph chain and graph builders."""

from typing import Any, Callable
from .base import BaseLLM


def build_chain(llm: BaseLLM, prompt_template: str, output_parser=None) -> Any:
    """Build a LangChain LCEL chain.

    Args:
        llm: a BaseLLM instance.
        prompt_template: a prompt template using {variable} placeholders.
        output_parser: output parser (defaults to StrOutputParser).

    Returns:
        A runnable LangChain chain.

    Example:
        >>> chain = build_chain(llm, "Explain the following code:\\n{code}")
        >>> result = chain.invoke({"code": "def foo(): pass"})
    """
    try:
        from langchain_core.prompts import ChatPromptTemplate
        from langchain_core.output_parsers import StrOutputParser
    except ImportError:
        raise ImportError("the 'langchain-core' package is required: pip install langchain-core")

    lc_llm = llm.get_langchain_llm()
    prompt = ChatPromptTemplate.from_template(prompt_template)
    parser = output_parser or StrOutputParser()

    return prompt | lc_llm | parser


def build_sequential_chain(llm: BaseLLM, steps: list[dict]) -> Any:
    """Build a chain that runs several steps sequentially.

    Args:
        llm: a BaseLLM instance.
        steps: per-step config list, e.g.
               [{"name": "step1", "prompt": "...", "input_key": "input", "output_key": "result"}, ...]

    Returns:
        A sequentially-runnable chain.

    Example:
        >>> steps = [
        ...     {"name": "summarize", "prompt": "Summarize: {text}", "output_key": "summary"},
        ...     {"name": "translate", "prompt": "Translate to English: {summary}", "output_key": "translated"},
        ... ]
        >>> chain = build_sequential_chain(llm, steps)
        >>> result = chain.invoke({"text": "a long passage..."})
    """
    try:
        from langchain_core.prompts import ChatPromptTemplate
        from langchain_core.output_parsers import StrOutputParser
        from langchain_core.runnables import RunnablePassthrough
    except ImportError:
        raise ImportError("the 'langchain-core' package is required: pip install langchain-core")

    lc_llm = llm.get_langchain_llm()
    parser = StrOutputParser()

    chain = RunnablePassthrough()
    for step in steps:
        prompt = ChatPromptTemplate.from_template(step["prompt"])
        output_key = step.get("output_key", "output")
        step_chain = prompt | lc_llm | parser
        chain = chain | RunnablePassthrough.assign(**{output_key: step_chain})

    return chain


def build_graph(
    llm: BaseLLM,
    nodes: dict[str, Callable],
    edges: list[tuple[str, str]],
    entry_point: str,
    state_schema: type | None = None,
) -> Any:
    """Build a LangGraph state graph.

    Args:
        llm: a BaseLLM instance (used inside each node function).
        nodes: {"node_name": node_function} dict.
               Node function signature: (state: dict) -> dict
        edges: [("from_node", "to_node"), ...]. Use ("node", "END") to mark the end.
        entry_point: name of the start node.
        state_schema: a TypedDict-based state schema (defaults to plain dict).

    Returns:
        A compiled LangGraph.

    Example:
        >>> from typing import TypedDict
        >>> class State(TypedDict):
        ...     input: str
        ...     result: str
        ...
        >>> def analyze(state):
        ...     result = llm.call(f"Analyze: {state['input']}")
        ...     return {"result": result}
        ...
        >>> graph = build_graph(
        ...     llm,
        ...     nodes={"analyze": analyze},
        ...     edges=[("analyze", "END")],
        ...     entry_point="analyze",
        ...     state_schema=State,
        ... )
        >>> output = graph.invoke({"input": "some text"})
    """
    try:
        from langgraph.graph import StateGraph, END
    except ImportError:
        raise ImportError("the 'langgraph' package is required: pip install langgraph")

    schema = state_schema or dict
    builder = StateGraph(schema)

    for name, func in nodes.items():
        builder.add_node(name, func)

    builder.set_entry_point(entry_point)

    for src, dst in edges:
        dst_node = END if dst == "END" else dst
        builder.add_edge(src, dst_node)

    return builder.compile()


def build_conditional_graph(
    llm: BaseLLM,
    nodes: dict[str, Callable],
    conditional_edges: dict[str, Callable],
    normal_edges: list[tuple[str, str]],
    entry_point: str,
    state_schema: type | None = None,
) -> Any:
    """Build a LangGraph graph with conditional branching.

    Args:
        llm: a BaseLLM instance.
        nodes: {"node_name": node_function} dict.
        conditional_edges: {"node_name": router_function} — the router returns
            the name of the next node.
        normal_edges: plain edge list [("from", "to"), ...].
        entry_point: name of the start node.
        state_schema: the state schema.

    Returns:
        A compiled conditional LangGraph.
    """
    try:
        from langgraph.graph import StateGraph, END
    except ImportError:
        raise ImportError("the 'langgraph' package is required: pip install langgraph")

    schema = state_schema or dict
    builder = StateGraph(schema)

    for name, func in nodes.items():
        builder.add_node(name, func)

    builder.set_entry_point(entry_point)

    for node_name, router_func in conditional_edges.items():
        all_targets = list(nodes.keys()) + ["END"]
        builder.add_conditional_edges(node_name, router_func, {t: t if t != "END" else END for t in all_targets})

    for src, dst in normal_edges:
        dst_node = END if dst == "END" else dst
        builder.add_edge(src, dst_node)

    return builder.compile()
