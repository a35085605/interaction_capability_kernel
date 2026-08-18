# Native entities, bindings, query contracts, and spatial surfaces

Native identity, runtime binding, and spatial geometry have separate owners. Platform
packages define concrete nouns and query capabilities; these terms do not imply shared
base classes or a cross-platform hierarchy.

## Ownership

| Concept | Model | Atomic query contract |
| --- | --- | --- |
| Desktop environment facts | `DesktopState` | `DesktopInspector` |
| Windows Window | `WindowState` + `WindowId` | `WindowInspector` |
| ADB server status payload | `AdbServerStatus` | `AdbServerStatusReader` |
| ADB transport inventory | `AdbDevicesSnapshot` + `AdbTrackedDevice` | `AdbDevicesSnapshotReader` / derived `AdbTrackedDeviceLookup` |
| ADB selected-transport features | `AdbTransportFeatures` | `AdbTransportFeaturesReader` |
| Android boot state | `AndroidBootState` | `AdbBootStateInspector` |
| Android build/version facts | `AndroidBuildInfo` | `AdbBuildInfoInspector` |
| Android logical display facts | `AndroidDisplaysSnapshot` + `AndroidDisplayState` + `AndroidDisplayId` | `AdbDisplaysInspector` / `AdbDisplayInspector` |
| Android physical capture displays | `AndroidPhysicalDisplaysSnapshot` + `AndroidPhysicalDisplayState` + `AndroidPhysicalDisplayId` | `AdbPhysicalDisplaysInspector` |
| Android current user / user profiles | `AndroidUserId` + `AndroidUsersSnapshot` | `AdbCurrentUserInspector` / `AdbUsersInspector` |
| Android user state | `AndroidUserState` + `AndroidUserId` | `AdbUserStateInspector` |
| Android package state | `AndroidPackageState` + `AndroidPackageName` | `AdbPackageStateInspector` |
| Android launcher resolution | `AndroidComponentName` | `AdbLauncherActivityInspector` |
| Android resumed activities | `AndroidResumedActivitiesSnapshot` + `AndroidResumedActivity` + `AndroidComponentName` | `AdbResumedActivitiesInspector` |
| Android WindowManager windows | `AndroidWindowsSnapshot` + `AndroidWindowState` + `AndroidWindowId` | `AdbWindowsInspector` / `AdbWindowInspector` |
| Android display occlusions | `AndroidDisplayOcclusionsSnapshot` | `AdbDisplayOcclusionsInspector` |
| Android power state | `AndroidPowerState` | `AdbPowerStateInspector` |
| Android keyguard state | `AndroidKeyguardState` | `AdbKeyguardStateInspector` |
| Desktop virtual screen | `DesktopVirtualScreenSurface` | via `DesktopInspector` |
| Window client area | `WindowClientSurface` | via `WindowInspector` |
| Android logical display surface | `AndroidDisplaySurface` | via `AndroidDisplayState.surface` |

ADB host facts follow AOSP host-protocol vocabulary. `AdbTrackedDevice` is one wire-aligned
observation row in the ADB server's transport inventory, not a separate entity with its own
identity, lifecycle, or commands. `AdbTrackedDevice.transport_id` is an `AdbTransportId` for
non-zero native IDs; the protobuf default remains integer zero. A non-zero transport ID is a
server-local runtime identity, not a durable configuration key. A row with transport ID zero
does not establish stable native identity. The observation layer therefore publishes complete
inventory snapshots rather than row lifecycle events. Different non-zero transport IDs denote
different runtime transport instances; a serial-selected binding may still re-resolve the same
serial to a different current transport from fresh inventory without treating those runtime IDs
as one continuous transport identity.

`AdbDeviceSerial`, `AdbTransportId`, `AdbTransportBySerial`, and `AdbTransportById` live under
`adb.transport` and provide deterministic native transport selection. Serial is the persistent
native selection key used by configured transport bindings. Serial-selected bindings are
re-resolved from fresh inventory as current facts change. `AdbTransportId` is the native
server-local runtime identity: it may be derived from fresh inventory and used when a caller
explicitly wants exact runtime-transport selection, but it is not a durable configuration key.
`AdbTransportFeatures` preserves the transport's advertised feature names as an open set; it is
not a kernel-defined closed capability enum. `AdbServerEndpoint` is the native ADB server
identity used by ADB queries, commands, observation, and orchestration. Caller-owned logical
server ids and the mapping from those ids to endpoints remain outside the ADB domain.

Android framework/runtime facts are owned by the `android` domain. `AndroidDisplayId` is a
logical framework display identity. `AndroidPhysicalDisplayId` is the SurfaceFlinger physical
display identity used by deterministic screencap. They are deliberately different types.
`AndroidDisplayState.physical_display_id` is populated only when inspected native data exposes
an explicit local-display relation; consumers must not equate the numeric values implicitly.
Display rotation remains normalized from `Surface.ROTATION_*` quarter-turn codes to clockwise
degrees.

`AndroidUserId`, `AndroidPackageName`, and `AndroidComponentName` are native Android identities
used by user/package/activity facts and typed commands. Build/version facts remain separate
from mechanism-specific capability policy. Package installation, enabled setting, hidden, and
suspended state are per-user; launcher activity resolution is queried separately. WindowManager
window bounds/focus/surface visibility and status/navigation/cutout/IME occlusions are native
facts, not an inferred application presentation. Resumed activity facts are scoped to user,
logical display, and task rather than claiming one device-global foreground activity. Boot,
user phase, power wakefulness, and keyguard visibility remain independent facts; none expands
the meaning of another.

## Query boundaries

A native query contract only asserts facts its own domain can obtain. For example:

- Desktop may identify the foreground `WindowId` without owning detailed `WindowState`;
- Window may report visibility/minimized/client geometry without asserting Desktop foreground ownership;
- ADB host readers may report server status, transport inventory, and selected-transport feature facts without aggregating Android runtime state;
- the derived `AdbTrackedDeviceLookup` finds a row from a fresh complete inventory snapshot rather than inventing a separate native ADB row service;
- Android ADB inspectors independently acquire build, boot, display, user/profile, package,
  launcher/activity, WindowManager geometry/insets, power, and keyguard facts without aggregating them into a cross-domain runtime state;
- no native query decides whether a caller-defined logical interaction target exists.

Cross-domain relations such as "this Window hosts this Android device" are external
composition, not native-domain state.

## Surface semantics

Spatial vocabulary is grouped by its owning native surface semantics. Within the Windows
domain, `DesktopVirtualScreenSurface` pairs with `ScreenPoint` and `WindowClientSurface` pairs
with `WindowClientPoint`. `AndroidDisplaySurface` pairs with `AndroidDisplayPoint`. A
`WindowClientSurface` may additionally carry placement in the desktop virtual-screen root.
`AndroidDisplayState` remains a time-scoped native fact and exposes its current
`AndroidDisplaySurface`. Physical display identity used by screencap is capture selection,
not a substitute logical coordinate surface.

Android display-specific presentation composition lives under `android.presentation`; it
interprets an application presentation inside an `AndroidDisplaySurface` without making ADB
the owner of that presentation vocabulary. Application presentation correspondence remains
separate from native surface placement. `ApplicationPresentationMapping` maps between
corresponding application presentations, while `LocalPlacement` maps a subordinate native
surface into its platform root when required.

## Freshness

Identity does not freeze mutable state. Window placement, display geometry, ADB transport
inventory snapshots, transport identifiers/features, user/package/activity state, power, and
keyguard state are time-scoped facts and should be queried or revalidated where current values
are required.
