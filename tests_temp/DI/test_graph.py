"""
Test DependencyGraph:
  detect_cycles():
    - graph không có cycle → []
    - cycle đơn giản A→B→A
    - self-dependency A→A
    - graph lớn (>1000 nodes) không gặp RecursionError — iterative DFS
    - cycle ở cuối chain dài được phát hiện đúng

  topological_order():
    - dependencies luôn đứng trước dependents
    - graph lớn (>1000 nodes) trả về đúng thứ tự
    - graph không có cycle → tất cả nodes đều có mặt
"""
import pytest

from core.container.graph import DependencyGraph
from core.container.resolver import ResolvedMap


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_resolved(adj: dict[type, list[type]]) -> ResolvedMap:
    """Build ResolvedMap từ adjacency dict {cls: [dep, ...]}."""
    return {
        cls: {f"dep_{i}": dep for i, dep in enumerate(deps)}
        for cls, deps in adj.items()
    }


def make_chain(n: int) -> tuple[list[type], ResolvedMap]:
    """
    Tạo chain tuyến tính n nodes: Node0 → Node1 → ... → Node(n-1).
    Node(n-1) là lá (không có dependency).
    Trả về (nodes, resolved).
    """
    nodes = [type(f"Node{i}", (), {}) for i in range(n)]
    adj = {nodes[i]: [nodes[i + 1]] for i in range(n - 1)}
    adj[nodes[-1]] = []
    return nodes, make_resolved(adj)


# ---------------------------------------------------------------------------
# detect_cycles — correctness
# ---------------------------------------------------------------------------

def test_detect_cycles_acyclic_returns_empty():
    class A: pass
    class B: pass
    class C: pass

    _, resolved = make_chain.__wrapped__ if hasattr(make_chain, "__wrapped__") else (None, None)
    resolved = make_resolved({A: [B], B: [C], C: []})
    assert DependencyGraph(resolved).detect_cycles() == []


def test_detect_cycles_simple_two_node_cycle():
    class A: pass
    class B: pass

    resolved = make_resolved({A: [B], B: [A]})
    cycles = DependencyGraph(resolved).detect_cycles()
    assert len(cycles) == 1
    # Cycle bắt đầu và kết thúc tại cùng node
    assert cycles[0][0] == cycles[0][-1]


def test_detect_cycles_self_dependency():
    class Loopy: pass

    resolved = make_resolved({Loopy: [Loopy]})
    cycles = DependencyGraph(resolved).detect_cycles()
    assert len(cycles) == 1


def test_detect_cycles_three_node_cycle():
    class X: pass
    class Y: pass
    class Z: pass

    resolved = make_resolved({X: [Y], Y: [Z], Z: [X]})
    cycles = DependencyGraph(resolved).detect_cycles()
    assert len(cycles) == 1
    names = {cls.__name__ for cls in cycles[0]}
    assert {"X", "Y", "Z"} <= names


# ---------------------------------------------------------------------------
# detect_cycles — large graph (iterative DFS, Issue #8)
# ---------------------------------------------------------------------------

def test_detect_cycles_large_acyclic_graph_no_recursion_error():
    """
    Chain 1500 nodes: vượt Python default recursion limit (1000).
    Iterative DFS phải xử lý được mà không raise RecursionError.
    """
    _, resolved = make_chain(1500)
    cycles = DependencyGraph(resolved).detect_cycles()
    assert cycles == []


def test_detect_cycles_large_graph_with_cycle_at_end():
    """
    Chain 1500 nodes với cycle đóng ở cuối (node cuối → node đầu).
    Cycle phải được phát hiện đúng dù graph rất sâu.
    """
    nodes, resolved = make_chain(1500)
    # Đóng vòng: node cuối phụ thuộc ngược về node đầu
    resolved[nodes[-1]] = {"dep_0": nodes[0]}
    cycles = DependencyGraph(resolved).detect_cycles()
    assert len(cycles) == 1
    assert len(cycles[0]) == 1501  # 1500 nodes + node đầu lặp lại


# ---------------------------------------------------------------------------
# topological_order — correctness
# ---------------------------------------------------------------------------

def test_topological_order_dependencies_before_dependents():
    """Mọi dependency phải xuất hiện trước class phụ thuộc vào nó."""
    class Repo: pass
    class Service: pass
    class Controller: pass

    # Controller → Service → Repo
    resolved = make_resolved({
        Controller: [Service],
        Service: [Repo],
        Repo: [],
    })
    order = DependencyGraph(resolved).topological_order()
    positions = {cls: i for i, cls in enumerate(order)}

    assert positions[Repo] < positions[Service]
    assert positions[Service] < positions[Controller]


def test_topological_order_contains_all_nodes():
    class A: pass
    class B: pass
    class C: pass

    resolved = make_resolved({A: [B, C], B: [], C: []})
    order = DependencyGraph(resolved).topological_order()
    assert set(order) == {A, B, C}


def test_topological_order_large_graph_correct_ordering():
    """
    Chain 1500 nodes: topological_order() trả về đúng thứ tự
    và không bị ảnh hưởng bởi recursion limit.
    """
    nodes, resolved = make_chain(1500)
    order = DependencyGraph(resolved).topological_order()

    assert len(order) == 1500
    positions = {cls: i for i, cls in enumerate(order)}

    # Với chain Node0→Node1→...→Node1499,
    # Node1499 (lá) phải đứng đầu, Node0 phải đứng cuối
    for i in range(len(nodes) - 1):
        assert positions[nodes[i + 1]] < positions[nodes[i]], (
            f"Node{i+1} phải đứng trước Node{i} trong topological order"
        )
