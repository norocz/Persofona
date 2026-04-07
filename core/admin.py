from django.contrib import admin
from .models import Person, Contact, Relationship, Document, Tag, Group, ActivityLog, Workspace, Membership, Invite

class ContactInline(admin.TabularInline):
    model = Contact; extra = 1

class DocInline(admin.TabularInline):
    model = Document; extra = 0

@admin.register(Person)
class PersonAdmin(admin.ModelAdmin):
    list_display = ['last_name','first_name','nickname','workspace','company','is_favorite','created_at']
    list_filter = ['workspace','is_favorite','is_active','gender','tags','groups']
    search_fields = ['first_name','last_name','nickname','company','notes']
    inlines = [ContactInline, DocInline]

@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ['name','workspace','color']
    list_filter = ['workspace']

@admin.register(Group)
class GroupAdmin(admin.ModelAdmin):
    list_display = ['name','workspace','color']
    list_filter = ['workspace']

@admin.register(Relationship)
class RelAdmin(admin.ModelAdmin):
    list_display = ['person_from','relation_type','person_to','is_active']
    list_filter = ['relation_type','is_active']

@admin.register(Workspace)
class WorkspaceAdmin(admin.ModelAdmin):
    list_display = ['name','owner','color','created_at']

@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ['user','workspace','role','joined_at']
    list_filter = ['role','workspace']

@admin.register(Invite)
class InviteAdmin(admin.ModelAdmin):
    list_display = ['code','workspace','role','uses','max_uses','is_active','expires_at']
    list_filter = ['is_active','workspace']

admin.site.register(ActivityLog)
