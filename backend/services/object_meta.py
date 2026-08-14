"""
The AI Object Model's identity/provenance metadata (ARCHITECTURE.md:
every object carries Identifier, Version, Owner, Trust Level, History,
Permissions) -- shared across Step, Tool, and Skill as of STATUS.md
item 24.

Originally built Step-only, as ScriptMeta (services/steps/script_meta.py,
Phase D), with 4 of the 6 target fields (identifier, version, owner,
history) -- trust_level and permissions were never added, and Tool/Skill
never got equivalent metadata at all (ARCHITECTURE.md's Tool Service gap
table: "Tools still lack the AI Object Model's full metadata... that
Steps have via ScriptMeta" -- itself an overstatement, since Steps didn't
have the full set either). This closes both gaps at once: ScriptMeta is
now a thin re-export of this class (see script_meta.py), and Tool/Skill
both carry their own `meta: ObjectMeta` class attribute the same way
Step already exposed `script`.

Fields:
  identifier: a stable, namespaced ID -- "tool.code", "skill.research_topic",
    "step.summarize" -- not the display `name` (which can change more
    freely). This is what a future Governance Service would reference to
    track one specific object across renames.
  version: semver-ish string, bumped by hand when behavior changes -- see
    `history` below for what actually triggers a bump. No automated
    content-hashing/build pipeline generates these.
  owner: who's accountable for this object. Every current one is
    "prudhvi" (single-developer project) -- this field exists for when
    that's no longer true, not because it's doing real access-control
    work today.
  trust_level: how much latitude this object gets without human review.
    Three values, used deliberately as a small closed set rather than an
    open-ended free-text field:
      "core" -- built-in, first-party, code-reviewed at write time.
        Every object in this codebase today is "core".
      "verified" -- reviewed and tested but not original first-party
        code (e.g. a future community-contributed Skill that's been
        vetted). Not yet used by any real object.
      "experimental" -- unreviewed or newly added; should not run
        unattended, should surface a warning in the UI if ever
        selected. Not yet used by any real object.
    Not a real enum class -- matches this codebase's existing preference
    (see storage/project_store.py's memory_type) for plain validated
    strings over Python Enums for a small, stable value set. Nothing
    currently reads or enforces this field (the Governance Service that
    would is itself unbuilt, ARCHITECTURE.md) -- it's provenance data
    waiting for a consumer, same as `experiences`/`step_metrics` were
    before Validation/Decision existed to use them.
  history: tuple of human-written one-line changelog entries, oldest
    first. For every object below, these are REAL past events mined
    from STATUS.md and this codebase's own docstrings/comments at the
    time this file was written -- not generic "1.0.0: initial version"
    placeholders. Where a Tool/Skill predates this metadata (all of
    them), the first entry describes when and why it was actually
    built, not "1.0.0" as an empty formality.
  permissions: tuple of what this object can actually DO or ACCESS in
    the real system -- "filesystem:read", "filesystem:write",
    "code:execute", "network:outbound". Not a user-permission system
    (this is single-user local software) but a genuine, code-derived
    record of blast radius. An object with permissions=() genuinely
    touches nothing outside its own input/output.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ObjectMeta:
    identifier: str
    version: str
    owner: str
    trust_level: str = "core"
    history: tuple[str, ...] = field(default_factory=tuple)
    permissions: tuple[str, ...] = field(default_factory=tuple)
