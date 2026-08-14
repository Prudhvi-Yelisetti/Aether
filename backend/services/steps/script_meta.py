"""
ScriptMeta is now a re-export of the shared services.object_meta.ObjectMeta
-- see that module's docstring for the full AI Object Model rationale
(STATUS.md item 24). Kept as a separate importable name for backward
compatibility with every existing Step subclass's
`from services.steps.script_meta import ScriptMeta` -- no need to touch
those import lines, only the `step_id=` keyword argument at each Step's
`script = ScriptMeta(...)` call site, renamed to `identifier=` to match
the shared field name Tool/Skill's `meta: ObjectMeta` also uses.
"""

from services.object_meta import ObjectMeta as ScriptMeta

__all__ = ["ScriptMeta"]
