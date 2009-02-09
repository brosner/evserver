'''
# PYTHONPATH="$HOME/evserver:$HOME/amqplib-0.6" 
 ./manage.py runevserver

or
 PYTHONPATH="$HOME/amqplib-0.6:.." DJANGO_SETTINGS_MODULE=django_agentpush.settings
 evserver --listen 127.0.0.1:8080 --framework=django

Beware, static files are served from ./static directory!
'''

from django.http import HttpResponse
from django.conf import settings

import socket
import datetime
import sys
import time
import os.path
import socket
import evserver.transports
import logging
import amqplib.client_0_8 as amqp
logging.getLogger('amqplib').setLevel(logging.INFO) # ignore msgs from there
log = logging.getLogger(os.path.basename(__file__))


cached_publisher_connection = None
cached_publisher_channel = None

def send_amqp_message(msg_body):
    global cached_publisher_connection, cached_publisher_channel
    if not cached_publisher_channel:
        conn = amqp.Connection('localhost', userid='guest', password='guest')
        ch = conn.channel()
        ch.access_request('/data', active=True, write=True)
        ch.exchange_declare('myfan', 'fanout', auto_delete=True)

        cached_publisher_connection = conn
        cached_publisher_channel = ch

    msg = amqp.Message(msg_body, content_type='text/plain')
    cached_publisher_channel.basic_publish(msg, 'myfan')


import cgi

# that is a raw hack that doesn't scale!
counter = 0
state_cache = []

def index(request):
    global counter
    counter += 1

    referer = request.META.get('HTTP_REFERER', '')
    agent = request.META.get('HTTP_USER_AGENT', '')
    msg = cgi.escape('#%i: %r %r' % (counter, referer, agent))
    send_amqp_message(msg)
    state_cache.append(msg)
    if len(state_cache) > 30: state_cache.pop(0) # remove first element

    f = open(os.path.join(settings.STATIC_DIR, 'index.html'), 'rb')
    data = f.read()
    f.close()

    return HttpResponse(data, mimetype="text/html")




def set_ridiculously_high_buffers(sd):
    for flag in [socket.SO_SNDBUF, socket.SO_RCVBUF]:
        for i in range(10):
            bef = sd.getsockopt(socket.SOL_SOCKET, flag)
            sd.setsockopt(socket.SOL_SOCKET, flag, bef*2)
            aft = sd.getsockopt(socket.SOL_SOCKET, flag)
            if aft <= bef or aft >= 16777216: # 16M
                break

def comet(request):
    t = evserver.transports.get_transport(request.GET.get('transport','basic'))

    # setup the amqp subscriber
    msgs = []
    def callback(msg):
        msgs.append(msg.body)
        msg.channel.basic_ack(msg.delivery_tag)

    t0 = time.time()
    conn = amqp.Connection('localhost', userid='guest', password='guest')

    ch = conn.channel()
    ch.access_request('/data', active=True, read=True)

    ch.exchange_declare('myfan', 'fanout', auto_delete=True)
    qname, _, _ = ch.queue_declare()
    ch.queue_bind(qname, 'myfan')
    ch.basic_consume(qname, callback=callback)

    sd = conn.transport.sock
    sd.setblocking(False)
    set_ridiculously_high_buffers(sd)

    def iterator():
        try:
            yield t.start()
            for msg in state_cache:# feed with the initial state
                yield t.write(msg)

            while ch.callbacks:
                try:
                    while True: # until exception
                        ch.wait()
                except (TypeError,), e:
                    pass

                while msgs:
                    msg = msgs.pop(0)
                    yield t.write(msg)

                yield request.environ['x-wsgiorg.fdevent.readable'](conn.transport.sock)
        except GeneratorExit:
            pass

        try:
            ch.close()
        except Exception:
            pass
        try:
            conn.close()
        except Exception:
            pass

    # build the response
    response = HttpResponse(iterator())
    for k, v in t.get_headers():
        response[k] = v
    return response


