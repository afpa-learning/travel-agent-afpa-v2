// --- Theme toggle ---------------------------------------------------------
const themeSwitch = document.getElementById('themeSwitch');
const root = document.documentElement;
let MAX_MESSAGES=20;


function applyTheme(isLight){
  root.setAttribute('data-theme', isLight ? 'light' : 'dark');
  themeSwitch.checked = isLight;
}
applyTheme(false); // sombre par défaut, à l'image de la maquette d'origine

themeSwitch.addEventListener('change', () => applyTheme(themeSwitch.checked));

// --- Chat logic -------------------------------------------------------------
const chatScroll = document.getElementById('chatScroll');
const chatInput = document.getElementById('chatInput');
const sendBtn = document.getElementById('sendBtn');
const newConversation = document.getElementById('newConversation');

function scrollDown(){
  chatScroll.scrollTop = chatScroll.scrollHeight;
}

function addUserMessage(text){
  const div = document.createElement('div');
  div.className = 'msg user';
  div.textContent = text;
  chatScroll.appendChild(div);
  scrollDown();
}

function addSystemNotice(text){
  const div = document.createElement('div');
  div.className = 'msg system';
  div.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg><span>${text}</span>`;
  chatScroll.appendChild(div);
  scrollDown();
}

function addAssistantHTML(innerHTML){
  const div = document.createElement('div');
  div.className = 'msg assistant';
  div.innerHTML = innerHTML;
  chatScroll.appendChild(div);
  scrollDown();
}

function showTyping(){
  const div = document.createElement('div');
  div.className = 'typing';
  div.id = 'typingIndicator';
  div.innerHTML = '<span></span><span></span><span></span>';
  chatScroll.appendChild(div);
  scrollDown();
  return div;
}

function clearConversation() {
  chatScroll.innerHTML="";
  chatInput.value='';
  scrollDown();
  fetchClearHistory();
  chatInput.focus();
}

const QUESTIONS = {
  "reservations": "Combien de réservations confirmées, et revenu total réservé ?",
  "top-cities": "Top 3 des villes de destination par revenu total.",
  "nights": "Nombre moyen de nuits par région.",
  "top-customers": "Qui sont mes 5 meilleurs clients par dépense ?",
  "monthly": "Revenu par mois pour 2026.",
  "sample": "Montrer 5 réservations types."
};

function handleSend(text){
  if(!text) return;
  addUserMessage(text);
  chatInput.value = '';
  fetchAsk(text);
}

newConversation.addEventListener('click', () => clearConversation());

sendBtn.addEventListener('click', () => handleSend(chatInput.value.trim()));
chatInput.addEventListener('keydown', (e) => {
  if(e.key === 'Enter') handleSend(chatInput.value.trim());
});

document.querySelectorAll('.suggestion').forEach(btn => {
  btn.addEventListener('click', () => {
    clearConversation();
    const key = btn.dataset.q;
    handleSend(QUESTIONS[key]);
  });
});

// --- Cache logic ------------------------------------------------------------

const cacheSelect= document.getElementById('cacheSelect');

function calculateCachePercent(value) {
  cacheSelect.innerText=Math.round((value*100)/MAX_MESSAGES)+" %";
}

document.getElementById('clearCache').addEventListener('click', () => {
  fetchClearHistory();
  addSystemNotice("Cache vidé. Les prochaines requêtes seront recalculées.");
});

// --- Calls to back-end (IA, MCP Server) ------------------------------------------------------------

async function fetchCallTool() {
  try {
    const res = await fetch("/api/call", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        tool_name: "search_flights",
        arguments: { origin: "CDG", destination: "HND" }
      })
    });
    const data = await res.json();
    console.log(data);
  } catch (error) {
      
      addSystemNotice("Erreur lors de la récupération : "+error);
  }
}

async function fetchAsk(demand) {
  showTyping();
  try {
    const res = await fetch("/api/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        question: demand
      })
    });
    const data = await res.json();
    
    const html = marked.parse(data.reply);
    addAssistantHTML(html);
    const t = document.getElementById('typingIndicator');
    if(t) t.remove();
    
    return data;
  } catch (error) {
      const t = document.getElementById('typingIndicator');
      if(t) t.remove();
      addSystemNotice("Erreur lors de la récupération : "+error);
  }
  fetchHistory();
}

async function fetchClearHistory() {
  try {
       const response = await fetch("/api/history/reset");
       if (!response.ok) {
           addSystemNotice(`Erreur HTTP : ${response.status}`);
       }
       const data = await response.json();
       calculateCachePercent(0);
  } catch (error) {
      addSystemNotice("Erreur lors de la récupération : "+error);
  }
}

async function fetchHistory() {
  try {
    const res = await fetch("/api/history");
    const data = await res.json();
    
    calculateCachePercent(data.history.length);
  } catch (error) {
      addSystemNotice("Erreur lors de la récupération : "+error);
  }
}

async function fetchApiStatus() {
   try {
       const response = await fetch("/api/status");
       if (!response.ok) {
           addSystemNotice(`Erreur HTTP : ${response.status}`);
       }
       const data = await response.json();
       
      if (data.mcp_connected=="False") {
        document.getElementById("connectedMcp").classList.remove("ok");
        document.getElementById("connectedMcp").classList.add("error");
        document.getElementById("connectedMcp").innerHTML='<span class="dot"></span>MCP: déconnecté';
      } else {
        document.getElementById("connectedMcp").classList.remove("error");
        document.getElementById("connectedMcp").classList.add("ok");
        document.getElementById("connectedMcp").innerHTML='<span class="dot"></span>MCP: connecté';
      }
      if (data.llm_connected=="False") {
        document.getElementById("connectedLLM").classList.remove("ok");
        document.getElementById("connectedLLM").classList.add("error");
        document.getElementById("connectedLLM").innerHTML='<span class="dot"></span>LLM: déconnecté';
      } else {
        document.getElementById("connectedLLM").classList.remove("error");
        document.getElementById("connectedLLM").classList.add("ok");
        document.getElementById("connectedLLM").innerHTML='<span class="dot"></span>LLM: connecté';
      }


      if (data.tools !=null) {
         document.getElementById("toolsList").innerHTML="";
          data.tools.forEach((tool, index) => {
              document.getElementById("toolsList").innerHTML+='<div class="tool-item tooltip"><span class="dot"></span>'+tool.name+'<span class="tooltiptext">'+tool.description+'</span></div>';
              
            });
      } 
      MAX_MESSAGES=data.max_messages;

      addUserMessage(QUESTIONS["sample"]);
      fetchAsk(QUESTIONS["sample"]);
      //fetchCallTool();
      
   } catch (error) {
       addSystemNotice("Erreur lors de la récupération : "+error);
   }
}
fetchApiStatus();

