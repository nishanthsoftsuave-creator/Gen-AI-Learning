# Top-3 known weaknesses

Written **2026-10-30**, before the demo and before any reviewer saw the system. Not backdated: the brief asks for Wednesday and this was written on 30 October. Each has a number.

1. **The judge is not trustworthy enough to gate anything.** Agreement with my drafted labels is **21/28 = 75%** (gate: 85%). It is also the same 20B model that wrote the answers. Four of its seven misses were my pipeline bug (it never saw the revision register; fixed, unmeasured). Three were it misreading evidence. Consequence: faithfulness claims about wording (not figures) rest on this judge. The pass rate does not; assertions decide.

2. **Citations point at everything retrieved, not at what the answer used.** G07's answer rests on chunk_56 and chunk_57; its trace lists 5 citations (chunks 57, 56, 51, 60, 11). So at least 3 of 5 do not support the claim. In an HR setting a citation that does not support the sentence next to it is worse than none. Citation precision is not measured anywhere in this suite.

3. **The group fix is a patch on one chunk, and it leaks in the other direction.** The leading-span trim protects non-technical callers (bleed 8/8 → 0/8), but a technical caller still receives the non-technical rule's opening line: **10/10** probe queries. The prompt tells the model to answer only for the technical team, and nothing in code enforces it. It works because there is one boundary chunk in one document; a different handbook will have different boundaries. Real fix is group-tagged sub-chunks, which means re-chunking, which the capstone brief says not to do this week.

## Also known, smaller

- Refusals can happen without searching (N03: zero tool calls, right words).
- The model sometimes leaks template text into an answer (R03's raw answer contained `【assistant to=get_handbook_revisions<|channel|>commentary】`).
- One run per case: no variance estimate.
- Group is self-declared; nothing authenticates the caller.
- Citations are `file://` links to a local PDF, not hosted URLs.
