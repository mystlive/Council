#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, os, re, subprocess, sys
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

try:
    from artifact_schema import validate_artifact, stage_field_warnings
except ModuleNotFoundError:  # pragma: no cover - supports test module loading
    from hooks.artifact_schema import validate_artifact, stage_field_warnings
try:
    from audit_store import audit_result_was_rewritten, is_audit_artifact, latest_audit
except ModuleNotFoundError:  # pragma: no cover - supports test module loading
    from hooks.audit_store import audit_result_was_rewritten, is_audit_artifact, latest_audit
try:
    import runner as run_kernel
except ModuleNotFoundError:  # pragma: no cover - supports test module loading
    from hooks import runner as run_kernel

ISSUE_RE=re.compile(r'^ISSUE-\d{4}-\d{4}$')
RUN_RE=re.compile(r'^RUN-\d{8}-\d{4}$')
ATTEMPT_PATH_RE=re.compile(r'(?:^|[\\/])attempt-(\d+)(?:[\\/]|$)')
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
COMMAND_TOOLS={'Bash','PowerShell'}
DESTRUCTIVE=(re.compile(r'git\s+reset\s+--hard',re.I),re.compile(r'git\s+clean\s+-[^\n]*f',re.I),re.compile(r'rm\s+-[^\n]*r[^\n]*f',re.I),re.compile(r'Remove-Item[^\n]*(?:-Recurse|-Force)',re.I))
# Written with quantifiers so this source file does not match its own patterns.
SECRET=(re.compile(r'-{5}BEGIN [A-Z ]*PRIVATE KEY-{5}'),re.compile(r'\bsk-ant-[A-Za-z0-9_-]{16,}\b'),re.compile(r'\bsk-[A-Za-z0-9_-]{20,}\b'),re.compile(r'\bgh[pousr]_[A-Za-z0-9]{20,}\b'),
        re.compile(r'\bAKIA[0-9A-Z]{16}\b'),re.compile(r'\bAIza[0-9A-Za-z_-]{35}\b'),re.compile(r'\bxox[abprs]-[A-Za-z0-9-]{10,}\b'))
# Redirection to a file. A '>' preceded by '-', '=', '<' or '>' ('->', '=>', '>=') is not a redirection,
# and targets such as '&1', '/dev/null', '$null' and 'NUL' do not write a file.
REDIRECT_RE=re.compile(r'(?:^|(?<=[^\-=<>]))\d?>{1,2}\s*([^\s|;&<>()]+)')
NULL_TARGETS={'/dev/null','$null','nul','null'}
WRITE_VERB_RE=re.compile(r'(?:\btee\b|\bsed\s+-i|\bperl\s+-[a-z]*i|\bcp\b|\bmv\b|\binstall\b|\brsync\b|\bdd\b[^\n]*\bof=|\btruncate\b|'
                         r'Set-Content|Add-Content|Out-File|Clear-Content|Copy-Item|Move-Item|Rename-Item|New-Item|'
                         r'WriteAll(?:Text|Lines|Bytes)|write_text|write_bytes|shutil\.|os\.replace|os\.rename|'
                         r'open\s*\([^)]*,\s*[\'"][^\'"]*[wax+]|\.open\s*\(\s*[\'"][^\'"]*[wax+]|'
                         r'\bgit\s+(?:checkout|restore|mv)\b)',re.I)
REFRESH_BASELINE_RE=re.compile(r'validate\.py[^\n]*\brefresh-baseline\b',re.I)
SENSITIVE_ENV_OK_SUFFIXES=('.example','.sample','.template')
STALE_RUN_SECONDS=24*3600

