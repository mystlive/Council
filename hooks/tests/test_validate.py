import hashlib,importlib.util,json,sys,tempfile,unittest
from pathlib import Path
p=Path(__file__).resolve().parents[1]/'validate.py';s=importlib.util.spec_from_file_location('cv',p);m=importlib.util.module_from_spec(s);sys.modules[s.name]=m;s.loader.exec_module(m)
class T(unittest.TestCase):
 def project(self,r):
  for n in m.REQUIRED:(r/n).write_text('# x\n',encoding='utf-8')
  for q in m.PRIVATE:(r/q).mkdir(parents=True,exist_ok=True)
  (r/'id_registry.json').write_text('{}',encoding='utf-8')
 def active(self,r,stage='chair-review',mode='NONE',status='RUNNING',next_action='CONTINUE',outputs=None,escalation=None):
  (r/'.council').mkdir(parents=True,exist_ok=True)
  d={'issue_id':'ISSUE-2026-0001','run_id':'RUN-20260722-0001','research_mode':mode,'current_stage':stage,'status':status,'next_action':next_action,'outputs':outputs or {}}
  if escalation is not None:d['escalation']=escalation
  (r/'.council'/'active_run.json').write_text(json.dumps(d),encoding='utf-8')
 def artifact_envelope(self,name):
  stages={'i':'issue-intake','c':'chair-review','d':'devil-advocate','s':'secretary','fv':'formal-validation','ca':'content-audit','fs':'final-synthesis'}
  skills={'i':'issue-intake','c':'chair-review','d':'devil-advocate','s':'secretary','fv':'formal-validation','ca':'content-audit','fs':'final-synthesis'}
  stage=stages.get(name,'research')
  return {'schema_version':'1.0','skill':skills.get(name,'web-research'),'issue_id':'ISSUE-2026-0001','run_id':'RUN-20260722-0001','attempt':1,'status':'COMPLETED','current_stage':stage,'next_action':'COMPLETE' if stage=='final-synthesis' else 'CONTINUE','escalation':None,'input_refs':[],'output_refs':[],'claims':[],'unknowns':[],'warnings':[],'errors':[]}
 def artifact(self,r,name):
  p=r/'runs'/'private'/f'{name}.json';p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(self.artifact_envelope(name)),encoding='utf-8');return str(p)
 def artifact_json(self,r,name,obj):
  p=r/'runs'/'private'/f'{name}.json';p.parent.mkdir(parents=True,exist_ok=True);data=self.artifact_envelope(name);data.update(obj);p.write_text(json.dumps(data),encoding='utf-8');return str(p)
 def final_outputs(self,r,content_audit_result=None):
  o={'issue_intake':self.artifact(r,'i'),'chair_review':self.artifact(r,'c'),'devil_advocate':self.artifact(r,'d'),'secretary':self.artifact(r,'s'),'formal_validation':self.artifact(r,'fv'),'final_synthesis':self.artifact(r,'fs')}
  if content_audit_result is not None:
   o['content_audit']=self.artifact_json(r,'ca',{'result':content_audit_result})
  return o
 def make_approval(self,r,filename='AGENTS.md',**overrides):
  fp=r/filename
  if not fp.is_file():fp.write_text('# x\n',encoding='utf-8')
  approval={'approved_file':filename,'reason':'test reason','approved_by':'tester',
            'approved_at':'2026-01-01T00:00:00+00:00','expires_at':'2999-01-01T00:00:00+00:00',
            'expected_pre_hash':hashlib.sha256(fp.read_bytes()).hexdigest(),'used':False}
  approval.update(overrides)
  (r/'.council').mkdir(parents=True,exist_ok=True)
  (r/'.council'/'maintenance_approval.json').write_text(json.dumps(approval),encoding='utf-8')
  return approval
 def test_pre_run(self):
  with tempfile.TemporaryDirectory() as d:
   r=Path(d);self.project(r);self.assertEqual(m.pre_run(r).result,'PASS_WITH_WARNINGS')
 def test_protected(self):
  with tempfile.TemporaryDirectory() as d:
   r=Path(d);x=m.pre_tool(r,{'tool_name':'Write','tool_input':{'file_path':str(r/'AGENTS.md'),'content':'x'}});self.assertEqual(x.result,'BLOCK')
 def test_destructive(self):
  with tempfile.TemporaryDirectory() as d:self.assertEqual(m.pre_tool(Path(d),{'tool_name':'Bash','tool_input':{'command':'git reset --hard HEAD'}}).result,'BLOCK')
 def test_no_active(self):
  with tempfile.TemporaryDirectory() as d:self.assertEqual(m.pre_decision(Path(d)).result,'PASS_WITH_WARNINGS')
 def test_stage_specific_pass(self):
  with tempfile.TemporaryDirectory() as d:
   r=Path(d);o={'issue_intake':self.artifact(r,'i'),'chair_review':self.artifact(r,'c')};self.active(r,outputs=o)
   self.assertEqual(m.pre_decision(r).result,'BLOCK')
 def test_artifact_envelope_is_required(self):
  with tempfile.TemporaryDirectory() as d:
   r=Path(d);p=r/'runs'/'private'/'i.json';p.parent.mkdir(parents=True,exist_ok=True);p.write_text('{}',encoding='utf-8')
   self.active(r,outputs={'issue_intake':str(p),'chair_review':str(p)})
   x=m.pre_decision(r);self.assertTrue(any(f.code=='ARTIFACT_FIELD_MISSING' for f in x.findings))
 def test_artifact_identity_must_match_active_run(self):
  with tempfile.TemporaryDirectory() as d:
   r=Path(d);p=Path(self.artifact(r,'i'));data=json.loads(p.read_text(encoding='utf-8'));data['issue_id']='ISSUE-2026-0099';p.write_text(json.dumps(data),encoding='utf-8')
   self.active(r,outputs={'issue_intake':str(p),'chair_review':str(p)})
   x=m.pre_decision(r);self.assertTrue(any(f.code=='ARTIFACT_ISSUE_ID_MISMATCH' for f in x.findings))
 def test_artifact_reference_traversal_is_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   r=Path(d);p=Path(self.artifact(r,'i'));data=json.loads(p.read_text(encoding='utf-8'));data['input_refs']=['../secret.json'];p.write_text(json.dumps(data),encoding='utf-8')
   self.active(r,outputs={'issue_intake':str(p),'chair_review':str(p)})
   x=m.pre_decision(r);self.assertTrue(any(f.code=='ARTIFACT_REF_UNSAFE' for f in x.findings))
 def test_existing_audit_artifact_is_append_only(self):
  with tempfile.TemporaryDirectory() as d:
   r=Path(d);p=r/'runs'/'private'/'RUN-20260722-0001'/'attempt-01'/'content_audit-01.json';p.parent.mkdir(parents=True,exist_ok=True);p.write_text('{}',encoding='utf-8')
   x=m.pre_tool(r,{'tool_name':'Write','tool_input':{'file_path':str(p),'content':'{}'}})
   self.assertEqual(x.result,'BLOCK');self.assertTrue(any(f.code=='AUDIT_ARTIFACT_REWRITE' for f in x.findings))
 def test_legacy_rewritten_audit_result_is_blocked(self):
  with tempfile.TemporaryDirectory() as d:
   r=Path(d);p=Path(self.artifact_json(r,'ca',{'result':'PASS_WITH_WARNINGS','audit_passes':[{'pass':1,'result':'REVISE'}]}));self.active(r,stage='final-synthesis',status='CONDITIONAL_COMPLETION',next_action='COMPLETE',outputs=self.final_outputs(r))
   data=json.loads((r/'.council'/'active_run.json').read_text(encoding='utf-8'));data['outputs']['content_audit']=str(p);(r/'.council'/'active_run.json').write_text(json.dumps(data),encoding='utf-8')
   x=m.pre_decision(r);self.assertTrue(any(f.code=='AUDIT_RESULT_REWRITTEN' for f in x.findings))
 def test_unknown_does_not_require_human(self):
  with tempfile.TemporaryDirectory() as d:
   r=Path(d);o={'issue_intake':self.artifact(r,'i'),'chair_review':self.artifact(r,'c')};self.active(r,outputs=o,status='RUNNING',next_action='RESEARCH')
   x=m.pre_decision(r);self.assertEqual(x.result,'BLOCK');self.assertFalse(any(f.code.startswith('ESCALATION') for f in x.findings))
 def test_invalid_human_escape_blocked(self):
  with tempfile.TemporaryDirectory() as d:
   r=Path(d);self.active(r,status='WAITING_FOR_HUMAN',next_action='ESCALATE',escalation={'reason_code':'UNKNOWN'})
   self.assertEqual(m.pre_decision(r).result,'BLOCK')
 def test_running_run_cannot_stop(self):
  with tempfile.TemporaryDirectory() as d:
   r=Path(d);o={'issue_intake':self.artifact(r,'i')};self.active(r,outputs=o)
   self.assertEqual(m.pre_decision(r).result,'BLOCK')
 def test_powershell_write_to_protected_file_is_blocked(self):
  with tempfile.TemporaryDirectory() as d:
   r=Path(d);data={'tool_name':'Bash','tool_input':{'command':'Set-Content AGENTS.md bad'}}
   self.assertEqual(m.pre_tool(r,data).result,'BLOCK')
 def test_valid_human_escalation(self):
  with tempfile.TemporaryDirectory() as d:
   r=Path(d);e={'reason_code':'HUMAN_ONLY_INFORMATION','question':'Provide internal budget','required_answer':'Budget ceiling','resume_step':'chair-review','why_conditions_cannot_substitute':'The recommendation changes at the unknown private threshold.'};self.active(r,status='WAITING_FOR_HUMAN',next_action='ESCALATE',escalation=e)
   self.assertEqual(m.pre_decision(r).result,'PASS')
 def test_premature_completion_fails(self):
  with tempfile.TemporaryDirectory() as d:
   r=Path(d);o={'issue_intake':self.artifact(r,'i'),'chair_review':self.artifact(r,'c')};self.active(r,status='COMPLETED',next_action='COMPLETE',outputs=o)
   self.assertEqual(m.pre_decision(r).result,'FAIL')
 def test_bash_write_to_protected_file_is_blocked(self):
  with tempfile.TemporaryDirectory() as d:
   r=Path(d);x=m.pre_tool(r,{'tool_name':'Bash','tool_input':{'command':'echo x > MASTER_DESIGN.md'}});self.assertEqual(x.result,'BLOCK')
 def test_content_audit_revise_then_recheck_pass_allows_completion(self):
  with tempfile.TemporaryDirectory() as d:
   r=Path(d);o=self.final_outputs(r,content_audit_result='PASS_WITH_WARNINGS')
   self.active(r,stage='final-synthesis',status='CONDITIONAL_COMPLETION',next_action='COMPLETE',outputs=o)
   self.assertEqual(m.pre_decision(r).result,'PASS')
 def test_content_audit_revise_budget_exhausted_allows_bounded_completion(self):
  with tempfile.TemporaryDirectory() as d:
   r=Path(d);o=self.final_outputs(r,content_audit_result='REVISE')
   self.active(r,stage='final-synthesis',status='BOUNDED_COMPLETION',next_action='COMPLETE',outputs=o)
   data=json.loads((r/'.council'/'active_run.json').read_text(encoding='utf-8'))
   data['deliberation_budget']={'max_research_revisions':2,'max_recritiques':2,'max_audit_revisions':1}
   data['counters']={'research_revisions':0,'recritiques':0,'audit_revisions':1}
   (r/'.council'/'active_run.json').write_text(json.dumps(data),encoding='utf-8')
   self.assertEqual(m.pre_decision(r).result,'PASS')
 def test_content_audit_revise_budget_not_exhausted_bounded_completion_blocked(self):
  with tempfile.TemporaryDirectory() as d:
   r=Path(d);o=self.final_outputs(r,content_audit_result='REVISE')
   self.active(r,stage='final-synthesis',status='BOUNDED_COMPLETION',next_action='COMPLETE',outputs=o)
   data=json.loads((r/'.council'/'active_run.json').read_text(encoding='utf-8'))
   data['deliberation_budget']={'max_research_revisions':2,'max_recritiques':2,'max_audit_revisions':2}
   data['counters']={'research_revisions':0,'recritiques':0,'audit_revisions':1}
   (r/'.council'/'active_run.json').write_text(json.dumps(data),encoding='utf-8')
   x=m.pre_decision(r);self.assertEqual(x.result,'BLOCK');self.assertTrue(any(f.code=='BOUNDED_COMPLETION_WITHOUT_BUDGET_EXHAUSTION' for f in x.findings))
 def test_content_audit_revise_conditional_completion_blocked(self):
  with tempfile.TemporaryDirectory() as d:
   r=Path(d);o=self.final_outputs(r,content_audit_result='REVISE')
   self.active(r,stage='final-synthesis',status='CONDITIONAL_COMPLETION',next_action='COMPLETE',outputs=o)
   x=m.pre_decision(r);self.assertEqual(x.result,'BLOCK');self.assertTrue(any(f.code=='CONTENT_AUDIT_UNRESOLVED' for f in x.findings))
 def test_maintenance_approval_grants_write_and_is_consumed(self):
  with tempfile.TemporaryDirectory() as d:
   r=Path(d);self.make_approval(r,filename='AGENTS.md')
   x=m.pre_tool(r,{'tool_name':'Write','tool_input':{'file_path':str(r/'AGENTS.md'),'content':'x'}})
   self.assertEqual(x.result,'PASS')
   self.assertFalse((r/'.council'/'maintenance_approval.json').exists())
   log=json.loads((r/'.council'/'maintenance_log.json').read_text(encoding='utf-8'))
   self.assertEqual(log[-1]['phase'],'granted');self.assertEqual(log[-1]['target_file'],'AGENTS.md')
 def test_maintenance_approval_wrong_file_still_blocked(self):
  with tempfile.TemporaryDirectory() as d:
   r=Path(d);self.make_approval(r,filename='AGENTS.md')
   x=m.pre_tool(r,{'tool_name':'Write','tool_input':{'file_path':str(r/'MASTER_DESIGN.md'),'content':'x'}})
   self.assertEqual(x.result,'BLOCK');self.assertTrue(any(f.code=='PROTECTED_FILE_WRITE' for f in x.findings))
   self.assertTrue((r/'.council'/'maintenance_approval.json').exists())
 def test_maintenance_approval_expired_blocks(self):
  with tempfile.TemporaryDirectory() as d:
   r=Path(d);self.make_approval(r,filename='AGENTS.md',expires_at='2000-01-01T00:00:00+00:00')
   x=m.pre_tool(r,{'tool_name':'Write','tool_input':{'file_path':str(r/'AGENTS.md'),'content':'x'}})
   self.assertEqual(x.result,'BLOCK');self.assertTrue(any(f.code=='MAINTENANCE_APPROVAL_EXPIRED' for f in x.findings))
 def test_maintenance_approval_already_used_blocks(self):
  with tempfile.TemporaryDirectory() as d:
   r=Path(d);self.make_approval(r,filename='AGENTS.md',used=True)
   x=m.pre_tool(r,{'tool_name':'Write','tool_input':{'file_path':str(r/'AGENTS.md'),'content':'x'}})
   self.assertEqual(x.result,'BLOCK');self.assertTrue(any(f.code=='MAINTENANCE_APPROVAL_ALREADY_USED' for f in x.findings))
 def test_maintenance_approval_hash_mismatch_blocks(self):
  with tempfile.TemporaryDirectory() as d:
   r=Path(d);self.make_approval(r,filename='AGENTS.md',expected_pre_hash='0'*64)
   x=m.pre_tool(r,{'tool_name':'Write','tool_input':{'file_path':str(r/'AGENTS.md'),'content':'x'}})
   self.assertEqual(x.result,'BLOCK');self.assertTrue(any(f.code=='MAINTENANCE_APPROVAL_HASH_MISMATCH' for f in x.findings))
 def test_maintenance_approval_wildcard_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   r=Path(d);self.make_approval(r,filename='AGENTS.md');(r/'.council'/'maintenance_approval.json').write_text(json.dumps({**json.loads((r/'.council'/'maintenance_approval.json').read_text(encoding='utf-8')),'approved_file':'*.md'}),encoding='utf-8')
   x=m.pre_tool(r,{'tool_name':'Write','tool_input':{'file_path':str(r/'AGENTS.md'),'content':'x'}})
   self.assertEqual(x.result,'BLOCK');self.assertTrue(any(f.code=='MAINTENANCE_APPROVAL_INVALID' for f in x.findings))
 def test_maintenance_approval_missing_reason_blocks(self):
  with tempfile.TemporaryDirectory() as d:
   r=Path(d);self.make_approval(r,filename='AGENTS.md',reason='')
   x=m.pre_tool(r,{'tool_name':'Write','tool_input':{'file_path':str(r/'AGENTS.md'),'content':'x'}})
   self.assertEqual(x.result,'BLOCK');self.assertTrue(any(f.code=='MAINTENANCE_APPROVAL_INVALID' for f in x.findings))
 def test_maintenance_approval_one_time_use(self):
  with tempfile.TemporaryDirectory() as d:
   r=Path(d);self.make_approval(r,filename='AGENTS.md')
   first=m.pre_tool(r,{'tool_name':'Write','tool_input':{'file_path':str(r/'AGENTS.md'),'content':'x'}})
   second=m.pre_tool(r,{'tool_name':'Write','tool_input':{'file_path':str(r/'AGENTS.md'),'content':'y'}})
   self.assertEqual(first.result,'PASS');self.assertEqual(second.result,'BLOCK')
   self.assertTrue(any(f.code=='PROTECTED_FILE_WRITE' for f in second.findings))
 def test_maintenance_approval_via_bash(self):
  with tempfile.TemporaryDirectory() as d:
   r=Path(d);self.make_approval(r,filename='AGENTS.md')
   x=m.pre_tool(r,{'tool_name':'Bash','tool_input':{'command':'python -c "open(\'AGENTS.md\',\'w\').write(\'x\')"'}})
   self.assertEqual(x.result,'PASS')
 def test_post_tool_use_records_post_hash(self):
  with tempfile.TemporaryDirectory() as d:
   r=Path(d);self.make_approval(r,filename='AGENTS.md')
   m.pre_tool(r,{'tool_name':'Write','tool_input':{'file_path':str(r/'AGENTS.md'),'content':'x'}})
   (r/'AGENTS.md').write_text('changed content',encoding='utf-8')
   m.post_tool(r,{'tool_name':'Write','tool_input':{'file_path':str(r/'AGENTS.md'),'content':'x'}})
   log=json.loads((r/'.council'/'maintenance_log.json').read_text(encoding='utf-8'))
   self.assertEqual(log[-1]['phase'],'completed');self.assertIsNotNone(log[-1]['post_hash']);self.assertIn('completed_at',log[-1])
 def test_no_maintenance_approval_protection_unaffected(self):
  with tempfile.TemporaryDirectory() as d:
   r=Path(d);x=m.pre_tool(r,{'tool_name':'Write','tool_input':{'file_path':str(r/'DECISION_RULES.md'),'content':'x'}})
   self.assertEqual(x.result,'BLOCK');self.assertTrue(any(f.code=='PROTECTED_FILE_WRITE' for f in x.findings))
if __name__=='__main__':unittest.main()
