# Todo

Ideas for **new behavior** not yet promoted to a feature doc — per
`docs/DOCS-DRIVEN-DEVELOPMENT.md`, a one-liner each. Once an idea is substantial
enough to design, it becomes a `docs/features/<PREFIX>-NNNN-slug.md` (`Status:
Planned`) and its line here is deleted; see `docs/FRD.md` for the checkbox that then
tracks it. Defects, tech debt, and chores on shipped behavior go in `docs/BUGS.md`
instead.

**Extension to the DDD template:** unlike DDD's bare-bullet template, entries here
keep a stable `#TODO-NNNN` ID — `docs/ROADMAP.md` cites these IDs directly (matching
DDD's own `ROADMAP.md` template, which cites `#TODO-NNNN`), so an idea can be ordered
against `docs/BUGS.md` items before it's substantial enough to promote. IDs are never
reused or renumbered; deletions (on promotion or on close) leave gaps. Next free ID:
**TODO-0094**.

Each entry may end with a `[P#/D#]` marker once triaged:

```
Priority:   P1 = high     P2 = medium   P3 = low
Difficulty: D1 = trivial  D2 = small    D3 = medium   D4 = large
```

## Unsorted

Not investigated enough to file properly: no verified root cause, no priority, no
difficulty. Move an entry into a real section below once it has all three, or decide
it and delete it.

- #TODO-0010 separate prod builds and local debug ones (?) -- no stated problem or
  acceptance criterion yet
- #TODO-0013 #2.0 split management system and hyprland repo content, make automations
  repo a submodule of content repo (?) -- a repo-topology decision, not a task, until
  someone rules on it

## Ideas

- #TODO-0011 add `make fmt` after scaffolding [P3/D1]
