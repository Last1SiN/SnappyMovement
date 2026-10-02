from __future__ import annotations

import math
from typing import Any

import unrealsdk
from mods_base import BoolOption, Game, HiddenOption, Mod, SliderOption, SpinnerOption, build_mod, get_pc, hook
from unrealsdk import logging
from unrealsdk.hooks import Type, add_hook, remove_hook
from unrealsdk.unreal import BoundFunction, UObject, WrappedStruct

assert Game.get_current() is Game.BL3, "SnappyMovement supports Borderlands 3 only"

PROFILE_SOFT = "Soft (8000 / 10000)"
PROFILE_NEAR = "Near Instant (30000 / 40000)"
PROFILE_INSTANT = "Instant (100000 / 120000)"
PROFILE_CUSTOM = "Custom"

CROUCH_SLIDE_OFF = "Off"
CROUCH_SLIDE_HOLD = "Slide on Crouch Hold"
CROUCH_SLIDE_TAP = "Slide on Crouch Tap"
CROUCH_SLIDE_MODES = (
    CROUCH_SLIDE_OFF,
    CROUCH_SLIDE_HOLD,
    CROUCH_SLIDE_TAP,
)

WALK_OVERRIDE_DISABLED = "Disabled"
WALK_OVERRIDE_HOLD = "Hold Sprint Input to Walk"
WALK_OVERRIDE_TOGGLE = "Toggle Sprint Input to Walk"
WALK_OVERRIDE_MODES = (
    WALK_OVERRIDE_DISABLED,
    WALK_OVERRIDE_HOLD,
    WALK_OVERRIDE_TOGGLE,
)

PRESETS: dict[str, tuple[float, float]] = {
    PROFILE_SOFT: (8000.0, 10000.0),
    PROFILE_NEAR: (30000.0, 40000.0),
    PROFILE_INSTANT: (100000.0, 120000.0),
}

ACCEL_MIN = 1000.0
ACCEL_MAX = 150000.0
BRAKE_MIN = 1000.0
BRAKE_MAX = 180000.0
AIR_CONTROL_MIN = 0.0
AIR_CONTROL_MAX = 20.0
ANY_DIRECTION_SPRINT_ANGLE = 180.0

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

air_control_override_option = BoolOption(
    identifier="air_control_override",
    value=False,
    display_name="Air Control Override",
    description=(
        "Use the custom Air Control value while airborne. Off restores the game's "
        "original AirControl value."
    ),
)

air_control_option = SliderOption(
    "air_control",
    1.0,
    AIR_CONTROL_MIN,
    AIR_CONTROL_MAX,
    0.1,
    is_integer=False,
    display_name="Air Control",
    description=(
        "Air steering strength from 0 to 20. 0 disables steering; higher values make "
        "direction changes increasingly immediate. Only used while Air Control Override is on."
    ),
)

remember_sprint_option = BoolOption(
    identifier="remember_sprint",
    value=False,
    display_name="Remember Sprint",
    description=(
        "Remembers sprint intent through jumps and slide-jumps, then lets the game "
        "resume sprint after landing without another sprint press. Auto Sprint supersedes it."
    ),
)

auto_sprint_option = BoolOption(
    identifier="auto_sprint",
    value=False,
    display_name="Auto Sprint",
    description=(
        "Keeps the game's native sprint intent enabled whenever walking override is not active."
    ),
)

walk_override_option = SpinnerOption(
    "walk_override",
    WALK_OVERRIDE_HOLD,
    list(WALK_OVERRIDE_MODES),
    wrap_enabled=False,
    display_name="Auto Sprint Walk Override",
    description=(
        "Disabled: Sprint input cannot cancel Auto Sprint. "
        "Hold: hold Sprint input to walk, then release to sprint again. "
        "Toggle: press Sprint input to switch between walking and Auto Sprint."
    ),
)

any_direction_sprint_option = BoolOption(
    identifier="any_direction_sprint",
    value=False,
    display_name="Sprint in All Directions",
    description=(
        "Raises the game's native sprint-angle limit to 180 degrees so sprint can continue "
        "sideways and backward without changing sprint speed."
    ),
)

legacy_slide_from_landing_option = HiddenOption(
    identifier="slide_from_landing",
    value=None,
)