COUNCIL='.council'
MAINTENANCE_APPROVAL_REL=(COUNCIL,'maintenance_approval.json')
MAINTENANCE_LOG_REL=(COUNCIL,'maintenance_log.json')
BASELINE_REL=(COUNCIL,'protected_baseline.json')
FINGERPRINT_REL=(COUNCIL,'runtime_fingerprint.json')
STOP_STATE_REL=(COUNCIL,'stop_state.json')
SNAPSHOT_REL=(COUNCIL,'active_run.snapshot.json')
_SHA256_RE=re.compile(r'^[0-9a-fA-F]{64}$')

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

def _now()->'datetime':
    return datetime.now(timezone.utc)

def _read_json(p:Path,default:Any=None)->Any:
    try:return json.loads(p.read_text(encoding='utf-8'))
    except Exception:return default

def _write_json(p:Path,value:Any)->None:
    p.parent.mkdir(parents=True,exist_ok=True)
    tmp=p.with_name(f'.{p.name}.{os.getpid()}.tmp')
    tmp.write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    os.replace(tmp,p)

# ---- protected-file integrity (detects changes regardless of the tool used) ----

def normalized_sha256(p:Path)->str:
    """SHA-256 of the file with CRLF normalized to LF, so git's autocrlf checkout is not a change."""
    return hashlib.sha256(p.read_bytes().replace(b'\r\n',b'\n')).hexdigest()

def protected_hashes(root:Path)->dict[str,str|None]:
    out={}
    for name in sorted(PROTECTED):
        p=root/name
        out[name]=normalized_sha256(p) if p.is_file() else None
    return out

def refresh_baseline(root:Path)->dict[str,str|None]:
    hashes=protected_hashes(root)
    _write_json(root.joinpath(*BASELINE_REL),{'hashes':hashes,'normalization':'crlf-to-lf','updated_at':_now().isoformat()})
    return hashes

def integrity_findings(root:Path,level:str='BLOCK')->list[Finding]:
    """Compare protected files with the session baseline. An approved maintenance write whose
    completed log entry records the current hash is accepted and folded into the baseline."""
    bp=root.joinpath(*BASELINE_REL)
    base=_read_json(bp)
    if not isinstance(base,dict) or not isinstance(base.get('hashes'),dict) or base.get('normalization')!='crlf-to-lf':
        refresh_baseline(root);return []
    current=protected_hashes(root);baseline=dict(base['hashes']);fs=[];changed=False
    log=_read_json(root.joinpath(*MAINTENANCE_LOG_REL),[])
    approved={(e.get('target_file'),e.get('post_hash_normalized')) for e in log if isinstance(e,dict) and e.get('phase')=='completed'} if isinstance(log,list) else set()
    for name,h in current.items():
        if baseline.get(name)==h:continue
        if (name,h) in approved:
            baseline[name]=h;changed=True;continue
        fs.append(Finding(level,'PROTECTED_FILE_INTEGRITY',f'{name} changed without an approved maintenance record. Restore it (git checkout -- {name}) or have a human approve the change.',name))
    if changed:_write_json(bp,{'hashes':baseline,'updated_at':_now().isoformat()})
    return fs

# ---- runtime fingerprint (IMP-07a) ----

AGENT_FIELD_RE=re.compile(r'^(model|effort)\s*:\s*(.+?)\s*$',re.M)

def agent_settings(root:Path)->dict[str,dict[str,str]]:
    out={}
    for p in sorted((root/'.claude'/'agents').glob('*.md')):
        text=p.read_text(encoding='utf-8',errors='replace')
        m=re.match(r'^---\s*\n(.*?)\n---',text,re.S)
        fields=dict(AGENT_FIELD_RE.findall(m.group(1))) if m else {}
        out[p.stem]={'model':fields.get('model','(inherit)'),'effort':fields.get('effort','(session)')}
    return out

