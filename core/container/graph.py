from __future__ import annotations

from core.container.resolver import ResolvedMap

# {cls: set of classes it directly depends on}
AdjacencyMap = dict[type, set[type]]


class DependencyGraph:
    """
    Directed graph where an edge A → B means "A depends on B".
    B must be instantiated before A.

    Responsibilities:
      - detect_cycles()      → find circular dependencies
      - topological_order()  → instantiation order (dependencies first)

    Only nodes that appear in the resolved map are treated as "known".
    Dependencies pointing outside the known set are left for the validator.
    """

    def __init__(self, resolved: ResolvedMap):
        self._nodes: set[type] = set(resolved.keys())

        # Build adjacency: cls → {dep1, dep2, ...} (only known deps)
        self._edges: AdjacencyMap = {
            cls: {dep for dep in deps.values() if dep in self._nodes}
            for cls, deps in resolved.items()
        }

        # Reverse map used by topological sort: dep → [classes that need it]
        self._dependents: dict[type, list[type]] = {n: [] for n in self._nodes}
        for cls, deps in self._edges.items():
            for dep in deps:
                self._dependents[dep].append(cls)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def nodes(self) -> set[type]:
        return self._nodes

    @property
    def edges(self) -> AdjacencyMap:
        return self._edges

    def detect_cycles(self) -> list[list[type]]:
        """
        Return all cycles found in the graph.
        Each cycle is a list of types forming the loop, e.g.:
          [UserService, AuthService, TokenService, UserService]
        Returns an empty list when the graph is acyclic.
        """
        WHITE, GRAY, BLACK = 0, 1, 2
        color: dict[type, int] = {n: WHITE for n in self._nodes}
        stack: list[type] = []
        cycles: list[list[type]] = []

        def dfs(node: type) -> None:
            color[node] = GRAY
            stack.append(node)

            for neighbor in self._edges.get(node, set()):
                if color[neighbor] == GRAY:
                    # Back-edge found → extract the cycle from the current stack
                    cycle_start = stack.index(neighbor)
                    cycles.append(stack[cycle_start:] + [neighbor])
                elif color[neighbor] == WHITE:
                    dfs(neighbor)

            stack.pop()
            color[node] = BLACK

        for node in self._nodes:
            if color[node] == WHITE:
                dfs(node)

        return cycles

    def topological_order(self) -> list[type]:
        """
        Return nodes ordered so every dependency appears before the class
        that needs it (Kahn's algorithm).

        If there are cycles, the cyclic nodes are omitted from the result —
        call detect_cycles() first and fail before reaching this method.
        """
        dep_count = {n: len(self._edges[n]) for n in self._nodes}
        queue = [n for n in self._nodes if dep_count[n] == 0]
        result: list[type] = []

        while queue:
            node = queue.pop(0)
            result.append(node)
            for dependent in self._dependents[node]:
                dep_count[dependent] -= 1
                if dep_count[dependent] == 0:
                    queue.append(dependent)

        return result
