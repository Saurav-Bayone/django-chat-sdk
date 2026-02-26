"""Template tags and filters for Chat SDK templates."""

from django import template
from django.utils.safestring import mark_safe

register = template.Library()


@register.filter(name="message_text")
def message_text(message):
    """Extract text content from a message's parts."""
    return message.get_text_content()


@register.filter(name="has_tool_calls")
def has_tool_calls(message):
    """Check if message has tool call parts."""
    return bool(message.get_tool_calls())


@register.filter(name="message_role_class")
def message_role_class(message):
    """Return CSS class based on message role."""
    classes = {
        "user": "bg-primary-subtle text-primary",
        "assistant": "bg-body-tertiary",
        "system": "bg-warning-subtle text-warning",
        "tool": "bg-info-subtle text-info",
    }
    return classes.get(message.role, "bg-body-tertiary")


@register.filter(name="message_role_icon")
def message_role_icon(message):
    """Return Feather icon name based on message role."""
    icons = {
        "user": "user",
        "assistant": "cpu",
        "system": "settings",
        "tool": "tool",
    }
    return icons.get(message.role, "message-circle")


@register.simple_tag
def chat_sdk_version():
    """Return Chat SDK version."""
    from chat_sdk import __version__
    return __version__