def runtime_fingerprint(root:Path,data:Mapping[str,Any]|None=None)->dict[str,Any]:
    execpath=os.environ.get('CLAUDE_CODE_EXECPATH','')
    m=re.search(r'(\d+\.\d+\.\d+)',execpath)
    return {
        'claude_code_version':m.group(1) if m else 'unknown',
        'entrypoint':os.environ.get('CLAUDE_CODE_ENTRYPOINT','unknown'),
        'desktop_app_version':os.environ.get('CLAUDE_CODE_DESKTOP_APP_VERSION'),
        'agent_sdk_version':os.environ.get('CLAUDE_AGENT_SDK_VERSION'),
        'session_effort':os.environ.get('CLAUDE_EFFORT'),
        'session_model':(data or {}).get('model') if isinstance((data or {}).get('model'),str) else None,
        'subagent_model_force':bool(os.environ.get('CLAUDE_CODE_SUBAGENT_MODEL_FORCE')),
        'background_tasks_disabled':os.environ.get('CLAUDE_CODE_DISABLE_BACKGROUND_TASKS')=='1',
        'agents':agent_settings(root),
    }

def record_fingerprint(root:Path,data:Mapping[str,Any]|None=None)->list[Finding]:
    fp=runtime_fingerprint(root,data);fs=[]
    p=root.joinpath(*FINGERPRINT_REL);prev=_read_json(p,{})
    last=prev.get('current') if isinstance(prev,dict) else None
    if isinstance(last,dict) and last.get('claude_code_version') not in (None,'unknown') and fp['claude_code_version']!=last.get('claude_code_version'):
        fs.append(Finding('WARNING','CLAUDE_CODE_VERSION_CHANGED',f"Claude Code changed {last.get('claude_code_version')} -> {fp['claude_code_version']}. Re-run: python -m unittest discover -s hooks/tests"))
    if fp['claude_code_version']=='unknown':
        fs.append(Finding('WARNING','CLAUDE_CODE_VERSION_UNKNOWN','Running Claude Code version could not be determined (CLAUDE_CODE_EXECPATH missing).'))
    if fp['subagent_model_force']:
        fs.append(Finding('WARNING','SUBAGENT_MODEL_FORCED','CLAUDE_CODE_SUBAGENT_MODEL_FORCE is set; per-role model settings in .claude/agents are ignored.'))
    fp['recorded_at']=_now().isoformat()
    _write_json(p,{'current':fp,'previous':last})
    return fs

def pre_run(root:Path,data:Mapping[str,Any]|None=None)->Result:
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
    if (root/COUNCIL).is_dir():
        # Changes between sessions are reported, then accepted as the new session baseline.
        for f in integrity_findings(root,level='WARNING'):
            fs.append(Finding('WARNING','PROTECTED_FILE_CHANGED_SINCE_LAST_SESSION',f.message,f.path))
        refresh_baseline(root)
        fs.extend(record_fingerprint(root,data))
    return finish('pre-run',fs)

def target(root:Path,data:Mapping[str,Any])->Path|None:
    ti=data.get('tool_input')
    if not isinstance(ti,Mapping):return None
    for key in ('file_path','path','notebook_path'):
        v=ti.get(key)
        if isinstance(v,str) and v.strip():
            p=Path(v); return (p if p.is_absolute() else root/p).resolve()
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

def _parse_dt(s:Any):
    if not isinstance(s,str) or not s.strip():return None
    try:
        v=s.replace('Z','+00:00')
        dt=datetime.fromisoformat(v)
        if dt.tzinfo is None:dt=dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None

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

def _is_sensitive_path(p:Path)->bool:
    name=p.name
    if name=='.env' or (name.startswith('.env.') and not name.endswith(SENSITIVE_ENV_OK_SUFFIXES)):return True
    if '.git' in p.parts:return True
    return False

def redirect_targets(cmd:str)->list[str]:
    out=[]
    for t in REDIRECT_RE.findall(cmd):
        t=t.strip('\'"')
        if not t or t.startswith(('&','=')) or t.lower() in NULL_TARGETS:continue
        out.append(t)
    return out

def _names_file(token:str,name:str)->bool:
    return Path(token.strip('\'"()')).name.lower()==name.lower()

