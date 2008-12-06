#
# evserver --exec "import examples.framework_webpy; application = examples.framework_webpy.application"
#
import web
import os
import datetime
import socket

urls = (
    '/(.*)', 'webpy_clock'
)

class webpy_clock:
    def GET(self, name):
        web.header('Content-Type','text/plain', unique=True)
        environ = web.ctx.environ
        def iterable():
            sd = socket.socket(socket.AF_INET, socket.SOCK_DGRAM) # any udp socket
            try:
                while True:
                    yield environ['x-wsgiorg.fdevent.readable'](sd, 1.0)
                    yield "%s\n" % (datetime.datetime.now(),)
            except GeneratorExit:
                pass
            sd.close()
        web.ctx.output = iterable()

# from http://code.google.com/p/modwsgi/wiki/IntegrationWithWebPy
try:
    # webpy 0.3
    application = web.application(urls, globals()).wsgifunc()
except AttributeError:
    # webpy 0.2
    application = web.wsgifunc(web.webpyfunc(urls, globals()))

