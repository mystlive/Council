#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, os, re, subprocess, sys
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

try:
    from artifact_schema import validate_artifact
except ModuleNotFoundError:  # pragma: no cover - supports test module loading
    from hooks.artifact_schema import validate_artifact

ISSUE_RE=re.compile(r'^ISSUE-\d{4}-\d{4}$')
RUN_RE=re.compile(r'^RUN-\d{8}-\d{4}$')
ALLOWED_RESEARCH_MODES={'NONE','LOCAL','WEB'}
ALLOWED_STATUSES={'RUNNING','COMPLETED','CONDITIONAL_COMPLETION','BOUNDED_COMPLETION','DEGRADED_COMPLETION','FAILED','BLOCKED','WAITING_FOR_HUMAN'}
ALLOWED_NEXT_ACTIONS={'CONTINUE','RESEARCH','RECRITIQUE','AUDIT','SYNTHESIZE','COMPLETE','ESCALATE'}
ESCALATION_REASONS={'HUMAN_ONLY_INFORMATION','CONSTRAINT_CONFLICT','IRREVERSIBLE_ACTION','LEGAL_OR_ORGANIZATIONAL_AUTHORITY','VALUE_CONFLICT'}
STAGE_REQUIREMENTS={
 'issue-intake':['issue_intake'],
 'chair-review':['issue_intake','chair_review'],
 'research':['issue_intake','chair_review','research'],
 'devil-advocate':['issue_intake','chair_review','devil_advocate'],
 'research-revision':['issue_intake','chair_review','research','devil_advocate','research_revision'],
 'devil-advocate-revision':['issue_intake','chair_review','devil_advocate','devil_advocate_revision'],
 'secretary':['issue_intake','chair_review','devil_advocate','secretary'],
 'formal-validation':['issue_intake','chair_review','devil_advocate','secretary','formal_validation'],
 'content-audit':['issue_intake','chair_review','devil_advocate','secretary','formal_validation','content_audit'],
 'final-synthesis':['issue_intake','chair_review','devil_advocate','secretary','formal_validation','final_synthesis'],
}
REQUIRED=('MASTER_DESIGN.md','STATE.md','AGENTS.md','ROLE_RULES.md','DECISION_RULES.md','SOURCES.md','HOOKS.md','SKILL_CONTRACT.md')
PRIVATE=('evidence/private','runs/private')
PROTECTED={'AGENTS.md','MASTER_DESIGN.md','ROLE_RULES.md','DECISION_RULES.md','HOOKS.md','SKILL_CONTRACT.md'}
DESTRUCTIVE=(re.compile(r'git\s+reset\s+--hard',re.I),re.compile(r'git\s+clean\s+-[^\n]*f',re.I),re.compile(r'rm\s+-[^\n]*r[^\n]*f',re.I),re.compile(r'Remove-Item[^\n]*(?:-Recurse|-Force)',re.I))
SECRET=(re.compile(r'-----BEGIN .*PRIVATE KEY-----'),re.compile(r'\bsk-ant-[A-Za-z0-9_-]{16,}\b'),re.compile(r'\bsk-[A-Za-z0-9_-]{20,}\b'),re.compile(r'\bgh[pousr]_[A-Za-z0-9]{20,}\b'))

@dataclass(frozen=True)
class Finding:
    level:str; code:str; message:str; path:str|None=None

@dataclass
class Result:
    phase:str; result:str; findings:list[Finding]
    @property
    def exit_code(self): return 2 if self.result in {'FAIL','BLOCK'} else 0

def finish(phase:str, findings:list[Finding])->Result:
    levels={f.level for f in findings}
    result='BLOCK' if 'BLOCK' in levels else 'FAIL' if 'FAIL' in levels else 'PASS_WITH_WARNINGS' if 'WARNING' in levels else 'PASS'
    return Result(phase,result,findings)

def hook_input()->dict[str,Any]:
    raw='' if sys.stdin.isatty() else sys.stdin.read().strip()
    if not raw:return {}
    value=json.loads(raw)
    if not isinstance(value,dict):raise ValueError('stdin must be a JSON object')
    return value

def root_from(data:Mapping[str,Any])->Path:
    raw=data.get('cwd') or os.getenv('CLAUDE_PROJECT_DIR') or os.getcwd()
    return Path(str(raw)).expanduser().resolve()

