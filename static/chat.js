/* FormSorted chat look (16 Nov 2026). Presentation only: the same questions and the same form posts as the step-by-step pages.
   Typed in the message bar: a clear answer to the question on screen fills it in here. A question (or text that could be either) goes to
   /api/assist for a short reply from our help notes; the question on screen is then shown again. Nothing is added to an answer unless the
   customer taps Yes. There is no message bar on the National Insurance / bank page. */
(function(){
var $=function(s,r){return (r||document).querySelector(s)},$$=function(s,r){return [].slice.call((r||document).querySelectorAll(s))};
function el(t,c,h){var e=document.createElement(t);if(c)e.className=c;if(h!=null)e.innerHTML=h;return e}
function txt(s){var d=document.createElement('div');d.textContent=s;return d.innerHTML}
var ORB='<span class=orb aria-hidden=true></span>';
function svg(p,c){return '<svg class=ic viewBox="0 0 24 24" width=16 height=16 fill=none stroke=currentColor stroke-width=2.4 stroke-linecap=round stroke-linejoin=round aria-hidden=true style="color:'+c+'">'+p+'</svg>'}
var IC={check:svg('<path d="M20 6 9 17l-5-5"/>','#079455'),x:svg('<path d="M18 6 6 18M6 6l12 12"/>','#D92D20')};
var RM=window.matchMedia&&window.matchMedia('(prefers-reduced-motion: reduce)').matches;
function typing(){return el('div','turn bot new',ORB+'<div class="bub typing" role=status aria-label="FormSorted assistant is typing"><i></i><i></i><i></i></div>')}
/* Yes / No answers get a check or a cross, like the reference buttons (look only) */
$$('label.chip').forEach(function(c){var sp=c.querySelector('span');if(!sp)return;var t=sp.textContent.trim();if(/^yes([,.!]|$)/i.test(t))c.classList.add('yes');else if(/^no([,.!]|$)/i.test(t))c.classList.add('no')});
/* Help: the footer link opens the help list */
$$('[data-help]').forEach(function(a){a.addEventListener('click',function(e){var h=document.getElementById('help');if(!h){e.preventDefault();var c=$('#cmsg');if(c){c.focus();c.placeholder='Confused? Ask a question here'}return}e.preventDefault();h.open=true;scrollTo(h);var s=h.querySelector('summary');if(s)s.focus({preventScroll:true})})});
function botBubble(html){var t=el('div','turn bot new',ORB+'<div class=bub>'+html+'</div>');return t}
function meBubble(s){return el('div','turn me new','<div class=bub>'+txt(s)+'</div>')}
function scrollTo(e){if(!e)return;try{e.scrollIntoView({block:'nearest',behavior:'smooth'})}catch(_){e.scrollIntoView()}}
/* ---- reveal buttons (home: Not sure / Something else) ---- */
$$('[data-show]').forEach(function(b){b.addEventListener('click',function(){var t=document.getElementById(b.getAttribute('data-show'));if(!t)return;
 $$('.reveal').forEach(function(r){if(r!==t)r.hidden=true});t.hidden=false;var i=$('input,textarea',t);scrollTo(t);if(i)setTimeout(function(){i.focus({preventScroll:true})},250)})});
/* ---- help answers: a fixed list, matched by words (no free-form answers are made up) ---- */
var FAQ=[];try{FAQ=JSON.parse(($('#cfaq')||{}).textContent||'[]')}catch(_){}
var SYN={pay:'pay paid paying payment cost costs price much fee charge money card when',stop:'stop later come back save pause finish leave',
 someone:'someone else behalf mum dad mother father parent child husband wife partner carer filling them',sure:'sure answer know unsure idea pick',
 government:'government dwp official gov council part',send:'send sends post submit who posts',cost:'cost much price fee',mistake:'mistake wrong change edit',
 long:'long time minutes quick',safe:'safe safety data private privacy delete secure information'};
var STOP=' a an the i my me we you your is are do does can to of for it in on and or be if what how who when why will this that with any am get ';
function words(s){return (s.toLowerCase().match(/[a-z]+/g)||[]).filter(function(w){return STOP.indexOf(' '+w+' ')<0&&w.length>1})}
function expand(ws){var o=ws.slice();ws.forEach(function(w){for(var k in SYN){if((' '+SYN[k]+' ').indexOf(' '+w+' ')>=0)o.push('#'+k)}});return o}
function answer(q){var qw=expand(words(q)),best=null,bs=0;FAQ.forEach(function(f){var fw=expand(words(f.q)),s=0;qw.forEach(function(w){if(fw.indexOf(w)>=0)s+=(w[0]=='#'?1:2)});if(s>bs){bs=s;best=f}});return bs>=2?best:null}
function isQuestion(s){return /\?\s*$/.test(s)||/^(what|how|when|why|who|can|do|does|is|are|will|should|could|where)\b/i.test(s)}
function replyHelp(q,where){var f=answer(q),w=where||$('#replies')||$('#thread');
 w.appendChild(meBubble(q));
 var b=botBubble(f?'<p><strong>'+txt(f.q)+'</strong></p><p>'+txt(f.a)+'</p>':'<p>I can\'t answer that one here. You can email <a href="mailto:hello@formsorted.com">hello@formsorted.com</a>. Your answers so far are kept.</p>');
 w.appendChild(b);scrollTo(b)}
/* ---- live help: a short reply from our help notes (server checks every reply) ---- */
var ERR='<p>Sorry, I couldn\'t answer that just now, you can carry on or email <a href="mailto:hello@formsorted.com">hello@formsorted.com</a>.</p>';
function token(){var m=/^\/[a-z]+\/([A-Za-z0-9_-]{16,})(\/|$)/.exec(location.pathname);return m?m[1]:''}
function formKey(){var m=/[?&]form=(\w+)/.exec(location.search);return m?m[1]:''}
var busy=0;
/* The help bar never writes to answer controls, including server-suggested additions. */
function safeQuestion(v){return v.replace(/\b[A-CEGHJ-PR-TW-Z]{2}\s*\d{2}\s*\d{2}\s*\d{2}\s*[A-D]\b/gi,'[private detail removed]').replace(/\b\d{2}[- ]\d{2}[- ]\d{2}\b/g,'[private detail removed]').replace(/\b\d{7,}\b/g,'[private detail removed]')}
function ask(v,where){var w=where||$('#replies')||$('#thread');if(Q&&w===Q.side)w.innerHTML='';
 v=safeQuestion(v);w.appendChild(meBubble(v));var t=typing();w.appendChild(t);scrollTo(t);busy=1;
 var c=Q?Q.ctx():{q:'',hint:'',options:[],box:false},body={text:v,token:token(),form:formKey(),q:c.q,hint:c.hint,options:c.options,box:false};
 var ac=window.AbortController?new AbortController():null,tm=setTimeout(function(){if(ac)ac.abort()},25000);
 function done(html){clearTimeout(tm);busy=0;if(t.parentNode)t.parentNode.removeChild(t);var b=botBubble(html);b.classList.add('help-reply');w.appendChild(b);
  var g=Q&&Q.again();if(g)w.appendChild(g);if(Q&&Q.convo&&window.FS.scrollPair)window.FS.scrollPair(b);else scrollTo(b)}
 fetch('/api/assist',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body),signal:ac?ac.signal:undefined})
 .then(function(r){if(!r.ok)throw r.status;return r.json()}).then(function(j){
  var answerLike=/^\s*\d+(?:[.,]\d+)?\s*$/.test(v)||j.kind==='answer';
  done(answerLike?'<p>This box is just for questions. Tap your answer below, or use the box under the question. If none fit, tap <strong>Something else</strong>.</p>':'<p>'+txt(j.reply||'')+'</p>')
 }).catch(function(){done(ERR)})}
