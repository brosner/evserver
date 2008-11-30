var fromTo = new Array( '&amp;','&',
                                '&lt;', '<',
                                '&gt;', '>',
                                '&quot;', "\"");

function replaceExtChars(text) {
    for (i=0; i < fromTo.length; i=i+2)
        text = text.replace(eval('/'+fromTo[i+1]+'/g'), fromTo[i]);
    text = text.replace(/\n/g, '<br class="space-line" />');
    text = text.replace(/\r/g, '');
    return (text);
}
