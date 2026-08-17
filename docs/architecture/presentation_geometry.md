# Presentation geometry and historical evidence

Generic geometry, application-presentation correspondence, and platform-owned spatial meaning
are separate concerns. The kernel does not maintain a global coordinate-space registry.

## Application presentations and correspondence

`ApplicationPresentation` pairs a correspondence anchor with a full rectangular application
presentation. `ApplicationPresentationCorrespondenceAnchor` is a consumer assertion that
full presentations carrying the same anchor may be related geometrically.
`ApplicationPresentationMapping` derives an invertible axis-aligned transform between their
rectangles.

`ApplicationPresentationRaster` is a durable, zero-based raster for one anchored application
presentation. It preserves source-capture identity and the correspondence anchor without
retaining the historical capture placement.

## Historical evidence and fresh native facts

Historical capture geometry is evidence from acquisition time. Capture does not attach that
evidence to an `InteractionTargetId`, Window, ADB transport, Android display, or execution
mechanism.

When external composition decides that historical evidence still applies, raster-local
geometry can be mapped into a fresh platform-owned presentation:

```text
historical capture                atomic native query
      │                                  │
      │ locate + materialize             ▼
      ▼                            fresh native facts
application raster                       │
      │                                  │
      └──────── external correspondence ─┘
                         │
                         ▼
             fresh application presentation
                         │
                  presentation mapping
                         ▼
              fresh application geometry
```

A command adapter may revalidate mutable native preconditions required by its own mechanism
immediately before crossing the native boundary. `NativeAttemptResult` reports native
completion only; application effects are evaluated later from fresh query or capture evidence.

## Native placement

`LocalPlacement` handles the separate case where a platform-owned local surface must be mapped
into its platform-owned root because a native API requires root coordinates.

```text
application-raster geometry
        │ presentation mapping
        ▼
fresh application geometry
        │ optional local placement
        ▼
platform-owned native geometry
```

Geometry helpers own the math. Native domains own the semantic meaning of their surfaces and
coordinates.

## Layout scaling stability

`app.layout.LayoutScalingStability` describes how application-internal spatial layout is
expected to behave when an application re-renders for a changed rendering extent:

- `UNSTABLE` — no linear layout-preservation assumption is declared;
- `ISOTROPIC` — uniform render-extent scaling is expected to preserve layout;
- `ANISOTROPIC` — independent horizontal and vertical render-extent scaling is expected to
  preserve layout.

This metadata is distinct from presentation geometry. A presentation mapping can derive
geometry between equally anchored rectangles; layout-stability metadata helps consumer policy
decide whether historical application-local findings remain meaningful after a re-render.

```text
historical finding
      │
      ├── correspondence still applicable? ── no ─► reacquire
      │ yes
      ▼
application re-rendered at a new extent?
      │
      ├── no ─► map geometry
      │
      └── yes ─► apply layout-stability and application policy
```

The enum does not construct transforms, track render history, or prove semantic continuity.
Those decisions remain application-specific.
