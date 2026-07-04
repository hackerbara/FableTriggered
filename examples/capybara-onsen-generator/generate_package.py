"""Generate the packages/capybara-onsen/ patch package (schemaVersion 2) from the
verified onsen-scene edits. Emits patch.json + payloads/*.js, computing every
sha256 / length against the pinned clean 2.1.199 cli.js module.

Also self-verifies: applying the emitted operations to the clean module reproduces
exactly the module the standalone build script produces.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

# Repo-relative: this script lives at examples/capybara-onsen-generator/, two
# levels below the repo root.
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))
from claude_monkey.macho import find_macho_layout
from claude_monkey.bun_graph import parse_bun_section

# Requires a local install of the pinned Claude Code binary (see README).
SOURCE = Path.home() / '.local/share/claude/versions/2.1.199'
DATA = Path(__file__).resolve().parent / 'onsen-data.json'
PKG = ROOT / 'packages/capybara-onsen'
MODULE = '/$bunfs/root/src/entrypoints/cli.js'
EXPECTED_SOURCE_SHA = 'e3cb61abc8a2ec7b98976cee1ffdde5a3fa755c9990bc8d688cd89290e0dcec0'
EXPECTED_MODULE_SHA = 'e30c857c2e1130ff0fa9d14349a210c588f8115fc8ac86e120c454547efc0c55'

# --- helper (same idiom as hotrod-dragons/generate_package.py, literal colors) ------
# Two independent walls, screen-orientation, NO runtime mirroring (asymmetric scene:
# spout+soaking capybara left, stone lantern+resting capybara right). Animated band is
# at the BOTTOM of each wall; static band is the FIRST child (top), animated band is
# the second child (bottom), so on short terminals the sky clips first and the
# pool/capybaras always survive. All bands (static/animated/pool) are precomputed once
# at module eval -- no per-tick assembly.
HELPER_TEMPLATE = r'''
let __coData=__DATA__;
let __coPal=__coData.pal,__coW=__coData.w,__coPhases=__coData.phases,__coAnimRows=__coData.animCellRows,__coStaticRows=__coData.cellRows-__coData.animCellRows;
let __coHALF=String.fromCharCode(9600),__coESC=String.fromCharCode(27);
let __coTrue=/truecolor|24bit/i.test(process.env.COLORTERM||"");
function __coCube(v){return v<48?0:v<115?1:Math.round((v-35)/40)}
function __coSgr(rgb,bg){let base=bg?48:38;if(__coTrue)return base+";2;"+rgb[0]+";"+rgb[1]+";"+rgb[2];let r=__coCube(rgb[0]),g=__coCube(rgb[1]),b=__coCube(rgb[2]),n=16+36*r+6*g+b;return base+";5;"+n}
function __coRun(run){let t=__coPal[run[0]],b=__coPal[run[1]];return __coESC+"["+__coSgr(t,!1)+";"+__coSgr(b,!0)+"m"+__coHALF.repeat(run[2])}
function __coAssemble(band){let lines=[];for(let r=0;r<band.length;r++){let runs=band[r],s="";for(let i=0;i<runs.length;i++)s+=__coRun(runs[i]);lines.push(s+__coESC+"[0m")}return lines.join("\n")}
let __coStaticL=__coAssemble(__coData.staticL),__coStaticR=__coAssemble(__coData.staticR);
let __coPoolL=__coAssemble(__coData.poolL),__coPoolR=__coAssemble(__coData.poolR);
let __coAnimL=[],__coAnimR=[];for(let p=0;p<__coPhases;p++){__coAnimL.push(__coAssemble(__coData.animL[p]));__coAnimR.push(__coAssemble(__coData.animR[p]))}
function __coRawNode(str,rows,key){return zd.jsx("ink-raw-ansi",{rawText:str,rawWidth:__coW,rawHeight:rows},key)}
function __coWall(staticStr,animStrs,ph,key){return zd.jsxs(B,{flexShrink:0,flexDirection:"column",backgroundColor:"rgb(10,12,26)",children:[__coRawNode(staticStr,__coStaticRows,key+"-static"),__coRawNode(animStrs[ph],__coAnimRows,key+"-anim")]},key)}
function __CodexCapyOnsenSceneV1({rows:e,columns:t}){let n=Math.max(16,Math.min((e??30)-2,120)),sw=__coW,[ph,setPh]=S_.useState(0);S_.useEffect(()=>{let tk=setInterval(()=>setPh((p)=>(p+1)%__coPhases),180);return()=>clearInterval(tk)},[]);return zd.jsxs(zd.Fragment,{children:[zd.jsx(B,{position:"absolute",top:0,left:sw,right:sw,bottom:0,backgroundColor:"rgb(10,12,26)"},"codex-capy-onsen-v1-core"),zd.jsx(B,{position:"absolute",top:0,left:0,width:sw,height:n,overflow:"hidden",flexDirection:"column",justifyContent:"flex-end",backgroundColor:"rgb(10,12,26)",children:__coWall(__coStaticL,__coAnimL,ph,"codex-capy-onsen-v1-left")},"codex-capy-onsen-v1-left-wrap"),zd.jsx(B,{position:"absolute",top:0,right:0,width:sw,height:n,overflow:"hidden",flexDirection:"column",justifyContent:"flex-end",backgroundColor:"rgb(10,12,26)",children:__coWall(__coStaticR,__coAnimR,ph,"codex-capy-onsen-v1-right")},"codex-capy-onsen-v1-right-wrap")]})}
function __CodexCapyOnsenPoolBottomV1({children:e}){let sw=__coW;return zd.jsxs(B,{flexDirection:"column",width:"100%",flexShrink:0,backgroundColor:"rgb(10,12,26)",children:[zd.jsxs(B,{flexDirection:"row",width:"100%",backgroundColor:"rgb(10,12,26)",children:[zd.jsx(B,{width:sw,flexShrink:0,flexGrow:0,children:__coRawNode(__coPoolL,__coData.poolL.length,"codex-capy-onsen-v1-pool-left")},"codex-capy-onsen-v1-pool-left-wrap"),zd.jsx(B,{flexDirection:"column",flexGrow:1,flexShrink:1,overflowY:"hidden",backgroundColor:"rgb(10,12,26)",children:e},"codex-capy-onsen-v1-bottom-core"),zd.jsx(B,{width:sw,flexShrink:0,flexGrow:0,children:__coRawNode(__coPoolR,__coData.poolR.length,"codex-capy-onsen-v1-pool-right")},"codex-capy-onsen-v1-pool-right-wrap")]})]})}
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
         'Insert onsen scene helpers + baked art data before app shell V8o',
         V8O, helper + V8O, ['function V8o(e){'],
         'Defines the ink-raw-ansi onsen scene components and embeds the baked '
         'half-block art data (no behavior change until the scene is mounted below).'),
        ('fullscreen-scene-pe',
         'Mount onsen scene in the fullscreen conversation view (pe)',
         'pe=zd.jsxs(B,{flexGrow:1,flexDirection:"column",overflow:"hidden",children:[Q,ee,ne,oe,ie]})',
         'pe=zd.jsxs(B,{flexGrow:1,flexDirection:"column",overflow:"hidden",backgroundColor:"rgb(10,12,26)",paddingX:32,children:[zd.jsx(__CodexCapyOnsenSceneV1,{rows:y,columns:T},"codex-capy-onsen-v1-scene"),Q,ee,ne,oe,ie]})',
         ['children:[Q,ee,ne,oe,ie]'],
         'Renders the two side onsen walls (twilight sky + water/steam pool with the '
         'capybaras) around the conversation, reserving 32-cell gutters via paddingX.'),
        ('composer-flank-ue',
         'Continue the onsen pool into the composer flanks (ue)',
         'ue=zd.jsx(B,{flexDirection:"column",width:"100%",flexGrow:1,flexShrink:0,overflowY:"hidden",children:s})',
         'ue=zd.jsx(__CodexCapyOnsenPoolBottomV1,{children:s},"codex-capy-onsen-v1-bottom-instance")',
         ['flexGrow:1,flexShrink:0,overflowY:"hidden",children:s'],
         'Wraps the composer so the onsen pool continues into the bottom-corner flanks.'),
        ('composer-parent-le',
         'Indigo background on the bottom chrome parent (le)',
         'le=zd.jsxs(B,{flexDirection:"column",flexShrink:0,width:"100%",maxHeight:w,children:[Ee,ce,ue]})',
         'le=zd.jsxs(B,{flexDirection:"column",flexShrink:0,width:"100%",maxHeight:w,backgroundColor:"rgb(10,12,26)",children:[Ee,ce,ue]})',
         ['children:[Ee,ce,ue]'],
         'Blends the composer chrome background with the scene.'),
        ('fallback-scene-v',
         'Mount onsen scene in the non-fullscreen fallback path (V)',
         'V=zd.jsxs(zd.Fragment,{children:[n,s,i]})',
         'V=zd.jsxs(B,{flexGrow:1,flexDirection:"column",backgroundColor:"rgb(10,12,26)",paddingX:32,children:[zd.jsx(__CodexCapyOnsenSceneV1,{rows:y,columns:T},"codex-capy-onsen-v1-scene-fallback"),n,s,i]})',
         ['V=zd.jsxs(zd.Fragment,{children:[n,s,i]})'],
         'Shows the onsen scene when the app renders outside the fullscreen alt-screen path.'),
    ]

    # verify each anchor is unique, apply sequentially to reproduce the build output
    applied = src
    operations = []
    payload_dir = PKG / 'payloads'
    payload_dir.mkdir(parents=True, exist_ok=True)
    for i, (seam, label, exact, new, within, behavior) in enumerate(ops, start=1):
        if src.count(exact) != 1:
            raise SystemExit(f'{seam}: anchor not unique ({src.count(exact)})')
        op_id = f'capy-onsen-{seam}-2-1-199'
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
        for v in ['function __CodexCapyOnsenSceneV1', '"ink-raw-ansi"',
                  'codex-capy-onsen-v1-scene', 'String.fromCharCode(9600)']
    ] + [
        {'type': 'module_must_not_contain', 'modulePath': MODULE, 'value': '▀'}  # no literal half-block
    ]

    manifest = {
        'schemaVersion': 2,
        'id': 'capybara-onsen',
        'name': 'Capybara Onsen',
        'description': 'A calming twilight Japanese onsen scene with two capybaras — '
                       'baked half-block pixel art with 16-phase water/steam animation, '
                       "drawn via the renderer's native ink-raw-ansi direct-draw path.",
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
                    'reason': 'Purely visual, calming TUI art (twilight onsen with animated '
                              'water/steam and two capybaras). Correct rendering, animation, '
                              'and layout must be confirmed in an interactive truecolor terminal.',
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
