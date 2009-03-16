# -*- coding: utf-8 -*-
from django.http import HttpResponse, HttpResponseRedirect

import evserver.other.django
import amqplib.client_0_8 as amqp
from broker import send_amqp_message
from django.shortcuts import render_to_response
import urllib
import socket


def document(request, key):
    key = urllib.quote(key)
    context = {
        'key': key.replace('%',''),
    }

    return render_to_response('index.html', context)


def index(request):
    return HttpResponse('Hello World!', mimetype="text/plain")


def ajax_push(request, key):
    key = urllib.quote(key)
    payload = request.raw_post_data
    if not isinstance(payload, unicode):
        payload = payload.encode('utf-8')

    payload = payload.replace('<', '&lt;').replace('>','&gt;')

    send_amqp_message(key, payload)

    return HttpResponse('ok', mimetype="text/plain")



def set_ridiculously_high_buffers(sd):
    for flag in [socket.SO_SNDBUF, socket.SO_RCVBUF]:
        for i in range(10):
            bef = sd.getsockopt(socket.SOL_SOCKET, flag)
            sd.setsockopt(socket.SOL_SOCKET, flag, bef*2)
            aft = sd.getsockopt(socket.SOL_SOCKET, flag)
            if aft <= bef or aft >= 16777216: # 16M
                break


@evserver.other.django.encapsulate_to_comet
def comet(request, key):
    key = urllib.quote(key)
    # setup the amqp subscriber
    msgs = []
    def callback(msg):
        msgs.append(msg.body)
        msg.channel.basic_ack(msg.delivery_tag)

    conn = amqp.Connection('localhost', userid='guest', password='guest')

    ch = conn.channel()
    ch.access_request('/data', active=True, read=True)

    ch.exchange_declare(key, 'fanout', auto_delete=True)
    qname, _, _ = ch.queue_declare()
    ch.queue_bind(qname, key,)
    ch.basic_consume(qname, callback=callback)

    sd = conn.transport.sock
    sd.setblocking(False)
    set_ridiculously_high_buffers(sd)

    def iterator():
        try:
            while ch.callbacks:
                try:
                    while True: # until exception
                        ch.wait()
                except (TypeError,), e:
                    pass

                if not msgs:
                    yield 'ping'
                while msgs:
                    msg = msgs.pop(0)
                    yield msg

                yield request.environ['x-wsgiorg.fdevent.readable'](conn.transport.sock, 60)
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

        ch.connection = None
        conn.channels = {}
        conn.connection = None
        conn.transport = None

    return HttpResponse(iterator())