def command_findings(root:Path,cmd:str)->list[Finding]:
    """Checks a shell command (Bash or PowerShell) for secrets, destructive operations and writes to
    protected files or append-only audit artifacts. Writes are either redirections (whose target is
    inspected) or write verbs (after which any protected-file token is treated as a possible target)."""
    fs=[]
    if any(rx.search(cmd) for rx in SECRET):
        fs.append(Finding('BLOCK','SECRET_PATTERN','Possible secret detected in command; value not logged.'))
    if any(rx.search(cmd) for rx in DESTRUCTIVE):
        fs.append(Finding('BLOCK','DESTRUCTIVE_COMMAND','Potentially destructive command requires human approval.'))
    if REFRESH_BASELINE_RE.search(cmd):
        fs.append(Finding('BLOCK','BASELINE_REFRESH_REQUIRES_HUMAN','Refreshing the protected-file baseline is a human-only operation.'))
    redirects=redirect_targets(cmd)
    verb=bool(WRITE_VERB_RE.search(cmd))
    if not redirects and not verb:return fs
    tokens=[t for t in re.findall(r'[^\s"\'=,;()]+',cmd)]
    candidates=redirects+(tokens if verb else [])
    for part in candidates:
        candidate=Path(part.strip('()'))
        full=candidate if candidate.is_absolute() else root/candidate
        try:
            if is_audit_artifact(full,root) and full.exists():
                fs.append(Finding('BLOCK','AUDIT_ARTIFACT_REWRITE','Existing content-audit artifacts are append-only.'))
                break
        except (OSError,ValueError):
            continue
    for pname in sorted(PROTECTED):
        if any(_names_file(t,pname) for t in candidates):
            granted,mfindings=check_maintenance_approval(root,pname)
            if not granted:
                fs.extend(mfindings) if mfindings else fs.append(Finding('BLOCK','PROTECTED_FILE_WRITE_VIA_BASH',f'Shell write to protected file {pname} requires approved maintenance.',pname))
    return fs

def pre_tool(root:Path,data:Mapping[str,Any])->Result:
    fs=[]; name=data.get('tool_name'); ti=data.get('tool_input') if isinstance(data.get('tool_input'),Mapping) else {}
    if name in {'Write','Edit','MultiEdit','NotebookEdit'}:
        p=target(root,data)
        if p and is_audit_artifact(p,root) and p.exists():
            fs.append(Finding('BLOCK','AUDIT_ARTIFACT_REWRITE','Existing content-audit artifacts are append-only.',str(p)))
        if p and p.name in PROTECTED:
            granted,mfindings=check_maintenance_approval(root,p.name)
            if not granted:
                fs.extend(mfindings) if mfindings else fs.append(Finding('BLOCK','PROTECTED_FILE_WRITE',f'Protected file requires approved change: {p.name}',p.name))
        if p and _is_sensitive_path(p):fs.append(Finding('BLOCK','SENSITIVE_PATH_WRITE',f'Blocked sensitive path: {p}'))
        if p and p.parent.name==COUNCIL and p.name==BASELINE_REL[1]:
            fs.append(Finding('BLOCK','BASELINE_REFRESH_REQUIRES_HUMAN','The protected-file baseline is maintained by hooks only.'))
        for key in ('content','new_string','cell_source'):
            v=ti.get(key)
            if isinstance(v,str) and any(rx.search(v) for rx in SECRET):fs.append(Finding('BLOCK','SECRET_PATTERN','Possible secret detected; value not logged.'))
    if name in COMMAND_TOOLS:
        cmd=ti.get('command')
        if isinstance(cmd,str):fs.extend(command_findings(root,cmd))
    return finish('pre-tool-use',fs)

