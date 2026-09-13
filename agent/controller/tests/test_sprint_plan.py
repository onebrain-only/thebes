import copy
import os, sys
from datetime import datetime
from zoneinfo import ZoneInfo

ROOT=os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, ROOT)
from agent.controller import sprint_plan

NOW=datetime(2026,9,14,10,tzinfo=ZoneInfo("Asia/Dubai"))

def task(key, owner=None, surfaces=None):
    return {"work_item_id":key,"record_type":"executable","project_id":"app","product_id":"dabbler",
      "lifecycle":{"canonical":"ready","jira_status_id":"10008","observed_at":"2026-09-14T10:00:00Z"},
      "ownership":owner,"surfaces":surfaces or [],"logical_surfaces":[],"executor_evidence":[],
      "execution_profile":{"required_capability":"backend","work_effort":1,"characteristics":{},"validation_route":"self"}}

class Jira:
 def __init__(self, issues): self.issues=issues; self.calls=[]
 def search_issues(self, jql, limit): self.calls.append((jql,limit)); return copy.deepcopy(self.issues)
class State:
 def __init__(self,tasks,edges=()): self.tasks=tasks; self.edges=list(edges); self.writes=0
 def read_all(self,kind): return copy.deepcopy(self.tasks if kind=="task" else self.edges if kind=="dependency" else [])
 def current_operating_mode(self): return "SYSTEM_MAINTENANCE"
def issue(key): return {"key":key,"status":"Ready","status_id":"10008","due_date":"2026-09-15","description":"AC"}

old=sprint_plan.validate.seats_by_capability
sprint_plan.validate.seats_by_capability=lambda:{"backend":["backend-1","backend-2"]}
try:
 empty=State([]); r=sprint_plan.plan_current_sprint(jira_client=Jira([]),state_store=empty,when=NOW)
 assert r["result_class"]=="EMPTY_SPRINT" and r["future_execution_waves"]==[] and empty.writes==0
 one=State([task("KAN-901")]); j=Jira([issue("KAN-901")]); r=sprint_plan.plan_current_sprint(jira_client=j,state_store=one,when=NOW)
 assert j.calls and r["executable_count"]==1 and r["admissions"][0]["planned_executor"]=="backend-1" and r["admissions"][0]["planned_provider"]=="claude-code"
 dep=State([task("KAN-901"),task("KAN-902")],[{"source_work_item":"KAN-901","target_work_item":"KAN-902","relation":"BLOCKS","completion_condition":"DONE"}]); r=sprint_plan.plan_current_sprint(jira_client=Jira([issue("KAN-901"),issue("KAN-902")]),state_store=dep,when=NOW)
 assert any(x["key"]=="KAN-902" and x["admission_class"]=="WAITING_DEPENDENCY" for x in r["admissions"])
 missing=issue("KAN-906"); missing["due_date"]=None
 r=sprint_plan.plan_current_sprint(jira_client=Jira([missing]),state_store=State([task("KAN-906")]),when=NOW)
 assert r["admissions"][0]["admission_class"]=="MISSING_READY_FACT" and r["operating_mode"]=="SYSTEM_MAINTENANCE"
 owned=task("KAN-903",{"seat_id":"backend-2","claim_ref":"r","claimed_at":"x"},logical:=[]); owned["logical_surfaces"]=["public.x"]
 contender=task("KAN-904"); contender["logical_surfaces"]=["public.x"]
 r=sprint_plan.plan_current_sprint(jira_client=Jira([issue("KAN-903"),issue("KAN-904")]),state_store=State([owned,contender]),when=NOW)
 assert any(x["key"]=="KAN-903" and x["admission_class"]=="ALREADY_OWNED" for x in r["admissions"]) and any(x["key"]=="KAN-904" and x["admission_class"]=="WAITING_CONTENTION" for x in r["admissions"])
 print("4 passed")
finally: sprint_plan.validate.seats_by_capability=old