def git_repo(root:Path)->bool:
    try:
        return subprocess.run(['git','-C',str(root),'rev-parse','--is-inside-work-tree'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=3).returncode==0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False

def git_ignored(root:Path,p:str)->bool:
    try:
        return subprocess.run(['git','-C',str(root),'check-ignore','-q','--',p],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=3).returncode==0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False

def pre_run(root:Path)->Result:
    fs=[]
    for name in REQUIRED:
        p=root/name
        if not p.is_file():fs.append(Finding('FAIL','REQUIRED_FILE_MISSING',f'Missing {name}',name))
        elif p.stat().st_size==0:fs.append(Finding('FAIL','REQUIRED_FILE_EMPTY',f'Empty {name}',name))
    states=list(root.glob('STATE*.md'))
    if len(states)!=1 or states[0].name!='STATE.md':fs.append(Finding('FAIL','STATE_NOT_CANONICAL','Exactly one STATE.md must exist.'))
    for rel in PRIVATE:
        if not (root/rel).is_dir():fs.append(Finding('FAIL','PRIVATE_DIR_MISSING',f'Missing {rel}',rel))
    if git_repo(root):
        for rel in PRIVATE:
            if not git_ignored(root,rel):fs.append(Finding('BLOCK','PRIVATE_NOT_IGNORED',f'{rel} is not gitignored',rel))
    else:fs.append(Finding('WARNING','GIT_NOT_INITIALIZED','Git ignore rules were not verified.'))
    reg=root/'id_registry.json'
    if reg.exists():
        try:
            if not isinstance(json.loads(reg.read_text(encoding='utf-8')),dict):raise ValueError('root must be object')
        except Exception as e:fs.append(Finding('FAIL','ID_REGISTRY_INVALID',str(e),'id_registry.json'))
    else:fs.append(Finding('WARNING','ID_REGISTRY_MISSING','id_registry.json is missing.'))
    return finish('pre-run',fs)

def target(root:Path,data:Mapping[str,Any])->Path|None:
    ti=data.get('tool_input')
    if not isinstance(ti,Mapping):return None
    for key in ('file_path','path','notebook_path'):
        v=ti.get(key)
        if isinstance(v,str) and v.strip():
            p=Path(v); return (p if p.is_absolute() else root/p).resolve()
    return None

MAINTENANCE_APPROVAL_REL=('.council','maintenance_approval.json')
MAINTENANCE_LOG_REL=('.council','maintenance_log.json')
_SHA256_RE=re.compile(r'^[0-9a-fA-F]{64}$')

def _now()->'datetime':
    return datetime.now(timezone.utc)

def _parse_dt(s:Any):
    if not isinstance(s,str) or not s.strip():return None
    try:
        v=s.replace('Z','+00:00')
        dt=datetime.fromisoformat(v)
        if dt.tzinfo is None:dt=dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None

def _maintenance_log_append(root:Path,entry:dict)->None:
    p=root.joinpath(*MAINTENANCE_LOG_REL)
    p.parent.mkdir(parents=True,exist_ok=True)
    log=[]
    if p.is_file():
        try:
            existing=json.loads(p.read_text(encoding='utf-8'))
            if isinstance(existing,list):log=existing
        except Exception:
            log=[]
    log.append(entry)
    p.write_text(json.dumps(log,indent=2,ensure_ascii=False),encoding='utf-8')

def check_maintenance_approval(root:Path,filename:str)->tuple[bool,list[Finding]]:
    """Checks .council/maintenance_approval.json for a one-time, single-file, non-wildcard
    exception to PROTECTED_FILE_WRITE for `filename`. Never weakens the default BLOCK: an
    absent approval, or one that does not name `filename` exactly, yields (False, []) so the
    caller falls back to the normal protected-file BLOCK. Any present-but-invalid approval for
    THIS filename yields (False, [specific BLOCK Finding]). A fully valid approval is consumed
    (deleted, one-time use), logged, and yields (True, [])."""
    p=root.joinpath(*MAINTENANCE_APPROVAL_REL)
    if not p.is_file():return False,[]
    try:
        approval=json.loads(p.read_text(encoding='utf-8'))
    except Exception as e:
        return False,[Finding('BLOCK','MAINTENANCE_APPROVAL_INVALID',f'Malformed maintenance approval JSON: {e}')]
    if not isinstance(approval,dict):
        return False,[Finding('BLOCK','MAINTENANCE_APPROVAL_INVALID','Maintenance approval root must be an object.')]
    approved_file=approval.get('approved_file')
    if not isinstance(approved_file,str) or not approved_file.strip():
        return False,[Finding('BLOCK','MAINTENANCE_APPROVAL_INVALID','approved_file is required and must be a non-empty string.')]
    if any(ch in approved_file for ch in '*?[]'):
        return False,[Finding('BLOCK','MAINTENANCE_APPROVAL_INVALID','approved_file must not contain wildcard characters.')]
    if approved_file!=filename:
        return False,[]
    if approved_file not in PROTECTED:
        return False,[Finding('BLOCK','MAINTENANCE_APPROVAL_INVALID',f'{approved_file} is not a recognized protected file.')]
    reason=approval.get('reason')
    if not isinstance(reason,str) or not reason.strip():
        return False,[Finding('BLOCK','MAINTENANCE_APPROVAL_INVALID','reason is required and must be non-empty.')]
    approved_by=approval.get('approved_by')
    if not isinstance(approved_by,str) or not approved_by.strip():
        return False,[Finding('BLOCK','MAINTENANCE_APPROVAL_INVALID','approved_by is required and must be non-empty.')]
    used=approval.get('used',False)
    if used is not False:
        return False,[Finding('BLOCK','MAINTENANCE_APPROVAL_ALREADY_USED','Maintenance approval has already been used.')]
    expires_at_raw=approval.get('expires_at')
    expires_at=_parse_dt(expires_at_raw)
    if expires_at is None:
        return False,[Finding('BLOCK','MAINTENANCE_APPROVAL_INVALID','expires_at is required and must be a valid ISO-8601 datetime.')]
    if _now()>=expires_at:
        return False,[Finding('BLOCK','MAINTENANCE_APPROVAL_EXPIRED','Maintenance approval has expired.')]
    expected_hash=approval.get('expected_pre_hash')
    if not isinstance(expected_hash,str) or not _SHA256_RE.match(expected_hash):
        return False,[Finding('BLOCK','MAINTENANCE_APPROVAL_INVALID','expected_pre_hash is required and must be a 64-hex-char sha256 string.')]
    fp=root/approved_file
    if not fp.is_file():
        return False,[Finding('BLOCK','MAINTENANCE_APPROVAL_INVALID',f'{approved_file} does not exist.')]
    actual_hash=hashlib.sha256(fp.read_bytes()).hexdigest()
    if actual_hash.lower()!=expected_hash.lower():
        return False,[Finding('BLOCK','MAINTENANCE_APPROVAL_HASH_MISMATCH','Current file hash does not match expected_pre_hash; approval does not match current file state.')]
    _maintenance_log_append(root,{
        'phase':'granted','target_file':approved_file,'reason':reason,'approved_by':approved_by,
        'approved_at':approval.get('approved_at'),'expires_at':expires_at_raw,
        'pre_hash':actual_hash,'granted_at':_now().isoformat(),
    })
    try:p.unlink()
    except Exception:pass
    return True,[]

def pre_tool(root:Path,data:Mapping[str,Any])->Result:
    fs=[]; name=data.get('tool_name'); ti=data.get('tool_input') if isinstance(data.get('tool_input'),Mapping) else {}
    if name in {'Write','Edit','MultiEdit','NotebookEdit'}:
        p=target(root,data)
        if p and p.name in PROTECTED:
            granted,mfindings=check_maintenance_approval(root,p.name)
            if not granted:
                fs.extend(mfindings) if mfindings else fs.append(Finding('BLOCK','PROTECTED_FILE_WRITE',f'Protected file requires approved change: {p.name}',p.name))
        if p and (p.name=='.env' or '.git' in p.parts):fs.append(Finding('BLOCK','SENSITIVE_PATH_WRITE',f'Blocked sensitive path: {p}'))
        for key in ('content','new_string','cell_source'):
            v=ti.get(key)
            if isinstance(v,str) and any(rx.search(v) for rx in SECRET):fs.append(Finding('BLOCK','SECRET_PATTERN','Possible secret detected; value not logged.'))
    if name=='Bash':
        cmd=ti.get('command')
        if isinstance(cmd,str):
            if any(rx.search(cmd) for rx in SECRET):
                fs.append(Finding('BLOCK','SECRET_PATTERN','Possible secret detected in command; value not logged.'))
            if any(rx.search(cmd) for rx in DESTRUCTIVE):
                fs.append(Finding('BLOCK','DESTRUCTIVE_COMMAND','Potentially destructive command requires human approval.'))
            write_like = re.search(r'(?:>|>>|tee\s+|sed\s+-i|perl\s+-i|python[^\n]*(?:write_text|open\s*\()|Set-Content|Add-Content|Out-File|WriteAllText|WriteAllLines)', cmd, re.I)
            if write_like:
                for pname in PROTECTED:
                    if re.search(rf'(?<![A-Za-z0-9_.-]){re.escape(pname)}(?![A-Za-z0-9_.-])', cmd, re.I):
                        granted,mfindings=check_maintenance_approval(root,pname)
                        if not granted:
                            fs.extend(mfindings) if mfindings else fs.append(Finding('BLOCK','PROTECTED_FILE_WRITE_VIA_BASH','Bash write to a protected file requires approved maintenance.'))
    return finish('pre-tool-use',fs)

def post_tool(root:Path,data:Mapping[str,Any])->Result:
    name=data.get('tool_name'); ti=data.get('tool_input') if isinstance(data.get('tool_input'),Mapping) else {}
    log_path=root.joinpath(*MAINTENANCE_LOG_REL)
    if not log_path.is_file():return finish('post-tool-use',[])
    try:
        log=json.loads(log_path.read_text(encoding='utf-8'))
    except Exception:
        return finish('post-tool-use',[])
    if not isinstance(log,list) or not log:return finish('post-tool-use',[])
    last=log[-1]
    if not isinstance(last,dict) or last.get('phase')!='granted' or 'completed_at' in last:
        return finish('post-tool-use',[])
    target_file=last.get('target_file')
    touched=False
    if name in {'Write','Edit','MultiEdit','NotebookEdit'}:
        p=target(root,data)
        touched=bool(p and p.name==target_file)
    elif name=='Bash':
        cmd=ti.get('command')
        touched=isinstance(cmd,str) and isinstance(target_file,str) and bool(re.search(rf'(?<![A-Za-z0-9_.-]){re.escape(target_file)}(?![A-Za-z0-9_.-])', cmd, re.I))
    if touched and isinstance(target_file,str):
        fp=root/target_file
        post_hash=hashlib.sha256(fp.read_bytes()).hexdigest() if fp.is_file() else None
        last['phase']='completed'; last['post_hash']=post_hash; last['completed_at']=_now().isoformat()
        log_path.write_text(json.dumps(log,indent=2,ensure_ascii=False),encoding='utf-8')
    return finish('post-tool-use',[])

def pre_decision(root:Path)->Result:
    p=root/'.council'/'active_run.json'
    if not p.exists():return finish('pre-decision',[Finding('WARNING','NO_ACTIVE_RUN','No active CouncilSystem run; skipped.')])
    try:data=json.loads(p.read_text(encoding='utf-8'))
    except Exception as e:return finish('pre-decision',[Finding('FAIL','ACTIVE_RUN_INVALID',str(e),str(p))])
    fs=[]
    if not isinstance(data,dict):return finish('pre-decision',[Finding('FAIL','ACTIVE_RUN_INVALID','Root must be object.')])
    if not isinstance(data.get('issue_id'),str) or not ISSUE_RE.fullmatch(data['issue_id']):fs.append(Finding('FAIL','ISSUE_ID_INVALID','Invalid issue_id.'))
    if not isinstance(data.get('run_id'),str) or not RUN_RE.fullmatch(data['run_id']):fs.append(Finding('FAIL','RUN_ID_INVALID','Invalid run_id.'))

    mode=data.get('research_mode')
    if mode not in ALLOWED_RESEARCH_MODES:fs.append(Finding('FAIL','RESEARCH_MODE_INVALID','research_mode must be NONE, LOCAL, or WEB.'))
    status=data.get('status','RUNNING')
    if status not in ALLOWED_STATUSES:fs.append(Finding('FAIL','STATUS_INVALID',f'Invalid status: {status}'))
    next_action=data.get('next_action','CONTINUE')
    if next_action not in ALLOWED_NEXT_ACTIONS:fs.append(Finding('FAIL','NEXT_ACTION_INVALID',f'Invalid next_action: {next_action}'))

    if status=='WAITING_FOR_HUMAN' or next_action=='ESCALATE':
        esc=data.get('escalation')
        if not isinstance(esc,dict):
            fs.append(Finding('BLOCK','ESCALATION_MISSING','WAITING_FOR_HUMAN requires an escalation object.'))
            return finish('pre-decision',fs)
        reason=esc.get('reason_code')
        if reason not in ESCALATION_REASONS:fs.append(Finding('BLOCK','ESCALATION_REASON_INVALID','Escalation reason is not an allowed human-only condition.'))
        for k in ('question','required_answer','resume_step','why_conditions_cannot_substitute'):
            if not esc.get(k):fs.append(Finding('FAIL','ESCALATION_FIELD_MISSING',f'Missing escalation.{k}.'))
        return finish('pre-decision',fs)

    outputs=data.get('outputs')
    if not isinstance(outputs,dict):return finish('pre-decision',fs+[Finding('FAIL','OUTPUTS_MISSING','outputs must be object.')])
    stage=data.get('current_stage')
    if stage not in STAGE_REQUIREMENTS:
        fs.append(Finding('FAIL','CURRENT_STAGE_INVALID',f'Unknown current_stage: {stage}'))
        return finish('pre-decision',fs)
    required=list(STAGE_REQUIREMENTS[stage])
    if mode in {'LOCAL','WEB'} and stage in {'devil-advocate','research-revision','devil-advocate-revision','secretary','formal-validation','content-audit','final-synthesis'} and 'research' not in required:
        required.insert(2,'research')
    for k in required:
        v=outputs.get(k)
        if not isinstance(v,str) or not v.strip():fs.append(Finding('FAIL','OUTPUT_PATH_MISSING',f'Missing {k}.'));continue
        fp=Path(v); fp=fp if fp.is_absolute() else root/fp
        try:
            fp.resolve().relative_to((root/'runs'/'private').resolve())
        except ValueError:
            fs.append(Finding('BLOCK','OUTPUT_OUTSIDE_PRIVATE_RUNS',f'Output {k} must be under runs/private.',str(fp)))
            continue
        if not fp.is_file() or fp.stat().st_size==0:
            fs.append(Finding('FAIL','OUTPUT_FILE_INVALID',f'Missing or empty {k}.',str(fp)))
            continue
        try:
            parsed=json.loads(fp.read_text(encoding='utf-8'))
            if not isinstance(parsed,dict):raise ValueError('root must be object')
        except Exception as e:
            fs.append(Finding('FAIL','OUTPUT_JSON_INVALID',f'Invalid JSON for {k}: {e}',str(fp)))
            continue
        attempt_match=re.search(r'(?:^|[\\/])attempt-(\\d+)(?:[\\/]|$)',str(fp))
        expected_attempt=int(attempt_match.group(1)) if attempt_match else None
        for issue in validate_artifact(
            parsed,
            expected_issue_id=data.get('issue_id'),
            expected_run_id=data.get('run_id'),
            expected_attempt=expected_attempt,
        ):
            fs.append(Finding('FAIL',f'ARTIFACT_{issue.code}',issue.message,str(fp)))
        for ref_field in ('input_refs','output_refs'):
            refs=parsed.get(ref_field)
            if not isinstance(refs,list):
                continue
            for ref in refs:
                if not isinstance(ref,str) or not ref.strip() or '..' in Path(ref).parts:
                    continue
                ref_path=(root/ref).resolve()
                try:
                    ref_path.relative_to(root.resolve())
                except ValueError:
                    continue
                if not ref_path.is_file():
                    fs.append(Finding('FAIL','ARTIFACT_REF_MISSING',f'{ref_field} references a missing file.',str(ref_path)))
    if data.get('content_audit_required') is True and stage in {'final-synthesis'} and not outputs.get('content_audit'):
        fs.append(Finding('FAIL','CONTENT_AUDIT_MISSING','Required content audit missing.'))
    content_audit_result=None
    ca_path=outputs.get('content_audit')
    if isinstance(ca_path,str) and ca_path.strip():
        ca_fp=Path(ca_path); ca_fp=ca_fp if ca_fp.is_absolute() else root/ca_fp
        if ca_fp.is_file():
            try:
                ca_parsed=json.loads(ca_fp.read_text(encoding='utf-8'))
                if isinstance(ca_parsed,dict):content_audit_result=ca_parsed.get('result')
            except Exception:
                pass
    budget=data.get('deliberation_budget',{})
    counters=data.get('counters',{})
    if budget or counters:
        if not isinstance(budget,dict) or not isinstance(counters,dict):
            fs.append(Finding('FAIL','BUDGET_INVALID','deliberation_budget and counters must be objects.'))
        else:
            for key in ('research_revisions','recritiques','audit_revisions'):
                limit=budget.get('max_'+key)
                used=counters.get(key,0)
                if not isinstance(limit,int) or limit < 0 or not isinstance(used,int) or used < 0:
                    fs.append(Finding('FAIL','BUDGET_FIELD_INVALID',f'Invalid budget/counter for {key}.'))
                elif used > limit:
                    fs.append(Finding('FAIL','BUDGET_EXCEEDED',f'{key} exceeds configured limit.'))
    if content_audit_result in {'REVISE','BLOCK'}:
        if status in {'COMPLETED','CONDITIONAL_COMPLETION','DEGRADED_COMPLETION'}:
            fs.append(Finding('BLOCK','CONTENT_AUDIT_UNRESOLVED',f'content-audit final result is {content_audit_result}; cannot reach {status} while unresolved. Only the content-audit role may change this result; re-run content-audit after fixes, or use BOUNDED_COMPLETION if the audit-revision budget is exhausted.'))
        elif status=='BOUNDED_COMPLETION':
            limit=(budget or {}).get('max_audit_revisions') if isinstance(budget,dict) else None
            used=(counters or {}).get('audit_revisions',0) if isinstance(counters,dict) else None
            if not(isinstance(limit,int) and isinstance(used,int) and used>=limit):
                fs.append(Finding('BLOCK','BOUNDED_COMPLETION_WITHOUT_BUDGET_EXHAUSTION','BOUNDED_COMPLETION with an unresolved content-audit REVISE/BLOCK requires the audit_revisions budget to be exhausted (counters.audit_revisions >= deliberation_budget.max_audit_revisions).'))
    if status in {'COMPLETED','CONDITIONAL_COMPLETION','BOUNDED_COMPLETION','DEGRADED_COMPLETION'}:
        if stage!='final-synthesis':fs.append(Finding('FAIL','PREMATURE_COMPLETION','Completion status requires current_stage final-synthesis.'))
        if next_action!='COMPLETE':fs.append(Finding('FAIL','COMPLETION_ACTION_INVALID','Completion status requires next_action COMPLETE.'))
    elif next_action=='COMPLETE':
        fs.append(Finding('FAIL','PREMATURE_COMPLETE_ACTION','next_action COMPLETE requires a completion status.'))
    if status=='RUNNING':
        fs.append(Finding('BLOCK','RUN_INCOMPLETE','Council RUN is still RUNNING; continue autonomously to completion, valid escalation, or explicit failure.'))
    return finish('pre-decision',fs)

def emit(r:Result,json_mode:bool):
    payload={'phase':r.phase,'result':r.result,'findings':[asdict(f) for f in r.findings]}
    if json_mode:print(json.dumps(payload,ensure_ascii=False));return
    if r.result in {'FAIL','BLOCK'}:
        print(f'[{r.result}] {r.phase} validation failed',file=sys.stderr)
        for f in r.findings:print(f'- {f.code}: {f.message}',file=sys.stderr)
    elif r.result=='PASS_WITH_WARNINGS':
        print('CouncilSystem validation passed with warnings:')
        for f in r.findings:print(f'- {f.code}: {f.message}')

def main(argv=None)->int:
    ap=argparse.ArgumentParser();ap.add_argument('phase',choices=('pre-run','pre-tool-use','post-tool-use','pre-decision'));ap.add_argument('--root',type=Path);ap.add_argument('--json',action='store_true');a=ap.parse_args(argv)
    try:
        data={} if a.root else hook_input();root=a.root.resolve() if a.root else root_from(data)
        r=pre_run(root) if a.phase=='pre-run' else pre_tool(root,data) if a.phase=='pre-tool-use' else post_tool(root,data) if a.phase=='post-tool-use' else pre_decision(root)
        emit(r,a.json);return r.exit_code
    except Exception as e:print(f'[ERROR] validator failed: {e}',file=sys.stderr);return 1
if __name__=='__main__':raise SystemExit(main())
