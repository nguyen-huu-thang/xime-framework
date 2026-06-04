from __future__ import annotations

from collections import deque

from xime.core.container.resolver import ResolvedMap

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

        Uses iterative DFS with an explicit call stack to avoid hitting
        Python's recursion limit on large dependency graphs.
        Each stack frame is (node, iterator_over_neighbors): when the
        iterator is exhausted the node is finished (BLACK) and popped.
        """
        WHITE, GRAY, BLACK = 0, 1, 2
        color: dict[type, int] = {n: WHITE for n in self._nodes}
        path: list[type] = []   # current DFS path, mirrors the call stack
        cycles: list[list[type]] = []

        for start in self._nodes:
            if color[start] != WHITE:
                continue

            color[start] = GRAY
            path.append(start)
            call_stack: list[tuple[type, object]] = [
                (start, iter(self._edges.get(start, set())))
            ]

            while call_stack:
                node, neighbors = call_stack[-1]
                try:
                    neighbor = next(neighbors)  # type: ignore[call-overload]
                    if color[neighbor] == GRAY:
                        # Back-edge → extract cycle from current path
                        cycle_start = path.index(neighbor)
                        cycles.append(path[cycle_start:] + [neighbor])
                    elif color[neighbor] == WHITE:
                        color[neighbor] = GRAY
                        path.append(neighbor)
                        call_stack.append(
                            (neighbor, iter(self._edges.get(neighbor, set())))
                        )
                except StopIteration:
                    # All neighbors processed — finish this node
                    call_stack.pop()
                    path.pop()
                    color[node] = BLACK

        return cycles

    def topological_order(self) -> list[type]:
        """
        Return nodes ordered so every dependency appears before the class
        that needs it (Kahn's algorithm).

        If there are cycles, the cyclic nodes are omitted from the result —
        call detect_cycles() first and fail before reaching this method.
        """
        dep_count = {n: len(self._edges[n]) for n in self._nodes}
        queue: deque[type] = deque(n for n in self._nodes if dep_count[n] == 0)
        result: list[type] = []

        while queue:
            node = queue.popleft()
            result.append(node)
            for dependent in self._dependents[node]:
                dep_count[dependent] -= 1
                if dep_count[dependent] == 0:
                    queue.append(dependent)

        return result