def _complete_maintenance(root:Path,data:Mapping[str,Any])->None:
    name=data.get('tool_name'); ti=data.get('tool_input') if isinstance(data.get('tool_input'),Mapping) else {}
    log_path=root.joinpath(*MAINTENANCE_LOG_REL)
    if not log_path.is_file():return
    try:
        log=json.loads(log_path.read_text(encoding='utf-8'))
    except Exception:
        return
    if not isinstance(log,list) or not log:return
    last=log[-1]
    if not isinstance(last,dict) or last.get('phase')!='granted' or 'completed_at' in last:return
    target_file=last.get('target_file')
    touched=False
    if name in {'Write','Edit','MultiEdit','NotebookEdit'}:
        p=target(root,data)
        touched=bool(p and p.name==target_file)
    elif name in COMMAND_TOOLS:
        cmd=ti.get('command')
        touched=isinstance(cmd,str) and isinstance(target_file,str) and bool(re.search(rf'(?<![A-Za-z0-9_.-]){re.escape(target_file)}(?![A-Za-z0-9_.-])', cmd, re.I))
    if touched and isinstance(target_file,str):
        fp=root/target_file
        post_hash=hashlib.sha256(fp.read_bytes()).hexdigest() if fp.is_file() else None
        last['phase']='completed'; last['post_hash']=post_hash; last['completed_at']=_now().isoformat()
        last['post_hash_normalized']=normalized_sha256(fp) if fp.is_file() else None
        log_path.write_text(json.dumps(log,indent=2,ensure_ascii=False),encoding='utf-8')

def active_run_findings(root:Path)->list[Finding]:
    """Validate any change to .council/active_run.json against the last accepted snapshot with the
    RUN transition kernel, and append accepted transitions to the RUN's transition log."""
    ap=root/COUNCIL/'active_run.json';sp=root.joinpath(*SNAPSHOT_REL)
    if not ap.is_file():return []
    current=_read_json(ap)
    if not isinstance(current,dict):
        return [Finding('BLOCK','ACTIVE_RUN_INVALID','active_run.json is not a JSON object.')]
    snap=_read_json(sp)
    if snap==current:return []
    if not isinstance(snap,dict) or snap.get('run_id')!=current.get('run_id'):
        fs=[]
        if isinstance(snap,dict) and snap.get('status')=='RUNNING':
            fs.append(Finding('WARNING','PREVIOUS_RUN_REPLACED_WHILE_RUNNING',f"{snap.get('run_id')} was still RUNNING when {current.get('run_id')} started."))
        _write_json(sp,current)
        try:run_kernel.append_transition_log(root,None,current,event='start')
        except Exception:pass
        return fs
    try:
        run_kernel.validate_transition(snap,current)
    except (run_kernel.TransitionError,ValueError) as e:
        return [Finding('BLOCK','RUN_TRANSITION_INVALID',f'active_run.json change rejected by runner: {e}. Restore the previous state or use hooks/runner.py apply.')]
    _write_json(sp,current)
    try:run_kernel.append_transition_log(root,snap,current,event='transition')
    except Exception:pass
    return []

def post_tool(root:Path,data:Mapping[str,Any])->Result:
    _complete_maintenance(root,data)
    fs=[]
    if (root/COUNCIL).is_dir():
        fs.extend(integrity_findings(root))
        fs.extend(active_run_findings(root))
    return finish('post-tool-use',fs)

def _run_progress_fingerprint(root:Path,data:Mapping[str,Any])->str:
    h=hashlib.sha256()
    ap=root/COUNCIL/'active_run.json'
    h.update(ap.read_bytes() if ap.is_file() else b'')
    outputs=data.get('outputs') if isinstance(data.get('outputs'),dict) else {}
    dirs={Path(v).parent for v in outputs.values() if isinstance(v,str)}
    for d in sorted(dirs,key=str):
        dd=d if d.is_absolute() else root/d
        if dd.is_dir():
            for f in sorted(dd.rglob('*')):
                if f.is_file():
                    st=f.stat();h.update(f'{f.relative_to(dd)}|{st.st_size}|{st.st_mtime_ns}\n'.encode())
    return h.hexdigest()