crouch_slide_mode_option = SpinnerOption(
    "crouch_slide_mode",
    CROUCH_SLIDE_OFF,
    list(CROUCH_SLIDE_MODES),
    wrap_enabled=False,
    display_name="Crouch Landing Slide",
    description=(
        "Off: no automatic slide on landing. "
        "Slide on Crouch Hold: slide only if crouch is still held at landing. "
        "Slide on Crouch Tap: pressing crouch while airborne arms a slide for the next landing, "
        "even if crouch is released before touching the ground."
    ),
)

OPTIONS = (
    profile_option,
    accel_option,
    brake_option,
    air_control_override_option,
    air_control_option,
    remember_sprint_option,
    auto_sprint_option,
    walk_override_option,
    any_direction_sprint_option,
    legacy_slide_from_landing_option,
    crouch_slide_mode_option,
)

_syncing_options = False
_patched_components: list[
    tuple[UObject, float, float, float | None, float | None]
] = []

_sprint_chain_armed = False
_resume_sprint_after_landing = False
_restoring_sprint = False
_landing_crouch_pending = False
_landing_transition_pending = False
_air_slide_intent = False
_crouch_input_held = False
_air_crouch_tap_pending = False
_auto_sprint_applying = False
_walk_override_active = False
_CROUCH_INPUT_FN_4 = (
    "GbxInpActEvt_InputAction_Discrete_Crouch_"
    "K2Node_GbxInputActionEvent_Discrete_4"
)
_CROUCH_INPUT_FN_5 = (
    "GbxInpActEvt_InputAction_Discrete_Crouch_"
    "K2Node_GbxInputActionEvent_Discrete_5"
)
_CROUCH_FLUSH_FN = "FlushCrouchInput"
_CROUCH_DYNAMIC_ID_PREFIX = "snappymovement:crouch-input:v1.3.5"
_crouch_dynamic_hooks: list[tuple[str, str]] = []

_SPRINT_DYNAMIC_ID_PREFIX = "snappymovement:sprint-input:v1.3.5"
_sprint_dynamic_hooks: list[tuple[str, Type, str]] = []
_sprint_event_by_path: dict[str, str] = {}


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


def _safe_float_value(
    raw: Any,
    default: float,
    minimum: float,
    maximum: float,
    label: str,
) -> float:
    try:
        value = float(raw)
    except (TypeError, ValueError):
        _error(f"{label}: invalid value {raw!r}; using {default:g}")
        return default
    if not math.isfinite(value):
        _error(f"{label}: non-finite value {value!r}; using {default:g}")
        return default
    return min(max(value, minimum), maximum)


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
    # Oak's local controller is exposed directly by mods_base. This is the same
    # path proven by the earlier SnappyMovement diagnostics.
    try:
        controller = get_pc(possibly_loading=True)
    except Exception:
        controller = None

    if controller is not None:
        try:
            if bool(controller.IsLocalController()):
                return controller
        except Exception:
            pass

    # Fallback only. find_all() alone is not reliable enough on BL3 and was the
    # cause of feature hooks seeing current pawn as None in v1.1.0-v1.1.3.
    try:
        controllers = unrealsdk.find_all("PlayerController", exact=False)
    except Exception:
        return None

    for candidate in controllers:
        try:
            if bool(candidate.IsLocalController()):
                return candidate
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


def _remember_original(
    component: UObject,
) -> tuple[UObject, float, float, float | None, float | None] | None:
    for record in _patched_components:
        if record[0] is component:
            return record

    try:
        old_accel = float(component.MaxAcceleration)
        old_brake = float(component.BrakingDecelerationWalking)
    except Exception as exc:
        _error(f"could not read original movement values from {_path(component)}: {exc}")
        return None

    try:
        old_air_control: float | None = float(component.AirControl)
    except Exception:
        old_air_control = None

    try:
        old_sprint_angle: float | None = float(component.MaxSprintAngle)
    except Exception:
        old_sprint_angle = None

    record = (
        component,
        old_accel,
        old_brake,
        old_air_control,
        old_sprint_angle,
    )
    _patched_components.append(record)
    return record


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

    record = _remember_original(component)
    if record is None:
        return

    _, _old_accel, _old_brake, old_air_control, old_sprint_angle = record

    try:
        component.MaxAcceleration = acceleration
        component.BrakingDecelerationWalking = braking
    except Exception as exc:
        _error(f"failed to apply movement values to {_path(component)}: {exc}")

    if old_air_control is not None:
        target_air_control = old_air_control
        if bool(air_control_override_option.value):
            target_air_control = _safe_float_value(
                air_control_option.value,
                1.0,
                AIR_CONTROL_MIN,
                AIR_CONTROL_MAX,
                "Air Control",
            )
        try:
            component.AirControl = target_air_control
        except Exception as exc:
            if bool(air_control_override_option.value):
                _error(f"failed to apply Air Control to {_path(component)}: {exc}")
    elif bool(air_control_override_option.value) and report_failure:
        _error(f"Air Control is unavailable on {_path(component)}")

    if old_sprint_angle is not None:
        target_sprint_angle = (
            ANY_DIRECTION_SPRINT_ANGLE
            if bool(any_direction_sprint_option.value)
            else old_sprint_angle
        )
        try:
            component.MaxSprintAngle = target_sprint_angle
        except Exception as exc:
            if bool(any_direction_sprint_option.value):
                _error(f"failed to apply sprint angle to {_path(component)}: {exc}")
    elif bool(any_direction_sprint_option.value) and report_failure:
        _error(f"MaxSprintAngle is unavailable on {_path(component)}")


