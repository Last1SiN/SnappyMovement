from __future__ import annotations

import math
from typing import Any

import unrealsdk
from mods_base import Game, Mod, SliderOption, SpinnerOption, build_mod, hook
from unrealsdk import logging
from unrealsdk.hooks import Type
from unrealsdk.unreal import BoundFunction, UObject, WrappedStruct

assert Game.get_current() is Game.BL3, "SnappyMovement supports Borderlands 3 only"

PROFILE_SOFT = "Soft (8000 / 10000)"
PROFILE_NEAR = "Near Instant (30000 / 40000)"
PROFILE_INSTANT = "Instant (100000 / 120000)"
PROFILE_CUSTOM = "Custom"

PRESETS: dict[str, tuple[float, float]] = {
    PROFILE_SOFT: (8000.0, 10000.0),
    PROFILE_NEAR: (30000.0, 40000.0),
    PROFILE_INSTANT: (100000.0, 120000.0),
}

ACCEL_MIN = 1000.0
ACCEL_MAX = 150000.0
BRAKE_MIN = 1000.0
BRAKE_MAX = 180000.0

profile_option = SpinnerOption(
    "profile",
    PROFILE_NEAR,
    [PROFILE_SOFT, PROFILE_NEAR, PROFILE_INSTANT, PROFILE_CUSTOM],
    wrap_enabled=False,
    display_name="Profile",
    description=(
        "Select one of the original v0.2 profiles or Custom. "
        "Changing either slider automatically switches the profile to Custom."
    ),
)

accel_option = SliderOption(
    "max_acceleration",
    30000.0,
    ACCEL_MIN,
    ACCEL_MAX,
    500.0,
    is_integer=True,
    display_name="Max Acceleration",
    description=(
        "Controls how quickly ground movement reaches the game's normal maximum speed. "
        "Does not change MaxWalkSpeed or MaxSprintSpeed. "
        "v0.2 presets: Soft 8000, Near Instant 30000, Instant 100000."
    ),
)

brake_option = SliderOption(
    "braking_deceleration_walking",
    40000.0,
    BRAKE_MIN,
    BRAKE_MAX,
    500.0,
    is_integer=True,
    display_name="Braking Deceleration Walking",
    description=(
        "Controls how quickly walking movement stops after movement input is released. "
        "GroundFriction is not modified. "
        "v0.2 presets: Soft 10000, Near Instant 40000, Instant 120000."
    ),
)

OPTIONS = (profile_option, accel_option, brake_option)

_syncing_options = False
_patched_components: list[tuple[UObject, float, float]] = []


def _error(message: str) -> None:
    logging.error(f"[SnappyMovement] {message}")


def _path(obj: Any) -> str:
    if obj is None:
        return "<None>"
    try:
        return str(obj._path_name())
    except Exception:
        return "<unreadable-path>"


def _safe_value(
    raw: Any,
    default: float,
    minimum: float,
    maximum: float,
    label: str,
) -> float:
    try:
        value = float(raw)
    except (TypeError, ValueError):
        _error(f"{label}: invalid value {raw!r}; using {default:.0f}")
        return default

    if not math.isfinite(value):
        _error(f"{label}: non-finite value {value!r}; using {default:.0f}")
        return default

    if value < minimum:
        _error(f"{label}: {value:.0f} below slider minimum; clamped to {minimum:.0f}")
        return minimum

    if value > maximum:
        _error(f"{label}: {value:.0f} above slider maximum; clamped to {maximum:.0f}")
        return maximum

    return round(value)


def _current_values(profile: str | None = None) -> tuple[float, float]:
    selected = profile if profile is not None else str(profile_option.value)

    if selected in PRESETS:
        return PRESETS[selected]

    acceleration = _safe_value(
        accel_option.value,
        30000.0,
        ACCEL_MIN,
        ACCEL_MAX,
        "Max Acceleration",
    )
    braking = _safe_value(
        brake_option.value,
        40000.0,
        BRAKE_MIN,
        BRAKE_MAX,
        "Braking Deceleration Walking",
    )
    return acceleration, braking


def _find_local_controller() -> UObject | None:
    try:
        controllers = unrealsdk.find_all("PlayerController", exact=False)
    except Exception:
        return None

    for controller in controllers:
        try:
            if bool(controller.IsLocalController()):
                return controller
        except Exception:
            continue

    return None


def _get_current_pawn() -> UObject | None:
    controller = _find_local_controller()
    if controller is None:
        return None

    try:
        return controller.Pawn
    except Exception:
        return None


def _get_move_component(pawn: UObject) -> UObject | None:
    for attr in ("CharMoveComp", "CharacterMovement", "CharacterMovementComponent"):
        try:
            component = getattr(pawn, attr)
        except Exception:
            continue
        if component is not None:
            try:
                float(component.MaxAcceleration)
                float(component.BrakingDecelerationWalking)
                return component
            except Exception:
                continue

    for getter in ("GetCharacterMovement", "GetMovementComponent"):
        try:
            component = getattr(pawn, getter)()
        except Exception:
            continue
        if component is not None:
            try:
                float(component.MaxAcceleration)
                float(component.BrakingDecelerationWalking)
                return component
            except Exception:
                continue

    return None


def _remember_original(component: UObject) -> None:
    for existing, _old_accel, _old_brake in _patched_components:
        if existing is component:
            return

    try:
        old_accel = float(component.MaxAcceleration)
        old_brake = float(component.BrakingDecelerationWalking)
    except Exception as exc:
        _error(f"could not read original movement values from {_path(component)}: {exc}")
        return

    _patched_components.append((component, old_accel, old_brake))


