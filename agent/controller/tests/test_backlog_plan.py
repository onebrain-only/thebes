import os, sys
ROOT=os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, ROOT)
from agent.controller import backlog_plan
from agent.controller import sprint_plan

class Jira:
 def __init__(self, issues): self.issues=issues; self.calls=[]
 def search_issues(self,jql,limit): self.calls.append((jql,limit)); return self.issues
class State:
 def __init__(self,tasks,edges=()): self.tasks=tasks; self.edges=list(edges); self.writes=0
 def read_all(self,k): return self.tasks if k=="task" else self.edges if k=="dependency" else []
 def current_operating_mode(self): return "SYSTEM_MAINTENANCE"
def t(k,owner=None): return {"work_item_id":k,"record_type":"executable","project_id":"app","product_id":"dabbler","lifecycle":{"canonical":"ready","jira_status_id":"10008"},"ownership":owner,"surfaces":[],"logical_surfaces":[],"executor_evidence":[],"execution_profile":{"required_capability":"backend","work_effort":1,"characteristics":{},"validation_route":"self"}}
def i(k,due="2026-09-15"): return {"key":k,"status":"Ready","status_id":"10008","due_date":due,"description":"AC"}
old=sprint_plan.validate.seats_by_capability; sprint_plan.validate.seats_by_capability=lambda:{"backend":["backend-1","backend-2"]}
try:
 s=State([]); r=backlog_plan.plan_backlog(jira_client=Jira([]),state_store=s); assert r["result_class"]=="EMPTY_BACKLOG" and not r["future_execution_waves"] and s.writes==0
 s=State([t("KAN-901"),t("KAN-902")]); r=backlog_plan.plan_backlog(jira_client=Jira([i("KAN-901"),i("KAN-902")]),state_store=s); assert r["executable_count"]==2
 s=State([t("KAN-900"),t("KAN-901"),t("KAN-902")],[{"source_work_item":"KAN-900","target_work_item":"KAN-901","relation":"BLOCKS","completion_condition":"DONE"}]); r=backlog_plan.plan_backlog(jira_client=Jira([i("KAN-901"),i("KAN-902")]),state_store=s); assert r["executable_count"]==1 and any(x["admission_class"]=="WAITING_DEPENDENCY" for x in r["admissions"])
 print("3 passed")
finally: sprint_plan.validate.seats_by_capability=old
