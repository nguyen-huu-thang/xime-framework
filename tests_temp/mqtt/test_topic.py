"""MQTT topic wildcard matching and filter validation (0.5)."""
from xime.adapters.mqtt._topic import is_valid_filter, topic_matches


class TestTopicMatches:
    def test_exact(self):
        assert topic_matches("a/b/c", "a/b/c")
        assert not topic_matches("a/b/c", "a/b/d")

    def test_single_level_wildcard(self):
        assert topic_matches("sensors/+/temp", "sensors/a/temp")
        assert not topic_matches("sensors/+/temp", "sensors/a/b/temp")
        assert not topic_matches("sensors/+", "sensors/a/b")

    def test_multi_level_wildcard(self):
        assert topic_matches("sensors/#", "sensors/a")
        assert topic_matches("sensors/#", "sensors/a/b/c")
        # '#' also matches the parent level with nothing after it.
        assert topic_matches("sensors/#", "sensors")

    def test_length_mismatch(self):
        assert not topic_matches("a/b", "a/b/c")
        assert not topic_matches("a/b/c", "a/b")

    def test_leading_wildcard(self):
        assert topic_matches("+/temp", "a/temp")
        assert topic_matches("#", "a/b/c")

    def test_leading_wildcard_does_not_match_dollar_topics(self):
        # Per MQTT spec, leading '#'/'+' must not match $SYS/$share topics.
        assert not topic_matches("#", "$SYS/broker/uptime")
        assert not topic_matches("+/broker", "$SYS/broker")
        assert not topic_matches("#", "$share/g/x")
        # An explicit '$...' filter still matches.
        assert topic_matches("$SYS/#", "$SYS/broker/uptime")
        assert topic_matches("$SYS/broker/+", "$SYS/broker/uptime")


class TestValidFilter:
    def test_valid(self):
        for f in ["a", "a/b", "a/+/b", "a/#", "+/+", "#", "+"]:
            assert is_valid_filter(f), f

    def test_invalid(self):
        for f in ["", "a/#/b", "a+/b", "a/b+", "#/a"]:
            assert not is_valid_filter(f), f
