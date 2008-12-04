/*
    Based on orbited.js from the Orbited project.
*/


/********************************************************************/
/** settings **/
/* how long to wait after the connection is lost (server died) */
comet_restart_timeout = 8000;       // 5 seconds
/* if no keepalive in this time - reconnect */
comet_keepalive_timeout = 76*1000;  // 66 seconds with no data

/********************************************************************/



/********************************************************************/
/** comet engines **/
/*
    parameters:
        url - url string to connect to, should contain ? character
            inside, we're going to append &transport= to it.
        callback - user callback function
        server_reconnect - the function that is going to be called
            when the connection will be lost
    return value:
        - function that is going to destroy current conenction
          for garbage collecting
    */
safari = 0;
/* xhr stream, for firefox and safari */
function schedule_connection_xhr(url, callback, server_reconnect) {
    var boundary = '\r\n|O|\r\n';
    var xhr = null;
    var offset = 0;

    xhr = create_xhr();
    xhr.onreadystatechange = function() {
            if(xhr.readyState==4)
                server_reconnect(true);
            else if(xhr.readyState==3 && xhr.status==200) {
                /* skip initial padding */
                if(offset == 0){
                    offset = xhr.responseText.indexOf('\r\n\r\n');
                    if(offset == -1)
                        offset = 0;
                    else
                        offset += 4;
                }
                while(true){
                    if(!xhr || !xhr.responseText)
                        break;
                    var data = xhr.responseText.substr(offset);
                    var end = data.indexOf(boundary);
                    if(end == -1)
                        break;
                    offset = offset + end + boundary.length;
                    callback( decode_utf8(data.substr(0, end)) );
                }
            }
    }
    xhr.open('GET', url + '&transport=xhr', true);
    xhr.send(null);


    function xhr_gc(){
        if(xhr){
            try{
                xhr.onreadystatechange=function () {};
                xhr.abort();
            }catch(e){};
        }
        delete(xhr);
        delete(offset);
        offset = null;
        xhr = null;
    };

    if(safari == 1){
        /* kill loading bar on safari */
        function f(){
            xhr.abort();
            server_reconnect(false);
        }
        setTimeout(f, 500);
        safari = 2;
    }

    return xhr_gc;
}


/* long polling */
function schedule_connection_longpoll(url, callback, server_reconnect) {
    var xhr = null;
    var eid = 0;
    var schedule = function(){
        if(xhr){
            try{
                xhr.onreadystatechange=function () {};
                xhr.abort();
            }catch(e){};
            try{
                delete(xhr);
            }catch(e){};
        }
        xhr = create_xhr();
        xhr.onreadystatechange = function() {
                if(xhr.readyState==4){
                    if(xhr.status==200){
                        eid += 1;
                        var data = xhr.responseText;
                        if(schedule)
                            schedule();

                        callback( data );
                    }else
                        server_reconnect(true);
                }
        }

        xhr.open('GET', url + '&transport=longpoll&eid=' + eid, true);
        xhr.send(null);
    };

    schedule();

    function xhr_gc(){
        if(xhr){
            try{
                xhr.onreadystatechange=function () {};
                xhr.abort();
            }catch(e){};
        }
        delete(xhr);
        xhr = null;
        delete(schedule);
        schedule = null;
    };

    return xhr_gc;
}



/* htmlfile, for ie */
function schedule_connection_htmlfile(url, user_callback, server_reconnect) {
    var i=0; while(window['c'+i] != undefined) i += 1;
    var fname = 'c' + i;

    function recon(){
            server_reconnect(true);
    }
    window[fname] = user_callback;
    window[fname + '_reconnect'] = recon;

    var transferDoc = new ActiveXObject('htmlfile');
    transferDoc.open();
    transferDoc.write(
        '<html><script>\n' +
        '    document.domain = "' + document.domain + '";\n' +
        '</script></html>\n');
    transferDoc.close();
    var ifrDiv = transferDoc.createElement("div");
    transferDoc.parentWindow[fname] = user_callback;
    transferDoc.parentWindow[fname +'_reconnect'] = recon;
    transferDoc.body.appendChild(ifrDiv);
    ifrDiv.innerHTML = "<iframe src='" + url +
                            '&transport=htmlfile'+
                            '&domain=' + document.domain +
                            '&callback=' + fname +
                            "' ></iframe>";


    // for ie 6
    kill_load_bar();
    function htmlfile_close() {
        if(transferDoc){
            transferDoc.body.removeChild(ifrDiv);
        }
        delete(ifrDiv);
        ifrDiv = null;
        delete(trasferDoc);
        transferDoc = null;
        window[fname] = null;
        window[fname+'_reconnect'] = null;
        CollectGarbage();
    }
    document.attachEvent('on'+'unload', htmlfile_close);
    window.attachEvent('on'+'unload', htmlfile_close);
    return htmlfile_close;
}

