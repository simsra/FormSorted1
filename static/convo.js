/* FormSorted assistant: the questions as a conversation (Simon, 16 Nov 2026).
   Same questions, same boxes and the same form post as before (intake.section_body). Each question is an assistant message;
   the answers are quick-tap replies under it, or the customer's own words in the message bar. Follow-ups arrive as the next
   messages. Typed words only fill an answer when they match a tap exactly, or when the customer says Yes to using them.
   Questions typed in the bar go to the help reply (chat.js ask()), then the question waiting for an answer is shown again. */
(function(){
var FS=window.FS,box=document.getElementById('qs');if(!FS||!box||!document.body.classList.contains('convo'))return;
var $=function(s,r){return (r||document).querySelector(s)},$$=function(s,r){return [].slice.call((r||document).querySelectorAll(s))};
var el=FS.el,txt=FS.txt,ORB=FS.ORB,RM=FS.RM;
var form=box.closest('form'),nav=form.querySelector('.navrow'),sub=nav.querySelector('button[value=next]');
function T(e){return (e.textContent||'').replace(/\s+/g,' ').trim()}
function shown(e){return !!(e&&(e.offsetWidth||e.offsetHeight||e.getClientRects().length))}
function fire(i){i.dispatchEvent(new Event('input',{bubbles:true}));i.dispatchEvent(new Event('change',{bubbles:true}))}
function chipText(c){var s=c&&c.querySelector('span');return s?T(s):''}
/* ---- 0. a list of conditions reads as one row of taps ---- */
$$('fieldset.iq',box).forEach(function(f){var cs=[].filter.call(f.children,function(c){return c.classList.contains('cond')});if(!cs.length)return;var w=el('div','condlist');f.insertBefore(w,cs[0]);cs.forEach(function(c){w.appendChild(c)})});
/* ---- 1. questions that have no words of their own on the page get them (same answers, same names) ---- */
function syn(before,text,cls){var p=el('p','cq-syn'+(cls?' '+cls:''),txt(text));before.parentNode.insertBefore(p,before);return p}
function groupQ(g){var t=chipText(g.querySelector('label.chip'))||'';
 return /nights?$/.test(t)?'how many nights a week?':/a night$/.test(t)?'how many times a night?':/min/.test(t)?'roughly how long each time?':/tablets/i.test(t)?'any treatment? Tap any that apply.':
  /times?|×/.test(t)?'how many times?':(g.querySelector('input[type=checkbox]:not([name$=_xon])')?'tap any that apply.':'tap the one that fits.')}
$$('.cond:not(.other)',box).forEach(function(c){var nm=chipText(c.querySelector('label.chip'));var s=$('.more>select',c);
 if(s)syn(s,nm+': roughly when did it start?');$$('.more>.chips',c).forEach(function(g){syn(g,nm+': '+groupQ(g))})});
$$('.cond.other',box).forEach(function(c,j){var i=$('input[name^=oc_]:not([type])',c)||$('input[name^=oc_]',c),s=$('select',c),g=$('.chips',c);
 if(i)syn(i,j?'Any other condition? Type it, or skip.':'Is there a condition that isn\'t in the list? Type it, or skip.');
 if(s)syn(s,'When did it start?','oc-since');if(g)syn(g,'Any treatment for it? Tap any that apply.','oc-treat')});
$$('select',box).forEach(function(s){var p=s.previousElementSibling;if(p&&p.classList.contains('cq-syn'))return;if(!s.closest('fieldset.iq')||s.closest('fieldset.iq').querySelector('select')!==s||!s.getAttribute('aria-label'))return;
 var l=s.closest('fieldset.iq').querySelector('legend');if(l&&l.compareDocumentPosition(s)&4)return;syn(s,s.getAttribute('aria-label'))});
$$('fieldset.iq',box).forEach(function(f){if(!f.querySelector('.yn'))return;var g=[].filter.call(f.children,function(c){return c.matches('div.chips')&&!c.querySelector('label.chip:not(.else label)')&&c.querySelector('.else')})[0];if(g)syn(g,'Anything else about this? Tap Something else to add it, or skip.')});
/* ---- 2. units: one question with the replies that belong to it ---- */
var QN='.ynq,legend,.card>h3,p.sub,p.fuq,.ltq,.fuw>span,.ltw>span,.kn>span,.cq-syn,label.q';
var CT='label.chip,.else,select,textarea,input:not([type=hidden]):not([type=radio]):not([type=checkbox]):not(.elsebox),button.starter,button.pcfind,p.prebtn';
var TP='p.hint,p.tip,p.carry';
function scopeOf(q){if(q.matches('.ynq'))return q.parentNode;if(q.matches('.ltw>span'))return q.parentNode.parentNode;if(q.matches('legend,.fuw>span,.kn>span,.cq-syn,label.q'))return q.parentNode;
 if(q.matches('.card>h3'))return q.parentNode;return q.parentNode}
var units=[],stack=[],pre=[];
var walk=document.createTreeWalker(box,NodeFilter.SHOW_ELEMENT,null),n;
while((n=walk.nextNode())){if(/^(SCRIPT|STYLE|OPTION)$/.test(n.tagName))continue;
 while(stack.length&&!stack[stack.length-1].scope.contains(n))stack.pop();
 if(n.matches(QN)){if(n.matches('.ltw>span')&&n.parentNode.matches('label.ltlast'))n.parentNode.classList.add('ltlast-q');
  var u={q:n,scope:scopeOf(n),ctrls:[],tips:[],pre:pre,i:units.length};pre=[];units.push(u);stack.push(u);continue}
 if(n.parentNode===box&&/^(P|H2|H3)$/.test(n.tagName)&&!n.querySelector('input,select,textarea')){pre.push(n);continue}
 var top=stack[stack.length-1];if(!top)continue;
 if(n.matches(CT)&&(n.matches('label.chip')||!n.closest('label.chip'))&&!(n.closest('.else')&&n!==n.closest('.else'))){top.ctrls.push(n);continue}
 if(n.matches(TP)&&!n.closest('label.chip'))top.tips.push(n)}
units.forEach(function(u){var ins=[];u.ctrls.forEach(function(c){ins=ins.concat(c.matches('input,select,textarea')?[c]:$$('input,select,textarea',c))});u.ins=ins;
 u.radios=ins.filter(function(i){return i.type=='radio'});u.checks=ins.filter(function(i){return i.type=='checkbox'&&!/_xon$/.test(i.name)});
 u.xon=ins.filter(function(i){return /_xon$/.test(i.name)})[0]||null;u.ebox=u.xon?u.xon.closest('.else').querySelector('.elsebox'):null;
 u.boxes=ins.filter(function(i){return i.tagName=='TEXTAREA'||(i.tagName=='INPUT'&&!/^(radio|checkbox|date|file)$/.test(i.type)&&!i.classList.contains('elsebox'))});
 u.date=ins.filter(function(i){return i.type=='date'})[0]||null;u.sel=ins.filter(function(i){return i.tagName=='SELECT'})[0]||null;
 u.kind=u.radios.length?'radio':u.checks.length||u.xon?'multi':u.sel?'select':u.date?'date':u.boxes.length?'text':'info';
 if(u.kind=='radio'&&u.boxes.length)u.kind='radio';
 u.q.classList.add('cq');u.pre.forEach(function(p){p.classList.add('cq','cpre')});u.q.setAttribute('data-kind',u.kind);
 /* answered already (coming back to a part): show as answered, with Change */
 u.done=u.kind=='info'||(u.kind=='multi'&&(u.checks.some(function(i){return i.checked})||(u.xon&&u.xon.checked&&u.ebox&&u.ebox.value.trim())))||
  ((u.kind=='text'||u.kind=='date')&&u.ins.some(function(i){return (i.type!='radio'&&i.type!='checkbox')&&i.value.trim()}))||(u.kind=='select'&&!!u.sel.value);
 /* the reply row: an inline box with Send for typed answers, Done for 'tap any', Skip for everything */
 var act=el('div','cact');u.act=act;
 if(u.kind=='text'||u.kind=='date'){var b0=u.boxes[0]||u.date;var row=el('div','cinrow');b0.parentNode.insertBefore(row,b0);row.appendChild(b0);u.row=row;
  var ok=el('button','qchip cok','Send');ok.type='button';ok.setAttribute('aria-label','Send this answer');row.appendChild(ok);ok.addEventListener('click',function(){commit(u)})}
 if(u.kind=='multi'){var d=el('button','qchip cdone','Done');d.type='button';act.appendChild(d);d.addEventListener('click',function(){commit(u)});u.dbtn=d}
 var sk=el('button','cskip','Skip this question');sk.type='button';act.appendChild(sk);sk.addEventListener('click',function(){skip(u)});u.sk=sk;
 if(u.kind=='radio'&&u.xon){var eo=el('button','qchip cdone celse','Use what I typed');eo.type='button';act.insertBefore(eo,act.firstChild);eo.addEventListener('click',function(){if(u.ebox.value.trim()){u.edone=true;render()}else u.ebox.focus()});u.ebtn=eo}
 var last=u.ctrls[u.ctrls.length-1]||u.q;var host=(last.closest&&last.closest('.else'))||last;
 if(u.ctrls.length&&(u.kind=='multi'||u.kind=='radio')){var g=last.closest('.chips');if(g&&u.scope.contains(g))host=g}
 if(u.row)host=u.row;
 if(host.parentNode)host.parentNode.insertBefore(act,host.nextSibling);
 if(u.kind=='info')act.hidden=true;
 u.me=el('div','turn me cme');u.q.parentNode.insertBefore(u.me,u.q.nextSibling);
});
/* ---- 3. what's answered ---- */
function answered(u){if(u.reopen)return false;if(u.done)return true;
 if(u.kind=='radio')return u.radios.some(function(i){return i.checked})||u.checks.some(function(i){return i.checked})||(!!u.xon&&u.xon.checked&&!!u.ebox.value.trim()&&!!u.edone);
 return false}
function summary(u){var out=[];
 if(u.kind=='radio'||u.kind=='multi'){u.ins.forEach(function(i){if((i.type=='radio'||i.type=='checkbox')&&i.checked){if(/_xon$/.test(i.name)){out.push(u.ebox&&u.ebox.value.trim()?u.ebox.value.trim():'Something else');return}out.push(chipText(i.closest('label')))}});
  u.boxes.forEach(function(b){if(b.value.trim())out.push(b.value.trim())})}
 else if(u.kind=='select'){if(u.sel.value)out.push(u.sel.options[u.sel.selectedIndex].text)}
 else if(u.kind=='date'){var m=/^(\d{4})-(\d\d)-(\d\d)$/.exec(u.date.value);if(m)out.push(m[3]+'/'+m[2]+'/'+m[1])}
 else u.boxes.forEach(function(b){if(b.value.trim())out.push(b.value.trim())});
 var t=out.join(', ');if(t.length>220)t=t.slice(0,217)+'…';return t}
function commit(u){if(u.kind=='text'&&!u.boxes.some(function(b){return b.value.trim()})){var b=u.boxes[0];b.focus();return}
 if(u.kind=='date'&&!u.date.value){u.date.focus();return}
 if(u.xon&&u.xon.checked&&!u.ebox.value.trim()&&u.kind!='radio'){u.ebox.focus();return}
 u.done=true;u.edone=true;u.reopen=false;u.skipped=false;render()}
function skip(u){u.done=true;u.skipped=true;u.reopen=false;render()}
/* ---- 4. drawing the conversation ---- */
var side=el('div','cside');side.setAttribute('aria-live','polite');
var endb=el('div','turn bot cend',ORB+'<div class=bub><p><strong>Thanks, that\'s this part done.</strong> Check your answers above, then carry on.</p></div>');nav.parentNode.insertBefore(endb,nav);
var cnt=$('#qcount');if(cnt)cnt.hidden=true;
var front=null,seen=-1,busyT=0;
function parts(u){return [u.q,u.me,u.act].concat(u.ctrls,u.tips,u.pre,u.row?[u.row]:[])}
function render(anim){
 units.forEach(function(u){parts(u).forEach(function(e){e.classList.remove('cfut','coff','cnow','cwait')})});
 units.forEach(function(u){u.live=shown(u.q)&&(u.kind=='info'||u.ctrls.some(shown)||(u.row&&shown(u.row)))});
 var f=null;for(var i=0;i<units.length;i++){var u=units[i];if(u.live&&!answered(u)){f=u;break}}
 units.forEach(function(u){
  if(f&&u.i>f.i){parts(u).forEach(function(e){e.classList.add('cfut')});return}
  if(u===f){u.q.classList.add('cnow');u.me.innerHTML='';u.me.classList.add('coff');
   if(u.dbtn)u.dbtn.textContent=(u.checks.some(function(i){return i.checked})||(u.xon&&u.xon.checked))?'Done':'None of these';
   if(u.ebtn)u.ebtn.classList.toggle('chide',!u.xon.checked);return}
  if(!u.live){u.me.classList.add('coff');return}
  u.ctrls.concat(u.tips,[u.act],u.row?[u.row]:[]).forEach(function(e){e.classList.add('coff')});
  if(u.kind=='info'){u.me.classList.add('coff');return}
  var s=summary(u);u.me.innerHTML='<button type=button class=bub aria-label="Change your answer: '+txt(T(u.q))+'">'+txt(s||'Skipped')+'<span class=chg>Change</span></button>';
  u.me.firstChild.onclick=function(){u.reopen=true;u.done=false;u.edone=false;render();focusQ(u)}});
 /* the end of the part */
 endb.hidden=!!f;sub.hidden=!!f;nav.classList.toggle('cnav-wait',!!f);
 if(!f)showTold();else if(told){told.parentNode.removeChild(told);told=null;endb.classList.remove('chide')}
 var host=f?f.act:null;if(host&&side.previousSibling!==host){host.parentNode.insertBefore(side,host.nextSibling)}
 if(!f&&side.parentNode!==nav.parentNode)nav.parentNode.insertBefore(side,endb);
 var changed=f!==front;front=f;
 if(changed){side.innerHTML='';if(f&&f.i>seen&&anim!==false&&!RM&&seen>=0){wait(f)}else{if(f)focusQ(f,seen<0);else scrollIn(endb)}if(f)seen=Math.max(seen,f.i);offerReuse(f)}}
function wait(u){var ps=parts(u).filter(function(e){return !e.classList.contains('coff')});ps.forEach(function(e){e.classList.add('cwait')});
 var t=FS.typing();u.q.parentNode.insertBefore(t,u.q);clearTimeout(busyT);
 busyT=setTimeout(function(){if(t.parentNode)t.parentNode.removeChild(t);ps.forEach(function(e){e.classList.remove('cwait')});focusQ(u)},480)}
function scrollPair(top,bot){setTimeout(function(){var a=top.getBoundingClientRect(),b=bot.getBoundingClientRect(),h=window.innerHeight,head=80,foot=170;
 var y=(b.bottom-a.top<h-head-foot)?a.top-head-10:b.bottom-(h-foot);var sc=document.scrollingElement;var m=$('#main');var t=(m&&m.scrollHeight>m.clientHeight+4)?m:null;
 if(t)t.scrollBy({top:y,behavior:RM?'auto':'smooth'});else window.scrollBy({top:y,behavior:RM?'auto':'smooth'})},40)}
FS.scrollPair=function(b){if(front)scrollPair(front.q,b)};
function scrollIn(e){if(!e)return;var u=front;if(u&&u.q!==e&&u.q.compareDocumentPosition(e)&4){scrollPair(u.q,e);return}scrollPair(e,(u&&u.q===e?(u.act.offsetParent?u.act:e):e))}
function focusQ(u,quiet){u.q.setAttribute('tabindex','-1');if(!quiet)try{u.q.focus({preventScroll:true})}catch(_){}scrollIn(u.q)}
/* ---- 'Here's what you told me': at the end of the last part, before evidence and paying. Their own taps and words only. ---- */
var told=null;
function showTold(){if(!form.hasAttribute('data-last')||told)return;told=el('div','turn bot ctold',ORB+'<div class=bub><p><strong>That\'s all the questions.</strong> Here\'s what you told me. Tap a part to check it, and Change to fix anything.</p><div class=tellsum aria-live=polite><p class=hint>Loading your answers…</p></div></div>');
 endb.parentNode.insertBefore(told,endb.nextSibling);endb.classList.add('chide');var tk=location.pathname.split('/')[2]||'';
 fetch('/api/'+tk+'/told?cur='+encodeURIComponent(form.getAttribute('data-sec')||''),{cache:'no-store'}).then(function(r){if(!r.ok)throw r.status;return r.json()}).then(function(j){
  var h='';j.parts.forEach(function(p){if(p.here){h+='<details class=tellsec><summary><span>'+txt(p.label)+'</span><span class=tn>This part</span></summary><p class=tnote>Your answers for this part are just above.</p></details>';return}
   var rows=p.rows.map(function(r){return '<div><dt>'+txt(r[0])+'</dt><dd>'+txt(r[1].join(', '))+'</dd></div>'}).join('')||'<div><dd>Nothing yet. That\'s fine: skip anything you\'re not sure about.</dd></div>';
   h+='<details class=tellsec><summary><span>'+txt(p.label)+'</span><span class=tn>'+p.rows.length+' answer'+(p.rows.length==1?'':'s')+'</span></summary><dl class=tell>'+rows+'</dl><a class="qchip tchg" href="/intake/'+tk+'?s='+encodeURIComponent(p.sec)+'&ret=1">Change '+txt(p.label.toLowerCase())+'</a></details>'});
  $('.tellsum',told).innerHTML=h;sub.textContent='That\'s right, carry on';scrollIn(told)}).catch(function(){$('.tellsum',told).innerHTML='<p>Your answers are saved. You can check each part with Back.</p>'})}
/* ---- 5. don't ask twice: if they already said one of these answers in their own words, offer it ---- */
var KEY='fs_said_'+(location.pathname.split('/')[2]||'');var SAID=[];try{SAID=JSON.parse(sessionStorage.getItem(KEY)||'[]')}catch(_){}
function remember(v){SAID.push(v);SAID=SAID.slice(-30);try{sessionStorage.setItem(KEY,JSON.stringify(SAID))}catch(_){}}
function norm(x){return ' '+x.toLowerCase().replace(/[^a-z0-9' ]/g,' ').replace(/\s+/g,' ').trim()+' '}
function mentions(v,labs){var t=norm(v),o=[];labs.forEach(function(l){var n=norm(l).trim();if(n.length<3||/^(yes|no|not sure|something else|none|none of these|other|never|less often)$/.test(n))return;if(t.indexOf(' '+n+' ')>=0&&o.indexOf(l)<0)o.push(l)});return o}
function mention(v,labs){return mentions(v,labs)[0]||null}
function chips(u){var o=[];u.ctrls.forEach(function(c){o=o.concat(c.matches('label.chip')?[c]:$$('label.chip',c))});return o.filter(shown)}
function offerReuse(u,keep){if(!u||(u.kind!='radio'&&u.kind!='multi')||u.offered)return;var cs=chips(u),labs=cs.map(chipText);
 for(var k=SAID.length-1;k>=0;k--){var ms=mentions(SAID[k],labs);if(u.kind=='radio')ms=ms.slice(0,1);if(ms.length){u.offered=1;var said=SAID[k];
  var b=FS.botBubble('<p>You told me earlier: &ldquo;'+txt(said)+'&rdquo;</p><p>Shall I use <strong>'+ms.map(txt).join('</strong> and <strong>')+'</strong> for this one?</p><div class=qchips><button type=button class="qchip c5" data-y=1>Yes, use it</button><button type=button class="qchip alt" data-y=0>No</button></div>');
  b.classList.add('creuse');if(!keep)side.innerHTML='';side.appendChild(b);if(keep)setTimeout(function(){scrollIn(b)},60);
  $$('[data-y]',b).forEach(function(x){x.addEventListener('click',function(){b.parentNode&&b.parentNode.removeChild(b);if(x.getAttribute('data-y')=='1'){ms.forEach(function(m){var c=cs[labs.indexOf(m)],i=c.querySelector('input');if(!i.checked)c.click()});if(u.kind=='multi')setTimeout(render,0)}})});return}}}
/* ---- 6. the message bar ---- */
function exact(u,v){var low=v.trim().toLowerCase().replace(/[.!]+$/,'');var cs=chips(u);for(var i=0;i<cs.length;i++){var inp=cs[i].querySelector('input');if(chipText(cs[i]).toLowerCase()===low&&!/_xon$/.test(inp.name))return cs[i]}return null}
function confirmUse(u,v){var cs=chips(u),labs=cs.map(chipText),ms=mentions(v,labs),m=ms[0]||null,canOwn=!!u.xon||u.ins.some(function(i){return i.type=='radio'&&i.value=='else'})&&u.boxes.length;
 side.innerHTML='';side.appendChild(FS.meBubble(v));
 var nm=u.kind=='radio'?ms.slice(0,1):ms;
 var h='<p>'+(canOwn?'Shall I put that down as your answer, in your words?':nm.length?'You mentioned '+(nm.length>1?'these':'this')+'. Shall I tap '+(nm.length>1?'them':'it')+' for you?':'I need one of the answers above for this question.')+'</p>';
 if(canOwn)h+='<p class=addq>&ldquo;'+txt(v)+'&rdquo;</p>';h+='<div class=qchips>';
 if(u.kind=='radio')ms=ms.slice(0,1);if(ms.length)h+='<button type=button class="qchip c5" data-c=tap>Use '+ms.map(function(x){return '&ldquo;'+txt(x)+'&rdquo;'}).join(' and ')+'</button>';
 if(canOwn)h+='<button type=button class="qchip c5" data-c=own>Yes, use my words</button>';
 h+='<button type=button class="qchip alt" data-c=ask>No, it\'s a question</button><button type=button class="qchip alt" data-c=no>No, I\'ll tap one</button></div>';
 var b=FS.botBubble(h);b.classList.add('cconfirm');side.appendChild(b);scrollIn(b);
 $$('[data-c]',b).forEach(function(x){x.addEventListener('click',function(){var c=x.getAttribute('data-c');
  if(c=='ask'){side.innerHTML='';FS.ask(v,side);return}
  side.innerHTML='';if(c=='no'){focusQ(u);return}
  if(c=='tap'){ms.forEach(function(x){var ch=cs[labs.indexOf(x)],i=ch.querySelector('input');if(!i.checked)ch.click()});u.offered=1;if(u.kind=='multi'){setTimeout(render,0)}return}
  if(u.xon){if(!u.xon.checked){u.xon.checked=true;fire(u.xon)}u.ebox.value=v;fire(u.ebox);u.edone=true;if(u.kind=='multi')u.done=true;render();return}
  var r=u.radios.filter(function(i){return i.value=='else'})[0];if(r&&!r.checked){r.closest('label').click()}
  setTimeout(function(){var nx=front;if(nx&&nx.boxes.length&&!nx.boxes[0].value){nx.boxes[0].value=v;fire(nx.boxes[0]);nx.done=true;render()}},0)})})}
function say(v){remember(v);var u=front;
 if(!u){FS.ask(v,side);return}
 var c=(u.kind=='radio'||u.kind=='multi')?exact(u,v):null;
 if(c){side.innerHTML='';var i=c.querySelector('input');if(!i.checked)c.click();return}
 if(FS.isQuestion(v)){FS.ask(v,side);return}
 if(u.kind=='text'){var b=u.boxes.filter(function(x){return !x.value.trim()})[0]||u.boxes[0];b.value=v;fire(b);side.innerHTML='';commit(u);return}
 if(u.kind=='date'){var m=/^(\d{1,2})[\/\.\- ](\d{1,2})[\/\.\- ](\d{4})$/.exec(v.trim());side.innerHTML='';
  if(m){u.date.value=m[3]+'-'+('0'+m[2]).slice(-2)+'-'+('0'+m[1]).slice(-2);fire(u.date);commit(u);return}
  side.appendChild(FS.meBubble(v));side.appendChild(FS.botBubble('<p>Please put the date in the box above, or type it like 04/05/2016.</p>'));return}
 if(u.kind=='select'){var low=v.trim().toLowerCase(),o=[].filter.call(u.sel.options,function(o){return o.value&&o.text.toLowerCase()===low})[0];side.innerHTML='';
  if(o){u.sel.value=o.value;fire(u.sel);return}side.appendChild(FS.meBubble(v));side.appendChild(FS.botBubble('<p>Please pick one from the list above, for example 2019. Or skip it if you\'re not sure.</p>'));return}
 if(u.kind=='radio'||u.kind=='multi'){confirmUse(u,v);return}
 FS.ask(v,side)}
/* the help reply needs: the question waiting, its tips and answers, and where an agreed note goes */
function ctx(){var u=front;if(!u)return {q:'',hint:'',options:[],box:false};var h=u.tips.map(T);var tips=$('.tips');if(tips)h.push('General tips: '+T(tips));
 return {q:T(u.q),hint:h.join(' '),options:chips(u).map(chipText),box:!!(u.boxes.length||u.xon)}}
function addBox(){var u=front;if(!u)return null;if(u.boxes.length)return u.boxes[0];if(u.xon){if(!u.xon.checked){u.xon.checked=true;fire(u.xon)}return u.ebox}return null}
function again(){var u=front;if(!u)return null;setTimeout(function(){offerReuse(front,1)},80);var b=FS.botBubble('<p>Back to the question: <strong>'+txt(T(u.q))+'</strong></p>');b.classList.add('cagain');
 setTimeout(function(){scrollIn(b)},40);return b}
FS.setQ({convo:true,side:side,ctx:ctx,addBox:addBox,again:again,say:say,focus:function(){if(front)focusQ(front)},take:function(){return 'none'}});
/* ---- 7. wiring ---- */
form.addEventListener('change',function(e){var u=units.filter(function(x){return x.ins.indexOf(e.target)>=0})[0];
 if(u&&u.reopen&&(e.target.type=='radio'||e.target.tagName=='SELECT'))u.reopen=false;
 if(u&&e.target.tagName=='SELECT'){u.done=!!e.target.value}
 if(u&&e.target.classList.contains('elsebox'))return;
 setTimeout(render,0)});
form.addEventListener('keydown',function(e){if(e.key!=='Enter'||e.target.tagName!=='INPUT')return;var u=units.filter(function(x){return x.ins.indexOf(e.target)>=0})[0];if(!u)return;e.preventDefault();
 if(e.target.classList.contains('elsebox')){if(e.target.value.trim()){u.edone=true;if(u.kind=='multi')u.done=true;render()}return}commit(u)});
document.addEventListener('click',function(e){if(e.target.closest('button.starter'))setTimeout(render,0)});
box.addEventListener('click',function(e){var c=e.target.closest('label.chip');if(!c)return;var i=c.querySelector('input');var u=units.filter(function(x){return x.ins.indexOf(i)>=0})[0];
 if(u&&u.reopen&&i&&i.type=='radio'&&i.checked){u.reopen=false;setTimeout(render,0)}});
window.qsShowAll=function(){units.forEach(function(u){parts(u).forEach(function(e){e.classList.remove('cfut','coff')})});sub.hidden=false};
window.__convo={units:units,front:function(){return front},render:render};
render(false);
})();
