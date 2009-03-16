import amqplib.client_0_8 as amqp
import logging, os, os.path
log = logging.getLogger(os.path.basename(__file__))
logging.getLogger('amqplib').setLevel(logging.INFO) # ignore msgs from there

cache = {}
def send_amqp_message(key, msg_body):
    if 'conn' in cache:
        conn = cache['conn']
        ch = cache['ch']
    else:
        log.info('connecting to amqp')
        # conn should be cached
        conn = amqp.Connection('localhost', userid='guest', password='guest')
        ch = conn.channel()
        ch.access_request('/data', active=True, write=True)
        ch.exchange_declare(key, 'fanout',auto_delete=True)
        ch.exchange_declare('render', 'fanout', auto_delete=False)
        cache['conn'] = conn
        cache['ch'] = ch

    try:
        msg = amqp.Message(msg_body, content_type='text/plain')
        ch.basic_publish(msg, key)

    except Exception:
        log.info('connection to amqp failed')
        try:
            ch.close()
        except Exception: pass
        try:
            conn.close()
        except Exception: pass

        ch.connection = None
        conn.channels = {}
        conn.connection = None
        conn.transport = None
        del cache['conn']
        del cache['ch']
        return send_amqp_message(key, msg_body)
