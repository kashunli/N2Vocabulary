const LABELS={replace:"Accepted replacement",keep:"Kept original",custom:"Custom replacement",audio_problem:"Audio problem"};
const ids=["counts","position","progressBar","classificationFilter","decisionFilter","unitFilter","reviewCard","emptyState","indexLabel","unitLabel","classificationChip","scoreLabel","headword","audio","playButton","originalText","suggestionLabel","suggestedText","asrText","rawText","evidenceText","customText","reviewNote","acceptButton","keepButton","audioProblemButton","customButton","clearButton","decisionState","previousButton","nextButton","exportButton"];
const el=Object.fromEntries(ids.map(id=>[id,document.getElementById(id)]));
const state={sourceSha256:"",items:[],visible:[],cursor:0,saving:false};
const current=()=>state.visible[state.cursor]||null;
async function requestJson(url,options={}){
  const response=await fetch(url,options);const text=await response.text();let payload={};
  if(text){try{payload=JSON.parse(text)}catch{payload={error:text}}}
  if(!response.ok)throw new Error(payload.error||"Request failed: "+response.status);
  return payload;
}
function buildUnits(){
  for(const unit of [...new Set(state.items.map(item=>item.unit))].sort((a,b)=>a-b)){
    const option=document.createElement("option");option.value=String(unit);option.textContent="Unit "+unit;el.unitFilter.append(option);
  }
}
function applyFilters(preferred=null){
  const classification=el.classificationFilter.value,decisionFilter=el.decisionFilter.value,unit=el.unitFilter.value;
  const prior=preferred||(current()?String(current().source_index):null);
  state.visible=state.items.filter(item=>{
    if(classification!=="all"&&item.classification!==classification)return false;
    if(unit!=="all"&&String(item.unit)!==unit)return false;
    if(decisionFilter==="pending"&&item.decision)return false;
    if(decisionFilter==="decided"&&!item.decision)return false;
    if(["replace","keep","custom","audio_problem"].includes(decisionFilter)&&item.decision?.decision!==decisionFilter)return false;
    return true;
  });
  const found=state.visible.findIndex(item=>String(item.source_index)===prior);state.cursor=found>=0?found:0;render();
}
function render(){
  const reviewed=state.items.filter(item=>item.decision).length;
  el.counts.textContent=reviewed+" reviewed · "+(state.items.length-reviewed)+" pending";
  el.progressBar.style.width=state.items.length?(reviewed/state.items.length*100)+"%":"0%";
  const item=current();
  if(!item){el.reviewCard.hidden=true;el.emptyState.hidden=false;el.position.textContent="0 / 0";el.previousButton.disabled=true;el.nextButton.disabled=true;return}
  el.reviewCard.hidden=false;el.emptyState.hidden=true;el.position.textContent=(state.cursor+1)+" / "+state.visible.length;
  el.indexLabel.textContent="#"+item.source_index;el.unitLabel.textContent="Unit "+item.unit;
  const classLabels={source_confirmed:"Source-confirmed",ambiguous:"Ambiguous",source_supports_db:"Source supports original"};
  el.classificationChip.textContent=classLabels[item.classification]||item.classification;
  el.classificationChip.className="chip "+(item.classification==="source_confirmed"?"confirmed":item.classification==="ambiguous"?"ambiguous":"supports");
  el.scoreLabel.textContent="Audio score "+Number(item.audit_score).toFixed(3);el.headword.textContent=item.headword;
  el.originalText.textContent=item.expected;el.suggestedText.textContent=item.suggested_text;
  el.suggestionLabel.textContent=item.has_text_replacement?"Suggested replacement":"No text change suggested";
  el.asrText.textContent=item.transcript;el.rawText.textContent=item.raw_line||"No raw OCR block extracted";
  el.evidenceText.textContent="ASR/raw "+item.asr_vs_raw+" · DB/raw "+item.db_vs_raw+" · margin "+item.evidence_margin+" · "+item.raw_page;
  if(el.audio.dataset.sourceIndex!==String(item.source_index)){el.audio.pause();el.audio.src=item.audio_url;el.audio.dataset.sourceIndex=String(item.source_index)}
  const decision=item.decision;
  el.customText.value=decision&&["custom","replace"].includes(decision.decision)?decision.replacement_text:item.suggested_text;
  el.reviewNote.value=decision?.note||"";el.acceptButton.disabled=!item.has_text_replacement||state.saving;
  el.keepButton.disabled=state.saving;el.audioProblemButton.disabled=state.saving;el.customButton.disabled=state.saving;el.clearButton.disabled=!decision||state.saving;
  el.decisionState.textContent=decision?"Saved in wordService: "+(LABELS[decision.decision]||decision.decision):"Pending review";
  el.previousButton.disabled=state.cursor===0;el.nextButton.disabled=state.cursor>=state.visible.length-1;
}
async function saveDecision(kind,text){
  const item=current();if(!item||state.saving)return;state.saving=true;render();el.decisionState.textContent="Saving…";
  try{
    item.decision=await requestJson("/api/audio-review/"+item.source_index,{method:"PUT",headers:{"Content-Type":"application/json"},body:JSON.stringify({decision:kind,replacement_text:text,note:el.reviewNote.value.trim()})});
    state.saving=false;if(el.decisionFilter.value==="pending")applyFilters();else render();
  }catch(error){state.saving=false;render();el.decisionState.textContent=error.message}
}
async function clearDecision(){
  const item=current();if(!item?.decision||state.saving)return;state.saving=true;render();
  try{await requestJson("/api/audio-review/"+item.source_index,{method:"DELETE"});item.decision=null;state.saving=false;applyFilters(String(item.source_index))}
  catch(error){state.saving=false;render();el.decisionState.textContent=error.message}
}
function play(){if(!current())return;if(el.audio.paused)el.audio.play().catch(()=>{el.decisionState.textContent="Could not play this audio file."});else el.audio.pause()}
function move(delta){state.cursor=Math.max(0,Math.min(state.visible.length-1,state.cursor+delta));render()}
function exportDecisions(){
  const decisions=state.items.filter(item=>item.decision).map(item=>({source_index:item.source_index,unit:item.unit,headword:item.headword,decision:item.decision.decision,original_text:item.expected,replacement_text:item.decision.replacement_text,audio_clip:item.audio_clip,note:item.decision.note,updated_at:item.decision.updated_at}));
  const payload={version:1,source_sha256:state.sourceSha256,exported_at:new Date().toISOString(),decisions};
  const url=URL.createObjectURL(new Blob([JSON.stringify(payload,null,2)],{type:"application/json"}));const link=document.createElement("a");
  link.href=url;link.download="n2-audio-review-decisions.json";link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
}
el.playButton.addEventListener("click",play);
el.acceptButton.addEventListener("click",()=>{const item=current();if(item?.has_text_replacement)saveDecision("replace",item.suggested_text)});
el.keepButton.addEventListener("click",()=>{const item=current();if(item)saveDecision("keep",item.expected)});
el.audioProblemButton.addEventListener("click",()=>{const item=current();if(item)saveDecision("audio_problem",item.expected)});
el.customButton.addEventListener("click",()=>{const text=el.customText.value.trim();if(!text){el.decisionState.textContent="Enter edited text before saving.";el.customText.focus();return}saveDecision("custom",text)});
el.clearButton.addEventListener("click",clearDecision);el.previousButton.addEventListener("click",()=>move(-1));el.nextButton.addEventListener("click",()=>move(1));el.exportButton.addEventListener("click",exportDecisions);
[el.classificationFilter,el.decisionFilter,el.unitFilter].forEach(control=>control.addEventListener("change",()=>applyFilters()));
document.addEventListener("keydown",event=>{
  if(["TEXTAREA","INPUT","SELECT"].includes(event.target.tagName))return;
  if(event.code==="Space"){event.preventDefault();play()}else if(event.key==="ArrowLeft")move(-1);else if(event.key==="ArrowRight")move(1);
  else if(event.key.toLowerCase()==="a")el.acceptButton.click();else if(event.key.toLowerCase()==="k")el.keepButton.click();
  else if(event.key.toLowerCase()==="p")el.audioProblemButton.click();else if(event.key.toLowerCase()==="c")el.customText.focus();
});
async function load(){
  try{const payload=await requestJson("/api/audio-review");state.sourceSha256=payload.source_sha256;state.items=payload.items;buildUnits();applyFilters()}
  catch(error){el.counts.textContent="Could not load review";el.reviewCard.hidden=true;el.emptyState.hidden=false;el.emptyState.textContent=error.message}
}
load();
