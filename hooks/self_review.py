#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, re, subprocess, sys
from pathlib import Path

CHECKS=[]
def check(name, ok, detail=''):
    CHECKS.append({'name':name,'ok':bool(ok),'detail':detail})

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--root',type=Path,default=Path('.'));ap.add_argument('--json',action='store_true');a=ap.parse_args()
    r=a.root.resolve()
    required=['CLAUDE.md','AGENTS.md','ROLE_RULES.md','DECISION_RULES.md','SKILL_CONTRACT.md','MASTER_DESIGN.md','HOOKS.md','STATE.md','.claude/settings.json','.claude/agents/council-orchestrator.md','.claude/skills/council-runner/SKILL.md','.claude/skills/final-synthesis/SKILL.md','hooks/validate.py']
    check('required_files',all((r/x).is_file() for x in required),'missing required file')
    check('no_duplicate_skill_tree',not (r/'skills').exists(),'root skills/ must not duplicate .claude/skills')
    try: json.loads((r/'.claude/settings.json').read_text(encoding='utf-8')); ok=True
    except Exception as e: ok=False
    check('settings_json',ok,'valid JSON required')
    contract=(r/'SKILL_CONTRACT.md').read_text(encoding='utf-8')
    validator=(r/'hooks/validate.py').read_text(encoding='utf-8')
    check('private_output_paths','runs/private/<RUN-ID>' in contract,'contract must use private run paths')
    check('status_consistency','COMPLETED_WITH_WARNINGS' not in contract,'unsupported status present')
    orch=(r/'.claude/agents/council-orchestrator.md').read_text(encoding='utf-8')
    final=(r/'.claude/skills/final-synthesis/SKILL.md').read_text(encoding='utf-8')
    check('conditional_content_audit','発動条件を満たす場合のみ' in orch and '監査発動時のみ' in final,'content audit optionality mismatch')
    check('stop_enforcement','RUN_INCOMPLETE' in validator,'RUNNING stop must be blocked')
    check('revision_stage_alignment',"'devil-advocate-revision'" in validator and 'devil-advocate-revision' in orch,'revision stage mismatch')
    check('powershell_protection','Set-Content' in validator and 'Out-File' in validator,'PowerShell writes not protected')
    check('budget_limits','deliberation_budget' in validator and '既定の審議上限' in orch,'loop bounds missing')
    check('fresh_state','初回実案件RUNを開始可能' in (r/'STATE.md').read_text(encoding='utf-8'),'state not fresh')
    check('no_active_run',not (r/'.council/active_run.json').exists(),'fresh package must not contain active run')
    cp=subprocess.run([sys.executable,'-m','unittest','discover','-s',str(r/'hooks/tests'),'-v'],cwd=r,capture_output=True,text=True)
    check('unit_tests',cp.returncode==0,(cp.stdout+cp.stderr)[-1000:])
    # manifest integrity
    try:
      man=json.loads((r/'MANIFEST.json').read_text(encoding='utf-8'))
      bad=[]
      for rel,h in man.items():
        p=r/rel
        if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest()!=h:bad.append(rel)
      check('manifest_integrity',not bad,','.join(bad))
    except Exception as e:check('manifest_integrity',False,str(e))
    score=round(100*sum(c['ok'] for c in CHECKS)/len(CHECKS))
    out={'score':score,'checks':CHECKS}
    print(json.dumps(out,ensure_ascii=False,indent=2) if a.json else f"SELF_REVIEW_SCORE={score}\n"+'\n'.join(f"[{'PASS' if c['ok'] else 'FAIL'}] {c['name']} {c['detail']}" for c in CHECKS))
    return 0 if score==100 else 2
if __name__=='__main__':raise SystemExit(main())
