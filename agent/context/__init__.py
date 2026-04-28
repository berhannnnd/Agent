from agent.context.builder import ContextBuilder
from agent.context.compaction import ConversationCompaction, ContextCompactor, HeuristicContextCompactor
from agent.context.memory import MemoryContextRetriever, MemoryRetrievalScope
from agent.context.pack import (
    CompiledContext,
    ContextFragment,
    ContextLayer,
    ContextPack,
    ContextScope,
    ContextTraceItem,
)
from agent.context.sources import build_context_pack
from agent.context.workspace import WorkspaceContext

__all__ = [
    "CompiledContext",
    "ContextCompactor",
    "ContextBuilder",
    "ContextFragment",
    "ContextLayer",
    "ContextPack",
    "ContextScope",
    "ContextTraceItem",
    "ConversationCompaction",
    "HeuristicContextCompactor",
    "MemoryContextRetriever",
    "MemoryRetrievalScope",
    "ModelRequestCompiler",
    "WorkspaceContext",
    "build_context_pack",
]


def __getattr__(name):
    if name == "ModelRequestCompiler":
        from agent.context.compiler import ModelRequestCompiler

        return ModelRequestCompiler
    raise AttributeError(name)
