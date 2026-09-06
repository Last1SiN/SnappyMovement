# SnappyMovement

SnappyMovement makes Borderlands 3 ground movement more responsive by reducing acceleration and stopping inertia without increasing the game's normal movement speed.

The mod changes only the local player's `MaxAcceleration` and `BrakingDecelerationWalking`. It does not intentionally change maximum walk speed, maximum sprint speed, `GroundFriction`, jump settings, air control, or slide speed.

## Features

- Reduces the sluggish feeling when starting ground movement.
- Reduces stopping inertia after movement input is released.
- Keeps the game's normal maximum walk and sprint speeds unchanged.
- Does not modify `GroundFriction`.
- Includes three tuning profiles plus manual control.
- Applies option changes immediately while the mod is enabled.
- Automatically reapplies the selected settings to a new local-player pawn after respawn/map transitions.
- Restores the movement-component values captured before SnappyMovement changed them when the mod is disabled.
- Normal operation does not add gameplay log spam; only errors are logged.

## Profiles

### Soft

- `MaxAcceleration`: `8000`
- `BrakingDecelerationWalking`: `10000`

A lighter response increase while retaining more of the original transition feel.

### Near Instant

- `MaxAcceleration`: `30000`
- `BrakingDecelerationWalking`: `40000`

The default profile and the original recommended v0.2 tuning.

### Instant

- `MaxAcceleration`: `100000`
- `BrakingDecelerationWalking`: `120000`

The most aggressive preset.

### Custom

Use the two sliders directly.

Moving either slider manually automatically switches the profile to **Custom**.

## Configuration

Available through **MODS -> SnappyMovement -> Options**.

- **Profile:** Soft / Near Instant / Instant / Custom
- **Max Acceleration:** `1000-150000`, step `500`
- **Braking Deceleration Walking:** `1000-180000`, step `500`

Selecting one of the three presets writes its values into both sliders.

SnappyMovement does **not** modify `MaxWalkSpeed`, `MaxSprintSpeed`, or `GroundFriction`.

## Requirements

- Borderlands 3.
- [BL3 PythonSDK / Oak Mod Manager v1.11+ — latest stable release](https://github.com/bl-sdk/oak-mod-manager/releases/latest).
- [Official BL3 SDK installation guide](https://bl-sdk.github.io/oak-mod-db/).

Oak Mod Manager v1.11 includes Mods Base 1.12, BL3 Mod Menu 1.8, Console Mod Menu 1.6, Keybinds 2.6, pyunrealsdk 1.10.0, UI Utils 1.4, and unrealsdk 3.2.0. These components normally do not need to be downloaded separately when using that release or a newer compatible Oak release.

## Installation

1. **Fully close Borderlands 3.**
2. If BL3 PythonSDK / Oak is not installed or needs updating, open the [latest stable Oak Mod Manager release](https://github.com/bl-sdk/oak-mod-manager/releases/latest).
3. Under **Assets**, download **`bl3-sdk.zip`** — not either `Source code` archive.
4. Locate the Borderlands 3 game folder. In Steam: **Library -> right-click Borderlands 3 -> Manage -> Browse local files**.
5. Extract the contents of `bl3-sdk.zip` directly into the Borderlands 3 game folder, allowing folders/files to merge and accepting overwrite prompts. See the [official BL3 SDK installation guide](https://bl-sdk.github.io/oak-mod-db/) for the complete procedure and Proton/Linux notes.
6. Start Borderlands 3 once and verify that the **MODS** entry appears on the main menu.
7. Download the latest SnappyMovement release.
8. Fully close the game and copy `SnappyMovement.sdkmod` **without extracting it** to:

   `Borderlands 3\sdk_mods\`

9. Remove any older `No_Movement_Inertia_*.bl3hotfix` builds from OpenHotfixLoader's `ohl-mods` folder so they cannot apply the same movement properties at the same time.
10. Start/restart Borderlands 3, open **MODS -> SnappyMovement**, enable the mod, and open **Options** to select a profile or tune the sliders.

To update SnappyMovement, replace the existing `SnappyMovement.sdkmod` with the newer file and restart the game.

## Compatibility and license

- Character scope: applies to the local player's runtime movement component.
- Co-op support: **Unknown** — not formally validated for this release.
- The mod does not intentionally alter `GroundFriction`, maximum movement speed, jump settings, air control, or slide speed.
- License: **GPL-3.0**

## Credits

- **Mod creator / code:** Sol (ChatGPT, GPT-5.6 Sol)
- **QA / maintainer:** [Last1SiN](https://github.com/Last1SiN)
- **BL3 PythonSDK / Oak Mod Manager:** created by [apple1417](https://github.com/apple1417), with contributions from the [BL-SDK](https://github.com/bl-sdk) project and contributors.
