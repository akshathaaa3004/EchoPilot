const $ = id => document.getElementById(id);
const input = $("cmd");
input.addEventListener("keydown", event => {
    if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();
        $("go").click();
    }
});
let currentCommandId = null;
let clarificationContext = null;
let timerInterval = null;
let activeTimerEnd = null;
let activeReminderId = null;

function esc(v) { return String(v ?? "").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c])); }
function row(label,value){return `<div class="row"><span>${esc(label)}</span><span>${esc(value)}</span></div>`;}
fetch("/api/health").then(r=>{$("api").textContent=r.ok?"Connected":"Offline"}).catch(()=>$("api").textContent="Offline");

$("go").addEventListener("click", async()=>{
  const text=input.value.trim(); if(!text){alert("Type or speak a command first.");input.focus();return;}
  $("go").disabled=true; $("go").textContent="Understanding…";
  try{
    const r=await fetch("/api/interpret",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({text,context:clarificationContext})});
    const d=await r.json(); if(!r.ok) throw new Error(d.detail||"Could not interpret command.");
    render(d);
    if (d.status === "needs_clarification") {
    clarificationContext = d.context || {
        intent: d.intent,
        original_text: d.transcript
    };
} else if (d.status === "awaiting_confirmation") {
    clarificationContext = null;
} else if (d.status === "unsupported" || d.status === "info") {
    clarificationContext = null;
}
  }catch(e){$("preview").innerHTML=`<div class="preview warn">Could not reach the backend. Check that the server is running.</div>`;}
  finally{$("go").disabled=false;$("go").textContent="Interpret command →";}
});

function render(d){
  currentCommandId = d.command_id || null;
  clarificationContext = 
    d.status === "needs_clarification" 
      ? (d.context || {
          intent: d.intent,
          original_text: d.transcript
        }) 
      : null;

  const entities = Object.entries(d.entities||{}).map(([k,v])=>row(k.replaceAll("_"," "),typeof v==="object"?JSON.stringify(v):v)).join("");
  $("analysis").innerHTML = row("Detected intent",String(d.intent||"unknown").replaceAll("_"," "))+row("Status",d.status)+row("Original command",d.transcript)+(entities||row("Extracted entities","None detected"))+(d.clarification?`<div class="question"><b>EchoPilot asks:</b><br>${esc(d.clarification)}</div>`:"");
  if(d.status==="awaiting_confirmation"){
    $("preview").innerHTML = `<div class="preview">${esc(d.preview||"Review this action.")}</div><p class="hint">Nothing happens until you confirm.</p><div class="buttons"><button id="confirm" class="good">✓ Confirm & run</button><button id="cancel" class="warn">Cancel</button></div>`;
    $("confirm").onclick = ()=>confirmCommand(true);$("cancel").onclick = ()=>confirmCommand(false);
  }else{
    $("preview").innerHTML = `<div class="preview">${esc(d.message||d.clarification||"No action available.")}</div>`;
  }
}

