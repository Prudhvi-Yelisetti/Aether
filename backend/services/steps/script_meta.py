"""
Minimal AI Object Model metadata (ARCHITECTURE.md: every object carries
Identifier, Version, Owner, Trust Level, History, Metadata, Permissions)
applied to a Step's "Script" property.

Design decision: this is identity + provenance metadata FOR a Step's
implementation, not the implementation itself stored as executable data.
Storing code as a string and exec()/eval()-ing it would reintroduce exactly
the class of vulnerability Phase A removed (see code_runner.py's history).
The actual logic stays a normal, code-reviewed Python method on the Step
subclass. ScriptMeta just makes that method an identified, versioned,
audit-able object instead of anonymous code — version bumps and history
entries are written by hand when a Step's run() logic changes, since there's
no automated content-hashing/build pipeline to do it for you yet.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ScriptMeta:
    step_id: str
    version: str
    owner: str
    history: tuple[str, ...] = field(default_factory=tuple)
