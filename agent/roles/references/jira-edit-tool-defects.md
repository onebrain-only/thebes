# Jira edit tool defects — read before writing or trusting any ticket description

Found by `po` on 2026-09-11 while restructuring the T-077 erasure tickets. Applies to every
seat that creates or edits a Jira ticket, not just `po` — `po` is the only seat that writes
tickets, but every seat reads them, and a ticket that reads clean may not be complete.

## The standing rule

**An edit is not done until its return value has been read back against what was submitted.**
Not "when something looks off" — one of the two instances below (the meaning-inverting one)
looked completely fine on the page. Verification-on-write has to be standing practice, not
vigilance, because vigilance only catches the visible failure mode.

The strongest form of this rule: **the author verifies their own edit immediately, while they
still remember the intended meaning.** Nobody downstream can catch a dropped word that still
reads as a grammatical sentence — only someone who knows what the ticket was supposed to say
can.

## Defect 1 — `createJiraIssue`'s `description` is a plain string, not JSON

`editJiraIssue` takes `fields` as a JSON object; inside a JSON string, `\n` is the standard
escape for a real newline, so writing markdown with `\n` line breaks into `fields.description`
works correctly. `createJiraIssue`'s `description` parameter is a **plain string**, not a JSON
value — a literal `\n` typed into it comes through as the two characters backslash-`n`, not a
line break. A ticket created this way renders with visible `\n`/`\*` escape sequences instead of
paragraphs and bullets.

**Mitigation:** never write real content through `createJiraIssue`. Create the issue with a
one-line placeholder description, note the returned key, then write the actual content via
`editJiraIssue` on that key. This is the pattern used for KAN-191/192/193/194 (2026-09-11)
after the defect was found on the first attempt.

## Defect 2 — bold spans crossing a hard line break silently drop content on the markdown→ADF round-trip

When a `**bold...**` span (or `_italic..._`) is written across a markdown hard line break
(two trailing spaces + newline, or just a line break inside the span in the source text), the
tool's markdown→ADF conversion does not reliably preserve everything between the markers. Two
distinct failure shapes have been observed:

- **Formatting-only loss:** the bold/italic closes early, right before the line break — no
  words are lost, only emphasis. Harmless but untidy (e.g. a marker landing right before a
  backtick-quoted identifier instead of after it).
- **Content loss:** an entire clause or word is silently dropped, leaving either a broken
  fragment (**visible** — a sentence that stops making sense) or, worse, a small deletion that
  leaves a grammatically valid but **wrong** sentence (**invisible** — nothing about the
  resulting text looks broken).

**The invisible shape is the dangerous one.** On KAN-186, a dropped `"un"` turned "rejected as
**un**available" into "rejected as available" — a ticket instructing its executor to do the
opposite of what the cited ruling actually decided, with no visible artefact that anything was
wrong. A dropped clause (also seen on KAN-186, and on KAN-170/KAN-176 from edits made this same
session) at least leaves a fragment a careful reader notices; a dropped negation does not.

**Detection guidance:**
- *Visible shape:* grep signature is a stranded formatting marker with little or no content
  around it — e.g. `**A**` followed immediately by a backtick-quoted identifier and then a verb,
  or a bold span that opens and closes with only a fragment of a word between the markers.
  Sentences that stop mid-thought, or headings whose body is missing entirely, are the same
  failure at a larger scale.
- *Invisible shape:* grep will not find this. It requires a reader who knows what the ticket is
  **supposed** to say — a negation that doesn't fit the surrounding argument, a criterion whose
  stated test doesn't match what the ticket says it's testing, or an instruction that contradicts
  a ruling quoted elsewhere in the same ticket. This is the argument for the author re-reading
  their own edit immediately: a fresh reader six months later has no way to know the sentence
  used to say something else.

**Mitigation when writing — this is a writing rule, not just a detection rule.** Keep every bold
(and italic) span entirely within one line of the submitted markdown — do not let `**...**` or
`_..._` cross a hard line break. If a sentence needs a line break, put it outside the span, or
don't force a hard break at all (a single logical paragraph does not need one). **Write to avoid
the trigger by default, rather than writing normally and relying on the re-read to catch it** —
the re-read is still mandatory (it also catches instances this rule doesn't, and the KAN-183
case below shows it catching two in one pass), but a paragraph authored with no bold span ever
touching a `  \n` cannot produce this failure at all, which is cheaper than finding it after the
fact.