def _apply_current_values() -> None:
    acceleration, braking = _current_values()
    _apply_to_pawn(_get_current_pawn(), acceleration, braking)


def _apply_air_control_override(
    pawn: UObject | None,
    *,
    report_failure: bool = False,
) -> bool:
    if pawn is None or not bool(air_control_override_option.value):
        return False

    component = _get_move_component(pawn)
    if component is None:
        if report_failure:
            _error(f"Air Control: movement component unavailable on {_path(pawn)}")
        return False

    record = _remember_original(component)
    if record is None:
        return False

    target = _safe_float_value(
        air_control_option.value,
        1.0,
        AIR_CONTROL_MIN,
        AIR_CONTROL_MAX,
        "Air Control",
    )
    try:
        before = float(component.AirControl)
        component.AirControl = target
        after = float(component.AirControl)
    except Exception as exc:
        if report_failure:
            _error(f"failed to reapply Air Control to {_path(component)}: {exc}")
        return False

    if abs(before - target) > 0.001:
        logging.warning(
            "[SnappyMovement airfix] "
            f"reapplied AirControl from={before:.3f} target={target:.3f} actual={after:.3f}"
        )

    return abs(after - target) <= 0.001


def _restore_all() -> None:
    global _patched_components

    for component, old_accel, old_brake, old_air_control, old_sprint_angle in _patched_components:
        try:
            component.MaxAcceleration = old_accel
            component.BrakingDecelerationWalking = old_brake
            if old_air_control is not None:
                component.AirControl = old_air_control
            if old_sprint_angle is not None:
                component.MaxSprintAngle = old_sprint_angle
        except Exception:
            # Destroyed pawns/components from map changes or respawns can remain as stale wrappers.
            pass

    _patched_components = []


def _same_uobject(left: UObject | None, right: UObject | None) -> bool:
    if left is None or right is None:
        return False
    if left is right:
        return True
    try:
        return int(left._get_address()) == int(right._get_address())
    except Exception:
        return False


def _movement_bool(obj: UObject | None, method_name: str) -> bool:
    if obj is None:
        return False
    try:
        method = getattr(obj, method_name)
    except Exception:
        return False
    if not callable(method):
        return False
    try:
        return bool(method())
    except Exception:
        return False


def _movement_flag(component: UObject | None, name: str) -> bool:
    if component is None:
        return False
    try:
        return bool(getattr(component, name))
    except Exception:
        return False


def _is_falling(pawn: UObject | None) -> bool:
    if pawn is None:
        return False
    component = _get_move_component(pawn)
    if component is None:
        return False
    try:
        return bool(component.IsFalling())
    except Exception:
        return False


def _is_sliding(pawn: UObject | None) -> bool:
    return _movement_bool(pawn, "IsCharacterSliding")


def _wants_sprint(pawn: UObject | None) -> bool:
    if pawn is None:
        return False
    if _movement_bool(pawn, "GetWantsToSprint"):
        return True
    return _movement_flag(_get_move_component(pawn), "bWantsToSprint")


def _wants_crouch(pawn: UObject | None) -> bool:
    return _movement_bool(pawn, "GetWantsToCrouch")



def _bound_function_path(func: BoundFunction) -> str:
    try:
        return str(func.func._path_name())
    except Exception:
        try:
            return str(func._path_name())
        except Exception:
            return "<unreadable-function>"




def _ability_belongs_to_pawn(ability: UObject, pawn: UObject | None) -> bool:
    if pawn is None:
        return False

    ability_path = _path(ability)
    pawn_path = _path(pawn)
    if ability_path.startswith("<") or pawn_path.startswith("<"):
        return False

    return ability_path.startswith(f"{pawn_path}.")


