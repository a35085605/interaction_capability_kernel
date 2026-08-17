# External extensions

Extensions are maintained outside this repository. A consuming application installs the
packages it needs and wires them explicitly against public kernel contracts.

```text
consumer composition
        │
        ├──────────────► external extensions
        │                         │
        │                         ▼
        └──────────────► public interaction contracts
                          ├── interaction_target
                          ├── capture
                          ├── windows / adb
                          ├── app.presentation / app.raster
                          ├── execution
                          └── imaging / geometry
```

Core packages must remain usable when every extension is absent.

## Detector and perception extensions

A detector turns captured or derived signals into application-relevant findings. A
detector package may own input preparation, ROI/search policy, OCR, template matching,
learned-model inference, rules, confidence, and provenance.

The kernel intentionally does not define one universal detector input, finding, evidence
model, registry, or lifecycle. Detector packages may depend on public contracts such as
`capture`, `app.raster`, `imaging`, and `geometry`. External composition decides how
findings map to application semantics and whether historical findings still apply before
execution.

## Native mechanism extensions

Windows and ADB are built-in native domains. Within Windows, desktop-global and Window
facts remain separately modeled. An extension that introduces a new native mechanism
should own the real platform nouns it needs: identities or bindings, time-scoped state,
atomic inspectors, atomic commands, domain-local orchestration, spatial surfaces,
and execution adapters.

For example a WebDriver extension may define its own session identity and inspector:

```python
from dataclasses import dataclass
from typing import Protocol

@dataclass(frozen=True, slots=True, order=True)
class WebDriverSessionId:
    value: str

@dataclass(frozen=True, slots=True)
class WebDriverSessionState:
    session_id: WebDriverSessionId
    current_url: str | None = None

class WebDriverSessionInspector(Protocol):
    def inspect(
        self,
        session_id: WebDriverSessionId,
    ) -> WebDriverSessionState | None:
        ...
```

The extension owns those native semantics; consumer composition wires the extension to the
public interaction contracts it implements or consumes.

## Composition rules

1. Activation is explicit in the consuming application's composition root.
2. Dependencies use public kernel contracts.
3. Core packages never import or dynamically discover an extension.
4. Removing or replacing an extension requires no core changes.
5. Extension-to-extension dependencies are explicit.
6. Package-version compatibility is declared by the extension.

Extensions should model real platform nouns rather than inventing shared abstractions only
because multiple native APIs happen to accept similar primitive values.