async function confirmCommand(confirmed){
  if(!currentCommandId)return;const id=currentCommandId;currentCommandId=null;
  try{
    const r=await fetch("/api/confirm",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({command_id:id,confirmed})});
    const d=await r.json();if(!r.ok||d.status==="error")throw new Error(d.message||"Confirmation failed.");
    if(d.status==="cancelled"){$("preview").innerHTML=`<div class="preview warn">${esc(d.message)}</div>`;return;}
    await performAction(d.action);
  }catch(e){$("preview").innerHTML=`<div class="preview warn">${esc(e.message)}</div>`;}
}
async function performAction(a){
  if(!a)return;
  
if (a.type === "multi_action") {
    $("preview").innerHTML =
        `<div class="preview">Executing confirmed actions…</div>`;

    for (let i = 0; i < a.actions.length; i++) {
        await performAction(a.actions[i]);
    }

    return;
}

  switch(a.type){
    case "set_timer": startTimer(a.seconds,a.label);break;
    case "cancel_timer":
      if(timerInterval)clearInterval(timerInterval);timerInterval=null;activeTimerEnd=null;
      $("preview").innerHTML=`<div class="preview warn">Timer cancelled.</div>`;break;
    case "create_note": saveNote(a.note);break;
    case "create_reminder": startReminder(a.seconds,a.task);break;
    case "open_website": openWebsite(a.website);break;
    
case "web_search":
    window.open(
        "https://www.google.com/search?q=" + encodeURIComponent(a.query),
        "_blank",
        "noopener"
    );
    $("preview").innerHTML =
        `<div class="preview good">Opened search results for: ${esc(a.query)}</div>`;
    break;

    case "tell_time":case "tell_date":case "show_result":
      $("preview").innerHTML=`<div class="preview good">${esc(a.value??a.label)}</div>`;break;
    default:$("preview").innerHTML=`<div class="preview">Confirmed, but no browser action is implemented for this type.</div>`;
  }
}
function fmt(s){s=Math.max(0,Math.ceil(s));const h=Math.floor(s/3600),m=Math.floor(s%3600/60),r=s%60;return h?`${String(h).padStart(2,"0")}:${String(m).padStart(2,"0")}:${String(r).padStart(2,"0")}`:`${String(m).padStart(2,"0")}:${String(r).padStart(2,"0")}`;}
function startTimer(seconds,label){
  if(timerInterval)clearInterval(timerInterval);const end=Date.now()+seconds*1000;activeTimerEnd=end;
  function tick(){if(activeTimerEnd!==end)return;const left=Math.max(0,(end-Date.now())/1000);
    $("preview").innerHTML=`<div class="tag good">TIMER RUNNING</div><div class="countdown">${fmt(left)}</div><div class="preview">Countdown for ${esc(label)}.</div><div class="buttons"><button id="stopTimer" class="warn">Cancel timer</button></div><p class="hint">Keep this webpage open. Background tabs may be throttled.</p>`;
    $("stopTimer").onclick=()=>{clearInterval(timerInterval);timerInterval=null;activeTimerEnd=null;$("preview").innerHTML=`<div class="preview warn">Timer cancelled.</div>`;};
    if(left<=0){clearInterval(timerInterval);timerInterval=null;activeTimerEnd=null;$("preview").innerHTML=`<div class="preview good"><b>⏰ Time's up!</b><br>Your ${esc(label)} timer has finished.</div>`;notify("EchoPilot timer","Your timer has finished.");beep();}
  }tick();timerInterval=setInterval(tick,250);
}
function saveNote(note){
  let notes=[];try{notes=JSON.parse(localStorage.getItem("echopilot_notes")||"[]")}catch{}
  notes.unshift({note,createdAt:new Date().toLocaleString()});
  try{localStorage.setItem("echopilot_notes",JSON.stringify(notes.slice(0,100)))}catch{}
  $("preview").innerHTML=`<div class="preview good">Note saved in this browser.</div>${row("Note",note)}${row("Saved at",new Date().toLocaleString())}<p class="hint">Stored locally in this browser, not in a cloud account.</p>`;
}
function startReminder(seconds,task){
  if(activeReminderId)clearTimeout(activeReminderId);
  $("preview").innerHTML=`<div class="preview good">Reminder scheduled in ${fmt(seconds)}: ${esc(task)}.</div><p class="hint">Keep this webpage open.</p>`;
  activeReminderId=setTimeout(()=>{$("preview").innerHTML=`<div class="preview good"><b>🔔 Reminder</b><br>${esc(task)}</div>`;notify("EchoPilot reminder",task);beep();activeReminderId=null;},seconds*1000);
}
async function notify(title,body){if(!("Notification"in window))return;try{if(Notification.permission==="granted")new Notification(title,{body});else if(Notification.permission!=="denied"&&await Notification.requestPermission()==="granted")new Notification(title,{body});}catch{}}
function beep(){try{const C=window.AudioContext||window.webkitAudioContext;if(!C)return;const c=new C(),o=c.createOscillator(),g=c.createGain();o.connect(g);g.connect(c.destination);o.frequency.value=880;g.gain.value=.12;o.start();o.stop(c.currentTime+.35);o.onended=()=>c.close();}catch{}}

function openWebsite(target) {
    let url = String(target || "").trim();

    if (!url) {
        $("preview").innerHTML =
            `<div class="preview warn">Please provide a website address.</div>`;
        return;
    }

    if (!/^https?:\/\//i.test(url)) {
        url = "https://" + url;
    }

    try {
        const u = new URL(url);

        if (
            !["http:", "https:"].includes(u.protocol) ||
            (!u.hostname.includes(".") && u.hostname !== "localhost")
        ) {
            throw new Error("Invalid website");
        }

        window.open(u.href, "_blank", "noopener");

        $("preview").innerHTML =
            `<div class="preview good">Requested website: ${esc(u.href)}. Allow pop-ups if it did not open.</div>`;
    } catch {
        $("preview").innerHTML =
            `<div class="preview warn">Invalid website address. Try example.com.</div>`;
    }
}

$("clear").addEventListener("click",()=>{input.value="";currentCommandId=null;clarificationContext=null;$("analysis").textContent="Your detected intent and extracted entities will appear here.";$("preview").textContent="Your action preview will appear here.";});
document.querySelectorAll("[data-c]").forEach(b=>b.addEventListener("click",()=>{input.value=b.dataset.c;input.focus();}));
const SR=window.SpeechRecognition||window.webkitSpeechRecognition;
if(!SR){$("mic").disabled=true;$("mic").textContent="Voice unsupported — type instead";$("miclabel").textContent="Use text input in this browser";}
else{const rec=new SR();rec.lang="en-IN";rec.interimResults=true;rec.continuous=false;rec.onstart=()=>$("miclabel").textContent="Listening…";rec.onresult=e=>{let t="";for(let i=e.resultIndex;i<e.results.length;i++)t+=e.results[i][0].transcript;input.value=t.trim();};rec.onerror=e=>{$("miclabel").textContent="Voice input failed — type instead";};rec.onend=()=>$("miclabel").textContent=input.value?"Speech captured — ready to interpret":"Ready to listen or type";$("mic").addEventListener("click",()=>{try{rec.start()}catch{alert("Microphone may already be active.")}});}
