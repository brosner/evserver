#
# evserver --exec "import examples.framework_wsgi; application = examples.framework_wsgi.application"
# or just:
# evserver --framework=demo
import datetime
import socket


def application(environ, start_response):
    start_response("200 OK", [('Content-type','text/plain')])
    sd = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        while True:
            yield environ['x-wsgiorg.fdevent.readable'](sd, 1.0)
            yield "%s\n" % (datetime.datetime.now(),)
    except GeneratorExit:
        pass
    sd.close()
