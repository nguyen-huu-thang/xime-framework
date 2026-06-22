from __future__ import annotations

# MQTT topic wildcard matching (MQTT 3.1.1 / 5.0 semantics).
#   +  matches exactly one topic level
#   #  matches zero or more levels, valid only as the final level
# Khớp wildcard topic MQTT: '+' một cấp, '#' nhiều cấp (chỉ ở cuối).


def topic_matches(filter_: str, topic: str) -> bool:
    """Return True if a concrete `topic` matches a subscription `filter_`.

    Examples:
        topic_matches("sensors/+/temp", "sensors/a/temp")  -> True
        topic_matches("sensors/#", "sensors/a/b/c")          -> True
        topic_matches("sensors/+", "sensors/a/b")            -> False
    """
    filter_levels = filter_.split("/")
    topic_levels = topic.split("/")

    # Per spec, a leading wildcard ('#' or '+') must NOT match topics whose first
    # level starts with '$' (e.g. $SYS, $share) - those are reserved/system topics.
    # Theo spec, wildcard ở cấp đầu KHÔNG khớp topic bắt đầu bằng '$' ($SYS, $share).
    if (
        topic_levels
        and topic_levels[0].startswith("$")
        and filter_levels
        and filter_levels[0] in ("+", "#")
    ):
        return False

    for i, f in enumerate(filter_levels):
        if f == "#":
            # '#' matches the remaining levels (including none). Per spec it must
            # be the last level in the filter; we treat it as terminal here.
            # '#' khớp các cấp còn lại (kể cả không có), phải là cấp cuối.
            return True
        if i >= len(topic_levels):
            return False
        if f == "+":
            continue  # any single level
        if f != topic_levels[i]:
            return False

    # All filter levels consumed: match only if the topic has no extra levels.
    # Hết cấp của filter: khớp khi topic cũng không còn cấp thừa.
    return len(filter_levels) == len(topic_levels)


def is_valid_filter(filter_: str) -> bool:
    """Validate a subscription filter's wildcard usage.

    Rules: '#' must stand alone as the final level; '+' must occupy a whole
    level. An empty filter is invalid.
    '#' phải đứng một mình ở cấp cuối; '+' chiếm trọn một cấp; rỗng là sai.
    """
    if not filter_:
        return False
    levels = filter_.split("/")
    for i, level in enumerate(levels):
        if "#" in level:
            if level != "#" or i != len(levels) - 1:
                return False
        if "+" in level and level != "+":
            return False
    return True
