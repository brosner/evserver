# Create your views here.
from django.http import HttpResponse
import socket
import datetime

def django_clock(request):
    def iterator():
        sd = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            while True:
                yield request.environ['x-wsgiorg.fdevent.readable'](sd, 1.0)
                yield '%s\n' % (datetime.datetime.now(),)
        except GeneratorExit:
            pass
        sd.close()
    return HttpResponse(iterator(), mimetype="text/plain")
