import json
from django import forms
from django.utils.translation import gettext_lazy as _
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from .models import Person, Contact, Relationship, Document, Tag, Group, Workspace, Invite, Membership

W = {'class': 'form-control'}


class PersonForm(forms.ModelForm):
    metadata_json = forms.CharField(label=_('Metadata (JSON)'), required=False,
        widget=forms.Textarea(attrs={'class': 'form-control code-input', 'rows': 4,
            'placeholder': '{"key": "value"}'}))

    class Meta:
        model = Person
        fields = ['first_name', 'last_name', 'middle_name', 'nickname', 'gender',
            'birth_date', 'death_date', 'photo', 'bio', 'notes',
            'address_street', 'address_city', 'address_zip', 'address_country',
            'company', 'job_title', 'tags', 'groups', 'is_favorite', 'is_active']
        widgets = {
            'first_name': forms.TextInput(attrs={**W, 'placeholder': _('Jméno')}),
            'last_name': forms.TextInput(attrs={**W, 'placeholder': _('Příjmení')}),
            'middle_name': forms.TextInput(attrs={**W, 'placeholder': _('Prostřední jméno')}),
            'nickname': forms.TextInput(attrs={**W, 'placeholder': _('Přezdívka')}),
            'gender': forms.Select(attrs=W),
            'birth_date': forms.DateInput(attrs={**W, 'type': 'date'}),
            'death_date': forms.DateInput(attrs={**W, 'type': 'date'}),
            'bio': forms.Textarea(attrs={**W, 'rows': 4}),
            'notes': forms.Textarea(attrs={**W, 'rows': 3}),
            'address_street': forms.TextInput(attrs=W),
            'address_city': forms.TextInput(attrs=W),
            'address_zip': forms.TextInput(attrs=W),
            'address_country': forms.TextInput(attrs=W),
            'company': forms.TextInput(attrs=W),
            'job_title': forms.TextInput(attrs=W),
            'tags': forms.CheckboxSelectMultiple(),
            'groups': forms.CheckboxSelectMultiple(),
        }

    def __init__(self, *args, workspace=None, **kwargs):
        super().__init__(*args, **kwargs)
        if workspace:
            self.fields['tags'].queryset = Tag.objects.filter(workspace=workspace)
            self.fields['groups'].queryset = Group.objects.filter(workspace=workspace)
        if self.instance.pk and self.instance.metadata:
            self.fields['metadata_json'].initial = json.dumps(self.instance.metadata, indent=2, ensure_ascii=False)

    def clean_metadata_json(self):
        d = self.cleaned_data.get('metadata_json', '').strip()
        if not d: return {}
        try: return json.loads(d)
        except json.JSONDecodeError as e:
            raise forms.ValidationError(_('Neplatný JSON: %(err)s') % {'err': str(e)})

    def save(self, commit=True):
        inst = super().save(commit=False)
        inst.metadata = self.cleaned_data.get('metadata_json', {})
        if commit: inst.save(); self.save_m2m()
        return inst


class ContactForm(forms.ModelForm):
    class Meta:
        model = Contact
        fields = ['contact_type', 'label', 'value', 'is_primary']
        widgets = {'contact_type': forms.Select(attrs=W),
            'label': forms.TextInput(attrs={**W, 'placeholder': _('např. osobní')}),
            'value': forms.TextInput(attrs={**W, 'placeholder': _('Hodnota')})}

ContactFormSet = forms.inlineformset_factory(Person, Contact, form=ContactForm, extra=1, can_delete=True)


class RelationshipForm(forms.ModelForm):
    class Meta:
        model = Relationship
        fields = ['person_to', 'relation_type', 'description', 'started_at', 'ended_at', 'is_active']
        widgets = {'person_to': forms.Select(attrs=W), 'relation_type': forms.Select(attrs=W),
            'description': forms.Textarea(attrs={**W, 'rows': 2}),
            'started_at': forms.DateInput(attrs={**W, 'type': 'date'}),
            'ended_at': forms.DateInput(attrs={**W, 'type': 'date'})}

    def __init__(self, *args, person_from=None, workspace=None, **kwargs):
        super().__init__(*args, **kwargs)
        qs = Person.objects.all()
        if workspace: qs = qs.filter(workspace=workspace)
        if person_from: qs = qs.exclude(pk=person_from.pk)
        self.fields['person_to'].queryset = qs


