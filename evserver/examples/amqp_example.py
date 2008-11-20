"""
Based on Barry Pederson code.
"""
import sys
import time

import amqplib.client_0_8 as amqp
import amqplib.nbclient_0_8 as nbamqp

def publish(msg_body):
    conn = amqp.Connection('localhost', userid='guest', password='guest')

    ch = conn.channel()
    ch.access_request('/data', active=True, write=True)

    ch.exchange_declare('myfan', 'fanout', auto_delete=True)

    msg = amqp.Message(msg_body, content_type='text/plain', application_headers={'foo': 7, 'bar': 'baz'})

    ch.basic_publish(msg, 'myfan')

    ch.close()
    conn.close()



class MException:pass

# simple AMQP subscriber example
# very hackish, but works
def wsgi_subscribe(environ, start_response):
    start_response("200 OK", [('Content-type','text/plain')])

    def my_nb_callback(ch):
        raise MException
    conn = nbamqp.NonBlockingConnection('localhost', userid='guest', password='guest', nb_callback=my_nb_callback, nb_sleep=0.0)

    ch = conn.channel()
    ch.access_request('/data', active=True, read=True)

    ch.exchange_declare('myfans', 'fanout', auto_delete=True)
    qname, _, _ = ch.queue_declare()
    ch.queue_bind(qname, 'myfans')

    msgs = []
    def callback(msg):
        msgs.append( msg )

    ch.connection.sock.sock.setblocking(False)
    ch.basic_consume(qname, callback=callback)
    try:
        yield "Subscribed to AMQP\n"
        while True:
            msgs = []
            yield environ['x-wsgiorg.fdevent.readable'](ch.connection.sock.sock, 300.0)
            try:
                nbamqp.nbloop([ch])
            except MException:
                pass
            unique_msgs_filter = {}
            unique_msgs = []
            for msg in msgs:
                msg.channel.basic_ack(msg.delivery_tag)
                if msg.body not in unique_msgs_filter:
                    unique_msgs_filter[msg.body] = True
                    unique_msgs.append(msg.body)
            yield environ['x-wsgiorg.fdevent.writable'](ch.connection.sock.sock, 5.0)
            yield '%r ' % (unique_msgs)
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

    del ch.callbacks
    del conn.connection.channels
    del conn.connection