def _apply_to_pawn(
    pawn: UObject | None,
    acceleration: float,
    braking: float,
    *,
    report_failure: bool = False,
) -> None:
    if pawn is None:
        return

    component = _get_move_component(pawn)
    if component is None:
        if report_failure:
            _error(f"could not locate movement component on {_path(pawn)}")
        return

    _remember_original(component)

    try:
        component.MaxAcceleration = acceleration
        component.BrakingDecelerationWalking = braking
    except Exception as exc:
        _error(f"failed to apply movement values to {_path(component)}: {exc}")


def _apply_current_values() -> None:
    acceleration, braking = _current_values()
    _apply_to_pawn(_get_current_pawn(), acceleration, braking)


def _restore_all() -> None:
    global _patched_components

    for component, old_accel, old_brake in _patched_components:
        try:
            component.MaxAcceleration = old_accel
            component.BrakingDecelerationWalking = old_brake
        except Exception:
            # Destroyed pawns/components from map changes or respawns can remain as stale wrappers.
            pass

    _patched_components = []


def _on_enable() -> None:
    _apply_current_values()


def _on_disable() -> None:
    _restore_all()


@hook("/Script/Engine.PlayerController:ClientRestart", Type.POST)
def _client_restart(
    obj: UObject,
    args: WrappedStruct,
    _ret: Any,
    _func: BoundFunction,
) -> None:
    try:
        if not bool(obj.IsLocalController()):
            return
    except Exception:
        return

    try:
        pawn = args.NewPawn
    except Exception:
        try:
            pawn = obj.Pawn
        except Exception:
            pawn = None

    acceleration, braking = _current_values()
    _apply_to_pawn(pawn, acceleration, braking, report_failure=True)


def _on_profile_change(_option: SpinnerOption, new_value: str) -> None:
    global _syncing_options

    if _syncing_options:
        return

    if new_value in PRESETS:
        acceleration, braking = PRESETS[new_value]

        _syncing_options = True
        try:
            accel_option.value = acceleration
            brake_option.value = braking
        finally:
            _syncing_options = False
    else:
        acceleration, braking = _current_values(PROFILE_CUSTOM)

    if mod.is_enabled:
        _apply_to_pawn(_get_current_pawn(), acceleration, braking)


def _on_accel_change(_option: SliderOption, new_value: float) -> None:
    global _syncing_options

    if _syncing_options:
        return

    acceleration = _safe_value(
        new_value,
        30000.0,
        ACCEL_MIN,
        ACCEL_MAX,
        "Max Acceleration",
    )
    braking = _safe_value(
        brake_option.value,
        40000.0,
        BRAKE_MIN,
        BRAKE_MAX,
        "Braking Deceleration Walking",
    )

    _syncing_options = True
    try:
        profile_option.value = PROFILE_CUSTOM
    finally:
        _syncing_options = False

    if mod.is_enabled:
        _apply_to_pawn(_get_current_pawn(), acceleration, braking)


def _on_brake_change(_option: SliderOption, new_value: float) -> None:
    global _syncing_options

    if _syncing_options:
        return

    acceleration = _safe_value(
        accel_option.value,
        30000.0,
        ACCEL_MIN,
        ACCEL_MAX,
        "Max Acceleration",
    )
    braking = _safe_value(
        new_value,
        40000.0,
        BRAKE_MIN,
        BRAKE_MAX,
        "Braking Deceleration Walking",
    )

    _syncing_options = True
    try:
        profile_option.value = PROFILE_CUSTOM
    finally:
        _syncing_options = False

    if mod.is_enabled:
        _apply_to_pawn(_get_current_pawn(), acceleration, braking)


def _sanitize_loaded_settings(mod_obj: Mod) -> None:
    global _syncing_options

    corrected = False
    profile = str(profile_option.value)

    _syncing_options = True
    try:
        if profile in PRESETS:
            expected_accel, expected_brake = PRESETS[profile]

            if float(accel_option.value) != expected_accel:
                accel_option.value = expected_accel
                corrected = True
            if float(brake_option.value) != expected_brake:
                brake_option.value = expected_brake
                corrected = True
        else:
            safe_accel = _safe_value(
                accel_option.value,
                30000.0,
                ACCEL_MIN,
                ACCEL_MAX,
                "Max Acceleration",
            )
            safe_brake = _safe_value(
                brake_option.value,
                40000.0,
                BRAKE_MIN,
                BRAKE_MAX,
                "Braking Deceleration Walking",
            )

            try:
                current_accel = float(accel_option.value)
            except (TypeError, ValueError):
                current_accel = float("nan")
            try:
                current_brake = float(brake_option.value)
            except (TypeError, ValueError):
                current_brake = float("nan")

            if not math.isfinite(current_accel) or current_accel != safe_accel:
                accel_option.value = safe_accel
                corrected = True
            if not math.isfinite(current_brake) or current_brake != safe_brake:
                brake_option.value = safe_brake
                corrected = True
    finally:
        _syncing_options = False

    if corrected:
        try:
            mod_obj.save_settings()
        except Exception as exc:
            _error(f"could not persist corrected settings: {exc}")


mod = build_mod(
    options=OPTIONS,
    on_enable=_on_enable,
    on_disable=_on_disable,
)

# build_mod() loads persisted settings before returning. Attach callbacks afterwards so loading
# old settings does not accidentally turn a saved preset into Custom.
profile_option.set_on_change(_on_profile_change, anytime=True, while_enabled=False)
accel_option.set_on_change(_on_accel_change, anytime=True, while_enabled=False)
brake_option.set_on_change(_on_brake_change, anytime=True, while_enabled=False)

_sanitize_loaded_settings(mod)
