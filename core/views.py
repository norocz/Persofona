import json, zipfile, io, os
from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView, TemplateView, View
from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Count
from django.http import JsonResponse, HttpResponse
from django.urls import reverse_lazy, reverse
from django.utils.translation import gettext_lazy as _, gettext
from django.core.paginator import Paginator
from django.conf import settings
from django.utils import timezone

from .models import (Person, Contact, Relationship, Document, Tag, Group,
                      ActivityLog, Workspace, Membership, Invite)
from .forms import (PersonForm, ContactFormSet, RelationshipForm, DocumentForm,
                     TagForm, GroupForm, SearchForm, ImportForm,
                     RegisterForm, LoginForm, WorkspaceForm, InviteForm)
from .inference import infer_relationships, apply_suggestion


# ==================== Workspace Mixin ====================

class WsMixin(LoginRequiredMixin):
    """Mixin that provides workspace-scoped querysets and checks membership."""

    def get_ws(self):
        return self.request.workspace

    def get_membership(self):
        return self.request.membership

    def can_edit(self):
        m = self.get_membership()
        return m and m.can_edit

    def get_queryset(self):
        qs = super().get_queryset()
        ws = self.get_ws()
        if ws and hasattr(qs.model, 'workspace'):
            return qs.filter(workspace=ws)
        return qs

    def log(self, action, person=None, details=None):
        ActivityLog.objects.create(
            workspace=self.get_ws(), user=self.request.user,
            person=person, action=action, details=details or {}
        )


# ==================== Auth ====================

class RegisterView(View):
    def get(self, req):
        if req.user.is_authenticated: return redirect('core:dashboard')
        return render(req, 'core/auth/register.html', {'form': RegisterForm()})

    def post(self, req):
        form = RegisterForm(req.POST)
        if form.is_valid():
            user = form.save()
            login(req, user)
            # Create default workspace
            ws = Workspace.objects.create(name=_('Moje databáze'), owner=user)
            Membership.objects.create(workspace=ws, user=user, role=Membership.Role.OWNER)
            req.session['workspace_id'] = ws.id
            messages.success(req, _('Účet vytvořen! Vítejte v Persofona.'))
            return redirect('core:dashboard')
        return render(req, 'core/auth/register.html', {'form': form})


class LoginView(View):
    def get(self, req):
        if req.user.is_authenticated: return redirect('core:dashboard')
        return render(req, 'core/auth/login.html', {'form': LoginForm()})

    def post(self, req):
        form = LoginForm(req, data=req.POST)
        if form.is_valid():
            login(req, form.get_user())
            return redirect(req.GET.get('next', 'core:dashboard'))
        return render(req, 'core/auth/login.html', {'form': form})


class LogoutView(View):
    def post(self, req):
        logout(req)
        return redirect('core:login')


# ==================== Workspace Management ====================

class WorkspacePickView(LoginRequiredMixin, View):
    def get(self, req):
        memberships = Membership.objects.filter(user=req.user).select_related('workspace')
        if not memberships.exists():
            return redirect('core:workspace_create')
        return render(req, 'core/workspace/pick.html', {'memberships': memberships})


class WorkspaceCreateView(LoginRequiredMixin, View):
    def get(self, req):
        return render(req, 'core/workspace/create.html', {'form': WorkspaceForm()})

    def post(self, req):
        form = WorkspaceForm(req.POST)
        if form.is_valid():
            ws = form.save(commit=False)
            ws.owner = req.user
            ws.save()
            Membership.objects.create(workspace=ws, user=req.user, role=Membership.Role.OWNER)
            req.session['workspace_id'] = ws.id
            messages.success(req, _('Pracovní prostor "%(n)s" vytvořen.') % {'n': ws.name})
            return redirect('core:dashboard')
        return render(req, 'core/workspace/create.html', {'form': form})


class WorkspaceSwitchView(LoginRequiredMixin, View):
    def post(self, req, pk):
        m = get_object_or_404(Membership, workspace_id=pk, user=req.user)
        req.session['workspace_id'] = m.workspace.id
        messages.info(req, _('Přepnuto na "%(n)s".') % {'n': m.workspace.name})
        return redirect('core:dashboard')


