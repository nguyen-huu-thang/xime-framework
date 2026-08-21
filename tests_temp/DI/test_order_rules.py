"""
Test DependencyGraph.topological_order_with_rules():

  Trường hợp bình thường:
  - Không có rules → kết quả giống topological_order()
  - [A, B] - hai class độc lập, A phải đứng trước B
  - [A, B, C] - chuỗi 3 class, giữ đúng thứ tự
  - Nhiều rule lists không xung đột nhau
  - Rule nhất quán với constructor dep (A trước B, B phụ thuộc C, rule [A, B]) → ok

  Fail fast - InvalidOrderRuleException:
  - Class trong rule không có trong DI container

  Fail fast - OrderRuleCycleException:
  - Cycle trong cùng một rule list [A, B, A]
  - Cycle chéo giữa 2 rule lists [A, B] và [B, A]
  - Rule mâu thuẫn với constructor dep (B constructor-dep A, rule khai báo [B, A] → cycle)
"""
import pytest

from xime.core.container.graph import DependencyGraph
from xime.core.container.resolver import ResolvedMap
from xime.core.exception import InvalidOrderRuleException, OrderRuleCycleException


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_resolved(adj: dict[type, list[type]]) -> ResolvedMap:
    """Build ResolvedMap từ adjacency dict {cls: [dep, ...]}."""
    return {
        cls: {f"dep_{i}": dep for i, dep in enumerate(deps)}
        for cls, deps in adj.items()
    }


def positions_of(order: list[type]) -> dict[type, int]:
    return {cls: i for i, cls in enumerate(order)}


# ---------------------------------------------------------------------------
# Không có rules → giống topological_order()
# ---------------------------------------------------------------------------

def test_no_rules_returns_same_as_topological_order():
    class A: pass
    class B: pass
    class C: pass

    resolved = make_resolved({A: [B], B: [C], C: []})
    graph = DependencyGraph(resolved)

    assert graph.topological_order_with_rules([]) == graph.topological_order()


# ---------------------------------------------------------------------------
# Hai class độc lập - rule quyết định thứ tự
# ---------------------------------------------------------------------------

def test_rule_orders_two_independent_classes():
    """A và B không phụ thuộc nhau trong constructor - rule [A, B] đặt A trước B."""
    class Loader: pass
    class Provider: pass
    class Root: pass

    # Root phụ thuộc cả Loader và Provider, nhưng Loader và Provider độc lập nhau
    resolved = make_resolved({Root: [Loader, Provider], Loader: [], Provider: []})
    graph = DependencyGraph(resolved)

    order = graph.topological_order_with_rules([[Loader, Provider]])
    pos = positions_of(order)

    assert pos[Loader] < pos[Provider]


def test_rule_reversed_order_of_two_independent_classes():
    """Rule [B, A] → B trước A, dù topological sort thường không đảm bảo thứ tự."""
    class ServiceA: pass
    class ServiceB: pass

    resolved = make_resolved({ServiceA: [], ServiceB: []})
    graph = DependencyGraph(resolved)

    order = graph.topological_order_with_rules([[ServiceB, ServiceA]])
    pos = positions_of(order)

    assert pos[ServiceB] < pos[ServiceA]


# ---------------------------------------------------------------------------
# Chuỗi 3 class
# ---------------------------------------------------------------------------

def test_rule_chain_three_classes():
    """[A, B, C] → A trước B, B trước C."""
    class A: pass
    class B: pass
    class C: pass

    resolved = make_resolved({A: [], B: [], C: []})
    graph = DependencyGraph(resolved)

    order = graph.topological_order_with_rules([[A, B, C]])
    pos = positions_of(order)

    assert pos[A] < pos[B]
    assert pos[B] < pos[C]


# ---------------------------------------------------------------------------
# Nhiều rule lists
# ---------------------------------------------------------------------------

def test_multiple_rule_lists_all_respected():
    """[[A, B], [C, D]] - A trước B VÀ C trước D."""
    class A: pass
    class B: pass
    class C: pass
    class D: pass

    resolved = make_resolved({A: [], B: [], C: [], D: []})
    graph = DependencyGraph(resolved)

    order = graph.topological_order_with_rules([[A, B], [C, D]])
    pos = positions_of(order)

    assert pos[A] < pos[B]
    assert pos[C] < pos[D]


