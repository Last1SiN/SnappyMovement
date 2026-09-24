from __future__ import annotations

import math
from typing import Any

import unrealsdk
from mods_base import MODS_DIR, Game, Mod, SliderOption, SpinnerOption, build_mod, get_pc, hook
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

DIAG_VERSION = "1.0.2"
DIAG_LOG = MODS_DIR / "SnappyMovement_diag.log"
_diag_counter = 0

try:
    DIAG_LOG.write_text(
        f"SnappyMovement DIAG {DIAG_VERSION}\n",
        encoding="utf-8",
    )
except Exception:
    pass


def _error(message: str) -> None:
    logging.error(f"[SnappyMovement] {message}")


def _path(obj: Any) -> str:
    if obj is None:
        return "<None>"
    try:
        return str(obj._path_name())
    except Exception:
        return "<unreadable-path>"


def _diag_component_text(component: UObject | None) -> str:
    if component is None:
        return "component=None"

    try:
        py_id = hex(id(component))
    except Exception:
        py_id = "<id-error>"

    try:
        address = hex(int(component._get_address()))
    except Exception:
        address = "<addr-error>"

    try:
        accel = f"{float(component.MaxAcceleration):.6f}"
    except Exception:
        accel = "<read-error>"

    try:
        brake = f"{float(component.BrakingDecelerationWalking):.6f}"
    except Exception:
        brake = "<read-error>"

    return (
        f"pyid={py_id} addr={address} path={_path(component)!r} "
        f"accel={accel} brake={brake}"
    )


def _diag(event: str, component: UObject | None = None, extra: str = "") -> None:
    global _diag_counter

    _diag_counter += 1
    suffix = f" {extra}" if extra else ""
    line = f"[{_diag_counter:04d}] {event} {_diag_component_text(component)}{suffix}\n"

    try:
        with DIAG_LOG.open("a", encoding="utf-8", errors="replace") as handle:
            handle.write(line)
    except Exception:
        pass


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
        controller = get_pc(possibly_loading=True)
    except Exception as exc:
        controller = None
        _diag("GET_PC_ERROR", extra=repr(exc))

    if controller is not None:
        try:
            is_local = bool(controller.IsLocalController())
        except Exception as exc:
            is_local = False
            _diag("GET_PC_LOCAL_ERROR", controller, repr(exc))

        _diag("GET_PC_RESULT", controller, f"is_local={is_local}")
        if is_local:
            return controller

    try:
        controllers = list(unrealsdk.find_all("PlayerController", exact=False))
    except Exception as exc:
        _diag("FIND_ALL_CONTROLLER_ERROR", extra=repr(exc))
        return None

    _diag("FIND_ALL_CONTROLLER_COUNT", extra=f"count={len(controllers)}")
    for index, candidate in enumerate(controllers):
        try:
            is_local = bool(candidate.IsLocalController())
        except Exception as exc:
            _diag("CONTROLLER_LOCAL_ERROR", candidate, f"index={index} error={exc!r}")
            continue

        _diag("CONTROLLER_CANDIDATE", candidate, f"index={index} is_local={is_local}")
        if is_local:
            return candidate

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


def _diag_current(event: str, extra: str = "") -> None:
    controller = _find_local_controller()
    if controller is None:
        _diag(event, extra=(extra + " stage=no_controller").strip())
        return

    try:
        pawn = controller.Pawn
    except Exception as exc:
        _diag(event, controller, (extra + f" stage=pawn_error error={exc!r}").strip())
        return

    if pawn is None:
        _diag(event, controller, (extra + " stage=no_pawn").strip())
        return

    component = _get_move_component(pawn)
    if component is None:
        _diag(event, pawn, (extra + " stage=no_component").strip())
        return

    _diag(event, component, (extra + " stage=ok").strip())