def running_stop_findings(root:Path,data:Mapping[str,Any],hook:Mapping[str,Any])->list[Finding]:
    """Stop while RUNNING: block, except (a) a stale active run, or (b) a repeated stop in the same
    Stop-hook continuation chain (stop_hook_active) with no progress since the last block. (b) lets
    Claude wait for background work or the user instead of looping into the 8-block override."""
    ap=root/COUNCIL/'active_run.json'
    age=_now().timestamp()-ap.stat().st_mtime
    if age>STALE_RUN_SECONDS:
        return [Finding('WARNING','STALE_ACTIVE_RUN',f"RUN {data.get('run_id')} has been RUNNING without changes for {int(age//3600)}h. Resume it or release it: python hooks/runner.py release --reason \"...\"")]
    sp=root.joinpath(*STOP_STATE_REL);state=_read_json(sp,{})
    fp=_run_progress_fingerprint(root,data)
    if hook.get('stop_hook_active') is True and isinstance(state,dict) and state.get('fingerprint')==fp and state.get('run_id')==data.get('run_id'):
        return [Finding('WARNING','RUN_INCOMPLETE_NO_PROGRESS',f"RUN {data.get('run_id')} is still RUNNING and nothing changed since the last block; stopping is allowed to wait for background work or the user. The RUN must still be completed, escalated, or released.")]
    _write_json(sp,{'run_id':data.get('run_id'),'fingerprint':fp,'blocked_at':_now().isoformat()})
    return [Finding('BLOCK','RUN_INCOMPLETE','Council RUN is still RUNNING; continue autonomously to completion, valid escalation, or explicit failure.')]

def _latest_audit_result(root:Path,ca_path:str,fs:list[Finding])->Any:
    ca_fp=Path(ca_path); ca_fp=ca_fp if ca_fp.is_absolute() else root/ca_fp
    if not ca_fp.is_file():return None
    try:
        ca_parsed=json.loads(ca_fp.read_text(encoding='utf-8'))
    except Exception:
        return None
    result=ca_parsed.get('result') if isinstance(ca_parsed,dict) else None
    if isinstance(ca_parsed,dict) and audit_result_was_rewritten(ca_parsed):
        fs.append(Finding('BLOCK','AUDIT_RESULT_REWRITTEN','content-audit final result hides an unresolved earlier audit pass.',str(ca_fp)))
    newest=latest_audit(ca_fp.parent)
    if newest is not None and newest[0].resolve()!=ca_fp.resolve():
        fs.append(Finding('FAIL','CONTENT_AUDIT_NOT_LATEST',f'outputs.content_audit must reference the newest audit pass ({newest[0].name}).',str(ca_fp)))
        return newest[1].get('result')
    return result

