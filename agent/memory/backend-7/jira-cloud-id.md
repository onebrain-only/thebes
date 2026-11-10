---
name: jira-cloud-id
description: Dabbler's Jira lives at dabbler.atlassian.net (cloudId 18c8e9f5-d139-4e03-b5d8-89122cc14937), NOT onebrain.atlassian.net — guessing the Onebrain host fails with a "not explicitly granted" error.
metadata:
  type: reference
---

Dabbler's Jira board (project `KAN`) is on the **`dabbler`** Atlassian site:

- URL: `https://dabbler.atlassian.net`
- cloudId: `18c8e9f5-d139-4e03-b5d8-89122cc14937`

Pass that cloudId to the Rovo tools (`mcp__claude_ai_Atlassian_Rovo__*`).

**The trap:** the Supabase project's *organisation* is named Onebrain, and the agent roster is the
"Onebrain Agent Team", so `onebrain.atlassian.net` is the natural guess. It resolves to a real cloudId
(`e9cb3651-3f06-4ae1-913c-0a8df3de5978`) and then **fails** with
`Cloud id ... isn't explicitly granted by the user`. That error looks like a permissions problem and is
actually a wrong-site problem. `getAccessibleAtlassianResources` lists only `dabbler`.

Use the **Rovo** server. The plain `mcp__atlassian__*` token is expired.
