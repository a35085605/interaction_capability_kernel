# Execution interaction capabilities

`execution` is a platform-neutral interaction capability and a peer of `capture`. It owns
interaction command contracts, not platform-native administration or lifecycle semantics.
Pointer/keyboard/text/navigation commands live under `execution.input`; touch-specific
commands live under `execution.touch`.

```text
interaction capabilities

capture                         execution
(read-only acquisition)         (interaction commands)
                                   ├── input
                                   └── touch
```

Platform domains may implement these contracts through native adapters, but a platform-native
operation does not belong in `execution` merely because it causes an external effect. If the
operation requires native nouns such as `AndroidPackageName`, `AndroidUserId`, `WindowId`, or
`AdbServerId` for its semantics, the owning platform domain should normally own that command.

Before an execution command is selected, external composition may use independently acquired
native facts and `ApplicationPresentationMapping`. Platform-domain preparation or recovery
remains outside `execution`. For example, a caller may inspect `AdbTransportFeatures` before
selecting a shell-v2-backed Android execution adapter; the adapter does not turn backend
selection into hidden retry/preparation policy.

A caller-side rejection or geometry-mapping failure is not a native attempt. Once an adapter
crosses its native boundary, it returns `NativeAttemptResult`. A timeout is reported as
`NativeAttemptStatus.TIMED_OUT`; when the client cannot prove which native completion
boundary was reached, `completion_scope` remains `None`.

Native-attempt success is intentionally narrower than application-level success. The intended
application effect can be evaluated later from fresh query or capture evidence.

## Android ADB interaction input

`android.adb.adapters` provides display-local single-pointer tap, long press, swipe, and
drag-and-drop plus key press, key combination, limited portable text, and Back. Touch and
key/text adapters accept an explicit `AndroidDisplayId` and issue only fixed typed AOSP
`input` command shapes through the private shell-v2 mechanism. They do not expose an
arbitrary shell string executor.

One adapter call represents one native attempt. The key adapter therefore supports one key
event (`repeat=1`, zero interval); repeated/cadenced key semantics are rejected rather than
collapsed into an aggregate `NativeAttemptResult`. The text adapter intentionally supports
only a conservative portable ASCII subset that can be represented by AOSP virtual-keyboard
`input text` semantics. It does not promise arbitrary Unicode; IME, clipboard, or
instrumentation mechanisms belong in separate adapters/extensions. Multi-touch and
continuous pointer streams also remain outside this ADB-shell slice.

Android activity launch and package force-stop are deliberately **not** execution contracts.
They are Android-native atomic commands under `android.command` with ADB implementations under
`android.adb.adapters.command`.
