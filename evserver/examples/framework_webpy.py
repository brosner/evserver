#
# evserver --exec "import examples.framework_webpy; application = examples.framework_webpy.application"
#
import web
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
        return iterable()

# webpy 0.3 specific
application = web.application(urls, globals()).wsgifunc()

