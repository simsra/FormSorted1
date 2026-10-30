/* "Ask a question?" helper (FormSorted, Oct 2026). Automatic answers from our help pages. Used on the website and the app's steps 1-2.
   <script src="ask.js" defer data-api="https://app.formsorted.com" data-choose="/#prices"></script>  (data-api "" = same site) */
(function(){
  var me=document.currentScript||document.querySelector('script[src*="ask.js"]'); if(!me||document.getElementById('askw'))return;
  var API=(me.getAttribute('data-api')||'').replace(/\/$/,'')+'/api/ask', CHOOSE=me.getAttribute('data-choose')||'/#prices', MAXQ=300;
  var css='#askw{position:fixed;right:16px;bottom:16px;z-index:50;font-family:inherit}'+
  '#askw .ask-open{display:inline-flex;align-items:center;gap:10px;min-height:56px;padding:0 22px;border-radius:999px;border:2px solid #fff;background:#0b1432;color:#fff;font:inherit;font-size:1.05rem;font-weight:700;cursor:pointer;box-shadow:0 6px 20px rgba(11,20,50,.28)}'+
  '#askw .ask-open:hover{background:#26357a}#askw .ask-open:focus-visible,#askw button:focus-visible,#askw textarea:focus-visible{outline:3px solid #ffbf47;outline-offset:2px}'+
  '#askw .ask-q{display:inline-grid;place-items:center;width:30px;height:30px;border-radius:50%;background:#9db1f9;color:#0b1432;font-weight:800}'+
  '#askw .ask-panel{position:fixed;right:16px;bottom:16px;width:420px;max-width:calc(100vw - 32px);max-height:min(680px,calc(100vh - 32px));display:flex;flex-direction:column;background:#fff;color:#0b1432;border-radius:24px;box-shadow:0 12px 40px rgba(11,20,50,.35);overflow:hidden;border:2px solid #0b1432}'+
  '#askw .ask-head{background:#0b1432;color:#fff;padding:18px 20px;display:flex;gap:12px;align-items:flex-start;justify-content:space-between}'+
  '#askw .ask-head h2{margin:0;font-size:1.3rem;line-height:1.25;color:#fff;font-family:inherit;letter-spacing:0}#askw .ask-head p{margin:4px 0 0;font-size:1rem;color:#c9d4fc}'+
  '#askw .ask-x{min-height:48px;min-width:48px;padding:0 14px;border-radius:999px;border:2px solid #9db1f9;background:transparent;color:#fff;font:inherit;font-size:1rem;font-weight:700;cursor:pointer}'+
  '#askw .ask-body{padding:16px 20px;overflow:auto;flex:1;font-size:1.1rem;line-height:1.5}'+
  '#askw .ask-note{background:#eef1fe;border-radius:16px;padding:12px 14px;margin:0 0 14px;font-size:1rem}'+
  '#askw .ask-sugg{display:flex;flex-wrap:wrap;gap:8px;margin:0 0 6px}#askw .ask-sugg button{min-height:48px;padding:8px 14px;border-radius:999px;border:2px solid #9db1f9;background:#fff;color:#0b1432;font:inherit;font-size:1rem;cursor:pointer;text-align:left}'+
  '#askw .ask-msg{margin:12px 0;padding:0;background:none;border:0;font-size:1.1rem}#askw .ask-msg p{font-size:1.1rem;line-height:1.5;max-width:none}#askw .ask-msg .who{display:block;font-size:.9rem;font-weight:700;color:#3f4766;margin-bottom:2px}'+
  '#askw .ask-msg.ask-you p{background:#f3f4f6;border-radius:16px;padding:10px 14px;margin:0}#askw .ask-msg.ask-bot p{background:#eef1fe;border-radius:16px;padding:10px 14px;margin:0}'+
  '#askw .ask-msg a{color:#0b1432;font-weight:700}#askw .ask-go{display:inline-flex;align-items:center;min-height:52px;margin-top:10px;padding:0 22px;border-radius:999px;background:#0b1432;color:#fff!important;text-decoration:none;font-weight:700}'+
  '#askw form{border-top:1px solid #e5eafd;padding:14px 20px 18px;background:#fff}#askw label{display:block;font-weight:700;margin-bottom:6px;font-size:1.05rem}'+
  '#askw textarea{width:100%;box-sizing:border-box;min-height:84px;padding:12px;border:2px solid #0b1432;border-radius:14px;font:inherit;font-size:1.1rem;resize:vertical;color:#0b1432}'+
  '#askw .ask-row{display:flex;justify-content:space-between;align-items:center;gap:12px;margin-top:10px}#askw .ask-count{font-size:.95rem;color:#3f4766}'+
  '#askw .ask-send{min-height:52px;padding:0 28px;border-radius:999px;border:0;background:#0b1432;color:#fff;font:inherit;font-size:1.1rem;font-weight:700;cursor:pointer}#askw .ask-send[disabled]{opacity:.6}'+
  '@media (max-width:600px){#askw{right:12px;bottom:12px}#askw .ask-panel{right:0;left:0;bottom:0;width:100%;max-width:100%;max-height:92vh;border-radius:24px 24px 0 0;border-width:2px 0 0}}'+
  'body.askw-pad{padding-bottom:84px}';
  var st=document.createElement('style'); st.textContent=css; document.head.appendChild(st);
  var w=document.createElement('div'); w.id='askw';
  w.innerHTML='<button type="button" class="ask-open" aria-expanded="false" aria-controls="askp"><span class="ask-q" aria-hidden="true">?</span>Ask a question?</button>'+
   '<div class="ask-panel" id="askp" role="dialog" aria-labelledby="askt" hidden><div class="ask-head"><div><h2 id="askt">Ask a question?</h2><p>Instant answers from our help pages</p></div><button type="button" class="ask-x">Close</button></div>'+
   '<div class="ask-body" aria-live="polite"><p class="ask-note">This is an automatic helper. It answers from our help pages only. It can\u2019t fill in your form or write your answers. Please don\u2019t type personal details.</p>'+
   '<div class="ask-sugg"><button type="button">How much does it cost?</button><button type="button">When do I pay?</button><button type="button">Do you send the form for me?</button></div><div class="ask-log"></div></div>'+
   '<form novalidate><label for="askq">Your question</label><textarea id="askq" maxlength="'+MAXQ+'" rows="2"></textarea><div class="ask-row"><span class="ask-count" aria-live="off">0 of '+MAXQ+'</span><button class="ask-send" type="submit">Ask</button></div></form></div>';
  document.body.appendChild(w); document.body.classList.add('askw-pad');
  var open=w.querySelector('.ask-open'), panel=w.querySelector('.ask-panel'), x=w.querySelector('.ask-x'), f=w.querySelector('form'), ta=w.querySelector('textarea'),
      log=w.querySelector('.ask-log'), body=w.querySelector('.ask-body'), cnt=w.querySelector('.ask-count'), send=w.querySelector('.ask-send');
  function show(on){panel.hidden=!on; open.hidden=on; open.setAttribute('aria-expanded',on?'true':'false'); if(on)ta.focus(); else open.focus();}
  open.onclick=function(){show(true)}; x.onclick=function(){show(false)};
  document.addEventListener('keydown',function(e){if(e.key==='Escape'&&!panel.hidden)show(false)});
  ta.oninput=function(){cnt.textContent=ta.value.length+' of '+MAXQ};
  ta.onkeydown=function(e){if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();f.requestSubmit?f.requestSubmit():f.onsubmit(e)}};
  function esc(s){return String(s).replace(/[&<>"]/g,function(c){return{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]})}
  function link(s){return esc(s).replace(/hello@formsorted\.com/g,'<a href="mailto:hello@formsorted.com">hello@formsorted.com</a>')}
  function add(cls,who,html){var d=document.createElement('div');d.className='ask-msg '+cls;d.innerHTML='<span class="who">'+who+'</span>'+html;log.appendChild(d);body.scrollTop=body.scrollHeight;return d}
  function ask(q){
    q=q.trim(); if(!q)return; add('ask-you','You asked','<p>'+esc(q)+'</p>'); ta.value=''; ta.oninput(); send.disabled=true; send.textContent='Finding\u2026';
    var wait=add('ask-bot','Answer from our help pages','<p>Looking in our help pages\u2026</p>');
    fetch(API,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({q:q,page:location.pathname+location.search})})
     .then(function(r){return r.json()}).then(function(j){
        wait.innerHTML='<span class="who">Answer from our help pages</span><p>'+link(j.answer||'')+'</p>'+(j.choose?'<a class="ask-go" href="'+esc(CHOOSE)+'">Choose your form</a>':'');
     }).catch(function(){wait.innerHTML='<span class="who">Answer from our help pages</span><p>Sorry, the helper isn\u2019t working right now. Try \u201cQuestions people ask\u201d on this page, or email <a href="mailto:hello@formsorted.com">hello@formsorted.com</a>.</p>'})
     .then(function(){send.disabled=false;send.textContent='Ask';body.scrollTop=body.scrollHeight});
  }
  f.onsubmit=function(e){e.preventDefault();ask(ta.value)};
  w.querySelectorAll('.ask-sugg button').forEach(function(b){b.onclick=function(){ask(b.textContent)}});
})();