class WorkspaceSettingsView(LoginRequiredMixin, View):
    def get(self, req):
        ws = req.workspace
        if not ws: return redirect('core:workspace_pick')
        form = WorkspaceForm(instance=ws)
        members = Membership.objects.filter(workspace=ws).select_related('user')
        invites = Invite.objects.filter(workspace=ws, is_active=True)
        invite_form = InviteForm()
        return render(req, 'core/workspace/settings.html', {
            'form': form, 'members': members, 'invites': invites,
            'invite_form': invite_form, 'is_owner': ws.owner == req.user})

    def post(self, req):
        ws = req.workspace
        if not ws or ws.owner != req.user:
            messages.error(req, _('Nemáte oprávnění.'))
            return redirect('core:dashboard')
        form = WorkspaceForm(req.POST, instance=ws)
        if form.is_valid():
            form.save()
            messages.success(req, _('Nastavení uloženo.'))
        return redirect('core:workspace_settings')


class InviteCreateView(LoginRequiredMixin, View):
    def post(self, req):
        ws = req.workspace
        if not ws: return redirect('core:workspace_pick')
        form = InviteForm(req.POST)
        if form.is_valid():
            inv = form.save(commit=False)
            inv.workspace = ws
            inv.created_by = req.user
            inv.save()
            messages.success(req, _('Pozvánka vytvořena! Kód: %(c)s') % {'c': inv.code})
        return redirect('core:workspace_settings')


class InviteRevokeView(LoginRequiredMixin, View):
    def post(self, req, pk):
        inv = get_object_or_404(Invite, pk=pk, workspace=req.workspace)
        inv.is_active = False
        inv.save()
        messages.info(req, _('Pozvánka zrušena.'))
        return redirect('core:workspace_settings')


class JoinWorkspaceView(View):
    def get(self, req, code):
        inv = get_object_or_404(Invite, code=code)
        if not inv.is_valid:
            messages.error(req, _('Pozvánka je neplatná nebo vypršela.'))
            return redirect('core:login')
        return render(req, 'core/workspace/join.html', {'invite': inv})

    def post(self, req, code):
        inv = get_object_or_404(Invite, code=code)
        if not inv.is_valid:
            messages.error(req, _('Pozvánka je neplatná nebo vypršela.'))
            return redirect('core:login')

        if not req.user.is_authenticated:
            # Store invite code in session and redirect to register
            req.session['pending_invite'] = code
            messages.info(req, _('Nejprve se zaregistrujte nebo přihlaste.'))
            return redirect('core:register')

        # Join workspace
        m, created = Membership.objects.get_or_create(
            workspace=inv.workspace, user=req.user,
            defaults={'role': inv.role}
        )
        if created:
            inv.uses += 1
            inv.save()
            req.session['workspace_id'] = inv.workspace.id
            messages.success(req, _('Připojeni k "%(n)s"!') % {'n': inv.workspace.name})
        else:
            messages.info(req, _('Již jste členem tohoto prostoru.'))
            req.session['workspace_id'] = inv.workspace.id

        return redirect('core:dashboard')


class MemberRemoveView(LoginRequiredMixin, View):
    def post(self, req, pk):
        ws = req.workspace
        if not ws or ws.owner != req.user:
            messages.error(req, _('Nemáte oprávnění.'))
            return redirect('core:workspace_settings')
        m = get_object_or_404(Membership, pk=pk, workspace=ws)
        if m.user == ws.owner:
            messages.error(req, _('Nelze odebrat vlastníka.'))
        else:
            m.delete()
            messages.success(req, _('Člen odebrán.'))
        return redirect('core:workspace_settings')


class MemberRoleView(LoginRequiredMixin, View):
    def post(self, req, pk):
        ws = req.workspace
        if not ws or ws.owner != req.user:
            messages.error(req, _('Nemáte oprávnění.'))
            return redirect('core:workspace_settings')
        m = get_object_or_404(Membership, pk=pk, workspace=ws)
        new_role = req.POST.get('role')
        if new_role in dict(Membership.Role.choices) and m.user != ws.owner:
            m.role = new_role
            m.save()
            messages.success(req, _('Role změněna.'))
        return redirect('core:workspace_settings')


# ==================== Dashboard ====================

