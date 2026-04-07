import json
from django import template
from django.utils.safestring import mark_safe

register = template.Library()

@register.filter
def json_pretty(value):
    if isinstance(value, str):
        try: value = json.loads(value)
        except: return value
    try: return mark_safe('<pre class="json-block">' + json.dumps(value, indent=2, ensure_ascii=False) + '</pre>')
    except: return str(value)

RELATION_ICONS = {
    'parent':'👤↑','child':'👤↓','sibling':'👥','spouse':'💍','partner':'❤️',
    'grandparent':'👴','grandchild':'👶','uncle_aunt':'👤','cousin':'👤',
    'friend':'🤝','bestfriend':'⭐','colleague':'💼','boss':'📊',
    'subordinate':'📋','classmate':'🎓','neighbor':'🏠','acquaintance':'👋',
    'enemy':'⚔️','mentor':'🎯','mentee':'📖','other':'🔗',
}
CONTACT_ICONS = {'email':'📧','phone':'☎️','mobile':'📱','web':'🌐','social':'💬','msg':'✉️','other':'📌'}
DOC_ICONS = {'photo':'📷','id_card':'🪪','passport':'🛂','driver_lic':'🚗','contract':'📄',
             'cert':'📜','letter':'✉️','invoice':'🧾','note':'📝','other':'📎'}

@register.filter
def rel_icon(t): return RELATION_ICONS.get(t, '🔗')
@register.filter
def contact_icon(t): return CONTACT_ICONS.get(t, '📌')
@register.filter
def doc_icon(t): return DOC_ICONS.get(t, '📎')
