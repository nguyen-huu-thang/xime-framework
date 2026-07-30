"""Node model declaration and validation (0.7)."""
import pytest

from xime.adapters.opcua._model import (
    Node,
    OpcuaNode,
    get_node_model_info,
    node_model,
    require_node_model_info,
)


@node_model
class Tank:
    level: float = Node("ns=2;s=Tank.Level")
    setpoint: float = Node("ns=2;s=Tank.Setpoint")
    alarm: bool = Node("ns=2;s=Tank.Alarm", writable=False)


class TestDeclaration:
    def test_nodes_are_collected(self):
        info = require_node_model_info(Tank)
        assert set(info.nodes) == {"level", "setpoint", "alarm"}
        assert info.node_ids() == [
            "ns=2;s=Tank.Level", "ns=2;s=Tank.Setpoint", "ns=2;s=Tank.Alarm",
        ]

    def test_writable_flag_is_kept(self):
        assert Tank.level.writable is True
        assert Tank.alarm.writable is False

    def test_namespace_form_of_the_decorator(self):
        @node_model(namespace="http://plant.example/tanks")
        class Custom:
            value: float = Node("ns=3;s=X")

        assert require_node_model_info(Custom).namespace == "http://plant.example/tanks"

    def test_bare_decorator_has_no_namespace(self):
        assert require_node_model_info(Tank).namespace is None

    def test_empty_model_is_refused(self):
        with pytest.raises(ValueError, match="declares no nodes"):

            @node_model
            class Empty:
                pass

    def test_duplicate_node_id_is_refused(self):
        # Two attributes on one NodeId always agree, which hides the typo.
        with pytest.raises(ValueError, match="Duplicate NodeId"):

            @node_model
            class Twice:
                a: float = Node("ns=2;s=Same")
                b: float = Node("ns=2;s=Same")

    def test_inherited_nodes_are_collected(self):
        @node_model
        class Base:
            common: float = Node("ns=2;s=Common")

        @node_model
        class Derived(Base):
            extra: float = Node("ns=2;s=Extra")

        assert set(require_node_model_info(Derived).nodes) == {"common", "extra"}


class TestNodeIdValidation:
    def test_empty_node_id_is_refused(self):
        with pytest.raises(ValueError, match="needs a NodeId"):
            Node("")

    def test_malformed_node_id_is_refused(self):
        # Catching this at declaration beats a BadNodeId at 3 a.m.
        with pytest.raises(ValueError, match="does not look like a NodeId"):
            Node("Tank.Level")

    def test_accepted_forms(self):
        for form in ("ns=2;s=Tank.Level", "ns=2;i=17", "i=85", "ns=1;g=abc", "ns=1;b=Zm8="):
            assert Node(form).node_id == form


class TestDescriptorProtocol:
    def test_class_access_returns_the_node(self):
        assert isinstance(Tank.level, OpcuaNode)
        assert Tank.level.name == "level"

    def test_instance_access_returns_the_value(self):
        tank = Tank(level=22.5)
        assert tank.level == 22.5
        assert tank.setpoint is None

    def test_instances_do_not_share_values(self):
        a, b = Tank(level=1.0), Tank(level=2.0)
        assert (a.level, b.level) == (1.0, 2.0)

    def test_generated_init_rejects_unknown_nodes(self):
        with pytest.raises(TypeError, match="unexpected node"):
            Tank(levl=1.0)

    def test_generated_repr_lists_nodes(self):
        assert "level=22.5" in repr(Tank(level=22.5))


class TestModelLookup:
    def test_get_works_on_instances(self):
        assert get_node_model_info(Tank()) is get_node_model_info(Tank)

    def test_plain_class_has_no_info(self):
        class NotAModel:
            pass

        assert get_node_model_info(NotAModel) is None
        with pytest.raises(TypeError, match="not an OPC UA node model"):
            require_node_model_info(NotAModel)
