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

/* xhr stream, for firefox and safari */
function schedule_connection_xhr(url, callback, server_reconnect) {
    var boundary = '\r\n|O|\r\n';
    var xhr = null;
    var offset = 0;

    var onreadystatechange = function(event) {
            if(!xhr)
                return;
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
    xhr = comet_create_ajax(url + '&transport=xhr', 'GET', null, onreadystatechange);

    function xhr_gc(){
        if(xhr){
            try{
                xhr.onreadystatechange=function () {};
                xhr.abort();
            }catch(e){};
            delete(xhr);
            delete(offset);
            offset = null;
            xhr = null;
        }
    };
    
    comet_attach_unload_event(xhr_gc);
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
        var onreadystatechange = function() {
                if(!xhr)
                    return;
                if(xhr.readyState==4){
                    if(xhr.status==200){
                        eid += 1;
                        var data = xhr.responseText;
                        if(schedule)
                            schedule();

                        callback( data );
                    }else{
                        server_reconnect(true);
                    }
                }
        }
        xhr = comet_create_ajax(url + '&transport=longpoll&eid=' + eid, 'GET', null, onreadystatechange)
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
        window[fname] = function(){};
        window[fname+'_reconnect'] = function(){};
        if(transferDoc){
            transferDoc.body.removeChild(ifrDiv);
            delete(trasferDoc);
            transferDoc = null;
        }
        if(ifrDiv){
            delete(ifrDiv);
            ifrDiv = null;
        }
        try{
            CollectGarbage();
        }catch(e){};
    }
    comet_attach_unload_event(htmlfile_close);
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
    var gc = function () {
        window[fname] = function(){};
        window[fname+'_reconnect'] = function(){};
        if(ifr){
            document.body.removeChild(ifr);
            delete(ifr);
            ifr=null;
        }
        try{
            CollectGarbage();
        }catch(e){};
    };
    comet_attach_unload_event(gc);
    return gc;
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




/* server_sent_events for opera
opera 9.60 is delivering messages _TWICE_.
to fix that we need to keep track on messages. fuck.
If they will fix it, it's going to be a huge memory drainer.
*/
function schedule_connection_sse(url, callback) {
    var es = document.createElement('event-source');
    es.setAttribute('src', url +"&transport=sse");
    // without this check opera 9.5 would make two connections.
    if (opera.version() < 9.5) {
        document.body.appendChild(es);
    }

    var event_callback = function (event){
        if(callback){
            if(event.data)
                callback(decode_utf8(unescape(event.data)));
        }
    };

    es.addEventListener('payload',   event_callback, false);


    var gc = function () {
        if(es){
            es.removeEventListener('payload',   event_callback, false);
            if (opera.version() < 9.5) {
                document.body.removeChild(es);
            }
            es.src='';
        }
        callback=null;
        event_callback=null;
        delete(es);
        es = null;
    };
    return gc;
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
        return 'xhrstream';
    }

    return 'xhrstream';
}

transport_global = guess_transport();



function comet_connection(url, user_callback_o, transport_local) {
    // due to safari bug, we need to do actual stuff after setTimeout
    var gc; // closure
    function foo(){
        gc = comet_connection_original(url, user_callback_o, transport_local);
    }
    if(comet_after_load_event == false)
        comet_attach_load_event(function(){setTimeout(foo,250);});
    else
        foo();

    return function(){
        if(gc)
            gc();
        else
            comet_log("don't cancel connection so fast!");
    }
}

/********************************************************************/
/** The Most Important Function. schedule connection for user **/
/*
    url - static url or function that returns url
    user_callback - callback function, is going to be called each time with
            one parameter - data
    */
function comet_connection_original(url, user_callback_o, transport_local) {
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
    var xx = function (){
        clearTimeout(keepalive_timer);
        if(garbage_function)
            garbage_function();
        if(comet_log)
            comet_log('comet: cleaning connection');
    }
    return xx;
}




