case"assistant":{let R=n.message.content?.find((O)=>O?.type==="fallback");
if(R){let w=R.from?.model??"original model",k=R.to?.model??"fallback model",
x=`Fable classifier triggered: ${w} triggered a model refusal fallback. Switched to ${k}.`;
return Hb.jsx(nvl,{message:{type:"system",subtype:"model_refusal_fallback",direction:"retry",
content:x,level:"warning",trigger:"refusal",originalModel:w,fallbackModel:k,requestId:n.requestId,
apiRefusalCategory:R.apiRefusalCategory,apiRefusalExplanation:null,isMeta:!1,timestamp:n.timestamp,uuid:n.uuid},
addMargin:s,verbose:l,isTranscriptMode:h})}
let x=r.firstTextBlockUuidByMessageID.get(n.message.id),k=o??"100%",
w=n.message.content.map((O,L)=>Hb.jsx(e0m,{param:O,addMargin:s,tools:i,commands:a,verbose:l,
inProgressToolUseIDs:c,progressMessagesForMessage:u,shouldAnimate:d,shouldShowDot:p,width:f,
inProgressToolCallCount:c.size,isTranscriptMode:h,lookups:r,onOpenRateLimitOptions:g,
advisorModel:n.advisorModel,messageUuid:n.uuid,apiMessageId:S?void 0:n.message.id,
isFirstTextBlock:x===void 0||x===n.uuid},L));
return Hb.jsx(B,{flexDirection:"column",width:k,children:w})}
