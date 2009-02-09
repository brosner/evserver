"""
Based on Barry Pederson code. Requires py-amqplib 0.6 package.

To run consumer server:
    evserver --exec="import evserver.examples.amqp06; application=evserver.examples.amqp06.wsgi_subscribe"
To produce message:
    python -c "import evserver.examples.amqp06; evserver.examples.amqp06.publish('Hello World')"
"""
import sys
import time
import os.path
import socket
import logging
log = logging.getLogger(os.path.basename(__file__))


import amqplib.client_0_8 as amqp
logging.getLogger('amqplib').setLevel(logging.INFO) # ignore msgs from there


def publish(msg_body):
    conn = amqp.Connection('localhost', userid='guest', password='guest')
    ch = conn.channel()
    ch.access_request('/data', active=True, write=True)
    ch.exchange_declare('myfan', 'fanout', auto_delete=True)

    msg = amqp.Message(msg_body, content_type='text/plain')
    ch.basic_publish(msg, 'myfan')

    ch.close()
    conn.close()


def set_ridiculously_high_buffers(sd):
    for flag in [socket.SO_SNDBUF, socket.SO_RCVBUF]:
        for i in range(10):
            bef = sd.getsockopt(socket.SOL_SOCKET, flag)
            sd.setsockopt(socket.SOL_SOCKET, flag, bef*2)
            aft = sd.getsockopt(socket.SOL_SOCKET, flag)
            if aft <= bef or aft >= 16777216: # 16M
                break



def wsgi_subscribe(environ, start_response):
    start_response("200 OK", [('Content-type','text/plain')])

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

    try:
        yield 'setting up an amqp connection took %.3fms\n' % ((time.time()-t0)*1000.0, )

        while ch.callbacks:
            t0 = time.time()
            try:
                while True: # until exception
                    ch.wait()
            except (TypeError,), e:
                pass

            yield '%.3fms: %r\n' % ((time.time()-t0)*1000.0, msgs)
            while msgs:
                msgs.pop()

            yield environ['x-wsgiorg.fdevent.readable'](conn.transport.sock)
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
    return