def _crouch_input_callback(
    obj: UObject,
    _args: WrappedStruct,
    _ret: Any,
    func: BoundFunction,
) -> None:
    global _crouch_input_held
    global _air_crouch_tap_pending

    pawn = _get_current_pawn()
    if not _ability_belongs_to_pawn(obj, pawn):
        return

    function_path = _bound_function_path(func)
    if function_path.endswith(_CROUCH_INPUT_FN_4):
        _crouch_input_held = True
        if _is_falling(pawn):
            _air_crouch_tap_pending = True
    elif function_path.endswith(_CROUCH_INPUT_FN_5):
        _crouch_input_held = False


def _crouch_flush_callback(
    obj: UObject,
    _args: WrappedStruct,
    _ret: Any,
    _func: BoundFunction,
) -> None:
    global _crouch_input_held
    global _air_crouch_tap_pending

    pawn = _get_current_pawn()
    if not _ability_belongs_to_pawn(obj, pawn):
        return

    _crouch_input_held = False
    _air_crouch_tap_pending = False


def _remove_crouch_dynamic_hooks() -> None:
    global _crouch_dynamic_hooks

    for path, identifier in tuple(_crouch_dynamic_hooks):
        try:
            remove_hook(path, Type.POST, identifier)
        except Exception:
            pass
    _crouch_dynamic_hooks = []


def _install_crouch_dynamic_hooks() -> bool:
    global _crouch_dynamic_hooks

    if _crouch_dynamic_hooks:
        return True

    try:
        abilities = list(unrealsdk.find_all("PlayerAbility_Crouch_C", exact=False))
    except Exception:
        return False

    live_ability = next(
        (ability for ability in abilities if "Default__" not in _path(ability)),
        None,
    )
    if live_ability is None:
        return False

    class_path = _path(live_ability.Class)
    targets = (
        (_CROUCH_INPUT_FN_4, _crouch_input_callback),
        (_CROUCH_INPUT_FN_5, _crouch_input_callback),
        (_CROUCH_FLUSH_FN, _crouch_flush_callback),
    )

    installed: list[tuple[str, str]] = []
    for index, (name, callback) in enumerate(targets):
        path = f"{class_path}:{name}"
        try:
            if unrealsdk.find_object("Function", path) is None:
                continue
            identifier = f"{_CROUCH_DYNAMIC_ID_PREFIX}:{index}"
            add_hook(path, Type.POST, identifier, callback)
        except Exception:
            continue
        installed.append((path, identifier))

    _crouch_dynamic_hooks = installed
    return len(installed) >= 2


def _input_event_name(value: Any) -> str | None:
    try:
        name = str(value.name)
    except Exception:
        name = str(value)

    lowered = name.lower()
    if "pressed" in lowered:
        return "pressed"
    if "released" in lowered:
        return "released"

    try:
        raw = int(getattr(value, "value", value))
    except Exception:
        return None
    if raw == 0:
        return "pressed"
    if raw == 1:
        return "released"
    return None


def _find_action_bindings(
    ability_class_name: str,
    action_name: str,
) -> tuple[UObject | None, dict[str, str]]:
    try:
        abilities = list(unrealsdk.find_all(ability_class_name, exact=False))
    except Exception:
        return None, {}

    live_ability = next(
        (ability for ability in abilities if "Default__" not in _path(ability)),
        None,
    )
    if live_ability is None:
        return None, {}

    cls = live_ability.Class
    class_path = _path(cls)
    result: dict[str, str] = {}

    try:
        dynamic_bindings = list(cls.DynamicBindingObjects)
    except Exception:
        return live_ability, {}

    for binding_obj in dynamic_bindings:
        try:
            entries = list(binding_obj.InputActionReceiverDelegateBindings)
        except Exception:
            continue
        for entry in entries:
            try:
                action = entry.Action
                current_action_name = str(action.ActionName)
            except Exception:
                continue
            if current_action_name.lower() != action_name.lower():
                continue
            try:
                event = _input_event_name(entry.InputEvent)
                function_name = str(entry.FunctionNameToBind)
            except Exception:
                continue
            if event in ("pressed", "released"):
                result[f"{class_path}:{function_name}"] = event

    return live_ability, result


def _walk_override_mode() -> str:
    mode = str(walk_override_option.value)
    if mode in WALK_OVERRIDE_MODES:
        return mode
    return WALK_OVERRIDE_HOLD