class DashboardView(WsMixin, TemplateView):
    template_name = 'core/dashboard.html'
    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ws = self.get_ws()
        if not ws: return ctx
        ctx.update({
            'total_persons': Person.objects.filter(workspace=ws, is_active=True).count(),
            'total_rels': Relationship.objects.filter(person_from__workspace=ws).count(),
            'total_docs': Document.objects.filter(person__workspace=ws).count(),
            'total_tags': Tag.objects.filter(workspace=ws).count(),
            'total_groups': Group.objects.filter(workspace=ws).count(),
            'favorites': Person.objects.filter(workspace=ws, is_favorite=True, is_active=True)[:6],
            'recent': Person.objects.filter(workspace=ws, is_active=True).order_by('-created_at')[:8],
            'tags': Tag.objects.filter(workspace=ws).annotate(cnt=Count('persons')),
            'groups': Group.objects.filter(workspace=ws).annotate(cnt=Count('members')),
            'activity': ActivityLog.objects.filter(workspace=ws)[:10],
        })
        return ctx


# ==================== Person ====================

class PersonListView(WsMixin, ListView):
    model = Person; template_name = 'core/person_list.html'; context_object_name = 'persons'
    def get_queryset(self):
        ws = self.get_ws()
        qs = Person.objects.filter(workspace=ws, is_active=True).prefetch_related('tags', 'groups')
        f = SearchForm(self.request.GET, workspace=ws)
        if f.is_valid():
            q = f.cleaned_data.get('q')
            if q:
                qs = qs.filter(Q(first_name__icontains=q)|Q(last_name__icontains=q)|
                    Q(nickname__icontains=q)|Q(company__icontains=q)|Q(notes__icontains=q))
            if f.cleaned_data.get('tag'): qs = qs.filter(tags=f.cleaned_data['tag'])
            if f.cleaned_data.get('group'): qs = qs.filter(groups=f.cleaned_data['group'])
            if f.cleaned_data.get('favorites_only'): qs = qs.filter(is_favorite=True)
        qs = qs.distinct()
        pp = getattr(settings, 'PERSONDB_PER_PAGE', 24)
        pag = Paginator(qs, pp)
        self.page_obj = pag.get_page(self.request.GET.get('page', 1))
        return self.page_obj
    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['search_form'] = SearchForm(self.request.GET, workspace=self.get_ws())
        ctx['page_obj'] = self.page_obj
        return ctx


class PersonDetailView(WsMixin, DetailView):
    model = Person; template_name = 'core/person_detail.html'; context_object_name = 'person'
    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        p = self.object
        ctx.update({
            'from_rels': p.rels_from.select_related('person_to').all(),
            'to_rels': p.rels_to.select_related('person_from').all(),
            'contacts': p.contacts.all(),
            'documents': p.documents.all(),
            'meta_json': json.dumps(p.metadata, indent=2, ensure_ascii=False) if p.metadata else '{}',
            'can_edit': self.can_edit(),
        })
        return ctx


class PersonCreateView(WsMixin, CreateView):
    model = Person; form_class = PersonForm; template_name = 'core/person_form.html'
    def get_form_kwargs(self):
        kw = super().get_form_kwargs(); kw['workspace'] = self.get_ws(); return kw
    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['title'] = _('Nová osoba')
        ctx['contact_formset'] = ContactFormSet(self.request.POST or None, prefix='c')
        return ctx
    def form_valid(self, form):
        ctx = self.get_context_data()
        cfs = ctx['contact_formset']
        if cfs.is_valid():
            p = form.save(commit=False); p.workspace = self.get_ws(); p.save(); form.save_m2m()
            cfs.instance = p; cfs.save()
            self.log('Osoba vytvořena', person=p, details={'name': str(p)})
            messages.success(self.request, _('Osoba vytvořena.'))
            return redirect(p.get_absolute_url())
        return self.render_to_response(ctx)


class PersonUpdateView(WsMixin, UpdateView):
    model = Person; form_class = PersonForm; template_name = 'core/person_form.html'
    def get_form_kwargs(self):
        kw = super().get_form_kwargs(); kw['workspace'] = self.get_ws(); return kw
    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['title'] = _('Upravit osobu')
        ctx['contact_formset'] = ContactFormSet(self.request.POST or None, instance=self.object, prefix='c')
        return ctx
    def form_valid(self, form):
        ctx = self.get_context_data()
        cfs = ctx['contact_formset']
        if cfs.is_valid():
            p = form.save(); cfs.save()
            self.log('Osoba upravena', person=p)
            messages.success(self.request, _('Osoba upravena.'))
            return redirect(p.get_absolute_url())
        return self.render_to_response(ctx)


