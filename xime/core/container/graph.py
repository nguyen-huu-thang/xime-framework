from __future__ import annotations

from collections import deque

from xime.core.container.resolver import ResolvedMap
from xime.core.exception.framework import InvalidOrderRuleException, OrderRuleCycleException

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
        # Insertion order is kept alongside the membership set and used for every
        # iteration below. `set` iteration order for types depends on their id(),
        # which differs from process to process, so seeding Kahn's algorithm from
        # the set made the construction order of MUTUALLY INDEPENDENT singletons
        # vary between runs - and with it the order their post_construct() hooks
        # fired. Every order was valid, but a bug that depends on one of them
        # would reproduce only sometimes. Iterating the declared order instead
        # costs one list and makes startup repeatable.
        # Thứ tự chèn được giữ song song với set và dùng cho MỌI vòng duyệt dưới
        # đây. Thứ tự duyệt `set` của type phụ thuộc id() nên đổi theo từng
        # process -> thứ tự dựng các singleton ĐỘC LẬP với nhau (và thứ tự chạy
        # post_construct của chúng) đổi theo từng lần chạy. Order nào cũng hợp lệ,
        # nhưng bug phụ thuộc vào một order cụ thể sẽ chỉ tái hiện thỉnh thoảng.
        self._order: list[type] = list(resolved.keys())
        self._nodes: set[type] = set(self._order)

        # Build adjacency: cls → {dep1, dep2, ...} (only known deps)
        self._edges: AdjacencyMap = {
            cls: {dep for dep in deps.values() if dep in self._nodes}
            for cls, deps in resolved.items()
        }

        # Reverse map used by topological sort: dep → [classes that need it].
        # Built by walking self._order so each dependent list is in declared
        # order regardless of how the edge sets happen to iterate.
        self._dependents: dict[type, list[type]] = {n: [] for n in self._order}
        for cls in self._order:
            for dep in self._edges[cls]:
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

        for start in self._order:
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
                    # All neighbors processed - finish this node
                    call_stack.pop()
                    path.pop()
                    color[node] = BLACK

        return cycles

    def topological_order(self) -> list[type]:
        """
        Return nodes ordered so every dependency appears before the class
        that needs it (Kahn's algorithm).

        If there are cycles, the cyclic nodes are omitted from the result -
        call detect_cycles() first and fail before reaching this method.
        """
        dep_count = {n: len(self._edges[n]) for n in self._order}
        queue: deque[type] = deque(n for n in self._order if dep_count[n] == 0)
        result: list[type] = []

        while queue:
            node = queue.popleft()
            result.append(node)
            for dependent in self._dependents[node]:
                dep_count[dependent] -= 1
                if dep_count[dependent] == 0:
                    queue.append(dependent)

        return result

    def topological_order_with_rules(
        self,
        rules: list[list[type]],
    ) -> list[type]:
        """
        Return topological order respecting both constructor dependencies and
        explicit post_construct() ordering rules from dependency.order().

        Rule semantics: [A, B, C] means A.post_construct() completes before
        B starts, B completes before C starts.

        In graph terms, rule (A before B) adds edge B→A, meaning B "depends
        on" A for ordering purposes - the same convention as constructor deps.

        Raises InvalidOrderRuleException if any class in the rules is not
        registered in the DI container.

        Raises OrderRuleCycleException if the combined constraints (constructor
        deps + order rules) form a cycle.
        """
        # Validate: every class in rules must be a known node
        unknown = [
            cls
            for rule in rules
            for cls in rule
            if cls not in self._nodes
        ]
        if unknown:
            names = ", ".join(f"'{c.__name__}'" for c in dict.fromkeys(unknown))
            raise InvalidOrderRuleException(names)

        # Build extra edges from rules.
        # Rule [A, B, C] yields pairs (A, B) and (B, C) meaning "A before B", "B before C".
        # To enforce "A before B" in topological order, B must "depend on" A,
        # so we add A to B's dependency set.
        combined: AdjacencyMap = {n: set(self._edges[n]) for n in self._order}
        for rule in rules:
            for i in range(len(rule) - 1):
                before, after = rule[i], rule[i + 1]
                combined[after].add(before)

        # Rebuild reverse map (dep → dependents) for the combined graph
        dependents: dict[type, list[type]] = {n: [] for n in self._order}
        for cls in self._order:
            for dep in combined[cls]:
                dependents[dep].append(cls)

        # Kahn's algorithm on combined graph
        dep_count = {n: len(combined[n]) for n in self._order}
        queue: deque[type] = deque(n for n in self._order if dep_count[n] == 0)
        result: list[type] = []

        while queue:
            node = queue.popleft()
            result.append(node)
            for dependent in dependents[node]:
                dep_count[dependent] -= 1
                if dep_count[dependent] == 0:
                    queue.append(dependent)

        if len(result) == len(self._nodes):
            return result

        # Not all nodes were processed → cycle in combined graph
        in_cycle = self._nodes - set(result)
        cycle = self._find_cycle(combined, in_cycle)
        raise OrderRuleCycleException(cycle)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _find_cycle(edges: AdjacencyMap, nodes: set[type]) -> list[str]:
        """Find and return one cycle among the given nodes using iterative DFS.

        Returns a list of class names forming the cycle, e.g.:
            ["A", "B", "C", "A"]
        Returns an empty list if no cycle is found (should not happen when
        called after Kahn's detects an incomplete result).
        """
        WHITE, GRAY, BLACK = 0, 1, 2
        color: dict[type, int] = {n: WHITE for n in nodes}
        path: list[type] = []

        for start in nodes:
            if color[start] != WHITE:
                continue

            color[start] = GRAY
            path.append(start)
            call_stack: list[tuple[type, object]] = [
                (start, iter(edges.get(start, set()) & nodes))
            ]

            while call_stack:
                node, neighbors = call_stack[-1]
                try:
                    neighbor = next(neighbors)  # type: ignore[call-overload]
                    if color[neighbor] == GRAY:
                        idx = path.index(neighbor)
                        return [c.__name__ for c in path[idx:]] + [neighbor.__name__]
                    if color[neighbor] == WHITE:
                        color[neighbor] = GRAY
                        path.append(neighbor)
                        call_stack.append(
                            (neighbor, iter(edges.get(neighbor, set()) & nodes))
                        )
                except StopIteration:
                    call_stack.pop()
                    path.pop()
                    color[node] = BLACK

        return []