/* iframe, fallback for konqueror */
function schedule_connection_iframe(url, user_callback, server_reconnect) {
    var i=0; while(window['c'+i] != undefined) i += 1;
    var fname = 'c' + i;

    window[fname] = function (data){
        user_callback(data);
        kill_load_bar();
    }
    window[fname + '_reconnect'] =  function(){
            server_reconnect(true);
    }

    var ifr = document.createElement('iframe');
    hide_iframe(ifr);
    ifr.setAttribute('src',  url +
                            '&transport=iframe'+
                            '&callback=' + fname );
    document.body.appendChild(ifr);
    kill_load_bar();

    return function () {
        if(ifr)
            document.body.removeChild(ifr);
        delete(ifr);
        ifr=null;
        window[fname] = null;
        window[fname+'_reconnect'] = null;
    };
}
function hide_iframe(ifr) {
    ifr.style.display = 'block';
    ifr.style.width = '0';
    ifr.style.height = '0';
    ifr.style.border = '0';
    ifr.style.margin = '0';
    ifr.style.padding = '0';
    ifr.style.overflow = 'hidden';
    ifr.style.visibility = 'hidden';
}




/* server_sent_events for opera */
function schedule_connection_sse(url, callback) {
    var es = document.createElement('event-source');
    es.setAttribute('src', url +"&transport=sse");
    document.body.appendChild(es);

    var last_event = '';
    var event_callback = function (event){
        if(last_event == event.data){
            comet_log('REPEATED EVENT: ' + event.data);
            // OPERA SUCKS!
            /*
            s = '';
            for(k in event)
                s+= ' ' + k;

            comet_log(s);
            */
            return;
        }
        if(callback){
            if(event.data)
                callback(decode_utf8(unescape(event.data)));
        }

        last_event = event.data;
        //event.data=null;
    };

    es.addEventListener('payload',   event_callback, false);


    return function () {
        if(es){
            es.removeEventListener('payload',   event_callback, false);
            document.body.removeChild(es);
            es.src='';
        }
        event_callback=null;
        delete(es);
        es = null;
    };
}


comet_transports = {
    xhr:    schedule_connection_xhr,
    xhrstream:    schedule_connection_xhr,
    longpoll:     schedule_connection_longpoll,
    htmlfile: schedule_connection_htmlfile,
    iframe: schedule_connection_iframe,
    sse:    schedule_connection_sse
};
/********************************************************************/
/** find proper transport for current browser **/
function guess_transport() {
    // IF we're on IE 5.01/5.5/6/7 we want to use an htmlfile
    try {
        var test = ActiveXObject;
        return 'htmlfile';
    }catch (e) {}

    // If the browser supports server-sent events, we should use those
    if ((typeof window.addEventStream) == 'function') {
        return 'sse';
    }

    if( navigator.userAgent.indexOf('Konqueror')!= -1)
        return 'iframe';

    if( navigator.userAgent.indexOf('Safari')!= -1 ||  navigator.userAgent.indexOf('Webkit')!= -1){
        safari = 1;
        return 'xhr';
    }

    return 'xhr';
}

transport_global = guess_transport();



/********************************************************************/
/** The Most Important Function. schedule connection for user **/
/*
    url - static url or function that returns url
    user_callback - callback function, is going to be called each time with
            one parameter - data
    */
