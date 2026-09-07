---
name: grill-po
description: Grill the PO before acting, whenever a message describes intent rather than directing a known step. Fires on uncertainty ("not sure", "I think", "maybe", "what do you think"), on a request to be understood ("I want you to understand", "does that make sense"), on a new feature, agent, or workflow described in prose, and on a brief thinner than the work it names. On a direct instruction or an acknowledgement, act immediately instead.
---

Interview the PO until you could build the thing without guessing once.

Same discipline as `grilling`: map the work as a **design tree**, work it in
**rounds**, ask the whole **frontier** at once — numbered, each carrying your
recommended answer — then wait.

```
❓ **Q1** - **<title>**: <body, with options where they exist>

➡️ <your recommended answer>
```

## The discriminator

Read the message and ask one thing: **does it describe, or does it direct?**

**Describes** — intent, a want, a shape, a problem, a direction. The PO is thinking
aloud and the detail lives in his head, not the message. **Grill.**

**Directs** — a step you already understand, in work already scoped. **Act.**

Applied:

| Message | Read | Do |
|---|---|---|
| "done", "continue", "work on it", "yes", "go ahead", "fix it" | directs | act now |
| "push that", "run the audit", "review KAN-8" | directs | act now |
| "I'm not sure if…", "I think maybe…", "what do you think?" | describes | grill |
| "I want you to understand…", "does that make sense?" | describes | grill |
| a new feature, agent, workflow, or process, described in prose | describes | grill |
| "build X" where X is a week of work in three words | describes | grill |

**Scope decides, not length.** A short message naming a large thing is a thin brief
and earns a grill. A long message walking through steps you already understand is a
direction and earns action.

## Cost discipline

Every round spends the PO's attention. That is the budget.

**Find facts yourself.** Anything the filesystem, the database, git, or Jira can
answer, answer it — then bring the finding into the question so he is deciding, not
retrieving. A question you could have looked up teaches him the grill is noise.

**Ask what only he holds:** intent, priority, scope, what "done" means, what he
would cut, what he already tried and rejected. That is the whole reason to ask.

**Recommend on every question.** He should be able to reply "1, 3, yes" and have it
mean something. A question with no recommendation attached hands the work back.

**One round at a time.** A question whose answer depends on another question still
open belongs to a later round.

## Done

The frontier is empty: every branch visited, nothing silently assumed. Say what you
now understand in a sentence or two, confirm it lands, and start.

If a single round settles it, one round is the whole grill. Depth follows the work,
not a quota.
