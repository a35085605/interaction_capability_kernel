# Capture backends

`FrameCaptureBackend.acquire()` is a read-only visual-acquisition attempt and returns
either `AcquiredFrame` or `CaptureUnavailable`. `CaptureBackendProfile` identifies the
backend but does not declare cross-domain prerequisites.

```text
CaptureBackendProfile
        │ backend identity
        ▼
FrameCaptureBackend.acquire()
        │
   ┌────┴────────────┐
   ▼                 ▼
AcquiredFrame   CaptureUnavailable
```

## Unavailability

Expected acquisition failures use capture-owned reasons:

- `SOURCE_UNAVAILABLE`;
- `PERMISSION_DENIED`;
- `TRANSIENT_FAILURE`.

A WGC adapter, ADB screencap adapter, desktop capture adapter, or external backend may
consume explicitly selected native identities or report backend-specific diagnostics.
`capture` owns acquisition outcomes; native preparation and cross-domain availability
policy remain external composition.

## Materialization

A successful acquisition fixes the frame identity and immutable pixel semantics.
`BackendFrameSource` preserves that result without forcing an independent full-frame copy.
Consumers can call `materialize_captured_frame()` when they need independently owned,
contiguous storage.

For application-focused workflows, `extract_application_presentation_raster()` can locate
and materialize only the selected application region as an
`ApplicationPresentationRaster`.

Deferred materialization copies pixels already acquired for the frame; it never performs a
new acquisition under an existing `FrameObservationRef`.

## Android ADB screencap

`capture.adapters.android_adb.AdbScreencapBackend` is a concrete read-only backend that
uses a typed ADB transport selector and a required `AndroidPhysicalDisplayId` to acquire
PNG bytes with the fixed `screencap -p -d <physical-id>` command through private raw
`exec`. It does not accept `AndroidDisplayId`: framework logical IDs and SurfaceFlinger
physical capture IDs are distinct native identities. Each acquired frame carries a platform-neutral
`CaptureSourceId`. The adapter additionally exposes an `AndroidAdbCaptureSource` descriptor that
relates that opaque source identity to the selected physical display and, only when supplied from
independently observed native evidence, an optional logical display. Generic `FrameInfo` does not
contain Android-specific fields.

`AdbPhysicalDisplaysInspector` discovers current physical capture identities. When a
logical `DisplayInfo` explicitly reports a local physical relation,
`AndroidDisplayState.physical_display_id` preserves that relation for external composition;
the kernel never substitutes a logical ID for a physical ID merely because the integers
happen to match.

Transport-selection failure maps to `SOURCE_UNAVAILABLE`; other ADB acquisition or decode
failures stay capture-owned `PERMISSION_DENIED` / `TRANSIENT_FAILURE` results. The backend
does not prepare transports, retry, reconnect, or infer that capture success means an
application-level effect succeeded.