class PersonDeleteView(WsMixin, DeleteView):
    model = Person; template_name = 'core/confirm_delete.html'; success_url = reverse_lazy('core:person_list')
    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['title'] = _('Smazat osobu')
        ctx['msg'] = _('Opravdu chcete smazat osobu "%(n)s"?') % {'n': self.object}
        return ctx


class ToggleFavView(WsMixin, View):
    def post(self, req, pk):
        ws = self.get_ws()
        p = get_object_or_404(Person, pk=pk, workspace=ws)
        p.is_favorite = not p.is_favorite; p.save(update_fields=['is_favorite'])
        if req.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'is_favorite': p.is_favorite})
        return redirect(p.get_absolute_url())


# ==================== Relationships ====================

class RelCreateView(WsMixin, CreateView):
    model = Relationship; form_class = RelationshipForm; template_name = 'core/relationship_form.html'
    def get_form_kwargs(self):
        kw = super().get_form_kwargs()
        kw['person_from'] = get_object_or_404(Person, pk=self.kwargs['person_pk'], workspace=self.get_ws())
        kw['workspace'] = self.get_ws()
        return kw
    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['person'] = get_object_or_404(Person, pk=self.kwargs['person_pk'], workspace=self.get_ws())
        ctx['title'] = _('Nový vztah')
        return ctx
    def form_valid(self, form):
        pf = get_object_or_404(Person, pk=self.kwargs['person_pk'], workspace=self.get_ws())
        form.instance.person_from = pf; r = form.save()
        self.log('Vztah přidán', person=pf, details={'to': str(r.person_to), 'type': r.get_relation_type_display()})
        messages.success(self.request, _('Vztah vytvořen.'))
        return redirect(pf.get_absolute_url())


class RelDeleteView(WsMixin, DeleteView):
    model = Relationship; template_name = 'core/confirm_delete.html'
    def get_queryset(self):
        return Relationship.objects.filter(person_from__workspace=self.get_ws())
    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['title'] = _('Smazat vztah'); ctx['msg'] = _('Opravdu smazat tento vztah?')
        return ctx
    def get_success_url(self): return self.object.person_from.get_absolute_url()


# ==================== Documents ====================

class DocCreateView(WsMixin, CreateView):
    model = Document; form_class = DocumentForm; template_name = 'core/document_form.html'
    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['person'] = get_object_or_404(Person, pk=self.kwargs['person_pk'], workspace=self.get_ws())
        ctx['title'] = _('Nový dokument')
        return ctx
    def form_valid(self, form):
        p = get_object_or_404(Person, pk=self.kwargs['person_pk'], workspace=self.get_ws())
        form.instance.person = p; d = form.save()
        self.log('Dokument přidán', person=p, details={'title': d.title})
        messages.success(self.request, _('Dokument nahrán.'))
        return redirect(p.get_absolute_url())


class DocDeleteView(WsMixin, DeleteView):
    model = Document; template_name = 'core/confirm_delete.html'
    def get_queryset(self):
        return Document.objects.filter(person__workspace=self.get_ws())
    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['title'] = _('Smazat dokument')
        ctx['msg'] = _('Opravdu smazat "%(n)s"?') % {'n': self.object.title}
        return ctx
    def get_success_url(self): return self.object.person.get_absolute_url()


# ==================== Tags & Groups ====================

class TagListView(WsMixin, ListView):
    model = Tag; template_name = 'core/tag_list.html'; context_object_name = 'tags'
    def get_queryset(self): return Tag.objects.filter(workspace=self.get_ws()).annotate(cnt=Count('persons'))

class TagDetailView(WsMixin, DetailView):
    model = Tag; template_name = 'core/tag_detail.html'
    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['persons'] = self.object.persons.filter(is_active=True); return ctx

class TagCreateView(WsMixin, CreateView):
    model = Tag; form_class = TagForm; template_name = 'core/generic_form.html'
    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs); ctx['title'] = _('Nový štítek'); return ctx
    def form_valid(self, form):
        t = form.save(commit=False); t.workspace = self.get_ws(); t.save()
        return redirect('core:tag_list')
    def get_success_url(self): return reverse('core:tag_list')

