"""
Relationship Inference Engine for PersonDB.

Rules:
- A is parent of B, B is parent of C → A is grandparent of C (C is grandchild of A)
- A is parent of B, A is parent of C (B≠C) → B is sibling of C
- A is spouse/partner of B, B is parent of C → A is parent of C (step-parent suggestion)
- A is parent of B, C is sibling of A → C is uncle_aunt of B

These are generated as suggestions that can be accepted or dismissed.
"""
from .models import Person, Relationship


# Map of inverse relationships
INVERSE = {
    'parent': 'child',
    'child': 'parent',
    'grandparent': 'grandchild',
    'grandchild': 'grandparent',
    'sibling': 'sibling',
    'spouse': 'spouse',
    'partner': 'partner',
    'uncle_aunt': None,  # no simple inverse
    'cousin': 'cousin',
    'mentor': 'mentee',
    'mentee': 'mentor',
    'boss': 'subordinate',
    'subordinate': 'boss',
    'friend': 'friend',
    'bestfriend': 'bestfriend',
    'colleague': 'colleague',
    'classmate': 'classmate',
    'neighbor': 'neighbor',
    'acquaintance': 'acquaintance',
    'enemy': 'enemy',
    'other': 'other',
}


def _rel_exists(a, b, rtype):
    """Check if relationship exists in either direction."""
    return Relationship.objects.filter(
        person_from=a, person_to=b, relation_type=rtype
    ).exists() or Relationship.objects.filter(
        person_from=b, person_to=a, relation_type=INVERSE.get(rtype, rtype)
    ).exists()


def _get_related(person, rtype_from=None, rtype_to=None):
    """Get persons related to `person` by given type."""
    result = set()
    if rtype_from:
        for r in Relationship.objects.filter(person_from=person, relation_type=rtype_from):
            result.add(r.person_to)
    if rtype_to:
        for r in Relationship.objects.filter(person_to=person, relation_type=rtype_to):
            result.add(r.person_from)
    return result


def get_parents(person):
    """All who are parent of this person."""
    # person_from=X, person_to=person, type=parent → X is parent
    # person_from=person, person_to=X, type=child → X is parent
    parents = set()
    for r in Relationship.objects.filter(person_to=person, relation_type='parent'):
        parents.add(r.person_from)
    for r in Relationship.objects.filter(person_from=person, relation_type='child'):
        parents.add(r.person_to)
    return parents


def get_children(person):
    """All who are children of this person."""
    children = set()
    for r in Relationship.objects.filter(person_from=person, relation_type='parent'):
        children.add(r.person_to)
    for r in Relationship.objects.filter(person_to=person, relation_type='child'):
        children.add(r.person_from)
    return children


def get_siblings(person):
    """All siblings (share at least one parent)."""
    siblings = set()
    for parent in get_parents(person):
        for child in get_children(parent):
            if child != person:
                siblings.add(child)
    return siblings


def infer_relationships(workspace):
    """
    Scan all relationships in workspace and return list of suggested new ones.
    Returns list of dicts: {person_from, person_to, relation_type, reason}
    """
    suggestions = []
    seen = set()  # (from_id, to_id, type) to avoid duplicates

    def add(pf, pt, rtype, reason):
        key = (pf.id, pt.id, rtype)
        rev_key = (pt.id, pf.id, INVERSE.get(rtype, rtype))
        if key in seen or rev_key in seen:
            return
        if _rel_exists(pf, pt, rtype):
            return
        if pf == pt:
            return
        seen.add(key)
        suggestions.append({
            'person_from': pf,
            'person_to': pt,
            'relation_type': rtype,
            'reason': reason,
        })

    persons = Person.objects.filter(workspace=workspace, is_active=True)

    for person in persons:
        parents = get_parents(person)
        children = get_children(person)

        # Rule 1: Grandparent/Grandchild
        # If person has parents, and those parents have parents → grandparents
        for parent in parents:
            for grandparent in get_parents(parent):
                add(grandparent, person, 'grandparent',
                    f'{grandparent} je rodič {parent}, {parent} je rodič {person}')

        # Rule 2: Siblings (share parents)
        for parent in parents:
            for sibling in get_children(parent):
                if sibling != person:
                    add(person, sibling, 'sibling',
                        f'Sdílí rodiče: {parent}')

        # Rule 3: Uncle/Aunt
        # If person's parent has siblings → those are uncles/aunts
        for parent in parents:
            for parent_sibling in get_siblings(parent):
                add(parent_sibling, person, 'uncle_aunt',
                    f'{parent_sibling} je sourozenec {parent}')

        # Rule 4: Cousins
        # If person's parent has siblings, and those siblings have children → cousins
        for parent in parents:
            for parent_sibling in get_siblings(parent):
                for cousin in get_children(parent_sibling):
                    if cousin != person:
                        add(person, cousin, 'cousin',
                            f'Přes rodiče {parent} a {parent_sibling}')

    return suggestions


def apply_suggestion(person_from, person_to, relation_type, description=''):
    """Create a relationship from a suggestion."""
    rel, created = Relationship.objects.get_or_create(
        person_from=person_from,
        person_to=person_to,
        relation_type=relation_type,
        defaults={'description': description}
    )
    return rel, created