/* ---- which form (home) ---- */
var ROUTE=[];try{ROUTE=JSON.parse(($('#croute')||{}).textContent||'[]')}catch(_){}
function route(s){var t=' '+s.toLowerCase().replace(/[^a-z0-9 ]/g,' ')+' ';for(var i=0;i<ROUTE.length;i++){for(var j=0;j<ROUTE[i].w.length;j++){if(t.indexOf(' '+ROUTE[i].w[j]+' ')>=0||(ROUTE[i].w[j].indexOf(' ')>0&&t.indexOf(ROUTE[i].w[j])>=0))return ROUTE[i]}}return null}
function replyRoute(s,where){var r=route(s),w=where||$('#replies')||$('#thread');w.appendChild(meBubble(s));
 var b=r?botBubble('<p>It sounds like you need the <strong>'+txt(r.name)+'</strong> form.</p><div class=qchips><a class="qchip c5" href="'+r.href+'">'+IC.check+'Yes, '+txt(r.name)+'</a><button type=button class="qchip alt" data-again=1>'+IC.x+'No, something else</button></div>')
  :botBubble('<p>I can fill in these forms at the moment: Attendance Allowance, PIP, PIP review, DLA for a child, Blue Badge and Access to Work. Tap one above. If yours isn\'t one of these, email <a href="mailto:hello@formsorted.com">hello@formsorted.com</a>.</p>');
 w.appendChild(b);var a=$('[data-again]',b);if(a)a.addEventListener('click',function(){var c=$('#cmsg')||$('#selse_t');if(c)c.focus()});scrollTo(b)}