class TagUpdateView(WsMixin, UpdateView):
    model = Tag; form_class = TagForm; template_name = 'core/generic_form.html'
    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs); ctx['title'] = _('Upravit štítek'); return ctx
    def get_success_url(self): return reverse('core:tag_list')

class TagDeleteView(WsMixin, DeleteView):
    model = Tag; template_name = 'core/confirm_delete.html'; success_url = reverse_lazy('core:tag_list')
    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['title'] = _('Smazat štítek'); ctx['msg'] = _('Smazat "%(n)s"?') % {'n': self.object.name}
        return ctx


class GroupListView(WsMixin, ListView):
    model = Group; template_name = 'core/group_list.html'; context_object_name = 'groups'
    def get_queryset(self): return Group.objects.filter(workspace=self.get_ws()).annotate(cnt=Count('members'))

class GroupDetailView(WsMixin, DetailView):
    model = Group; template_name = 'core/group_detail.html'
    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['members'] = self.object.members.filter(is_active=True); return ctx

class GroupCreateView(WsMixin, CreateView):
    model = Group; form_class = GroupForm; template_name = 'core/generic_form.html'
    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs); ctx['title'] = _('Nová skupina'); return ctx
    def form_valid(self, form):
        g = form.save(commit=False); g.workspace = self.get_ws(); g.save()
        return redirect('core:group_list')

class GroupUpdateView(WsMixin, UpdateView):
    model = Group; form_class = GroupForm; template_name = 'core/generic_form.html'
    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs); ctx['title'] = _('Upravit skupinu'); return ctx
    def get_success_url(self): return reverse('core:group_list')

class GroupDeleteView(WsMixin, DeleteView):
    model = Group; template_name = 'core/confirm_delete.html'; success_url = reverse_lazy('core:group_list')


# ==================== Export / Import / Backup / Restore ====================

class ExportView(WsMixin, View):
    def get(self, req):
        ws = self.get_ws()
        data = {
            'workspace': ws.name,
            'persons': [p.to_json() for p in Person.objects.filter(workspace=ws).prefetch_related('tags','groups','contacts')],
            'tags': list(Tag.objects.filter(workspace=ws).values('name','color','icon','metadata')),
            'groups': list(Group.objects.filter(workspace=ws).values('name','description','color','metadata')),
            'relationships': [
                {'from_uuid': str(r.person_from.uuid), 'to_uuid': str(r.person_to.uuid),
                 'type': r.relation_type, 'description': r.description,
                 'started_at': str(r.started_at) if r.started_at else None,
                 'ended_at': str(r.ended_at) if r.ended_at else None,
                 'is_active': r.is_active, 'metadata': r.metadata}
                for r in Relationship.objects.filter(person_from__workspace=ws).select_related('person_from','person_to')
            ],
        }
        resp = HttpResponse(json.dumps(data, indent=2, ensure_ascii=False, default=str), content_type='application/json')
        resp['Content-Disposition'] = f'attachment; filename="persondb_{ws.name}_export.json"'
        return resp


