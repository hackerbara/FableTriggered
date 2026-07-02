async function wpf(e,t){if(!e.isLite||!e.fullPath)return e;
let n=await Nmc(e.fullPath,e.fileSize??0,t),b=!1;
try{let l=D$.readFileSync(e.fullPath,"utf8");
b=l.includes("claude-fable-5")&&(l.includes('"type":"fallback"')||l.includes("model_refusal_fallback"))}catch{}
let r=n.projectPath!==void 0&&Dg.dirname(e.fullPath)===t_(n.projectPath),
o=n.relocatedCwd??(r||e.projectPath===void 0?n.projectPath??e.projectPath:e.projectPath),
s={...e,isLite:!1,firstPrompt:n.firstPrompt,gitBranch:n.gitBranch,isSidechain:n.isSidechain,
teamName:n.teamName,sessionKind:n.sessionKind,customTitle:n.customTitle,aiTitle:n.aiTitle,
summary:n.summary,tag:n.tag,agentSetting:n.agentSetting,prNumber:n.prNumber,prUrl:n.prUrl,
prRepository:n.prRepository,projectPath:o,fableClassifierTriggered:b};
if(!s.firstPrompt&&!s.customTitle&&!s.aiTitle)s.firstPrompt="(session)";
if(s.isSidechain||s.teamName||s.sessionKind==="daemon"||s.sessionKind==="daemon-worker")return null;
let i=rgn.has(Tmc()??"");if(!i&&rgn.has(n.entrypoint??""))return null;
if(!i&&n.isLoopSession)return null;return s}