def _apply_auto_sprint_intent(pawn: UObject | None) -> bool:
    global _auto_sprint_applying

    if pawn is None or not bool(auto_sprint_option.value):
        return False

    wanted = not _walk_override_active
    try:
        _auto_sprint_applying = True
        pawn.SetWantsToSprint(wanted)
        if wanted:
            movement = _get_move_component(pawn)
            if movement is not None:
                try:
                    movement.bWantsToStartSprinting = True
                except Exception:
                    pass
    except Exception as exc:
        _error(f"Auto Sprint: failed to set native sprint intent: {exc}")
        return False
    finally:
        _auto_sprint_applying = False

    return True


def _release_auto_sprint(pawn: UObject | None) -> None:
    global _auto_sprint_applying

    if pawn is None:
        return
    try:
        _auto_sprint_applying = True
        pawn.SetWantsToSprint(False)
    except Exception:
        pass
    finally:
        _auto_sprint_applying = False


def _sprint_input_pre(
    obj: UObject,
    _args: WrappedStruct,
    _ret: Any,
    func: BoundFunction,
) -> None:
    global _walk_override_active

    if not bool(auto_sprint_option.value):
        return

    pawn = _get_current_pawn()
    if not _ability_belongs_to_pawn(obj, pawn):
        return

    event = _sprint_event_by_path.get(_bound_function_path(func))
    mode = _walk_override_mode()

    if event == "pressed":
        if mode == WALK_OVERRIDE_HOLD:
            _walk_override_active = True
        elif mode == WALK_OVERRIDE_TOGGLE:
            _walk_override_active = not _walk_override_active
        else:
            _walk_override_active = False
    elif event == "released" and mode == WALK_OVERRIDE_HOLD:
        _walk_override_active = False


def _sprint_input_post(
    obj: UObject,
    _args: WrappedStruct,
    _ret: Any,
    _func: BoundFunction,
) -> None:
    if not bool(auto_sprint_option.value):
        return
    pawn = _get_current_pawn()
    if _ability_belongs_to_pawn(obj, pawn):
        _apply_auto_sprint_intent(pawn)


def _remove_sprint_dynamic_hooks() -> None:
    global _sprint_dynamic_hooks
    global _sprint_event_by_path

    for path, hook_type, identifier in tuple(_sprint_dynamic_hooks):
        try:
            remove_hook(path, hook_type, identifier)
        except Exception:
            pass
    _sprint_dynamic_hooks = []
    _sprint_event_by_path = {}


def _install_sprint_dynamic_hooks() -> bool:
    global _sprint_dynamic_hooks
    global _sprint_event_by_path

    if _sprint_dynamic_hooks:
        return True

    _ability, bindings = _find_action_bindings("PlayerAbility_Sprint_C", "Sprint")
    if not bindings:
        return False

    installed: list[tuple[str, Type, str]] = []
    event_map: dict[str, str] = {}
    for index, (path, event) in enumerate(sorted(bindings.items())):
        try:
            if unrealsdk.find_object("Function", path) is None:
                continue
            pre_id = f"{_SPRINT_DYNAMIC_ID_PREFIX}:pre:{index}"
            post_id = f"{_SPRINT_DYNAMIC_ID_PREFIX}:post:{index}"
            add_hook(path, Type.PRE, pre_id, _sprint_input_pre)
            add_hook(path, Type.POST, post_id, _sprint_input_post)
        except Exception:
            try:
                remove_hook(path, Type.PRE, pre_id)
            except Exception:
                pass
            continue
        installed.append((path, Type.PRE, pre_id))
        installed.append((path, Type.POST, post_id))
        event_map[path] = event

    _sprint_dynamic_hooks = installed
    _sprint_event_by_path = event_map
    return "pressed" in event_map.values() and "released" in event_map.values()


def _reset_flow_state() -> None:
    global _sprint_chain_armed
    global _resume_sprint_after_landing
    global _restoring_sprint
    global _landing_crouch_pending
    global _landing_transition_pending
    global _air_slide_intent
    global _crouch_input_held
    global _air_crouch_tap_pending
    global _auto_sprint_applying
    global _walk_override_active

    _sprint_chain_armed = False
    _resume_sprint_after_landing = False
    _restoring_sprint = False
    _landing_crouch_pending = False
    _landing_transition_pending = False
    _air_slide_intent = False
    _crouch_input_held = False
    _air_crouch_tap_pending = False
    _auto_sprint_applying = False
    _walk_override_active = False