/********************************************************************/
function comet_crossdomain_connection(iframe_uri, comet_uri, user_callback, transport){
    var i=0; while(window['c'+i] != undefined) i += 1;
    var fname = 'c' + i;
    var transportstr = '';
    if(transport)
        transportstr = '&transport=' + transport;

    comet_log('cometcrossdomain: started');
    window[fname] = user_callback;
    window[fname + '_uri'] = comet_uri;

    if(iframe_uri.indexOf('?') == -1)
        iframe_uri = iframe_uri + '?a=' + Math.random()

    var ifr = document.createElement('iframe');
    hide_iframe(ifr);
    ifr.setAttribute('src',  iframe_uri +
                            '&callback=' + fname + transportstr);
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
            try{
            if(doc && doc.comet_garbage)
                doc.comet_garbage();
            }catch(e){};
            document.body.removeChild(ifr);
            delete(ifr);
            ifr=null;
        }
        window[fname] = function(){};
        window[fname + '_uri'] = null;
    }
    comet_attach_unload_event(garbc);
    return garbc;
}


/********************************************************************/
function comet_create_crossdomain_ajax(iframe_uri, ajax_uri, method, post_data, user_callback, mimetype) {
    var queue_key = escape(iframe_uri) + '_queue';
    var garbc_key = escape(iframe_uri) + '_garbc';
    var push_key  = escape(iframe_uri) + '_push';
    if(window[queue_key] == undefined){
        window[queue_key] = [];
        window[push_key] = function(){};
    }

    var v = [ajax_uri, method, post_data, user_callback, mimetype];
    window[queue_key] = ([v]).concat(window[queue_key]);
    window[push_key]();

    if(window[garbc_key] == undefined) {
        window[garbc_key] = comet_create_crossdomain_ajax_iframe(iframe_uri);
    }
}

function comet_create_crossdomain_ajax_iframe(iframe_uri) {
    var i=0; while(window['ajc'+i] != undefined) i += 1;
    var fname = 'ajc' + i;
    var ifr;
    window[fname] = escape(iframe_uri);
    var queue_key = fname + '_data';


    if(iframe_uri.indexOf('?') == -1)
        iframe_uri = iframe_uri + '?a=' + Math.random()

    ifr = document.createElement('iframe');
    hide_iframe(ifr);
    ifr.setAttribute('src',  iframe_uri +
                            '&callback=' + fname);
    document.body.appendChild(ifr);
    kill_load_bar();

    var garbc = function(){
        if(ifr){
            document.body.removeChild(ifr);
            delete(ifr);
            ifr=null;
        }
        window[fname] = null;
    }
    comet_attach_unload_event(garbc);
    return garbc;
}




/********************************************************************/
/** various helpers **/
/********************************************************************/
function strip(str) {
    return str.replace(/^\s*(.*?)\s*$/, "$1");
    return(str);
}

function getURLParam(strParamName){
    var strReturn = "";
    var strHref = window.location.href;
    if ( strHref.indexOf("?") > -1 ){
        var strQueryString = strHref.substr(strHref.indexOf("?")).toLowerCase();
        var aQueryString = strQueryString.split("&");
            for ( var iParam = 0; iParam < aQueryString.length; iParam++ ){
            if(aQueryString[iParam].indexOf(strParamName.toLowerCase() + "=") > -1 ){
                var aParam = aQueryString[iParam].split("=");
                strReturn = aParam[1];
                break;
            }
        }
    }
    return unescape(strReturn);
}


function comet_log(arg){
    arg = '' + arg;
    arg = arg.substr(0, 512);
    if (typeof window.console !== 'undefined') {
      console.log(arg);
    }
    else if (typeof window.opera !== 'undefined') {
      opera.postError(arg);
    }else if (window['YAHOO'] && YAHOO.log){
        YAHOO.log(arg, 'info');
    }/*else
        alert(arg);
    */
}