def pre_decision(root:Path,hook:Mapping[str,Any]|None=None)->Result:
    hook=hook or {}
    fs=integrity_findings(root) if (root/COUNCIL).is_dir() else []
    p=root/COUNCIL/'active_run.json'
    if not p.exists():return finish('pre-decision',fs+[Finding('WARNING','NO_ACTIVE_RUN','No active CouncilSystem run; skipped.')])
    try:data=json.loads(p.read_text(encoding='utf-8'))
    except Exception as e:return finish('pre-decision',fs+[Finding('FAIL','ACTIVE_RUN_INVALID',str(e),str(p))])
    if not isinstance(data,dict):return finish('pre-decision',fs+[Finding('FAIL','ACTIVE_RUN_INVALID','Root must be object.')])
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
        attempt_match=ATTEMPT_PATH_RE.search(str(fp))
        expected_attempt=int(attempt_match.group(1)) if attempt_match else None
        for issue in validate_artifact(
            parsed,
            expected_issue_id=data.get('issue_id'),
            expected_run_id=data.get('run_id'),
            expected_attempt=expected_attempt,
        ):
            fs.append(Finding('FAIL',f'ARTIFACT_{issue.code}',issue.message,str(fp)))
        for issue in stage_field_warnings(parsed):
            fs.append(Finding('WARNING',f'ARTIFACT_{issue.code}',issue.message,str(fp)))
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
        content_audit_result=_latest_audit_result(root,ca_path,fs)
    budget=data.get('deliberation_budget',{})
    counters=data.get('counters',{})
    def _count(v):return isinstance(v,int) and not isinstance(v,bool) and v>=0
    if budget or counters:
        if not isinstance(budget,dict) or not isinstance(counters,dict):
            fs.append(Finding('FAIL','BUDGET_INVALID','deliberation_budget and counters must be objects.'))
        else:
            for key in ('research_revisions','recritiques','audit_revisions'):
                limit=budget.get('max_'+key)
                used=counters.get(key,0)
                if not _count(limit) or not _count(used):
                    fs.append(Finding('FAIL','BUDGET_FIELD_INVALID',f'Invalid budget/counter for {key}.'))
                elif used > limit:
                    fs.append(Finding('FAIL','BUDGET_EXCEEDED',f'{key} exceeds configured limit.'))
    if content_audit_result in {'REVISE','BLOCK'}:
        if status in {'COMPLETED','CONDITIONAL_COMPLETION','DEGRADED_COMPLETION'}:
            fs.append(Finding('BLOCK','CONTENT_AUDIT_UNRESOLVED',f'content-audit final result is {content_audit_result}; cannot reach {status} while unresolved. Only the content-audit role may change this result; re-run content-audit after fixes, or use BOUNDED_COMPLETION if the audit-revision budget is exhausted.'))
        elif status=='BOUNDED_COMPLETION':
            limit=(budget or {}).get('max_audit_revisions') if isinstance(budget,dict) else None
            used=(counters or {}).get('audit_revisions',0) if isinstance(counters,dict) else None
            if not(_count(limit) and _count(used) and used>=limit):
                fs.append(Finding('BLOCK','BOUNDED_COMPLETION_WITHOUT_BUDGET_EXHAUSTION','BOUNDED_COMPLETION with an unresolved content-audit REVISE/BLOCK requires the audit_revisions budget to be exhausted (counters.audit_revisions >= deliberation_budget.max_audit_revisions).'))
    if status in {'COMPLETED','CONDITIONAL_COMPLETION','BOUNDED_COMPLETION','DEGRADED_COMPLETION'}:
        if stage!='final-synthesis':fs.append(Finding('FAIL','PREMATURE_COMPLETION','Completion status requires current_stage final-synthesis.'))
        if next_action!='COMPLETE':fs.append(Finding('FAIL','COMPLETION_ACTION_INVALID','Completion status requires next_action COMPLETE.'))
    elif next_action=='COMPLETE':
        fs.append(Finding('FAIL','PREMATURE_COMPLETE_ACTION','next_action COMPLETE requires a completion status.'))
    if status=='RUNNING':
        fs.extend(running_stop_findings(root,data,hook))
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
    ap=argparse.ArgumentParser();ap.add_argument('phase',choices=('pre-run','pre-tool-use','post-tool-use','pre-decision','refresh-baseline'));ap.add_argument('--root',type=Path);ap.add_argument('--json',action='store_true');a=ap.parse_args(argv)
    try:
        data={} if a.root else hook_input();root=a.root.resolve() if a.root else root_from(data)
        if a.phase=='refresh-baseline':
            refresh_baseline(root);print('protected-file baseline refreshed');return 0
        r=pre_run(root,data) if a.phase=='pre-run' else pre_tool(root,data) if a.phase=='pre-tool-use' else post_tool(root,data) if a.phase=='post-tool-use' else pre_decision(root,data)
        emit(r,a.json);return r.exit_code
    except Exception as e:print(f'[ERROR] validator failed: {e}',file=sys.stderr);return 1
if __name__=='__main__':raise SystemExit(main())
