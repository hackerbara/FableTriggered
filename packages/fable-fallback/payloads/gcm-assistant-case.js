case"assistant":{let R=n.message.content?.find((O)=>O?.type==="fallback");
if(R){let w=R.from?.model??"original model",k=R.to?.model??"fallback model",
x=`${w} triggered a model refusal fallback. Switched to ${k}.`;
return Ab.jsx(mEl,{message:{type:"system",subtype:"model_refusal_fallback",direction:"retry",
content:x,level:"warning",trigger:"refusal",originalModel:w,fallbackModel:k,requestId:n.requestId,
apiRefusalCategory:R.apiRefusalCategory,apiRefusalExplanation:null,isMeta:!1,timestamp:n.timestamp,uuid:n.uuid},
addMargin:s,verbose:l,isTranscriptMode:h})}
let w=r.firstTextBlockUuidByMessageID.get(n.message.id),k=o??"100%",
x=n.message.content.map((O,M)=>Ab.jsx(SCm,{param:O,addMargin:s,tools:i,commands:a,verbose:l,
inProgressToolUseIDs:c,progressMessagesForMessage:u,shouldAnimate:d,shouldShowDot:p,width:f,
inProgressToolCallCount:c.size,isTranscriptMode:h,lookups:r,onOpenRateLimitOptions:g,
advisorModel:n.advisorModel,messageUuid:n.uuid,apiMessageId:S?void 0:n.message.id,
isFirstTextBlock:w===void 0||w===n.uuid},M));
return Ab.jsx(B,{flexDirection:"column",width:k,children:x})}