**Mitigation when repairing a found instance:** state explicitly, in the ticket text, whether a
repair is a **verbatim recovery** (the exact original wording is known or strongly corroborated
— e.g. the identical phrase appears elsewhere in the same ticket family) or a **reconstruction**
(the repairer's best guess at intended meaning from context). Label reconstructions as such. A
reconstruction that reads as a clean recovery is itself a risk — on KAN-186, a first repair
attempt was a plausible-sounding reconstruction that turned out to repair the wrong premise
(it patched the "which tables cascade" sentence when the actual lost clause explained "why is
this list seven, not eight" — a related but different point in the same paragraph). It was
caught because it had been labeled a reconstruction rather than presented as recovered fact,
which is what let `cto` re-derive the actual lost content from the surviving fragment shape and
correct it. **Label every round-trip repair this way, without exception.**

## Frequency, as measured 2026-09-11

Four tickets confirmed corrupted in one session, seven instances total: `KAN-170` (one
pre-existing instance found and fixed, one instance introduced and caught on the same day's own
edit), `KAN-176` (one instance introduced and caught on the same day's own edit), `KAN-186` (two
pre-existing instances, unrelated to that day's edits, found only because the ticket was re-read
closely for an unrelated audit), `KAN-183` (two instances, both introduced in the same single
`editJiraIssue` call — see below). `KAN-131` and `KAN-171` were checked on the same pass and read
clean — so this is frequent enough to require verification-on-write as standing practice, not so
frequent that no ticket text can be trusted at all.

**A single edit can carry more than one instance — do not stop at the first one found.** Every
prior confirmed case (KAN-170, KAN-176, KAN-186) happened to be one instance per edit or per
ticket, so the natural habit is to fix the one you spot and move on. `KAN-183` broke that pattern:
two separate bold spans, each crossing its own hard break, both dropped content in the same
submission. Anyone who fixed the first and stopped would have shipped the second uncorrected.
**Read the entire returned description back, start to finish, against the entire submitted text
— not just the section you were worried about.**

**On how far back this goes: don't try to bound it by inference.** Tickets edited through this
tool before 2026-09-11 were never verified on write, because this defect was not yet known. An
unexplained inconsistency, a sentence that reads a little oddly, or an instruction that seems to
cut against a ruling it cites — in a ticket predating this date — should default to "possible
corruption from this tool," checked against context and any corroborating phrase elsewhere in the
ticket family, rather than assumed to be an authoring mistake by whoever wrote it. That is the
useful inference to carry forward, not a specific list of affected tickets, which cannot be
known.

## What to do on discovery

- Fix corruption in place once found — restoring dropped text (correctly labeled per the
  mitigation above) is repair, not a scope change, and does not need separate authorization.
- Report the running count as it's found, not only in a final summary — three instances in one
  session is enough to change whether *any* ticket text should be trusted without a fresh read,
  including tickets already closed. That determination affects verification that already
  happened (a lost clause in an AC means the AC, as it read at verification time, was never
  actually checked) and is worth surfacing immediately rather than at the end of a pass.
- A lost clause discovered in a **closed** ticket's acceptance criteria or ruling/authorization
  text is more serious than one in an open ticket's description: an open ticket gets caught at
  Preflight by whoever claims it; a closed ticket was already verified against its ACs as they
  read at the time, so a requirement that was silently missing was never actually checked. That
  is a false Done, not just incomplete text. Report the ticket, the suspected lost text, and what
  the executor's evidence actually demonstrated — whether the closure should stand is a judgement
  for `po`/`team-lead`/`cto` together, not something to decide or act on unilaterally while
  scanning.

## A related but separate pattern — the one-question check for any ticket

The tool defects above are one way a requirement ends up living outside a ticket's acceptance
criteria. It is not the only way, and the other way doesn't need a tool bug — a human (or an
agent) can file a real requirement in prose and never turn it into a criterion, on a ticket the
tool never touched. Found three times on 2026-09-11 alone, three different disguises:

1. **KAN-170** (the original instance): `"(column becomes nullable)"` was a parenthetical in the
   ticket's prose, with no AC asserting the column actually ended up nullable — a criterion that
   cannot detect its own failure, one layer up from the AC-writing discipline it was supposed to
   model.
2. **KAN-131**: a restatement requirement (`T-044`/`CONVENTIONS.md` §6c, `search_path` and
   `prosecdef` on a restated function) sat in a section titled "Superseded sequencing text" that
   itself says the requirement "still applies" — true, and un-enforced, until an AC was added.
3. **KAN-178**: the worst version, because it was deliberate. A safety-critical non-recursion
   invariant was filed under a heading reading **"For the reviewer, not an AC"**, with an
   explicit instruction not to let it be trimmed as noise. Someone recognised the requirement
   was load-bearing and *still* placed it where the review gate doesn't look.

**The common shape: a real requirement lives somewhere in the description other than the
acceptance criteria list.** It can be a stray parenthetical, a note in a section marked
superseded-but-still-applicable, or a paragraph explicitly labeled as deliberately outside the
ACs. All three read as reasonable, well-written ticket text — none of them look like a defect
while you're writing or reviewing them normally.

**The check, to run when writing or reviewing any ticket, not only ones this tool touched:**

> Does every requirement in this description appear in the criteria that will actually be
> tested?

Ask it of every ruling quoted, every "must"/"must not," every named standard the ticket invokes
(a `CONVENTIONS.md` section, a prior `T-`/`P-` decision, a security property). If the answer
requires a review-time human to remember a paragraph from three sections up rather than read an
AC, the requirement isn't enforced — it's a hope. That single question would have caught all
three instances above, plus the original `NOT NULL` miss that started this whole audit.

## When the requirement is an ordering constraint: reach for the claim system, not an AC

A cross-ticket ordering constraint (ticket B must land before or with ticket A, never after) is
a special case of the pattern above, and it has a better fix than adding an AC. On KAN-191/192
(2026-09-11), the constraint — the frontend nullable-model fix must ship before or with the
backend DDL that starts producing nulls — was first caught living only in prose (the same defect
class as everywhere else in this section). The instinct was to add an AC asserting the order was
followed. **That would only have caught the violation at review, after the wrong-order migration
had already applied and crashed every squad screen.**

The actual fix: a Persistent State `BLOCKS` dependency (only canonical `DONE` on the blocking
ticket satisfies the edge) makes the dependent ticket **unclaimable** until the blocker is Done —
confirmed firing correctly via `queue.unclaimable_reasons` (`dependency-blocked` present on the
blocked ticket, absent on the blocker). **Prevention at claim time beats detection at review
time** for exactly the reason the claim system exists at all: an AC only ever tells you after the
fact that something already went wrong. For any future ordering constraint between two tickets,
create the dependency edge first — an AC is defense in depth on top of it, not a substitute for
it.

## A full-description resubmission re-risks the WHOLE document, not just the new text (KAN-188, 2026-09-11)

`editJiraIssue` takes the entire `description` on every call — there is no partial-patch path.
That means every edit re-runs the markdown→ADF conversion over content that has already survived
unchanged through prior reads, and content believed safe from earlier round-trips is not
exempt. On a KAN-188 edit that only touched AC1/AC2, a bold span in the untouched "## The
defect" section — `**Attacker capability: ... holds  \nauthority over an arbitrary venue.**`,
present verbatim in every earlier fetch of this ticket with no reported issue — dropped
"authority over an arbitrary venue." on this pass, leaving "...can ask whether an arbitrary user
holds**" trailing into the next sentence. Visible-shape content loss, caught by the standing
full re-read, not by assuming untouched sections were safe.

**The operating assumption has to be "every bold/italic span in the entire submitted document is
at risk on every submission," not "only the spans I just wrote."** A span that rendered fine
three edits ago is not evidence it will render fine on this edit — the conversion runs fresh
each time. Two consequences: (1) when fixing a corrupted span, do not also leave other
hard-break-crossing spans elsewhere in the same document untouched on the theory that they
"already proved safe" — they didn't prove anything, they just weren't resubmitted before now;
(2) for a ticket whose text is edited more than once across a session, each edit is a fresh
opportunity for a *pre-existing, previously-fine* span to fail, not only for newly-written text
to fail. Re-read (or diff) the *entire* returned description on every edit, including the parts
you didn't intend to change.

## Trigger refined: it is not only a hard line break — an inline code span inside the formatting span does it too (KAN-191, 2026-09-11)

Five formatting-only losses found in one `editJiraIssue` call on KAN-191, confirmed by a full
byte-for-byte diff of the submitted text against the tool's own return (not a visual scan — see
"how this was caught" below). All five: a `**bold**` or `~~strikethrough~~` span that wrapped a
backtick-quoted identifier lost its closing marker right at or just after the backtick, leaving
the identifier and everything after it unformatted for the rest of the sentence. Every instance
was purely cosmetic — **zero words dropped, zero meaning changed** — which is why this is filed
separately from the content-loss instances above rather than merged into the frequency count.