def _crouch_slide_mode() -> str:
    mode = str(crouch_slide_mode_option.value)
    if mode in CROUCH_SLIDE_MODES:
        return mode
    return CROUCH_SLIDE_OFF


def _should_slide_from_landing(pawn: UObject | None) -> bool:
    mode = _crouch_slide_mode()
    if mode == CROUCH_SLIDE_HOLD:
        return bool(_crouch_input_held or _wants_crouch(pawn) or _air_slide_intent)
    if mode == CROUCH_SLIDE_TAP:
        return bool(_air_crouch_tap_pending)
    return False


def _restore_remembered_sprint(pawn: UObject | None, reason: str) -> bool:
    global _resume_sprint_after_landing
    global _restoring_sprint
    global _sprint_chain_armed

    if (
        pawn is None
        or bool(auto_sprint_option.value)
        or not bool(remember_sprint_option.value)
    ):
        _resume_sprint_after_landing = False
        return False

    if not _resume_sprint_after_landing:
        return False

    if _wants_sprint(pawn):
        _resume_sprint_after_landing = False
        _sprint_chain_armed = True
        return False

    try:
        _restoring_sprint = True
        pawn.SetWantsToSprint(True)
    except Exception as exc:
        _error(f"Remember Sprint: failed to restore sprint after {reason}: {exc}")
        return False
    finally:
        _restoring_sprint = False

    _resume_sprint_after_landing = False
    _sprint_chain_armed = True
    return True


def _on_enable() -> None:
    _reset_flow_state()
    _apply_current_values()
    _install_crouch_dynamic_hooks()
    _install_sprint_dynamic_hooks()

    _apply_auto_sprint_intent(_get_current_pawn())


def _on_disable() -> None:
    pawn = _get_current_pawn()
    if bool(auto_sprint_option.value):
        _release_auto_sprint(pawn)
    _remove_sprint_dynamic_hooks()
    _remove_crouch_dynamic_hooks()
    _reset_flow_state()
    _restore_all()


@hook("/Script/OakGame.OakCharacter:SetWantsToSprint", Type.POST)
def _set_wants_to_sprint(
    obj: UObject,
    args: WrappedStruct,
    _ret: Any,
    _func: BoundFunction,
) -> None:
    global _sprint_chain_armed
    global _resume_sprint_after_landing


    if (
        _restoring_sprint
        or _auto_sprint_applying
        or not _same_uobject(obj, _get_current_pawn())
    ):
        return

    try:
        requested = bool(args.bNewWantsToSprint)
    except Exception:
        return


    if requested:
        return

    if bool(auto_sprint_option.value):
        if not _walk_override_active:
            _apply_auto_sprint_intent(obj)
        return

    _sprint_chain_armed = False
    _resume_sprint_after_landing = False


@hook("/Script/OakGame.OakCharacter:OnStartSprinting", Type.POST)
def _on_start_sprinting(
    obj: UObject,
    _args: WrappedStruct,
    _ret: Any,
    _func: BoundFunction,
) -> None:
    global _sprint_chain_armed

    if not _same_uobject(obj, _get_current_pawn()):
        return

    if bool(remember_sprint_option.value) and not bool(auto_sprint_option.value):
        _sprint_chain_armed = True


@hook("/Script/OakGame.OakCharacter:OnEndSprinting", Type.POST)
def _on_end_sprinting(
    obj: UObject,
    _args: WrappedStruct,
    _ret: Any,
    _func: BoundFunction,
) -> None:
    global _sprint_chain_armed

    if not _same_uobject(obj, _get_current_pawn()):
        return

    if bool(auto_sprint_option.value):
        if not _walk_override_active:
            restored = _apply_auto_sprint_intent(obj)
            if restored:
                logging.warning(
                    "[SnappyMovement autosprintfix] "
                    "re-armed native sprint intent after OnEndSprinting"
                )
        return

    if not bool(remember_sprint_option.value):
        return

    if _is_falling(obj) or _is_sliding(obj):
        return

    if not _wants_sprint(obj):
        _sprint_chain_armed = False


