import uuid, os, secrets, string
from django.db import models
from django.conf import settings as django_settings
from django.utils.translation import gettext_lazy as _
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta


def photo_path(inst, fn):
    ext = fn.rsplit('.', 1)[-1] if '.' in fn else 'jpg'
    return f'photos/{inst.workspace_id}/{inst.uuid}/{uuid.uuid4().hex[:8]}.{ext}'

def doc_path(inst, fn):
    ext = fn.rsplit('.', 1)[-1] if '.' in fn else 'bin'
    return f'documents/{inst.person.workspace_id}/{inst.person.uuid}/{uuid.uuid4().hex[:8]}.{ext}'

def _gen_code():
    return ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(8))


class Workspace(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    name = models.CharField(_('Název'), max_length=200)
    description = models.TextField(_('Popis'), blank=True, default='')
    owner = models.ForeignKey(django_settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                              related_name='owned_workspaces', verbose_name=_('Vlastník'))
    color = models.CharField(_('Barva'), max_length=7, default='#00ff41')
    metadata = models.JSONField(_('Metadata'), default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('Pracovní prostor'); verbose_name_plural = _('Pracovní prostory')
        ordering = ['name']

    def __str__(self): return self.name


class Membership(models.Model):
    class Role(models.TextChoices):
        OWNER = 'owner', _('Vlastník')
        EDITOR = 'editor', _('Editor')
        VIEWER = 'viewer', _('Čtenář')

    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name='memberships')
    user = models.ForeignKey(django_settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='ws_memberships')
    role = models.CharField(_('Role'), max_length=10, choices=Role.choices, default=Role.EDITOR)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _('Členství'); verbose_name_plural = _('Členství')
        unique_together = ['workspace', 'user']

    def __str__(self): return f'{self.user} → {self.workspace} ({self.get_role_display()})'

    @property
    def can_edit(self): return self.role in (self.Role.OWNER, self.Role.EDITOR)


class Invite(models.Model):
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name='invites')
    created_by = models.ForeignKey(django_settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    code = models.CharField(_('Kód'), max_length=20, unique=True, default=_gen_code)
    role = models.CharField(_('Role'), max_length=10, choices=Membership.Role.choices, default=Membership.Role.EDITOR)
    max_uses = models.PositiveIntegerField(_('Max použití'), default=1)
    uses = models.PositiveIntegerField(_('Použito'), default=0)
    expires_at = models.DateTimeField(_('Platnost do'), null=True, blank=True)
    is_active = models.BooleanField(_('Aktivní'), default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _('Pozvánka'); verbose_name_plural = _('Pozvánky'); ordering = ['-created_at']

    def __str__(self): return f'{self.code} → {self.workspace}'

    @property
    def is_valid(self):
        if not self.is_active: return False
        if self.max_uses and self.uses >= self.max_uses: return False
        if self.expires_at and timezone.now() > self.expires_at: return False
        return True

    def save(self, *args, **kwargs):
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(days=7)
        super().save(*args, **kwargs)


class Tag(models.Model):
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name='tags')
    name = models.CharField(_('Název'), max_length=100)
    color = models.CharField(_('Barva'), max_length=7, default='#00ff41')
    icon = models.CharField(_('Ikona'), max_length=50, blank=True, default='')
    metadata = models.JSONField(_('Metadata'), default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _('Štítek'); verbose_name_plural = _('Štítky'); ordering = ['name']
        unique_together = ['workspace', 'name']

    def __str__(self): return self.name
    def get_absolute_url(self): return reverse('core:tag_detail', kwargs={'pk': self.pk})


class Group(models.Model):
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name='groups')
    name = models.CharField(_('Název'), max_length=200)
    description = models.TextField(_('Popis'), blank=True, default='')
    color = models.CharField(_('Barva'), max_length=7, default='#00ff41')
    metadata = models.JSONField(_('Metadata'), default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('Skupina'); verbose_name_plural = _('Skupiny'); ordering = ['name']

    def __str__(self): return self.name
    def get_absolute_url(self): return reverse('core:group_detail', kwargs={'pk': self.pk})


class Person(models.Model):
    class Gender(models.TextChoices):
        MALE = 'M', _('Muž'); FEMALE = 'F', _('Žena')
        OTHER = 'O', _('Jiné'); UNKNOWN = 'U', _('Neuvedeno')

    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name='persons')
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    first_name = models.CharField(_('Jméno'), max_length=100)
    last_name = models.CharField(_('Příjmení'), max_length=100)
    middle_name = models.CharField(_('Prostřední jméno'), max_length=100, blank=True, default='')
    nickname = models.CharField(_('Přezdívka'), max_length=100, blank=True, default='')
    gender = models.CharField(_('Pohlaví'), max_length=1, choices=Gender.choices, default=Gender.UNKNOWN)
    birth_date = models.DateField(_('Datum narození'), null=True, blank=True)
    death_date = models.DateField(_('Datum úmrtí'), null=True, blank=True)
    photo = models.ImageField(_('Fotografie'), upload_to=photo_path, null=True, blank=True)
    bio = models.TextField(_('Biografie'), blank=True, default='')
    notes = models.TextField(_('Poznámky'), blank=True, default='')
    address_street = models.CharField(_('Ulice'), max_length=200, blank=True, default='')
    address_city = models.CharField(_('Město'), max_length=100, blank=True, default='')
    address_zip = models.CharField(_('PSČ'), max_length=20, blank=True, default='')
    address_country = models.CharField(_('Země'), max_length=100, blank=True, default='')
    company = models.CharField(_('Firma'), max_length=200, blank=True, default='')
    job_title = models.CharField(_('Pozice'), max_length=200, blank=True, default='')
    tags = models.ManyToManyField(Tag, verbose_name=_('Štítky'), blank=True, related_name='persons')
    groups = models.ManyToManyField(Group, verbose_name=_('Skupiny'), blank=True, related_name='members')
    metadata = models.JSONField(_('Metadata'), default=dict, blank=True)
    is_active = models.BooleanField(_('Aktivní'), default=True)
    is_favorite = models.BooleanField(_('Oblíbený'), default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('Osoba'); verbose_name_plural = _('Osoby')
        ordering = ['last_name', 'first_name']

    def __str__(self):
        s = f'{self.first_name} {self.last_name}'
        return f'{s} "{self.nickname}"' if self.nickname else s

    @property
    def full_name(self):
        return ' '.join(filter(None, [self.first_name, self.middle_name, self.last_name]))

    def get_absolute_url(self): return reverse('core:person_detail', kwargs={'pk': self.pk})

    def to_json(self):
        return {
            'uuid': str(self.uuid), 'first_name': self.first_name, 'last_name': self.last_name,
            'middle_name': self.middle_name, 'nickname': self.nickname, 'gender': self.gender,
            'birth_date': str(self.birth_date) if self.birth_date else None,
            'death_date': str(self.death_date) if self.death_date else None,
            'bio': self.bio, 'notes': self.notes,
            'address': {'street': self.address_street, 'city': self.address_city,
                        'zip': self.address_zip, 'country': self.address_country},
            'company': self.company, 'job_title': self.job_title,
            'tags': list(self.tags.values_list('name', flat=True)),
            'groups': list(self.groups.values_list('name', flat=True)),
            'metadata': self.metadata, 'is_favorite': self.is_favorite,
            'contacts': [c.to_json() for c in self.contacts.all()],
        }


class Contact(models.Model):
    class Type(models.TextChoices):
        EMAIL = 'email', _('E-mail'); PHONE = 'phone', _('Telefon')
        MOBILE = 'mobile', _('Mobil'); WEB = 'web', _('Web')
        SOCIAL = 'social', _('Sociální síť'); MESSENGER = 'msg', _('Messenger')
        OTHER = 'other', _('Jiný')

    person = models.ForeignKey(Person, on_delete=models.CASCADE, related_name='contacts')
    contact_type = models.CharField(_('Typ'), max_length=10, choices=Type.choices, default=Type.OTHER)
    label = models.CharField(_('Popis'), max_length=100, blank=True, default='')
    value = models.CharField(_('Hodnota'), max_length=500)
    is_primary = models.BooleanField(_('Primární'), default=False)
    metadata = models.JSONField(_('Metadata'), default=dict, blank=True)

    class Meta:
        verbose_name = _('Kontakt'); verbose_name_plural = _('Kontakty')
        ordering = ['-is_primary', 'contact_type']

    def __str__(self): return f'{self.get_contact_type_display()}: {self.value}'
    def to_json(self):
        return {'type': self.contact_type, 'label': self.label, 'value': self.value,
                'is_primary': self.is_primary, 'metadata': self.metadata}


class Relationship(models.Model):
    class Type(models.TextChoices):
        PARENT = 'parent', _('Rodič'); CHILD = 'child', _('Dítě')
        SIBLING = 'sibling', _('Sourozenec'); SPOUSE = 'spouse', _('Manžel/ka')
        PARTNER = 'partner', _('Partner/ka'); GRANDPARENT = 'grandparent', _('Prarodič')
        GRANDCHILD = 'grandchild', _('Vnuk/vnučka'); UNCLE_AUNT = 'uncle_aunt', _('Strýc/teta')
        COUSIN = 'cousin', _('Bratranec/sestřenice')
        FRIEND = 'friend', _('Přítel/kyně'); BEST_FRIEND = 'bestfriend', _('Nejlepší přítel/kyně')
        COLLEAGUE = 'colleague', _('Kolega/yně'); BOSS = 'boss', _('Nadřízený/á')
        SUBORDINATE = 'subordinate', _('Podřízený/á'); CLASSMATE = 'classmate', _('Spolužák/čka')
        NEIGHBOR = 'neighbor', _('Soused/ka'); ACQUAINTANCE = 'acquaintance', _('Známý/á')
        ENEMY = 'enemy', _('Nepřítel/kyně'); MENTOR = 'mentor', _('Mentor/ka')
        MENTEE = 'mentee', _('Mentee'); OTHER = 'other', _('Jiný vztah')

    person_from = models.ForeignKey(Person, on_delete=models.CASCADE, related_name='rels_from')
    person_to = models.ForeignKey(Person, on_delete=models.CASCADE, related_name='rels_to')
    relation_type = models.CharField(_('Typ vztahu'), max_length=20, choices=Type.choices, default=Type.OTHER)
    description = models.TextField(_('Popis'), blank=True, default='')
    started_at = models.DateField(_('Začátek'), null=True, blank=True)
    ended_at = models.DateField(_('Konec'), null=True, blank=True)
    is_active = models.BooleanField(_('Aktivní'), default=True)
    metadata = models.JSONField(_('Metadata'), default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _('Vztah'); verbose_name_plural = _('Vztahy')
        unique_together = ['person_from', 'person_to', 'relation_type']

    def __str__(self):
        return f'{self.person_from} -> {self.get_relation_type_display()} -> {self.person_to}'


class Document(models.Model):
    class Type(models.TextChoices):
        PHOTO = 'photo', _('Fotografie'); ID_CARD = 'id_card', _('Občanský průkaz')
        PASSPORT = 'passport', _('Pas'); DRIVER_LIC = 'driver_lic', _('Řidičský průkaz')
        CONTRACT = 'contract', _('Smlouva'); CERTIFICATE = 'cert', _('Certifikát')
        LETTER = 'letter', _('Dopis'); INVOICE = 'invoice', _('Faktura')
        NOTE = 'note', _('Poznámka'); OTHER = 'other', _('Jiný')

    person = models.ForeignKey(Person, on_delete=models.CASCADE, related_name='documents')
    title = models.CharField(_('Název'), max_length=200)
    doc_type = models.CharField(_('Typ'), max_length=20, choices=Type.choices, default=Type.OTHER)
    file = models.FileField(_('Soubor'), upload_to=doc_path)
    description = models.TextField(_('Popis'), blank=True, default='')
    metadata = models.JSONField(_('Metadata'), default=dict, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _('Dokument'); verbose_name_plural = _('Dokumenty'); ordering = ['-uploaded_at']

    def __str__(self): return self.title
    @property
    def ext(self): return os.path.splitext(self.file.name)[1].lower() if self.file else ''
    @property
    def is_image(self): return self.ext in ('.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp')


class ActivityLog(models.Model):
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name='activity', null=True)
    user = models.ForeignKey(django_settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    person = models.ForeignKey(Person, on_delete=models.SET_NULL, null=True, blank=True, related_name='logs')
    action = models.CharField(max_length=200)
    details = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self): return f'{self.created_at:%d.%m.%Y %H:%M} - {self.action}'