function comet_raw_xhr() {
    // also interesting: http://keelypavan.blogspot.com/2006/03/reusing-xmlhttprequest-object-in-ie.html
    try { return new ActiveXObject('MSXML3.XMLHTTP'); } catch(e) {}
    try { return new ActiveXObject('MSXML2.XMLHTTP.3.0'); } catch(e) {}
    try { return new ActiveXObject('Msxml2.XMLHTTP'); } catch(e) {}
    try { return new ActiveXObject('Microsoft.XMLHTTP'); } catch(e) {}
    try { return new XMLHttpRequest(); } catch(e) {}
    throw new Error('Could not find XMLHttpRequest or an alternative.');
}



function comet_create_xhr() {
    var xhr = comet_raw_xhr();
    // stolen from http://blog.mibbit.com/?p=143
    function safeSet(k, v) {
        try {
            xhr.setRequestHeader(k, v);
        } catch(e) {}
    }

    safeSet("User-Agent", null);
    safeSet("Accept", null);
    safeSet("Accept-Language", null);
    safeSet("Content-Type", "M");
    safeSet("Connection", "keep-alive");
    safeSet("Keep-Alive", null);
    return(xhr);
}

function comet_create_ajax(url, method, data, onreadycallback, mimetype) {
    var xhr = comet_create_xhr();

    /*
    try { 
        netscape.security.PrivilegeManager.enablePrivilege('UniversalBrowserRead');
    } catch (ex) { } 
    */
    xhr.open(method, url, true);
    if(data){
        if(!mimetype)
            mimetype = "application/x-www-form-urlencoded";
        try{
            xhr.setRequestHeader("Content-type", mimetype);
        }catch(e){};
        try{
           xhr.setRequestHeader("Content-length", data.length);
        }catch(e){};
    }
    xhr.onreadystatechange = onreadycallback;
    /*
    function(){
        if(onreadycallback)
            onreadycallback();
        if(xhr.readyState==4){
            // especially for explorer
            try{
                xhr.abort();
            }catch(e){};
            delete(xhr);
            xhr = null;
            try{
                CollectGarbage();
            }catch(e){};
        }
    }
    */

    xhr.send(data);
    return(xhr);
}


load_kill_ifr = null;
function  kill_load_bar() {
    if (load_kill_ifr == null) {
      load_kill_ifr = document.createElement('iframe');
      hide_iframe(load_kill_ifr);
    }
    document.body.appendChild(load_kill_ifr);
    load_kill_ifr.src = 'about:blank';
    document.body.removeChild(load_kill_ifr);
}

function comet_attach_unload_event(foo){
    if(window.addEventListener){
        document.addEventListener('unload', foo, false);
        window.addEventListener('unload', foo, false);
    } else { // IE
        document.attachEvent('onunload', foo);
        window.attachEvent('onunload', foo);
    }
}

// http://www.sitepoint.com/blogs/2004/05/26/closures-and-executing-javascript-on-page-load/
function comet_attach_load_event(fn){
    var oldfn = window.onload;
    if (typeof window.onload != 'function'){
        window.onload = fn;
    }else{
        window.onload = function(){
                oldfn();
                fn();
            };
    }
}

function extract_xss_domain(old_domain) {
    var domain_pieces = old_domain.split('.');
    if (domain_pieces.length === 4) {
        var is_ip = !isNaN(Number(domain_pieces.join('')));
        if (is_ip) {
            return old_domain;
        }
    }
    var new_domain = domain_pieces.slice(-2).join('.');
    var colon = old_domain.split(':');
    if(colon.length > 1)
        return new_domain + ':' + colon[1];
    return new_domain;
}

function encode_utf8( s )
{
    try{
        return unescape( encodeURIComponent( s ) );
    }catch(e){
        return(s);
    }
}

function decode_utf8( s )
{
    try{
        return decodeURIComponent( escape( s ) );
    }catch(e){
        return(s);
    }
}

comet_after_load_event = false;

comet_attach_load_event(function(){comet_after_load_event=true});