def test_rules_consistent_with_constructor_deps():
    """Rule [A, B] khi A và B đều phụ thuộc C - rule này không tạo cycle."""
    class C: pass
    class A: pass
    class B: pass

    resolved = make_resolved({A: [C], B: [C], C: []})
    graph = DependencyGraph(resolved)

    # A và B đều phụ thuộc C, không phụ thuộc nhau → rule [A, B] hợp lệ
    order = graph.topological_order_with_rules([[A, B]])
    pos = positions_of(order)

    assert pos[C] < pos[A]   # constructor dep: C trước A
    assert pos[C] < pos[B]   # constructor dep: C trước B
    assert pos[A] < pos[B]   # rule: A trước B


def test_rule_same_direction_as_constructor_dep_is_valid():
    """B constructor-dep trên A (A trước B). Rule [A, B] là nhất quán → không lỗi."""
    class A: pass
    class B: pass

    resolved = make_resolved({B: [A], A: []})
    graph = DependencyGraph(resolved)

    # Rule [A, B] trùng hướng với constructor dep - không tạo cycle
    order = graph.topological_order_with_rules([[A, B]])
    pos = positions_of(order)
    assert pos[A] < pos[B]


def test_all_nodes_present_in_result():
    """Kết quả phải chứa đủ tất cả nodes dù có rules hay không."""
    class A: pass
    class B: pass
    class C: pass
    class D: pass

    resolved = make_resolved({A: [B], B: [], C: [], D: [C]})
    graph = DependencyGraph(resolved)

    order = graph.topological_order_with_rules([[C, A]])
    assert set(order) == {A, B, C, D}


# ---------------------------------------------------------------------------
# Fail fast - InvalidOrderRuleException
# ---------------------------------------------------------------------------

def test_unknown_class_in_rule_raises():
    class A: pass
    class B: pass
    class NotInContainer: pass

    resolved = make_resolved({A: [], B: []})
    graph = DependencyGraph(resolved)

    with pytest.raises(InvalidOrderRuleException) as exc_info:
        graph.topological_order_with_rules([[A, NotInContainer]])

    assert "NotInContainer" in str(exc_info.value)


def test_multiple_unknown_classes_all_reported():
    class A: pass
    class Ghost1: pass
    class Ghost2: pass

    resolved = make_resolved({A: []})
    graph = DependencyGraph(resolved)

    with pytest.raises(InvalidOrderRuleException) as exc_info:
        graph.topological_order_with_rules([[A, Ghost1], [Ghost2, A]])

    error_msg = str(exc_info.value)
    assert "Ghost1" in error_msg
    assert "Ghost2" in error_msg


# ---------------------------------------------------------------------------
# Fail fast - OrderRuleCycleException
# ---------------------------------------------------------------------------

def test_direct_cycle_in_rules_raises():
    """[A, B] và [B, A] → cycle A ↔ B."""
    class A: pass
    class B: pass

    resolved = make_resolved({A: [], B: []})
    graph = DependencyGraph(resolved)

    with pytest.raises(OrderRuleCycleException) as exc_info:
        graph.topological_order_with_rules([[A, B], [B, A]])

    cycle_str = str(exc_info.value)
    assert "A" in cycle_str
    assert "B" in cycle_str


def test_three_node_cycle_in_rules_raises():
    """[A, B], [B, C], [C, A] → cycle A → B → C → A."""
    class A: pass
    class B: pass
    class C: pass

    resolved = make_resolved({A: [], B: [], C: []})
    graph = DependencyGraph(resolved)

    with pytest.raises(OrderRuleCycleException):
        graph.topological_order_with_rules([[A, B], [B, C], [C, A]])


def test_rule_contradicts_constructor_dep_raises():
    """B constructor-dep trên A (A trước B). Rule [B, A] mâu thuẫn → cycle."""
    class A: pass
    class B: pass

    # B phụ thuộc A trong constructor → A phải trước B
    resolved = make_resolved({B: [A], A: []})
    graph = DependencyGraph(resolved)

    # Rule [B, A] nói B trước A - ngược với constructor dep → cycle
    with pytest.raises(OrderRuleCycleException) as exc_info:
        graph.topological_order_with_rules([[B, A]])

    cycle_str = str(exc_info.value)
    assert "A" in cycle_str
    assert "B" in cycle_str


def test_cycle_error_message_contains_class_names():
    """Thông báo lỗi phải đọc được - chứa tên class."""
    class TrustLoader: pass
    class CredentialsProvider: pass

    resolved = make_resolved({TrustLoader: [], CredentialsProvider: []})
    graph = DependencyGraph(resolved)

    with pytest.raises(OrderRuleCycleException) as exc_info:
        graph.topological_order_with_rules([
            [TrustLoader, CredentialsProvider],
            [CredentialsProvider, TrustLoader],
        ])

    msg = str(exc_info.value)
    assert "TrustLoader" in msg
    assert "CredentialsProvider" in msg
    assert "→" in msg
