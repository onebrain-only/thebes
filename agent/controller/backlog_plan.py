"""Read-only controller entry point for canonical Jira Product backlog planning."""
from agent.integrations import jira
from agent.controller.sprint_plan import plan_issues


def plan_backlog(*, jira_client=jira, state_store=None):
    """Discover the Jira Product backlog and delegate to the shared batch adapter."""
    if state_store is None:
        from agent.state import store as state_store
    issues = jira_client.search_issues(
        'project = KAN ORDER BY priority ASC, duedate ASC', limit=200)
    result = plan_issues(issues, "KAN Jira Product backlog",
                          "canonical Jira project query ordered by existing priority/due-date facts",
                          state_store=state_store)
    result["result_class"] = "EMPTY_BACKLOG" if not issues else "PLANNED"
    return result