@hook(
    "/Game/PlayerCharacters/_Shared/_Design/Character/BPChar_Player.BPChar_Player_C:OnJumped",
    Type.POST,
)
def _on_jumped(
    obj: UObject,
    _args: WrappedStruct,
    _ret: Any,
    _func: BoundFunction,
) -> None:
    global _resume_sprint_after_landing
    global _landing_crouch_pending
    global _air_crouch_tap_pending

    _install_crouch_dynamic_hooks()
    _install_sprint_dynamic_hooks()

    if not _same_uobject(obj, _get_current_pawn()):
        return

    _landing_crouch_pending = False
    _air_crouch_tap_pending = False
    _apply_air_control_override(obj)

    if bool(auto_sprint_option.value) or not bool(remember_sprint_option.value):
        _resume_sprint_after_landing = False
        return

    component = _get_move_component(obj)
    sprint_related = (
        _sprint_chain_armed
        or _wants_sprint(obj)
        or _movement_flag(component, "bIsSprinting")
    )
    _resume_sprint_after_landing = bool(sprint_related)




@hook(
    "/Game/PlayerCharacters/_Shared/_Design/Character/BPChar_Player.BPChar_Player_C:OnLanded",
    Type.POST,
)
def _on_landed_post(
    obj: UObject,
    _args: WrappedStruct,
    _ret: Any,
    _func: BoundFunction,
) -> None:
    global _landing_crouch_pending
    global _landing_transition_pending


    if not _same_uobject(obj, _get_current_pawn()):
        return

    _landing_transition_pending = True
    _landing_crouch_pending = _should_slide_from_landing(obj)


def _finalize_landing_after_walking(pawn: UObject | None, source: str) -> None:
    global _landing_crouch_pending
    global _landing_transition_pending
    global _air_slide_intent
    global _air_crouch_tap_pending

    if pawn is None or not _landing_transition_pending:
        return

    movement = _get_move_component(pawn)
    if movement is None:
        return

    try:
        mode_raw = movement.MovementMode
        mode = int(getattr(mode_raw, "value", mode_raw))
    except Exception:
        return

    if mode != 1:
        return

    _landing_transition_pending = False

    slide_requested = False
    if _crouch_slide_mode() != CROUCH_SLIDE_OFF and _landing_crouch_pending:
        try:
            pawn.SetWantsToSlide(True)
            slide_requested = True
        except Exception as exc:
            _error(f"Slide from Landing: failed to request native slide: {exc}")

    _landing_crouch_pending = False
    _air_slide_intent = False
    _air_crouch_tap_pending = False

    if not slide_requested:
        if bool(auto_sprint_option.value):
            _apply_auto_sprint_intent(pawn)
        else:
            _restore_remembered_sprint(pawn, f"{source} MOVE_Walking")


@hook("/Script/Engine.Character:K2_OnMovementModeChanged", Type.POST)
def _movement_mode_changed(
    obj: UObject,
    args: WrappedStruct,
    _ret: Any,
    _func: BoundFunction,
) -> None:
    if not _same_uobject(obj, _get_current_pawn()):
        return

    try:
        new_mode_raw = args.NewMovementMode
        new_mode = int(getattr(new_mode_raw, "value", new_mode_raw))
    except Exception:
        return


    if new_mode == 3:
        _apply_air_control_override(obj)
    elif new_mode == 1:
        _finalize_landing_after_walking(obj, "K2")


@hook("/Script/Engine.CharacterMovementComponent:SetMovementMode", Type.POST)
def _movement_component_mode_changed(
    obj: UObject,
    args: WrappedStruct,
    _ret: Any,
    _func: BoundFunction,
) -> None:
    pawn = _get_current_pawn()
    if pawn is None:
        return

    movement = _get_move_component(pawn)
    if not _same_uobject(obj, movement):
        return

    try:
        new_mode_raw = args.NewMovementMode
        new_mode = int(getattr(new_mode_raw, "value", new_mode_raw))
    except Exception:
        return


    if new_mode == 3:
        _apply_air_control_override(pawn)
    elif new_mode == 1:
        _finalize_landing_after_walking(pawn, "SetMovementMode")


@hook("/Script/OakGame.OakCharacter:SetWantsToSlide", Type.POST)
def _set_wants_to_slide(
    obj: UObject,
    args: WrappedStruct,
    _ret: Any,
    _func: BoundFunction,
) -> None:
    global _air_slide_intent


    if not _same_uobject(obj, _get_current_pawn()):
        return

    try:
        requested = bool(args.bNewWantsToSlide)
    except Exception:
        return

    falling = _is_falling(obj)

    if falling:
        _air_slide_intent = requested

    if requested:
        return

    if not falling and not _is_sliding(obj):
        if bool(auto_sprint_option.value):
            _apply_auto_sprint_intent(obj)
        elif _resume_sprint_after_landing:
            _restore_remembered_sprint(obj, "slide")


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

    _reset_flow_state()
    acceleration, braking = _current_values()
    _apply_to_pawn(pawn, acceleration, braking, report_failure=True)
    _install_crouch_dynamic_hooks()
    sprint_hooks_ready = _install_sprint_dynamic_hooks()
    if bool(auto_sprint_option.value) and not sprint_hooks_ready:
        _error("Auto Sprint Walk Override: Sprint input bindings are unavailable")
    _apply_auto_sprint_intent(pawn)


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