class DocumentForm(forms.ModelForm):
    metadata_json = forms.CharField(label=_('Metadata (JSON)'), required=False,
        widget=forms.Textarea(attrs={'class': 'form-control code-input', 'rows': 3, 'placeholder': '{}'}))
    class Meta:
        model = Document
        fields = ['title', 'doc_type', 'file', 'description']
        widgets = {'title': forms.TextInput(attrs=W), 'doc_type': forms.Select(attrs=W),
            'description': forms.Textarea(attrs={**W, 'rows': 2})}
    def clean_metadata_json(self):
        d = self.cleaned_data.get('metadata_json', '').strip()
        if not d: return {}
        try: return json.loads(d)
        except json.JSONDecodeError as e:
            raise forms.ValidationError(_('Neplatný JSON: %(err)s') % {'err': str(e)})
    def save(self, commit=True):
        inst = super().save(commit=False)
        inst.metadata = self.cleaned_data.get('metadata_json', {})
        if commit: inst.save()
        return inst


class TagForm(forms.ModelForm):
    class Meta:
        model = Tag; fields = ['name', 'color', 'icon']
        widgets = {'name': forms.TextInput(attrs=W),
            'color': forms.TextInput(attrs={**W, 'type': 'color'}),
            'icon': forms.TextInput(attrs={**W, 'placeholder': _('Emoji nebo CSS class')})}


class GroupForm(forms.ModelForm):
    class Meta:
        model = Group; fields = ['name', 'description', 'color']
        widgets = {'name': forms.TextInput(attrs=W),
            'description': forms.Textarea(attrs={**W, 'rows': 3}),
            'color': forms.TextInput(attrs={**W, 'type': 'color'})}


class SearchForm(forms.Form):
    q = forms.CharField(label=_('Hledat'), required=False,
        widget=forms.TextInput(attrs={'class': 'form-control search-input',
            'placeholder': _('Hledat osobu...'), 'autofocus': True}))
    tag = forms.ModelChoiceField(queryset=Tag.objects.none(), required=False,
        empty_label=_('-- Všechny štítky --'), widget=forms.Select(attrs=W))
    group = forms.ModelChoiceField(queryset=Group.objects.none(), required=False,
        empty_label=_('-- Všechny skupiny --'), widget=forms.Select(attrs=W))
    favorites_only = forms.BooleanField(label=_('Pouze oblíbené'), required=False)

    def __init__(self, *args, workspace=None, **kwargs):
        super().__init__(*args, **kwargs)
        if workspace:
            self.fields['tag'].queryset = Tag.objects.filter(workspace=workspace)
            self.fields['group'].queryset = Group.objects.filter(workspace=workspace)


class ImportForm(forms.Form):
    file = forms.FileField(label=_('JSON soubor'))


# ---- Auth & Workspace Forms ----

class RegisterForm(UserCreationForm):
    email = forms.EmailField(required=True, widget=forms.EmailInput(attrs={**W, 'placeholder': 'E-mail'}))
    class Meta:
        model = User; fields = ['username', 'email', 'password1', 'password2']
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for f in self.fields.values(): f.widget.attrs['class'] = 'form-control'


class LoginForm(AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for f in self.fields.values(): f.widget.attrs['class'] = 'form-control'


class WorkspaceForm(forms.ModelForm):
    class Meta:
        model = Workspace; fields = ['name', 'description', 'color']
        widgets = {'name': forms.TextInput(attrs={**W, 'placeholder': _('Název prostoru')}),
            'description': forms.Textarea(attrs={**W, 'rows': 3}),
            'color': forms.TextInput(attrs={**W, 'type': 'color'})}


class InviteForm(forms.ModelForm):
    class Meta:
        model = Invite; fields = ['role', 'max_uses']
        widgets = {'role': forms.Select(attrs=W),
            'max_uses': forms.NumberInput(attrs={**W, 'min': 1, 'max': 100})}
