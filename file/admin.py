from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from . import models
from .models import User


class FileAdmin(admin.ModelAdmin):
    list_display = ('file', 'full_path',
                    'created_at', 'updated_at', 'content_type')


class FolderAdmin(admin.ModelAdmin):
    list_display = ('name', 'full_path',
                    'created_at', 'updated_at')


class AppTokenAdmin(admin.ModelAdmin):
    list_display = ('user', 'name', 'created_at', 'last_used_at')
    readonly_fields = ('token',)


class SharedFolderMembershipInline(admin.TabularInline):
    model = models.SharedFolderMembership
    extra = 1


class SharedFolderAdmin(admin.ModelAdmin):
    list_display = ('name', 'created_by', 'created_at')
    exclude = ('root_folder',)
    inlines = [SharedFolderMembershipInline]


class CustomUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ('Role', {'fields': ('role',)}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Role', {'fields': ('role',)}),
    )
    list_display = UserAdmin.list_display + ('role',)


class CalendarShareInline(admin.TabularInline):
    model = models.CalendarShare
    extra = 1


class CalendarAdmin(admin.ModelAdmin):
    list_display = ('owner', 'name', 'display_name', 'color', 'created_at')
    list_filter = ('owner',)
    inlines = [CalendarShareInline]


class EventAdmin(admin.ModelAdmin):
    list_display = ('uid', 'summary', 'calendar', 'dtstart', 'dtend', 'all_day')
    list_filter = ('calendar', 'all_day')
    search_fields = ('uid', 'summary', 'description')


class AddressBookShareInline(admin.TabularInline):
    model = models.AddressBookShare
    extra = 1


class AddressBookAdmin(admin.ModelAdmin):
    list_display = ('owner', 'name', 'display_name', 'created_at')
    list_filter = ('owner',)
    inlines = [AddressBookShareInline]


class ContactAdmin(admin.ModelAdmin):
    list_display = ('uid', 'fn', 'email', 'tel', 'addressbook')
    list_filter = ('addressbook',)
    search_fields = ('uid', 'fn', 'email', 'tel')


admin.site.register(User, CustomUserAdmin)
admin.site.register(models.File, FileAdmin)
admin.site.register(models.Folder, FolderAdmin)
admin.site.register(models.AppToken, AppTokenAdmin)
admin.site.register(models.SharedFolder, SharedFolderAdmin)
admin.site.register(models.Calendar, CalendarAdmin)
admin.site.register(models.Event, EventAdmin)
admin.site.register(models.AddressBook, AddressBookAdmin)
admin.site.register(models.Contact, ContactAdmin)
