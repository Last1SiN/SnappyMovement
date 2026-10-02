# SnappyMovement

[English](README.md) | [Русский](README_RU.md)

SnappyMovement makes Borderlands 3 movement feel less floaty and more immediate while keeping the game's normal walk and sprint top speeds.

Its core acceleration/braking profiles remain intact, with optional movement helpers layered on top. All optional features are off by default unless noted.

## Features

- Faster ground acceleration and braking without changing normal walk or sprint top speed.
- Three ready-made profiles: Soft, Near Instant and Instant, plus Custom sliders.
- **Air Control Override:** raises airborne steering strength above the game's normal `0.6`. The effect becomes subtle when Max Acceleration is already very high.
- **Auto Sprint:** keeps the game's native sprint intent armed.
- **Auto Sprint Walk Override:** Disabled, Hold Sprint Input to Walk, or Toggle Sprint Input to Walk.
- **Sprint in All Directions:** raises the native sprint-angle limit to 180 degrees; sprint speed itself is not changed.
- **Remember Sprint:** restores sprint intent after jump/slide chains when Auto Sprint is off.
- **Crouch Landing Slide:** Off, Slide on Crouch Hold, or Slide on Crouch Tap.
- Runtime values are reapplied after respawn/map transitions and restored when the mod is disabled.

## Profiles

### Soft
- `MaxAcceleration`: `8000`
- `BrakingDecelerationWalking`: `10000`

### Near Instant
- `MaxAcceleration`: `30000`
- `BrakingDecelerationWalking`: `40000`

Default profile.

### Instant
- `MaxAcceleration`: `100000`
- `BrakingDecelerationWalking`: `120000`

### Custom
Adjust the acceleration/braking sliders directly. Changing either slider switches the profile to **Custom**.

## Configuration

Available through **MODS -> SnappyMovement -> Options**.

- **Profile:** Soft / Near Instant / Instant / Custom
- **Max Acceleration:** `1000-150000`, step `500`
- **Braking Deceleration Walking:** `1000-180000`, step `500`
- **Air Control Override:** Off / On
- **Air Control:** `0.6-20.0`, step `0.1`
- **Remember Sprint:** Off / On
- **Auto Sprint:** Off / On
- **Auto Sprint Walk Override:** Disabled / Hold Sprint Input to Walk / Toggle Sprint Input to Walk
- **Sprint in All Directions:** Off / On
- **Crouch Landing Slide:** Off / Slide on Crouch Hold / Slide on Crouch Tap

## Requirements

- Borderlands 3
- [BL3 PythonSDK / Oak Mod Manager](https://github.com/bl-sdk/oak-mod-manager/releases/latest)

Use the [official BL3 SDK / Oak installation guide](https://bl-sdk.github.io/oak-mod-db/) for SDK installation and updates.

## Installing the mod

1. Install or update BL3 PythonSDK / Oak using the official guide above.
2. Download `SnappyMovement.sdkmod` from [GitHub Releases](https://github.com/Last1SiN/SnappyMovement/releases/latest).
3. With Borderlands 3 closed, copy the `.sdkmod` file intact to `Borderlands 3\sdk_mods\`. Do not extract it.
4. Start the game, open **MODS -> SnappyMovement**, enable the mod and configure it under **Options**.

To update SnappyMovement, replace the existing `.sdkmod` and restart the game.

## Compatibility and behavior

- Scope: the local player's runtime movement component and native sprint/crouch intent.
- Co-op support: **Unknown** — client-only behavior against an unmodded host has not been validated.
- The mod does **not** write `Velocity`, `MaxWalkSpeed`, `MaxSprintSpeed`, `GroundFriction`, jump height/gravity, or slide speed.
- Air Control Override changes `AirControl` only when enabled.
- Sprint in All Directions changes `MaxSprintAngle` only when enabled.
- License: **GNU GPLv3 with [Section 7 additional provenance terms](ADDITIONAL_TERMS.md)**.

## Credits

**Development:** Sol / GPT-5.6 Sol  
**Design, testing & QA:** Last1SiN

**BL3 PythonSDK / Oak Mod Manager:** created by [apple1417](https://github.com/apple1417), with contributions from the [BL-SDK](https://github.com/bl-sdk) project and contributors.
