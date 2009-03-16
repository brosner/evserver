from django.conf.urls.defaults import *
from pkg_resources import resource_filename
import os.path
import django.views.static
import django.views.generic.simple

module_dir = resource_filename(__name__, '.')

urlpatterns = patterns('views',
    (r'^$', django.views.generic.simple.redirect_to, {'url':'start/'}),
    (r'^static/(?P<path>.*)$', django.views.static.serve,
        {'document_root': os.path.join(module_dir, 'static')}),
    (r'^(?P<key>\w{3,32})/$',           'document'),
    (r'^(?P<key>\w{3,32})/push/$',      'ajax_push'),
    (r'^(?P<key>\w{3,32})/pop/$',       'comet'),
)