$$('form.elseask').forEach(function(f){var i0=$('input,textarea',f);if(i0)i0.addEventListener('keydown',function(e){if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();f.requestSubmit?f.requestSubmit():f.dispatchEvent(new Event('submit',{cancelable:true}))}});
 f.addEventListener('submit',function(e){e.preventDefault();var i=$('input,textarea',f),v=i.value.trim();if(!v){i.focus();return}i.value='';
 if(isQuestion(v)&&!route(v))ask(v,f.closest('.reveal'));else replyRoute(v,f.closest('.reveal'))})});
/* ---- questions, one at a time, as a conversation ---- */
var Q=null;(function(){var box=$('#qs');if(!box||document.body.classList.contains('convo'))return;var form=box.closest('form'),nav=form.querySelector('.navrow'),sub=nav.querySelector('button[value=next]'),sback=nav.querySelector('button[value=back]'),cnt=$('#qcount');
var kids=[].slice.call(box.children).filter(function(e){return !/^(SCRIPT|STYLE|INPUT)$/.test(e.tagName)}),steps=[],pre=[];
function simple(e){return /^(FIELDSET|DIV)$/.test(e.tagName)&&!e.querySelector('.chips,.card,.cond,textarea,select,input[type=radio],input[type=checkbox],input[type=file],button')&&!!e.querySelector('input')}
kids.forEach(function(e){if(/^(P|H2|H3)$/.test(e.tagName)&&!e.querySelector('input,select,textarea')){e.setAttribute('data-qpre','1');pre.push(e);return}
var last=steps[steps.length-1],sm=simple(e);if(sm&&last&&last.sm&&last.els.length<3&&!pre.length){last.els.push(e);return}steps.push({els:pre.concat([e]),sm:sm});pre=[]});
if(pre.length&&steps.length)steps[steps.length-1].els=steps[steps.length-1].els.concat(pre);
if(!steps.length)return;
var TIC={"user": "<path d=\"M20 21c0-1.396 0-2.093-.172-2.661a4 4 0 0 0-2.667-2.667c-.568-.172-1.265-.172-2.661-.172h-5c-1.396 0-2.093 0-2.661.172a4 4 0 0 0-2.667 2.667C4 18.907 4 19.604 4 21M16.5 7.5a4.5 4.5 0 1 1-9 0 4.5 4.5 0 0 1 9 0Z\"/>", "cal": "<path d=\"M21 10H3m13-8v4M8 2v4m2.5 8 1.5-1v5m-1.25 0h2.5M7.8 22h8.4c1.68 0 2.52 0 3.162-.327a3 3 0 0 0 1.311-1.311C21 19.72 21 18.88 21 17.2V8.8c0-1.68 0-2.52-.327-3.162a3 3 0 0 0-1.311-1.311C18.72 4 17.88 4 16.2 4H7.8c-1.68 0-2.52 0-3.162.327a3 3 0 0 0-1.311 1.311C3 6.28 3 7.12 3 8.8v8.4c0 1.68 0 2.52.327 3.162a3 3 0 0 0 1.311 1.311C5.28 22 6.12 22 7.8 22Z\"/>", "pin": "<path d=\"M12 12.5a3 3 0 1 0 0-6 3 3 0 0 0 0 6Z\"/><path d=\"M12 22c2-4 8-6.582 8-12a8 8 0 1 0-16 0c0 5.418 6 8 8 12Z\"/>", "edit": "<path d=\"M11 4H6.8c-1.68 0-2.52 0-3.162.327a3 3 0 0 0-1.311 1.311C2 6.28 2 7.12 2 8.8v8.4c0 1.68 0 2.52.327 3.162a3 3 0 0 0 1.311 1.311C4.28 22 5.12 22 6.8 22h8.4c1.68 0 2.52 0 3.162-.327a3 3 0 0 0 1.311-1.311C20 19.72 20 18.88 20 17.2V13M8 16h1.675c.489 0 .733 0 .963-.055.204-.05.4-.13.579-.24.201-.123.374-.296.72-.642L21.5 5.5a2.121 2.121 0 0 0-3-3l-9.563 9.563c-.346.346-.519.519-.642.72a2 2 0 0 0-.24.579c-.055.23-.055.474-.055.963V16Z\"/>"};
function cardIcon(t){t=t.toLowerCase();return /date|born|birth|when|age/.test(t)?TIC.cal:/address|postcode|town|street|live/.test(t)?TIC.pin:/name|called/.test(t)?TIC.user:TIC.edit}
var H1=$('.turn.bot.intro h1');
steps.forEach(function(st){if(!st.sm)return;var real=st.els.filter(function(e){return !e.hasAttribute('data-qpre')});if(!real.length)return;
 var lg=real[0].querySelector('legend,label,.q');var q=lg?lg.textContent.trim():'';
 var c=el('div','qcard'),hd=el('div','qch','<span class=otile aria-hidden=true><svg viewBox="0 0 24 24" width=24 height=24 fill=none stroke=currentColor stroke-width=2 stroke-linecap=round stroke-linejoin=round>'+cardIcon(q+' '+(H1?H1.textContent:''))+'</svg></span>'+
  '<span class=qct>'+txt(real.length>1&&H1?H1.textContent.trim():q)+'</span><span class=qcs>'+(real.length>1?'Type them as they should appear on the form.':'Type it as it should appear on the form.')+'</span>');
 c.appendChild(hd);st.els[0].parentNode.insertBefore(c,st.els[0]);st.els.forEach(function(e){c.appendChild(e)});st.card=c});
function ok(st){return st.els.some(function(e){return !e.hidden&&!e.hasAttribute('data-qpre')})}
var cur=0,qb=el('button','btn btn-2','Back'),qn=el('button','btn btn-start','Next question');qb.type=qn.type='button';qb.setAttribute('aria-label','Back');qn.setAttribute('aria-label','Next question');
if(steps.length>1){nav.insertBefore(qb,nav.firstChild);nav.appendChild(qn)}
var side=el('div','cside');side.setAttribute('aria-live','polite');nav.parentNode.insertBefore(side,nav);
function live(){return steps.filter(ok)}
function qtext(st){for(var i=0;i<st.els.length;i++){var e=st.els[i];if(e.hidden||e.hasAttribute('data-qpre'))continue;var t=e.querySelector('legend,h3,.q,.ltq,.fuq');if(t)return t.textContent.trim()}return ''}
function fmtDate(v){var m=/^(\d{4})-(\d\d)-(\d\d)$/.exec(v);return m?m[3]+'/'+m[2]+'/'+m[1]:v}
function summ(st){var out=[];st.els.forEach(function(e){if(e.hidden)return;$$('input,select,textarea',e).forEach(function(i){if(i.type=='hidden'||i.closest('[hidden]'))return;
 if(i.type=='radio'||i.type=='checkbox'){if(!i.checked)return;if(/_xon$/.test(i.name)){var b=i.closest('.else');b=b&&b.querySelector('.elsebox');out.push(b&&b.value.trim()?b.value.trim():'Something else');return}var sp=i.parentNode.querySelector('span');out.push(sp?sp.textContent.trim():i.value);return}
 if(i.classList.contains('elsebox'))return;if(i.tagName=='SELECT'){if(i.value&&i.selectedIndex>0)out.push(i.options[i.selectedIndex].text);return}
 if(i.value&&i.value.trim())out.push(i.type=='date'?fmtDate(i.value):i.value.trim())})});
 var t=out.join(' · ');if(t.length>180)t=t.slice(0,177)+'…';return t||'Skipped'}
function hist(st){if(!st.h){st.h=el('div','chist');var a=st.card||st.els[0];a.parentNode.insertBefore(st.h,a)}
 st.h.innerHTML='<div class="turn bot">'+ORB+'<div class=bub>'+txt(qtext(st)||'Question')+'</div></div><div class="turn me"><button type=button class=bub>'+txt(summ(st))+'<span class=chg>Change</span></button></div>';
 st.h.querySelector('button').onclick=function(){cur=steps.indexOf(st);show(true)};st.h.hidden=false}
function show(focus){var L=live();if(L.indexOf(steps[cur])<0){for(var j=cur;j<steps.length&&!ok(steps[j]);j++);cur=j<steps.length?j:steps.indexOf(L[L.length-1])}
var k=L.indexOf(steps[cur]);steps.forEach(function(st,j){if(st.card){st.card.classList.toggle('qoff',j!==cur);st.card.classList.toggle('qnow',j===cur);st.card.classList.toggle('qfirst',j===cur)}st.els.forEach(function(e){e.classList.toggle('qoff',j!==cur);e.classList.toggle('qnow',j===cur);e.classList.remove('qfirst')});var f0=st.els.filter(function(e){return !e.hidden})[0];if(j===cur&&f0)f0.classList.add('qfirst');
 if(j<cur&&ok(st))hist(st);else if(st.h)st.h.hidden=true});
cnt.hidden=L.length<2;cnt.textContent='Question '+(k+1)+' of '+L.length;var lastq=k===L.length-1;qn.hidden=lastq;sub.hidden=!lastq;qb.hidden=k===0;if(sback)sback.hidden=k>0;
if(side.cur!==cur){side.innerHTML='';side.cur=cur}
if(focus){var h=steps[cur].els.filter(function(e){return !e.hidden})[0];var t=h&&h.querySelector('legend,h3,.q');if(t){t.setAttribute('tabindex','-1');t.focus({preventScroll:true})}
 var top=steps[cur].h||h;setTimeout(function(){var r=h.getBoundingClientRect();if(r.top<90||r.top>window.innerHeight*0.55)window.scrollBy({top:r.top-110,behavior:'smooth'})},30)}}
var waiting=0;
function go(d){var L=live(),k=L.indexOf(steps[cur])+d;if(k<0||k>=L.length||waiting)return;cur=steps.indexOf(L[k]);
 if(d<0||RM){show(true);return}
 /* a short typing indicator between questions (look only; nothing is sent) */
 show(false);var st=steps[cur],parts=(st.card?[st.card]:[]).concat(st.els);parts.forEach(function(e){e.classList.add('qwait')});nav.classList.add('qwait');
 var t=typing();side.innerHTML='';side.appendChild(t);scrollTo(t);waiting=1;
 setTimeout(function(){waiting=0;if(t.parentNode)t.parentNode.removeChild(t);parts.forEach(function(e){e.classList.remove('qwait')});nav.classList.remove('qwait');show(true)},520)}
qn.addEventListener('click',function(){go(1)});qb.addEventListener('click',function(){go(-1)});
form.addEventListener('keydown',function(ev){if(ev.key==='Enter'&&ev.target.tagName==='INPUT'&&!qn.hidden){ev.preventDefault();go(1)}});
document.addEventListener('change',function(){setTimeout(function(){show(false)},0)});
window.qsShowAll=function(){steps.forEach(function(st){st.els.forEach(function(e){e.classList.remove('qoff')});if(st.h)st.h.hidden=true});qn.hidden=qb.hidden=cnt.hidden=true;sub.hidden=false;if(sback)sback.hidden=false};
show(false);
function vis(i){return !!(i.offsetWidth||i.offsetHeight||i.getClientRects().length)}
function fire(i){i.dispatchEvent(new Event('input',{bubbles:true}));i.dispatchEvent(new Event('change',{bubbles:true}))}
/* typed in the message bar: it becomes the answer to the question on screen, in the same boxes the page already has */
function ctx(){var st=steps[cur],els=st.els.filter(function(e){return !e.hidden}),o=[],h=[];
 els.forEach(function(e){$$('label.chip span',e).forEach(function(sp){if(vis(sp))o.push(sp.textContent.trim())});$$('.hint,.tip,.sub',e).forEach(function(p){if(vis(p))h.push(p.textContent.trim())})});
 var tips=$('.tips');if(tips)h.push('General tips: '+tips.textContent.replace(/\s+/g,' ').trim());
 var bx=els.some(function(e){return $$('input[type=text],input:not([type]),textarea,.elsebox',e).some(vis)});
 return {q:qtext(st),hint:h.join(' '),options:o,box:bx}}
/* the box an agreed note goes into: the open text box of the question on screen ('Tell us what happens', Something else, or a typed box) */
function addBox(){var st=steps[cur],els=st.els.filter(function(e){return !e.hidden}),b=null;
 els.forEach(function(e){if(!b)b=$$('textarea,.fuw input,input[type=text],input:not([type])',e).filter(function(i){return vis(i)&&!i.closest('[hidden]')})[0]||null});
 if(!b)els.forEach(function(e){if(!b){var x=$$('.else',e).filter(vis)[0];if(x){var cb=x.querySelector('input[type=checkbox]');if(cb&&!cb.checked){cb.checked=true;fire(cb)}b=x.querySelector('.elsebox')}}});return b}
function again(){var t=qtext(steps[cur]);if(!t)return null;return botBubble('<p>Back to the question: <strong>'+txt(t)+'</strong></p>')}
Q={side:side,ctx:ctx,addBox:addBox,again:again,focus:function(){show(true)},take:function(s){var st=steps[cur],els=st.els.filter(function(e){return !e.hidden}),low=s.trim().toLowerCase();
 var chips=[];els.forEach(function(e){chips=chips.concat($$('label.chip',e).filter(vis))});
 for(var i=0;i<chips.length;i++){var sp=chips[i].querySelector('span'),inp=chips[i].querySelector('input');if(sp&&inp&&sp.textContent.trim().toLowerCase()===low&&!/_xon$/.test(inp.name)){if(!inp.checked)chips[i].click();return 'tap'}}
 var boxes=[];els.forEach(function(e){boxes=boxes.concat($$('input:not([type]),input[type=text],input[type=tel],input[type=email],input[type=number],textarea',e).filter(function(i){return vis(i)&&!i.classList.contains('elsebox')&&!i.value.trim()}))});
 if(boxes.length){boxes[0].value=s;fire(boxes[0]);boxes[0].classList.add('filled');setTimeout(function(){boxes[0].classList.remove('filled')},1200);
  var hasTaps=els.some(function(e){return !!e.querySelector('input[type=radio],input[type=checkbox],select,input[type=date]')});
  if(boxes.length==1&&!hasTaps&&!qn.hidden){go(1);return 'next'}return 'box'}
 var xo=null;els.forEach(function(e){if(!xo)xo=$$('.else',e).filter(vis)[0]||null});
 if(xo){var cb=xo.querySelector('input[type=checkbox]'),bx=xo.querySelector('.elsebox');if(cb&&!cb.checked){cb.checked=true;fire(cb)}if(bx){bx.value=s;fire(bx)}return 'else'}
 var dt=null;els.forEach(function(e){if(!dt)dt=$$('input[type=date]',e).filter(function(i){return vis(i)&&!i.value})[0]||null});
 if(dt){var m=/^(\d{1,2})[\/\.\- ](\d{1,2})[\/\.\- ](\d{4})$/.exec(s.trim());if(m){dt.value=m[3]+'-'+('0'+m[2]).slice(-2)+'-'+('0'+m[1]).slice(-2);fire(dt);return 'box'}return 'date'}
 return 'none'}};
})();
/* shared with convo.js (the questions as a conversation) */
window.FS={el:el,txt:txt,ORB:ORB,RM:RM,typing:typing,botBubble:botBubble,meBubble:meBubble,ask:ask,isQuestion:isQuestion,setQ:function(q){Q=q}};
/* ---- the message bar ---- */
var cf=$('#composer');if(cf){var ta=$('#cmsg');var sb=cf.querySelector('.send');function sendState(){if(sb){var e=!ta.value.trim();sb.disabled=e;sb.setAttribute('aria-disabled',e?'true':'false')}}sendState();ta.addEventListener('input',sendState);
 ta.addEventListener('input',function(){ta.style.height='auto';ta.style.height=Math.min(ta.scrollHeight,200)+'px'});
 ta.addEventListener('keydown',function(e){if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();cf.requestSubmit?cf.requestSubmit():cf.dispatchEvent(new Event('submit',{cancelable:true}))}});
 cf.addEventListener('submit',function(e){e.preventDefault();var v=ta.value.trim();if(!v){ta.focus();return}ta.value='';ta.style.height='auto';sendState();
  if(busy)return;
  if(!Q&&ROUTE.length&&!(isQuestion(v)&&!route(v))){replyRoute(v);return}
  if(Q&&Q.place)Q.place();ask(v,Q&&Q.side)})}
})();
