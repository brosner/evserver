/** various helpers **/
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

function create_xhr() {
    try { return new ActiveXObject('MSXML3.XMLHTTP'); } catch(e) {}
    try { return new ActiveXObject('MSXML2.XMLHTTP.3.0'); } catch(e) {}
    try { return new ActiveXObject('Msxml2.XMLHTTP'); } catch(e) {}
    try { return new ActiveXObject('Microsoft.XMLHTTP'); } catch(e) {}
    try { return new XMLHttpRequest(); } catch(e) {}
    throw new Error('Could not find XMLHttpRequest or an alternative.');
}

load_kill_ifr = null;
function  kill_load_bar() {
    if (load_kill_ifr == null) {
      load_kill_ifr = document.createElement('iframe');
      hide_iframe(load_kill_ifr);
    }
    document.body.appendChild(this.load_kill_ifr);
    document.body.removeChild(this.load_kill_ifr);
}

function extract_xss_domain(old_domain) {
    domain_pieces = old_domain.split('.');
    if (domain_pieces.length === 4) {
        var is_ip = !isNaN(Number(domain_pieces.join('')));
        if (is_ip) {
            return old_domain;
        }
    }
    return domain_pieces.slice(-2).join('.');
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