def _remember_original(component: UObject) -> None:
    _diag("REMEMBER_ENTER", component, f"records={len(_patched_components)}")

    for index, (existing, _old_accel, _old_brake) in enumerate(_patched_components):
        same_wrapper = existing is component
        _diag(
            "REMEMBER_COMPARE",
            existing,
            (
                f"index={index} same_wrapper={same_wrapper} "
                f"candidate_pyid={hex(id(component))}"
            ),
        )
        if same_wrapper:
            _diag("REMEMBER_HIT", component, f"index={index}")
            return

    try:
        old_accel = float(component.MaxAcceleration)
        old_brake = float(component.BrakingDecelerationWalking)
    except Exception as exc:
        _diag("REMEMBER_READ_ERROR", component, repr(exc))
        _error(f"could not read original movement values from {_path(component)}: {exc}")
        return

    _patched_components.append((component, old_accel, old_brake))
    _diag(
        "REMEMBER_APPEND",
        component,
        (
            f"stored_accel={old_accel:.6f} stored_brake={old_brake:.6f} "
            f"records={len(_patched_components)}"
        ),
    )


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

    _diag(
        "APPLY_BEFORE",
        component,
        f"target_accel={acceleration:.6f} target_brake={braking:.6f}",
    )
    _remember_original(component)

    try:
        component.MaxAcceleration = acceleration
        component.BrakingDecelerationWalking = braking
        _diag(
            "APPLY_AFTER",
            component,
            f"target_accel={acceleration:.6f} target_brake={braking:.6f}",
        )
    except Exception as exc:
        _diag("APPLY_WRITE_ERROR", component, repr(exc))
        _error(f"failed to apply movement values to {_path(component)}: {exc}")


def _apply_current_values() -> None:
    acceleration, braking = _current_values()
    _apply_to_pawn(_get_current_pawn(), acceleration, braking)


def _restore_all() -> None:
    global _patched_components

    _diag("RESTORE_BEGIN", extra=f"records={len(_patched_components)}")

    for index, (component, old_accel, old_brake) in enumerate(_patched_components):
        _diag(
            "RESTORE_BEFORE",
            component,
            (
                f"index={index} stored_accel={old_accel:.6f} "
                f"stored_brake={old_brake:.6f}"
            ),
        )
        try:
            component.MaxAcceleration = old_accel
            component.BrakingDecelerationWalking = old_brake
            _diag(
                "RESTORE_AFTER",
                component,
                (
                    f"index={index} stored_accel={old_accel:.6f} "
                    f"stored_brake={old_brake:.6f}"
                ),
            )
        except Exception as exc:
            _diag("RESTORE_WRITE_ERROR", component, f"index={index} error={exc!r}")
            # Destroyed pawns/components from map changes or respawns can remain as stale wrappers.
            pass

    _patched_components = []
    _diag("RESTORE_END", extra="records=0")


def _on_enable() -> None:
    _diag_current("ENABLE_BEFORE")
    _apply_current_values()
    _diag_current("ENABLE_AFTER")


def _on_disable() -> None:
    _diag_current("DISABLE_BEFORE")
    _restore_all()
    _diag_current("DISABLE_AFTER")


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

    component = _get_move_component(pawn) if pawn is not None else None
    _diag("CLIENT_RESTART_BEFORE", component)

    acceleration, braking = _current_values()
    _apply_to_pawn(pawn, acceleration, braking, report_failure=True)

    component = _get_move_component(pawn) if pawn is not None else None
    _diag("CLIENT_RESTART_AFTER", component)


def _on_profile_change(_option: SpinnerOption, new_value: str) -> None:
    global _syncing_options

    _diag_current("PROFILE_CHANGE", f"new_value={new_value!r}")

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

    _diag_current("ACCEL_CHANGE", f"new_value={new_value!r}")

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

    _diag_current("BRAKE_CHANGE", f"new_value={new_value!r}")

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


_diag_current("MODULE_READY", f"records={len(_patched_components)}")