def _on_movement_feature_change(_option: Any, _new_value: Any) -> None:
    if mod.is_enabled:
        _apply_current_values()


def _on_auto_sprint_change(_option: BoolOption, new_value: bool) -> None:
    global _walk_override_active
    global _sprint_chain_armed
    global _resume_sprint_after_landing

    _walk_override_active = False
    _sprint_chain_armed = False
    _resume_sprint_after_landing = False
    if not mod.is_enabled:
        return

    pawn = _get_current_pawn()
    sprint_hooks_ready = _install_sprint_dynamic_hooks()
    if bool(new_value):
        if pawn is not None and not sprint_hooks_ready:
            _error("Auto Sprint Walk Override: Sprint input bindings are unavailable")
        _apply_auto_sprint_intent(pawn)
    else:
        _release_auto_sprint(pawn)


def _on_walk_override_change(_option: SpinnerOption, _new_value: str) -> None:
    global _walk_override_active
    global _move_input_active

    _walk_override_active = False
    _move_input_active = False
    if mod.is_enabled and bool(auto_sprint_option.value):
        _apply_auto_sprint_intent(_get_current_pawn())


def _sanitize_loaded_settings(mod_obj: Mod) -> None:
    global _syncing_options

    corrected = False
    profile = str(profile_option.value)
    crouch_mode = str(crouch_slide_mode_option.value)
    walk_mode = str(walk_override_option.value)
    legacy_slide = legacy_slide_from_landing_option.value

    _syncing_options = True
    try:
        if crouch_mode not in CROUCH_SLIDE_MODES:
            crouch_slide_mode_option.value = CROUCH_SLIDE_OFF
            crouch_mode = CROUCH_SLIDE_OFF
            corrected = True

        if walk_mode not in WALK_OVERRIDE_MODES:
            walk_override_option.value = WALK_OVERRIDE_HOLD
            corrected = True

        safe_air_control = _safe_float_value(
            air_control_option.value,
            1.0,
            AIR_CONTROL_MIN,
            AIR_CONTROL_MAX,
            "Air Control",
        )
        try:
            current_air_control = float(air_control_option.value)
        except (TypeError, ValueError):
            current_air_control = float("nan")
        if not math.isfinite(current_air_control) or current_air_control != safe_air_control:
            air_control_option.value = safe_air_control
            corrected = True

        if isinstance(legacy_slide, bool):
            if legacy_slide and crouch_mode == CROUCH_SLIDE_OFF:
                crouch_slide_mode_option.value = CROUCH_SLIDE_HOLD
            legacy_slide_from_landing_option.value = None
            corrected = True

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


HOOKS = (
    _set_wants_to_sprint,
    _on_start_sprinting,
    _on_end_sprinting,
    _on_jumped,
    _on_landed_post,
    _movement_mode_changed,
    _movement_component_mode_changed,
    _set_wants_to_slide,
    _client_restart,
)

mod = build_mod(
    options=OPTIONS,
    hooks=HOOKS,
    on_enable=_on_enable,
    on_disable=_on_disable,
)

# build_mod() loads persisted settings before returning. Attach callbacks afterwards so loading
# old settings does not accidentally turn a saved preset into Custom.
profile_option.set_on_change(_on_profile_change, anytime=True, while_enabled=False)
accel_option.set_on_change(_on_accel_change, anytime=True, while_enabled=False)
brake_option.set_on_change(_on_brake_change, anytime=True, while_enabled=False)
air_control_override_option.set_on_change(
    _on_movement_feature_change, anytime=True, while_enabled=False
)
air_control_option.set_on_change(
    _on_movement_feature_change, anytime=True, while_enabled=False
)
any_direction_sprint_option.set_on_change(
    _on_movement_feature_change, anytime=True, while_enabled=False
)
auto_sprint_option.set_on_change(
    _on_auto_sprint_change, anytime=True, while_enabled=False
)
walk_override_option.set_on_change(
    _on_walk_override_change, anytime=True, while_enabled=False
)

_sanitize_loaded_settings(mod)