function comet_connection(url, user_callback_o, transport_local) {
    var keepalive_timer = null;
    var connect_function = null;
    var garbage_function = null;
    var comet_transport = '';
    function get_url(url){
        var c = url;
        if(typeof(url) == "function")
            c = url();

        if(c.indexOf('?') == -1)
            c = c + '?a=' + Math.random();
        return c;
    }
    function user_callback(data){
        /*
        if(strip(data) == '' || data == 'ping'){
            //comet_log('comet: got keepalive');
            return;
        }
        */
        //comet_log('comet: got data length:' + data.length);
        if(typeof(data) != "string" && typeof(data)!="String")
            data = '';
        user_callback_o(data);
    }
    function server_reconnect(conn_broken) {
            if(conn_broken == true){
                if(garbage_function)
                    garbage_function();
                garbage_function = null;

                comet_log('comet: '+comet_transport +' conn broken, reconnecting in '+ comet_restart_timeout +'....');
                setTimeout(function () {
                    garbage_function = connect_function(get_url(url), callback, server_reconnect);
                }, comet_restart_timeout);
            }else{
                comet_log('comet: '+comet_transport +' no keepalive reconnecting now...');
                if(garbage_function)
                    garbage_function();
                garbage_function = null;
                garbage_function = connect_function(get_url(url), callback, server_reconnect);
            }
            update_keepalive();
    }
    function update_keepalive() {
            clearTimeout(keepalive_timer);
            keepalive_timer = setTimeout( server_reconnect, comet_keepalive_timeout);
    }
    keepalive_timer = setTimeout( server_reconnect, comet_keepalive_timeout);

    var callback = function (data){
        update_keepalive();
        user_callback(data);
    };

    if(!transport_local){
        comet_transport = transport_global;
    }else{
        comet_transport = transport_local;
    }
    comet_log('comet: using transport:' + comet_transport +'  restart_timeout:' + comet_restart_timeout + ' keepalive_timeout:' + comet_keepalive_timeout);
    connect_function = comet_transports[comet_transport];

    if(!connect_function){
        comet_log('comet: bad transport: '+ comet_transport);
        return null;
    }

    garbage_function = connect_function(get_url(url), callback, server_reconnect);
    return function (){
        clearTimeout(keepalive_timer);
        if(garbage_function)
            garbage_function();
        if(comet_log)
            comet_log('comet: cleaning connection');
    }
}




/********************************************************************/
function comet_schedule_crossdomain(iframe_uri, comet_uri, user_callback){
    var i=0; while(window['c'+i] != undefined) i += 1;
    var fname = 'c' + i;

    comet_log('cometcrossdomain: started');

    window[fname] = user_callback;
    window[fname + '_uri'] = comet_uri;

    if(iframe_uri.indexOf('?') == -1)
        iframe_uri = iframe_uri + '?a=' + Math.random()

    var ifr = document.createElement('iframe');
    hide_iframe(ifr);
    ifr.setAttribute('src',  iframe_uri +
                            '&callback=' + fname);
    document.body.appendChild(ifr);
    function garbc(){
        if(ifr){
            comet_log('cometcrossdomain: stopped');
            var doc = ifr.contentDocument;
            if(doc == undefined || doc == null){
                doc = null;
                if(ifr.contentWindow)
                    doc = ifr.contentWindow.document;
            }
            if(doc && doc.comet_garbage){
                doc.comet_garbage();
            }
            document.body.removeChild(ifr);
            delete(ifr);
            ifr=null;
        }

        window[fname] = null;
        window[fname + '_uri'] = null;
    }
    if(window.addEventListener){
        document.addEventListener('unload', garbc, false);
        window.addEventListener('unload', garbc, false);
    } else { // IE
        document.attachEvent('onunload', garbc);
        window.attachEvent('onunload', garbc);
    }
    return garbc;
}


/********************************************************************/
function ajax_crossdomain(iframe_uri, method, ajax_uri, user_callback, post_data){
    var i=0; while(window['ajc'+i] != undefined) i += 1;
    var fname = 'ajc' + i;
    var ifr;

    if(iframe_uri.indexOf('?') == -1)
        iframe_uri = iframe_uri + '?a=' + Math.random()

    function gc(){
        document.body.removeChild(ifr);
        delete(ifr);
        ifr=null;
        window[fname] = null;
        window[fname + '_method']    = null;
        window[fname + '_ajax_uri']  = null;
        window[fname + '_post_data'] = null;
    }

    function callback(o){
        if(user_callback)
            user_callback(o);
        gc();
    }

    window[fname] = callback;
    window[fname + '_method']    = method;
    window[fname + '_ajax_uri']  = ajax_uri;
    window[fname + '_post_data'] = post_data;

    ifr = document.createElement('iframe');
    hide_iframe(ifr);
    ifr.setAttribute('src',  iframe_uri +
                            '&callback=' + fname);
    document.body.appendChild(ifr);
    kill_load_bar();
    return gc;
}



