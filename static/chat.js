/* FormSorted chat look (16 Nov 2026). Presentation only: the same questions and the same form posts as the step-by-step pages.
   Nothing typed in the message bar leaves the browser unless it becomes the answer to the question on screen. */
(function(){
var $=function(s,r){return (r||document).querySelector(s)},$$=function(s,r){return [].slice.call((r||document).querySelectorAll(s))};
function el(t,c,h){var e=document.createElement(t);if(c)e.className=c;if(h!=null)e.innerHTML=h;return e}
function txt(s){var d=document.createElement('div');d.textContent=s;return d.innerHTML}
var ORB='<span class=orb aria-hidden=true></span>';
function botBubble(html){var t=el('div','turn bot new',ORB+'<div class=bub>'+html+'</div>');return t}
function meBubble(s){return el('div','turn me new','<div class=bub>'+txt(s)+'</div>')}
function scrollTo(e){if(!e)return;try{e.scrollIntoView({block:'nearest',behavior:'smooth'})}catch(_){e.scrollIntoView()}}
/* ---- reveal buttons (home: Not sure / Something else) ---- */
$$('[data-show]').forEach(function(b){b.addEventListener('click',function(){var t=document.getElementById(b.getAttribute('data-show'));if(!t)return;
 $$('.reveal').forEach(function(r){if(r!==t)r.hidden=true});t.hidden=false;var i=$('input',t);scrollTo(t);if(i)setTimeout(function(){i.focus({preventScroll:true})},250)})});
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
/* ---- which form (home) ---- */
var ROUTE=[];try{ROUTE=JSON.parse(($('#croute')||{}).textContent||'[]')}catch(_){}
function route(s){var t=' '+s.toLowerCase().replace(/[^a-z0-9 ]/g,' ')+' ';for(var i=0;i<ROUTE.length;i++){for(var j=0;j<ROUTE[i].w.length;j++){if(t.indexOf(' '+ROUTE[i].w[j]+' ')>=0||(ROUTE[i].w[j].indexOf(' ')>0&&t.indexOf(ROUTE[i].w[j])>=0))return ROUTE[i]}}return null}
function replyRoute(s,where){var r=route(s),w=where||$('#replies')||$('#thread');w.appendChild(meBubble(s));
 var b=r?botBubble('<p>It sounds like you need the <strong>'+txt(r.name)+'</strong> form.</p><div class=qchips><a class=qchip href="'+r.href+'">Yes, '+txt(r.name)+'</a><button type=button class="qchip alt" data-again=1>No, something else</button></div>')
  :botBubble('<p>I can fill in these forms at the moment: Attendance Allowance, PIP, PIP review, DLA for a child, Blue Badge and Access to Work. Tap one above. If yours isn\'t one of these, email <a href="mailto:hello@formsorted.com">hello@formsorted.com</a>.</p>');
 w.appendChild(b);var a=$('[data-again]',b);if(a)a.addEventListener('click',function(){var c=$('#cmsg')||$('#selse_t');if(c)c.focus()});scrollTo(b)}
$$('form.elseask').forEach(function(f){f.addEventListener('submit',function(e){e.preventDefault();var i=$('input',f),v=i.value.trim();if(!v){i.focus();return}i.value='';
 if(isQuestion(v)&&!route(v))replyHelp(v,f.closest('.reveal'));else replyRoute(v,f.closest('.reveal'))})});
/* ---- questions, one at a time, as a conversation ---- */
var Q=null;(function(){var box=$('#qs');if(!box)return;var form=box.closest('form'),nav=form.querySelector('.navrow'),sub=nav.querySelector('button[value=next]'),sback=nav.querySelector('button[value=back]'),cnt=$('#qcount');
var kids=[].slice.call(box.children).filter(function(e){return !/^(SCRIPT|STYLE|INPUT)$/.test(e.tagName)}),steps=[],pre=[];
function simple(e){return /^(FIELDSET|DIV)$/.test(e.tagName)&&!e.querySelector('.chips,.card,.cond,textarea,select,input[type=radio],input[type=checkbox],input[type=file],button')&&!!e.querySelector('input')}
kids.forEach(function(e){if(/^(P|H2|H3)$/.test(e.tagName)&&!e.querySelector('input,select,textarea')){e.setAttribute('data-qpre','1');pre.push(e);return}
var last=steps[steps.length-1],sm=simple(e);if(sm&&last&&last.sm&&last.els.length<3&&!pre.length){last.els.push(e);return}steps.push({els:pre.concat([e]),sm:sm});pre=[]});
if(pre.length&&steps.length)steps[steps.length-1].els=steps[steps.length-1].els.concat(pre);
if(!steps.length)return;
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
function hist(st){if(!st.h){st.h=el('div','chist');st.els[0].parentNode.insertBefore(st.h,st.els[0])}
 st.h.innerHTML='<div class="turn bot">'+ORB+'<div class=bub>'+txt(qtext(st)||'Question')+'</div></div><div class="turn me"><button type=button class=bub>'+txt(summ(st))+'<span class=chg>Change</span></button></div>';
 st.h.querySelector('button').onclick=function(){cur=steps.indexOf(st);show(true)};st.h.hidden=false}
function show(focus){var L=live();if(L.indexOf(steps[cur])<0){for(var j=cur;j<steps.length&&!ok(steps[j]);j++);cur=j<steps.length?j:steps.indexOf(L[L.length-1])}
var k=L.indexOf(steps[cur]);steps.forEach(function(st,j){st.els.forEach(function(e){e.classList.toggle('qoff',j!==cur);e.classList.toggle('qnow',j===cur);e.classList.remove('qfirst')});var f0=st.els.filter(function(e){return !e.hidden})[0];if(j===cur&&f0)f0.classList.add('qfirst');
 if(j<cur&&ok(st))hist(st);else if(st.h)st.h.hidden=true});
cnt.hidden=L.length<2;cnt.textContent='Question '+(k+1)+' of '+L.length;var lastq=k===L.length-1;qn.hidden=lastq;sub.hidden=!lastq;qb.hidden=k===0;if(sback)sback.hidden=k>0;
side.innerHTML='';
if(focus){var h=steps[cur].els.filter(function(e){return !e.hidden})[0];var t=h&&h.querySelector('legend,h3,.q');if(t){t.setAttribute('tabindex','-1');t.focus({preventScroll:true})}
 var top=steps[cur].h||h;setTimeout(function(){var r=h.getBoundingClientRect();if(r.top<90||r.top>window.innerHeight*0.55)window.scrollBy({top:r.top-110,behavior:'smooth'})},30)}}
function go(d){var L=live(),k=L.indexOf(steps[cur])+d;if(k<0||k>=L.length)return;cur=steps.indexOf(L[k]);show(true)}
qn.addEventListener('click',function(){go(1)});qb.addEventListener('click',function(){go(-1)});
form.addEventListener('keydown',function(ev){if(ev.key==='Enter'&&ev.target.tagName==='INPUT'&&!qn.hidden){ev.preventDefault();go(1)}});
document.addEventListener('change',function(){setTimeout(function(){show(false)},0)});
window.qsShowAll=function(){steps.forEach(function(st){st.els.forEach(function(e){e.classList.remove('qoff')});if(st.h)st.h.hidden=true});qn.hidden=qb.hidden=cnt.hidden=true;sub.hidden=false;if(sback)sback.hidden=false};
show(false);
function vis(i){return !!(i.offsetWidth||i.offsetHeight||i.getClientRects().length)}
function fire(i){i.dispatchEvent(new Event('input',{bubbles:true}));i.dispatchEvent(new Event('change',{bubbles:true}))}
/* typed in the message bar: it becomes the answer to the question on screen, in the same boxes the page already has */
Q={side:side,take:function(s){var st=steps[cur],els=st.els.filter(function(e){return !e.hidden}),low=s.trim().toLowerCase();
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
/* ---- the message bar ---- */
var cf=$('#composer');if(cf){var ta=$('#cmsg');
 ta.addEventListener('input',function(){ta.style.height='auto';ta.style.height=Math.min(ta.scrollHeight,140)+'px'});
 ta.addEventListener('keydown',function(e){if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();cf.requestSubmit?cf.requestSubmit():cf.dispatchEvent(new Event('submit',{cancelable:true}))}});
 cf.addEventListener('submit',function(e){e.preventDefault();var v=ta.value.trim();if(!v){ta.focus();return}ta.value='';ta.style.height='auto';
  if(Q){if(isQuestion(v)){replyHelp(v,Q.side);return}var r=Q.take(v);
   if(r=='date'){Q.side.innerHTML='';Q.side.appendChild(botBubble('<p>Please use the date box above. For example 04/05/2016.</p>'))}
   else if(r=='none'){Q.side.innerHTML='';Q.side.appendChild(meBubble(v));Q.side.appendChild(botBubble('<p>Please tap one of the answers above. If none of them fit, tap <strong>Something else</strong> and type it there.</p>'))}
   else Q.side.innerHTML='';return}
  if(ROUTE.length&&!(isQuestion(v)&&!route(v))){replyRoute(v);return}
  replyHelp(v)})}
})();
