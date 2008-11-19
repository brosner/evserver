#
# PYTHONPATH=. evserver --exec "import framework_webpy; application = framework_webpy.application"
#
import web
import os
import datetime

urls = (
    '/(.*)', 'webpy_clock'
)

class webpy_clock:
    def GET(self, name):
        web.header('Content-Type','text/plain', unique=True)
        def iterable():
            fd = os.open('/dev/null', os.O_RDONLY)
            try:
                while True:
                    yield web.ctx.environ['x-wsgiorg.fdevent.readable'](fd, 1.0)
                    yield "%s\n" % (datetime.datetime.now(),)
            except GeneratorExit:
                pass
            os.close(fd)
        web.ctx.output = iterable()

# from http://code.google.com/p/modwsgi/wiki/IntegrationWithWebPy
try:
    # webpy 0.3
    application = web.application(urls, globals()).wsgifunc()
except AttributeError:
    # webpy 0.2
    application = web.wsgifunc(web.webpyfunc(urls, globals()))

