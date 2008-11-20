# Create your views here.
from django.http import HttpResponse
import os
import time
import datetime

# basic clock example
def django_clock(request):
    def iter():
        fd = os.open('/dev/null', os.O_RDONLY)
        try:
            while True:
                yield request.environ['x-wsgiorg.fdevent.readable'](fd, 1.0)
                yield '%s\n' % (datetime.datetime.now(),)
        except GeneratorExit:
            pass
        os.close(fd)
    return HttpResponse(iter(), mimetype="text/plain")