Examples, submitted → returned:
- `**...step (1) is VACUOUS for `games`, not merely unauthored.**` → bold closed after "for",
  `` `games` `` and the rest of the sentence rendered plain.
- `~~Live `games` RLS policy set~~` → strikethrough closed after "Live", the rest plain.
- `~~`unaccent` extension installed~~` → strikethrough dropped entirely, no mark at all.

**This means the trigger is not "a hard line break inside the span," full stop — it is "a span
that contains other inline markup," and a backtick-quoted code span is inline markup.** A bold or
strikethrough span that wraps a single plain word crossing a hard break failed before (the KAN-183
cases); a bold or strikethrough span that wraps a code span failed here, with no hard break
involved at all. Treat **any** `**`/`_`/`~~` span that contains a `` `...` `` inside it as a
second, independent trigger for this defect, alongside the hard-break one. The mitigation is the
same shape: keep formatting spans to plain text only, and put the code span, if one is needed,
outside the bold/strikethrough markers rather than inside them.

**How this was caught, and why a visual scan would have missed some of it:** a visual re-read of
the return caught none of these five on KAN-191 — every sentence still reads grammatically
complete, since no words were lost. They were only found by writing the exact submitted text and
the exact returned text to two files and running `diff` between them. **For any edit large enough
that a full visual re-read is impractical, diff the submitted text against the return rather than
eyeballing it** — the standing rule ("read the return back") still holds, but for a long edit the
reliable way to execute it is a mechanical diff, not a read-through, precisely because this
failure mode produces text that reads fine.