class ImportView(WsMixin, View):
    def get(self, req): return render(req, 'core/import.html', {'form': ImportForm()})
    def post(self, req):
        ws = self.get_ws()
        form = ImportForm(req.POST, req.FILES)
        if not form.is_valid(): return render(req, 'core/import.html', {'form': form})
        try:
            data = json.loads(req.FILES['file'].read().decode('utf-8'))
        except Exception as e:
            messages.error(req, _('Chyba JSON: %(e)s') % {'e': str(e)})
            return render(req, 'core/import.html', {'form': form})
        cnt = {'p':0,'t':0,'g':0,'r':0}
        for td in data.get('tags', []):
            Tag.objects.get_or_create(workspace=ws, name=td['name'], defaults={
                'color': td.get('color','#00ff41'), 'icon': td.get('icon',''), 'metadata': td.get('metadata',{})})
            cnt['t'] += 1
        for gd in data.get('groups', []):
            Group.objects.get_or_create(workspace=ws, name=gd['name'], defaults={
                'description': gd.get('description',''), 'color': gd.get('color','#00ff41'), 'metadata': gd.get('metadata',{})})
            cnt['g'] += 1
        umap = {}
        for pd_item in data.get('persons', []):
            p, __ = Person.objects.update_or_create(uuid=pd_item.get('uuid'), defaults={
                'workspace': ws, 'first_name': pd_item.get('first_name',''), 'last_name': pd_item.get('last_name',''),
                'middle_name': pd_item.get('middle_name',''), 'nickname': pd_item.get('nickname',''),
                'gender': pd_item.get('gender','U'), 'bio': pd_item.get('bio',''), 'notes': pd_item.get('notes',''),
                'company': pd_item.get('company',''), 'job_title': pd_item.get('job_title',''),
                'metadata': pd_item.get('metadata',{}), 'is_favorite': pd_item.get('is_favorite', False)})
            a = pd_item.get('address', {})
            if a:
                p.address_street=a.get('street',''); p.address_city=a.get('city','')
                p.address_zip=a.get('zip',''); p.address_country=a.get('country',''); p.save()
            for tn in pd_item.get('tags', []): t,__=Tag.objects.get_or_create(workspace=ws, name=tn); p.tags.add(t)
            for gn in pd_item.get('groups', []): g,__=Group.objects.get_or_create(workspace=ws, name=gn); p.groups.add(g)
            for cd in pd_item.get('contacts', []):
                Contact.objects.get_or_create(person=p, contact_type=cd.get('type','other'),
                    value=cd.get('value',''), defaults={'label': cd.get('label',''),
                    'is_primary': cd.get('is_primary', False), 'metadata': cd.get('metadata',{})})
            umap[pd_item.get('uuid')] = p; cnt['p'] += 1
        for rd in data.get('relationships', []):
            fp, tp = umap.get(rd.get('from_uuid')), umap.get(rd.get('to_uuid'))
            if fp and tp:
                Relationship.objects.get_or_create(person_from=fp, person_to=tp,
                    relation_type=rd.get('type','other'), defaults={'description': rd.get('description',''),
                    'is_active': rd.get('is_active', True), 'metadata': rd.get('metadata',{})})
                cnt['r'] += 1
        messages.success(req, _('Import: %(p)s osob, %(t)s štítků, %(g)s skupin, %(r)s vztahů') % cnt)
        return redirect('core:dashboard')


class BackupView(WsMixin, View):
    def get(self, req):
        ws = self.get_ws()
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
            data = {
                'workspace': ws.name,
                'persons': [p.to_json() for p in Person.objects.filter(workspace=ws).prefetch_related('tags','groups','contacts')],
                'tags': list(Tag.objects.filter(workspace=ws).values('name','color','icon','metadata')),
                'groups': list(Group.objects.filter(workspace=ws).values('name','description','color','metadata')),
                'relationships': [
                    {'from_uuid': str(r.person_from.uuid), 'to_uuid': str(r.person_to.uuid),
                     'type': r.relation_type, 'description': r.description,
                     'started_at': str(r.started_at) if r.started_at else None,
                     'ended_at': str(r.ended_at) if r.ended_at else None,
                     'is_active': r.is_active, 'metadata': r.metadata}
                    for r in Relationship.objects.filter(person_from__workspace=ws).select_related('person_from','person_to')
                ],
                'documents': [
                    {'person_uuid': str(d.person.uuid), 'title': d.title, 'doc_type': d.doc_type,
                     'description': d.description, 'metadata': d.metadata, 'file_path': d.file.name if d.file else ''}
                    for d in Document.objects.filter(person__workspace=ws).select_related('person')
                ],
            }
            zf.writestr('data.json', json.dumps(data, indent=2, ensure_ascii=False, default=str))
            for p in Person.objects.filter(workspace=ws).exclude(photo='').exclude(photo__isnull=True):
                if p.photo and p.photo.storage.exists(p.photo.name):
                    try:
                        with p.photo.open('rb') as f: zf.writestr(f'media/{p.photo.name}', f.read())
                    except Exception: pass
            for d in Document.objects.filter(person__workspace=ws):
                if d.file and d.file.storage.exists(d.file.name):
                    try:
                        with d.file.open('rb') as f: zf.writestr(f'media/{d.file.name}', f.read())
                    except Exception: pass
        buf.seek(0)
        from datetime import datetime
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        resp = HttpResponse(buf.getvalue(), content_type='application/zip')
        resp['Content-Disposition'] = f'attachment; filename="persondb_{ws.name}_{ts}.zip"'
        return resp


