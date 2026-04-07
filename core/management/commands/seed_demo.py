"""Seed demo data for PersonDB — workspace-aware."""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from core.models import Person, Tag, Group, Contact, Relationship, ActivityLog, Workspace, Membership


class Command(BaseCommand):
    help = 'Seed database with demo data. Creates a demo user + workspace if needed.'

    def add_arguments(self, parser):
        parser.add_argument('--user', type=str, default='demo', help='Username (default: demo)')
        parser.add_argument('--password', type=str, default='demo1234', help='Password (default: demo1234)')
        parser.add_argument('--workspace', type=str, default='Demo DB', help='Workspace name')

    def handle(self, *args, **options):
        username = options['user']
        password = options['password']
        ws_name = options['workspace']

        # Create user
        user, created = User.objects.get_or_create(username=username,
            defaults={'email': f'{username}@persondb.local'})
        if created:
            user.set_password(password)
            user.save()
            self.stdout.write(f'  + User: {username} / {password}')

        # Create workspace
        ws, ws_created = Workspace.objects.get_or_create(name=ws_name, owner=user,
            defaults={'description': 'Demo pracovní prostor'})
        if ws_created:
            Membership.objects.get_or_create(workspace=ws, user=user,
                defaults={'role': Membership.Role.OWNER})
            self.stdout.write(f'  + Workspace: {ws_name}')

        self.stdout.write(f'Seeding into workspace "{ws_name}"...')

        # Tags
        tags_data = [
            ('Rodina', '#f06292', '👨‍👩‍👧‍👦'), ('Práce', '#ff9800', '💼'),
            ('Škola', '#9c27b0', '🎓'), ('Sport', '#4caf50', '⚽'),
            ('Cestování', '#00bcd4', '✈️'), ('IT', '#00ff41', '💻'),
            ('Důležité', '#f44336', '❗'),
        ]
        tags = {}
        for name, color, icon in tags_data:
            t, _ = Tag.objects.get_or_create(workspace=ws, name=name,
                defaults={'color': color, 'icon': icon})
            tags[name] = t

        # Groups
        groups_data = [
            ('Blízcí přátelé', 'Nejbližší okruh lidí', '#00ff41'),
            ('Kolegové', 'Pracovní kontakty', '#ff9800'),
            ('Rodina Nováků', 'Širší rodina', '#f06292'),
            ('Fotbalový tým', 'FC PersonDB', '#4caf50'),
        ]
        groups = {}
        for name, desc, color in groups_data:
            g, _ = Group.objects.get_or_create(workspace=ws, name=name,
                defaults={'description': desc, 'color': color})
            groups[name] = g

        # Persons
        persons_data = [
            {'first_name':'Jan','last_name':'Novák','nickname':'Honza','gender':'M',
             'birth_date':'1985-03-15','company':'CyberTech s.r.o.','job_title':'Senior Developer',
             'bio':'Hlavní kontakt.','is_favorite':True,'address_city':'Praha','address_country':'CZ',
             'metadata':{'hobby':['programování','šachy'],'blood_type':'A+'},
             'tags':['IT','Důležité'],'groups':['Blízcí přátelé']},
            {'first_name':'Marie','last_name':'Nováková','gender':'F',
             'birth_date':'1987-07-22','company':'Design Studio','job_title':'UX Designer',
             'is_favorite':True,'address_city':'Praha',
             'tags':['Rodina','Důležité'],'groups':['Rodina Nováků']},
            {'first_name':'Petr','last_name':'Svoboda','nickname':'Pete','gender':'M',
             'birth_date':'1990-11-03','company':'CyberTech s.r.o.','job_title':'DevOps',
             'tags':['IT','Práce','Sport'],'groups':['Kolegové','Fotbalový tým']},
            {'first_name':'Eva','last_name':'Černá','gender':'F',
             'birth_date':'1992-05-18','company':'Startup X','job_title':'PM',
             'tags':['Práce'],'groups':['Kolegové']},
            {'first_name':'Tomáš','last_name':'Dvořák','gender':'M',
             'birth_date':'1982-01-09','bio':'Soused a kamarád.',
             'tags':['Sport','Škola'],'groups':['Fotbalový tým']},
            {'first_name':'Lucie','last_name':'Králová','gender':'F',
             'birth_date':'1995-09-30','company':'CyberTech s.r.o.',
             'tags':['IT','Cestování'],'groups':['Kolegové']},
            {'first_name':'Karel','last_name':'Novák','gender':'M',
             'birth_date':'1958-12-01','bio':'Otec Jana.',
             'tags':['Rodina'],'groups':['Rodina Nováků']},
            {'first_name':'Anna','last_name':'Nováková','gender':'F',
             'birth_date':'1960-04-14','bio':'Matka Jana.',
             'tags':['Rodina'],'groups':['Rodina Nováků']},
        ]
        created_persons = {}
        for pd in persons_data:
            tag_names = pd.pop('tags', [])
            group_names = pd.pop('groups', [])
            p, created = Person.objects.get_or_create(
                workspace=ws, first_name=pd['first_name'], last_name=pd['last_name'],
                defaults=pd)
            for tn in tag_names:
                if tn in tags: p.tags.add(tags[tn])
            for gn in group_names:
                if gn in groups: p.groups.add(groups[gn])
            created_persons[f"{pd['first_name']} {pd['last_name']}"] = p
            if created: self.stdout.write(f'  + {p}')

        # Contacts
        jan = created_persons.get('Jan Novák')
        if jan and not jan.contacts.exists():
            Contact.objects.create(person=jan, contact_type='email', value='jan@cybertech.cz', label='práce', is_primary=True)
            Contact.objects.create(person=jan, contact_type='mobile', value='+420 777 123 456', label='osobní')
            Contact.objects.create(person=jan, contact_type='web', value='https://jan-novak.dev')

        marie = created_persons.get('Marie Nováková')
        if marie and not marie.contacts.exists():
            Contact.objects.create(person=marie, contact_type='email', value='marie@design.cz', is_primary=True)

        # Relationships
        rels = [
            ('Jan Novák','Marie Nováková','spouse','Manželé'),
            ('Jan Novák','Karel Novák','child','Syn'),
            ('Jan Novák','Anna Nováková','child','Syn'),
            ('Karel Novák','Anna Nováková','spouse','Manželé'),
            ('Jan Novák','Petr Svoboda','colleague','Kolegové v CyberTech'),
            ('Jan Novák','Tomáš Dvořák','friend','Kamarádi ze školy'),
            ('Jan Novák','Lucie Králová','colleague',''),
            ('Jan Novák','Eva Černá','acquaintance',''),
            ('Petr Svoboda','Lucie Králová','colleague',''),
            ('Petr Svoboda','Tomáš Dvořák','friend','Fotbal'),
        ]
        for fn, tn, rtype, desc in rels:
            pf, pt = created_persons.get(fn), created_persons.get(tn)
            if pf and pt:
                Relationship.objects.get_or_create(person_from=pf, person_to=pt,
                    relation_type=rtype, defaults={'description': desc})

        ActivityLog.objects.create(workspace=ws, user=user, action='Demo data seeded',
            details={'persons': len(created_persons)})
        self.stdout.write(self.style.SUCCESS(
            f'Done! {len(created_persons)} persons. Login: {username} / {password}'))
