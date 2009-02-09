from django.conf.urls.defaults import *
import django.views.static
from django.conf import settings
import views


urlpatterns = patterns('',
    (r'^static/(?P<path>.*)$', django.views.static.serve, {'document_root': settings.STATIC_DIR}),
    (r'^$', views.index),
    (r'^index.html$', views.index),
    (r'^comet/$', views.comet),
)

