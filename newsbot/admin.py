import flask_admin as admin
import flask_login as login
from flask_admin.contrib.mongoengine import ModelView
from flask import redirect,url_for
from .models import Account, User, ChatUserAttribute, Invitation
from flask_admin.base import AdminIndexView


class UserView(ModelView):
    def is_accessible(self):
        if(login.current_user.role=='superadmin'): return True
        return False
    def inaccessible_callback(self, name, **kwargs):
        # redirect to login page if user doesn't have access
        return redirect('/')
    form_columns = ['name', 'email', 'accounts', 'role']
    column_list = ['name', 'email', 'accounts']
    column_filters = ['name']
    column_searchable_list = ('name', 'email')
    can_create = False
    can_delete = False


class AccountView(ModelView):
    def is_accessible(self):
        if(login.current_user.role=='superadmin'): return True
        return False
    def inaccessible_callback(self, name, **kwargs):
        # redirect to login page if user doesn't have access
        return redirect('/')
    column_filters = ['name']
    column_searchable_list = ('name',)

class MyHomeView(AdminIndexView):
    def is_accessible(self):
        if(login.current_user.role=='superadmin'): return True
        return False
    def inaccessible_callback(self, name, **kwargs):
        # redirect to login page if user doesn't have access
        return redirect('/')

class ChatUserAttributeView(ModelView):
    def is_accessible(self):
        if(login.current_user.role=='superadmin'): return True
        return False
    def inaccessible_callback(self, name, **kwargs):
        # redirect to login page if user doesn't have access
        return redirect('/')
    form_columns = ['attribute', 'type', 'options',]
    column_list = ['attribute', 'type', 'options',]

class InvitationView(ModelView):
    def is_accessible(self):
        if(login.current_user.role=='superadmin'): return True
        return False
    def inaccessible_callback(self, name, **kwargs):
        # redirect to login page if user doesn't have access
        return redirect('/')

admin = admin.Admin(name='Example: MongoEngine', template_mode='bootstrap3',index_view=MyHomeView())
admin.add_view(UserView(User))
admin.add_view(AccountView(Account))
admin.add_view(ChatUserAttributeView(ChatUserAttribute))
admin.add_view(InvitationView(Invitation))
