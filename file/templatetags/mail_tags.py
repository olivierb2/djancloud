from django import template

register = template.Library()


@register.filter
def multiply(value, arg):
    try:
        return int(value) * int(arg)
    except (ValueError, TypeError):
        return 0


@register.filter
def add_int(value, arg):
    try:
        return int(value) + int(arg)
    except (ValueError, TypeError):
        return 0
