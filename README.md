# SnappyMovement

[English](README.md) | [Русский](README_RU.md)

SnappyMovement makes Borderlands 3 movement feel less floaty and more immediate.

You get up to speed faster, stop faster when you let go of movement, and keep the game's normal top walking and sprinting speeds. It is meant to change how movement responds, not make your character run faster.

Three presets are included, plus a Custom mode if you want to tune it yourself.

## Features

- Faster response when you start moving.
- Less sliding after you release movement input.
- Does not increase normal walk or sprint top speed.
- Three ready-made profiles: Soft, Near Instant and Instant.
- Custom mode with separate acceleration and braking sliders.
- Changes apply immediately while the mod is enabled.
- Settings are reapplied after respawn and map changes.
- Original movement values are restored when the mod is disabled.

## Profiles

### Soft

- `MaxAcceleration`: `8000`
- `BrakingDecelerationWalking`: `10000`

A lighter response increase while retaining more of the original transition feel.

### Near Instant

- `MaxAcceleration`: `30000`
- `BrakingDecelerationWalking`: `40000`

The default profile.

### Instant

- `MaxAcceleration`: `100000`
- `BrakingDecelerationWalking`: `120000`

The most aggressive preset.

### Custom

Use the two sliders directly. Moving either slider manually switches the profile to **Custom**.

## Configuration

Available through **MODS -> SnappyMovement -> Options**.

- **Profile:** Soft / Near Instant / Instant / Custom
- **Max Acceleration:** `1000-150000`, step `500`
- **Braking Deceleration Walking:** `1000-180000`, step `500`

## Requirements

- Borderlands 3
- [BL3 PythonSDK / Oak Mod Manager](https://github.com/bl-sdk/oak-mod-manager/releases/latest)

Use the [official BL3 SDK / Oak installation guide](https://bl-sdk.github.io/oak-mod-db/) for SDK installation and updates.

## Installing the mod

1. Install or update BL3 PythonSDK / Oak using the official guide above.
2. Download `SnappyMovement.sdkmod` from [GitHub Releases](https://github.com/Last1SiN/SnappyMovement/releases/latest).
3. With Borderlands 3 closed, copy the `.sdkmod` file intact to `Borderlands 3\sdk_mods\`. Do not extract the `.sdkmod` itself.
4. Start the game, open **MODS -> SnappyMovement**, enable the mod and choose a profile or tune the sliders under **Options**.

To update SnappyMovement, replace the existing `.sdkmod` with the newer file and restart the game.

## Compatibility and license

- Character scope: local player's runtime movement component.
- Co-op support: **Unknown** — behavior with the mod installed only on a client while the host does not have it has not yet been validated.
- The mod does not intentionally alter maximum movement speed, `GroundFriction`, jump settings, air control or slide speed.
- License: **GNU GPLv3 with [Section 7 additional provenance terms](ADDITIONAL_TERMS.md)**

## Credits

**Development:** Sol / GPT-5.6 Sol  
**Design, testing & QA:** Last1SiN

**BL3 PythonSDK / Oak Mod Manager:** created by [apple1417](https://github.com/apple1417), with contributions from the [BL-SDK](https://github.com/bl-sdk) project and contributors.
