from django.conf.urls import patterns, include, url

# Uncomment the next two lines to enable the admin:
# from django.contrib import admin
# admin.autodiscover()

urlpatterns = patterns('',
    # Examples:
    url(r'^$', 'daq328p.views.home', name='home'),
#     url(r'^query/(?P<cmd>[a-zA-Z0-9]+)$', 'daq328p.views.query', name='query'),
    url(r'^query/(?P<cmd>.*)$', 'daq328p.views.query', name='query'),
    url(r'^query', 'daq328p.views.query', name='query'),
    
    url(r'^cmd', 'daq328p.views.cmd', name='cmd'),
    
    # url(r'^daq328p/', include('daq328p.foo.urls')),

    # Uncomment the admin/doc line below to enable admin documentation:
    # url(r'^admin/doc/', include('django.contrib.admindocs.urls')),

    # Uncomment the next line to enable the admin:
    # url(r'^admin/', include(admin.site.urls)),
)
