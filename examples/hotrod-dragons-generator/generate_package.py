"""Generate the packages/hotrod-dragons/ patch package (schemaVersion 2) from the
verified dragon-scene edits. Emits patch.json + payloads/*.js, computing every
sha256 / length against the pinned clean 2.1.199 cli.js module.

Also self-verifies: applying the emitted operations to the clean module reproduces
exactly the module the standalone build script produces.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

# Repo-relative: this script lives at examples/hotrod-dragons-generator/, two
# levels below the repo root.
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))
from claude_monkey.macho import find_macho_layout
from claude_monkey.bun_graph import parse_bun_section

# Requires a local install of the pinned Claude Code binary (see README).
SOURCE = Path.home() / '.local/share/claude/versions/2.1.199'
DATA = Path(__file__).resolve().parent / 'v11-data.json'
PKG = ROOT / 'packages/hotrod-dragons'
MODULE = '/$bunfs/root/src/entrypoints/cli.js'
EXPECTED_SOURCE_SHA = 'e3cb61abc8a2ec7b98976cee1ffdde5a3fa755c9990bc8d688cd89290e0dcec0'
EXPECTED_MODULE_SHA = 'e30c857c2e1130ff0fa9d14349a210c588f8115fc8ac86e120c454547efc0c55'

# --- helper (same as build-hotrod-dragons-final.py, literal colors) ----------
HELPER_TEMPLATE = r'''
let __hdData=__DATA__;
let __hdPal=__hdData.pal,__hdW=__hdData.w,__hdPhases=__hdData.phases,__hdFireRows=__hdData.fireCellRows,__hdStaticRows=__hdData.cellRows-__hdData.fireCellRows;
let __hdHALF=String.fromCharCode(9600),__hdESC=String.fromCharCode(27);
let __hdTrue=/truecolor|24bit/i.test(process.env.COLORTERM||"");
function __hdCube(v){return v<48?0:v<115?1:Math.round((v-35)/40)}
function __hdSgr(rgb,bg){let base=bg?48:38;if(__hdTrue)return base+";2;"+rgb[0]+";"+rgb[1]+";"+rgb[2];let r=__hdCube(rgb[0]),g=__hdCube(rgb[1]),b=__hdCube(rgb[2]),n=16+36*r+6*g+b;return base+";5;"+n}
function __hdRun(run){let t=__hdPal[run[0]],b=__hdPal[run[1]];return __hdESC+"["+__hdSgr(t,!1)+";"+__hdSgr(b,!0)+"m"+__hdHALF.repeat(run[2])}
function __hdAssemble(band,mirror){let lines=[];for(let r=0;r<band.length;r++){let runs=band[r],s="";if(mirror)for(let i=runs.length-1;i>=0;i--)s+=__hdRun(runs[i]);else for(let i=0;i<runs.length;i++)s+=__hdRun(runs[i]);lines.push(s+__hdESC+"[0m")}return lines.join("\n")}
let __hdStaticStr=__hdAssemble(__hdData.staticBand,!1),__hdStaticStrM=__hdAssemble(__hdData.staticBand,!0);
let __hdTowerStr=__hdAssemble(__hdData.tower,!1),__hdTowerStrM=__hdAssemble(__hdData.tower,!0);
let __hdFireStr=[],__hdFireStrM=[];for(let p=0;p<__hdPhases;p++){__hdFireStr.push(__hdAssemble(__hdData.fireBands[p],!1));__hdFireStrM.push(__hdAssemble(__hdData.fireBands[p],!0))}
function __hdRawNode(str,rows,key){return zd.jsx("ink-raw-ansi",{rawText:str,rawWidth:__hdW,rawHeight:rows},key)}
function __hdWall(fireStr,staticStr,key){return zd.jsxs(B,{flexShrink:0,flexDirection:"column",backgroundColor:"rgb(0,0,0)",children:[__hdRawNode(fireStr,__hdFireRows,key+"-fire"),__hdRawNode(staticStr,__hdStaticRows,key+"-static")]},key)}
function __CodexHotrodSpriteSceneV11({rows:e,columns:t}){let n=Math.max(16,Math.min((e??30)-2,120)),sw=__hdW,[ph,setPh]=S_.useState(0);S_.useEffect(()=>{let tk=setInterval(()=>setPh((p)=>(p+1)%__hdPhases),95);return()=>clearInterval(tk)},[]);return zd.jsxs(zd.Fragment,{children:[zd.jsx(B,{position:"absolute",top:0,left:sw,right:sw,bottom:0,backgroundColor:"rgb(0,0,0)"},"codex-hotrod-v11-core"),zd.jsx(B,{position:"absolute",top:0,left:0,width:sw,height:n,overflow:"hidden",flexDirection:"column",justifyContent:"flex-end",backgroundColor:"rgb(0,0,0)",children:__hdWall(__hdFireStr[ph],__hdStaticStr,"codex-hotrod-v11-left")},"codex-hotrod-v11-left-wrap"),zd.jsx(B,{position:"absolute",top:0,right:0,width:sw,height:n,overflow:"hidden",flexDirection:"column",justifyContent:"flex-end",backgroundColor:"rgb(0,0,0)",children:__hdWall(__hdFireStrM[ph],__hdStaticStrM,"codex-hotrod-v11-right")},"codex-hotrod-v11-right-wrap")]})}
function __CodexHotrodCastleBottomV11({children:e}){let sw=__hdW;return zd.jsxs(B,{flexDirection:"column",width:"100%",flexShrink:0,backgroundColor:"rgb(18,20,24)",children:[zd.jsxs(B,{flexDirection:"row",width:"100%",backgroundColor:"rgb(18,20,24)",children:[zd.jsx(B,{width:sw,flexShrink:0,flexGrow:0,children:__hdRawNode(__hdTowerStr,__hdData.tower.length,"codex-hotrod-v11-tower-left")},"codex-hotrod-v11-tower-left-wrap"),zd.jsx(B,{flexDirection:"column",flexGrow:1,flexShrink:1,overflowY:"hidden",backgroundColor:"rgb(0,0,0)",children:e},"codex-hotrod-v11-bottom-core"),zd.jsx(B,{width:sw,flexShrink:0,flexGrow:0,children:__hdRawNode(__hdTowerStrM,__hdData.tower.length,"codex-hotrod-v11-tower-right")},"codex-hotrod-v11-tower-right-wrap")]})]})}
'''


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def build_helper() -> str:
    data = json.loads(DATA.read_text())
    payload = json.dumps(data, separators=(',', ':'))
    helper = HELPER_TEMPLATE.replace('__DATA__', payload)
    assert '▀' not in helper and '\x1b' not in helper
    return helper


def main() -> None:
    raw = SOURCE.read_bytes()
    assert sha(raw) == EXPECTED_SOURCE_SHA, 'source sha mismatch'
    layout = find_macho_layout(raw)
    graph = parse_bun_section(raw[layout.bun_section.offset:layout.bun_section.offset + layout.bun_section.size])
    module = graph.module_by_path(MODULE)
    assert sha(module.content) == EXPECTED_MODULE_SHA, 'module sha mismatch'
    src = module.content.decode('utf-8')

    helper = build_helper()
    V8O = 'function V8o(e){let t=KJe.c(78)'

    # (seam, label, exact-anchor, replacement-new-string, requireWithinRange, behaviorChange)
    ops = [
        ('scene-helpers-before-v8o',
         'Insert dragon scene helpers + baked art data before app shell V8o',
         V8O, helper + V8O, ['function V8o(e){'],
         'Defines the ink-raw-ansi dragon/fire scene components and embeds the baked '
         'half-block art data (no behavior change until the scene is mounted below).'),
        ('fullscreen-scene-pe',
         'Mount dragon scene in the fullscreen conversation view (pe)',
         'pe=zd.jsxs(B,{flexGrow:1,flexDirection:"column",overflow:"hidden",children:[Q,ee,ne,oe,ie]})',
         'pe=zd.jsxs(B,{flexGrow:1,flexDirection:"column",overflow:"hidden",backgroundColor:"rgb(0,0,0)",paddingX:32,children:[zd.jsx(__CodexHotrodSpriteSceneV11,{rows:y,columns:T},"codex-hotrod-v11-scene"),Q,ee,ne,oe,ie]})',
         ['children:[Q,ee,ne,oe,ie]'],
         'Renders the two side dragon walls (fire + serpentine body) around the '
         'conversation, reserving 32-cell gutters via paddingX.'),
        ('composer-flank-ue',
         'Continue the dragon tail into the composer flanks (ue)',
         'ue=zd.jsx(B,{flexDirection:"column",width:"100%",flexGrow:1,flexShrink:0,overflowY:"hidden",children:s})',
         'ue=zd.jsx(__CodexHotrodCastleBottomV11,{children:s},"codex-hotrod-v11-bottom-instance")',
         ['flexGrow:1,flexShrink:0,overflowY:"hidden",children:s'],
         'Wraps the composer so the dragon body continues into the bottom-corner flanks.'),
        ('composer-parent-le',
         'Dark background on the bottom chrome parent (le)',
         'le=zd.jsxs(B,{flexDirection:"column",flexShrink:0,width:"100%",maxHeight:w,children:[Ee,ce,ue]})',
         'le=zd.jsxs(B,{flexDirection:"column",flexShrink:0,width:"100%",maxHeight:w,backgroundColor:"rgb(18,20,24)",children:[Ee,ce,ue]})',
         ['children:[Ee,ce,ue]'],
         'Blends the composer chrome background with the scene.'),
        ('fallback-scene-v',
         'Mount dragon scene in the non-fullscreen fallback path (V)',
         'V=zd.jsxs(zd.Fragment,{children:[n,s,i]})',
         'V=zd.jsxs(B,{flexGrow:1,flexDirection:"column",backgroundColor:"rgb(0,0,0)",paddingX:32,children:[zd.jsx(__CodexHotrodSpriteSceneV11,{rows:y,columns:T},"codex-hotrod-v11-scene-fallback"),n,s,i]})',
         ['V=zd.jsxs(zd.Fragment,{children:[n,s,i]})'],
         'Shows the dragon scene when the app renders outside the fullscreen alt-screen path.'),
    ]

    # verify each anchor is unique, apply sequentially to reproduce the build output
    applied = src
    operations = []
    payload_dir = PKG / 'payloads'
    payload_dir.mkdir(parents=True, exist_ok=True)
    for i, (seam, label, exact, new, within, behavior) in enumerate(ops, start=1):
        if src.count(exact) != 1:
            raise SystemExit(f'{seam}: anchor not unique ({src.count(exact)})')
        op_id = f'hotrod-dragons-{seam}-2-1-199'
        pay_name = f'{i:02d}-{op_id}.js'
        (payload_dir / pay_name).write_text(new)
        operations.append({
            'opId': op_id,
            'label': label,
            'type': 'replace_exact',
            'exact': exact,
            'requireWithinRange': within,
            'oldRangeSha256': sha(exact.encode()),
            'oldRangeLength': len(exact.encode()),
            'replacement': {
                'path': f'payloads/{pay_name}',
                'sha256': sha(new.encode()),
            },
            'knownBehaviorChange': behavior,
        })
        applied = applied.replace(exact, new, 1)

    patched_module = applied.encode('utf-8')

    preconditions = [
        {'type': 'module_must_contain', 'modulePath': MODULE, 'value': exact}
        for (_s, _l, exact, _n, _w, _b) in ops
    ]
    postconditions = [
        {'type': 'module_must_contain', 'modulePath': MODULE, 'value': v}
        for v in ['function __CodexHotrodSpriteSceneV11', '"ink-raw-ansi"',
                  'codex-hotrod-v11-scene', 'String.fromCharCode(9600)']
    ] + [
        {'type': 'module_must_not_contain', 'modulePath': MODULE, 'value': '▀'}  # no literal half-block
    ]

    manifest = {
        'schemaVersion': 2,
        'id': 'hotrod-dragons',
        'name': 'Hotrod Dragons',
        'description': 'Two heraldic fire-breathing dragons flank the terminal — high-def '
                       'half-block pixel art with 8-phase baked flame animation, drawn via '
                       "the renderer's native ink-raw-ansi direct-draw path.",
        'packageVersion': '1.0.0',
        'targets': [
            {
                'sourceIdentity': {
                    'claudeVersion': '2.1.199',
                    'versionOutput': '2.1.199 (Claude Code)',
                    'sha256': EXPECTED_SOURCE_SHA,
                    'sizeBytes': len(raw),
                    'platform': 'darwin',
                    'arch': 'arm64',
                },
                'requiredEngine': 'bun_graph_repack',
                'requiredBinaryFormat': 'bun_standalone_macho64',
                'modules': [
                    {
                        'path': MODULE,
                        'contentSha256': EXPECTED_MODULE_SHA,
                        'contentLength': len(module.content),
                        'operations': operations,
                    }
                ],
                'preconditions': preconditions,
                'postconditions': postconditions,
                'manualSmoke': {
                    'required': True,
                    'reason': 'Purely visual TUI art (animated dragons around the '
                              'conversation). Correct rendering, animation, and layout '
                              'must be confirmed in an interactive truecolor terminal.',
                },
            }
        ],
    }
    (PKG / 'patch.json').write_text(json.dumps(manifest, indent=2) + '\n')

    print('wrote', PKG / 'patch.json')
    print('operations:', len(operations))
    print('patched module length:', len(patched_module))
    print('patched module sha256:', sha(patched_module))


if __name__ == '__main__':
    main()