class RestoreView(WsMixin, View):
    def get(self, req): return render(req, 'core/restore.html', {})
    def post(self, req):
        ws = self.get_ws()
        uploaded = req.FILES.get('file')
        if not uploaded: return render(req, 'core/restore.html', {'error': _('Vyberte soubor.')})
        try: zf = zipfile.ZipFile(io.BytesIO(uploaded.read()))
        except zipfile.BadZipFile: return render(req, 'core/restore.html', {'error': _('Neplatný ZIP.')})
        try:
            data = json.loads(zf.read('data.json').decode('utf-8'))
        except Exception as e:
            return render(req, 'core/restore.html', {'error': str(e)})

        cnt = {'p':0,'t':0,'g':0,'r':0,'d':0,'f':0}
        for td in data.get('tags',[]): Tag.objects.get_or_create(workspace=ws, name=td['name'], defaults={'color':td.get('color','#00ff41'),'icon':td.get('icon',''),'metadata':td.get('metadata',{})}); cnt['t']+=1
        for gd in data.get('groups',[]): Group.objects.get_or_create(workspace=ws, name=gd['name'], defaults={'description':gd.get('description',''),'color':gd.get('color','#00ff41'),'metadata':gd.get('metadata',{})}); cnt['g']+=1
        umap = {}
        for pd_item in data.get('persons',[]):
            p,__ = Person.objects.update_or_create(uuid=pd_item.get('uuid'), defaults={
                'workspace':ws,'first_name':pd_item.get('first_name',''),'last_name':pd_item.get('last_name',''),
                'middle_name':pd_item.get('middle_name',''),'nickname':pd_item.get('nickname',''),
                'gender':pd_item.get('gender','U'),'bio':pd_item.get('bio',''),'notes':pd_item.get('notes',''),
                'company':pd_item.get('company',''),'job_title':pd_item.get('job_title',''),
                'metadata':pd_item.get('metadata',{}),'is_favorite':pd_item.get('is_favorite',False)})
            a=pd_item.get('address',{})
            if a: p.address_street=a.get('street','');p.address_city=a.get('city','');p.address_zip=a.get('zip','');p.address_country=a.get('country','');p.save()
            for tn in pd_item.get('tags',[]): t,__=Tag.objects.get_or_create(workspace=ws,name=tn);p.tags.add(t)
            for gn in pd_item.get('groups',[]): g,__=Group.objects.get_or_create(workspace=ws,name=gn);p.groups.add(g)
            for cd in pd_item.get('contacts',[]):
                Contact.objects.get_or_create(person=p,contact_type=cd.get('type','other'),value=cd.get('value',''),
                    defaults={'label':cd.get('label',''),'is_primary':cd.get('is_primary',False),'metadata':cd.get('metadata',{})})
            umap[pd_item.get('uuid')]=p; cnt['p']+=1
        for rd in data.get('relationships',[]):
            fp,tp=umap.get(rd.get('from_uuid')),umap.get(rd.get('to_uuid'))
            if fp and tp: Relationship.objects.get_or_create(person_from=fp,person_to=tp,relation_type=rd.get('type','other'),defaults={'description':rd.get('description',''),'is_active':rd.get('is_active',True),'metadata':rd.get('metadata',{})}); cnt['r']+=1
        media_root = settings.MEDIA_ROOT
        for name in zf.namelist():
            if name.startswith('media/') and not name.endswith('/'):
                dest = os.path.join(media_root, name[6:])
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                with open(dest,'wb') as f: f.write(zf.read(name))
                cnt['f']+=1
        for pd_item in data.get('persons',[]):
            p=umap.get(pd_item.get('uuid'))
            if not p: continue
            for name in zf.namelist():
                if name.startswith(f'media/photos/{pd_item["uuid"]}/'):
                    rel=name[6:]
                    if not p.photo or p.photo.name!=rel: p.photo=rel; p.save(update_fields=['photo'])
                    break
        for dd in data.get('documents',[]):
            p=umap.get(dd.get('person_uuid')); fp=dd.get('file_path','')
            if p and fp:
                doc,created=Document.objects.get_or_create(person=p,title=dd.get('title',''),
                    defaults={'doc_type':dd.get('doc_type','other'),'description':dd.get('description',''),'metadata':dd.get('metadata',{}),'file':fp})
                if created: cnt['d']+=1
        zf.close()
        messages.success(req, _('Záloha obnovena: %(p)s osob, %(t)s štítků, %(g)s skupin, %(r)s vztahů, %(d)s dok, %(f)s souborů') % cnt)
        return redirect('core:dashboard')