Left uncorrected on KAN-191 deliberately: these five are cosmetic only, and a further edit to fix
them carries its own re-corruption risk for no substantive gain. Worth a follow-up sweep only if
someone is already re-editing that ticket for another reason.

## Two more instances, one edit call, KAN-183 (2026-09-11 burn-down)

Same defect as the original two, same root cause (a bold span crossing a hard `  \n` line break),
caught in the same `editJiraIssue` call this time — not two separate edits. Both silently dropped
the tail of the bold span:

- `**This conditional does not authorise assuming\n  the favourable branch**` → returned as
  `**This conditional does not authorise assuming**   —` with the phrase "the favourable branch"
  gone entirely and a stray double space left where it used to sit.
- `**never\n  populated**` → returned as `**never**  ,` — "populated" dropped, comma orphaned.

Both were caught by the standing rule (re-read the return value immediately) and fixed on a
second submission with the hard breaks moved to sit **outside** every bold span rather than
inside one — the second submission came back verbatim, no corruption. Confirms the rule from the
top of this file is not paranoia: two silent drops in one call, on a ticket where the content is
purely explanatory (not an AC, not a legal instruction), still would have shipped a garbled
sentence to whoever read it next if the return value hadn't been checked. The fix is mechanical
and cheap — never let `**`/`_` wrap text that also contains a `  \n` — and it is now the second
time in one session this exact shape (bold span + hard break) has caused loss, which upgrades it
from "a thing that can happen" to "assume it will happen and write around it by default," not
just check for it after the fact.