# ==================== Network ====================

class NetworkMapView(WsMixin, TemplateView):
    template_name = 'core/network_map.html'
    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ws = self.get_ws()
        ctx['person_count'] = Person.objects.filter(workspace=ws, is_active=True).count()
        ctx['rel_count'] = Relationship.objects.filter(person_from__workspace=ws).count()
        return ctx


class NetworkDataView(WsMixin, View):
    def get(self, req):
        ws = self.get_ws()
        nodes = [{'id':p['id'],'label':f"{p['first_name']} {p['last_name']}",'fav':p['is_favorite']}
                 for p in Person.objects.filter(workspace=ws,is_active=True).values('id','first_name','last_name','is_favorite')]
        edges = [{'from':r['person_from_id'],'to':r['person_to_id'],'type':r['relation_type'],'active':r['is_active']}
                 for r in Relationship.objects.filter(person_from__workspace=ws).values('person_from_id','person_to_id','relation_type','is_active')]
        return JsonResponse({'nodes':nodes,'edges':edges})


class FullGraphDataView(WsMixin, View):
    def get(self, req):
        ws = self.get_ws()
        persons = Person.objects.filter(workspace=ws, is_active=True).prefetch_related('tags','groups')
        all_tags = list(Tag.objects.filter(workspace=ws).values('id','name','color','icon'))
        all_groups = list(Group.objects.filter(workspace=ws).values('id','name','color','description'))
        nodes = []
        for p in persons:
            ptags = list(p.tags.values('id','name','color'))
            pgroups = list(p.groups.values_list('id', flat=True))
            nodes.append({
                'id':p.id, 'label':f'{p.first_name} {p.last_name}', 'fav':p.is_favorite,
                'company':p.company or '', 'job_title':p.job_title or '',
                'tag_ids':[t['id'] for t in ptags], 'tag_names':[t['name'] for t in ptags],
                'tag_colors':[t['color'] for t in ptags], 'group_ids':list(pgroups),
            })
        edges = [{'from':r['person_from_id'],'to':r['person_to_id'],'type':r['relation_type'],'active':r['is_active']}
                 for r in Relationship.objects.filter(person_from__workspace=ws).values('person_from_id','person_to_id','relation_type','is_active')]
        return JsonResponse({'nodes':nodes,'edges':edges,'tags':all_tags,'groups':all_groups})

# ==================== Relationship Inference ====================

class InferenceSuggestionsView(WsMixin, TemplateView):
    template_name = 'core/inference.html'
    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ws = self.get_ws()
        ctx['suggestions'] = infer_relationships(ws)
        return ctx


class InferenceApplyView(WsMixin, View):
    def post(self, req):
        ws = self.get_ws()
        from_id = req.POST.get('from_id')
        to_id = req.POST.get('to_id')
        rtype = req.POST.get('type')
        reason = req.POST.get('reason', '')

        if from_id and to_id and rtype:
            pf = get_object_or_404(Person, pk=from_id, workspace=ws)
            pt = get_object_or_404(Person, pk=to_id, workspace=ws)
            rel, created = apply_suggestion(pf, pt, rtype, description=reason)
            if created:
                self.log('Vztah odvozen', person=pf,
                         details={'to': str(pt), 'type': rtype, 'reason': reason})
                messages.success(req, _('Vztah %(t)s mezi %(a)s a %(b)s vytvořen.') % {
                    't': rel.get_relation_type_display(), 'a': pf, 'b': pt})
            else:
                messages.info(req, _('Tento vztah již existuje.'))
        return redirect('core:inference')


class InferenceApplyAllView(WsMixin, View):
    def post(self, req):
        ws = self.get_ws()
        suggestions = infer_relationships(ws)
        count = 0
        for s in suggestions:
            rel, created = apply_suggestion(
                s['person_from'], s['person_to'],
                s['relation_type'], description=s['reason']
            )
            if created:
                count += 1
        if count:
            self.log('Hromadné odvození vztahů', details={'count': count})
            messages.success(req, _('Vytvořeno %(n)s nových vztahů.') % {'n': count})
        else:
            messages.info(req, _('Žádné nové vztahy k odvození.'))
        return redirect('core:inference')
