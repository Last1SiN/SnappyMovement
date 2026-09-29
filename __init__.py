from __future__ import annotations

import math
from typing import Any

import unrealsdk
from mods_base import BoolOption, Game, Mod, SliderOption, SpinnerOption, build_mod, get_pc, hook
from unrealsdk import logging
from unrealsdk.hooks import Type, add_hook, remove_hook
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

remember_sprint_option = BoolOption(
    identifier="remember_sprint",
    value=False,
    display_name="Remember Sprint",
    description=(
        "Remembers sprint intent through jumps and slide-jumps, then lets the game "
        "resume sprint after landing without another sprint press."
    ),
)

slide_from_landing_option = BoolOption(
    identifier="slide_from_landing",
    value=False,
    display_name="Slide from Landing",
    description=(
        "If crouch is still held as you land, asks the game to start its native slide "
        "instead of requiring another crouch press."
    ),
)

OPTIONS = (
    profile_option,
    accel_option,
    brake_option,
    remember_sprint_option,
    slide_from_landing_option,
)

_syncing_options = False
_patched_components: list[tuple[UObject, float, float]] = []

_sprint_chain_armed = False
_resume_sprint_after_landing = False
_restoring_sprint = False
_landing_crouch_pending = False
_landing_transition_pending = False
_air_slide_intent = False

_CROUCH_INPUT_FN_4 = (
    "GbxInpActEvt_InputAction_Discrete_Crouch_"
    "K2Node_GbxInputActionEvent_Discrete_4"
)
_CROUCH_INPUT_FN_5 = (
    "GbxInpActEvt_InputAction_Discrete_Crouch_"
    "K2Node_GbxInputActionEvent_Discrete_5"
)
_CROUCH_FLUSH_FN = "FlushCrouchInput"
_CROUCH_DYNAMIC_ID_PREFIX = "snappymovement:crouch-input-diag:v1.1.8"
_crouch_dynamic_hooks: list[tuple[str, str]] = []

_GBX_DISCRETE_ACTION_HOOK = "/Script/GbxInput.GbxInputComponent:StartInputAction_Discrete_Impl"


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



@hook(_GBX_DISCRETE_ACTION_HOOK, Type.POST)
def _gbx_discrete_action_probe(
    obj: UObject,
    args: WrappedStruct,
    _ret: Any,
    _func: BoundFunction,
) -> None:
    try:
        action = args.DiscreteAction
    except Exception:
        return

    try:
        action_name = str(action.ActionName)
    except Exception:
        action_name = "<unreadable>"

    if action_name.lower() != "crouch":
        return

    pawn = _get_current_pawn()
    movement = _get_move_component(pawn) if pawn is not None else None
    try:
        consumed = bool(args.bConsumeEvent)
    except Exception:
        consumed = False

    logging.warning(
        "[SnappyMovement actiondiag] Crouch "
        f"component={_path(obj)!r} action={_path(action)!r} "
        f"consume={consumed} pawn={_path(pawn)!r} "
        f"falling={_is_falling(pawn)} "
        f"wants_crouch={_wants_crouch(pawn)} "
        f"wants_slide={_movement_flag(movement, 'bWantsToSlide')}"
    )


def _binding_event_debug(value: Any) -> tuple[str, str]:
    try:
        event_name = str(value.name)
    except Exception:
        event_name = str(value)
    try:
        raw = getattr(value, "value", value)
        event_value = str(int(raw))
    except Exception:
        event_value = repr(value)
    return event_name, event_value


def _log_crouch_binding_metadata(cls: UObject) -> bool:
    class_path = _path(cls)

    try:
        dynamic_bindings = list(cls.DynamicBindingObjects)
    except Exception as exc:
        logging.warning(
            "[SnappyMovement bindingdiag] DynamicBindingObjects unavailable "
            f"class={class_path!r} error={type(exc).__name__}:{exc}"
        )
        return False

    logging.warning(
        "[SnappyMovement bindingdiag] dynamic bindings "
        f"class={class_path!r} count={len(dynamic_bindings)} "
        f"paths={[ _path(x) for x in dynamic_bindings ]!r}"
    )

    matches = 0
    for binding_obj in dynamic_bindings:
        try:
            entries = list(binding_obj.InputActionReceiverDelegateBindings)
        except Exception:
            continue

        for entry in entries:
            try:
                action = entry.Action
            except Exception:
                action = None

            try:
                action_name = str(action.ActionName)
            except Exception:
                action_name = "<unreadable>"

            if action_name.lower() != "crouch":
                continue

            try:
                input_event = entry.InputEvent
            except Exception:
                input_event = None
            event_name, event_value = _binding_event_debug(input_event)

            try:
                function_name = str(entry.FunctionNameToBind)
            except Exception:
                function_name = "<unreadable>"

            function_path = f"{class_path}:{function_name}"
            try:
                found = unrealsdk.find_object("Function", function_path) is not None
            except Exception:
                found = False

            matches += 1
            logging.warning(
                "[SnappyMovement bindingdiag] Crouch binding "
                f"binding={_path(binding_obj)!r} "
                f"action={_path(action)!r} "
                f"input_event_name={event_name!r} "
                f"input_event_value={event_value!r} "
                f"function={function_name!r} "
                f"path={function_path!r} found={found}"
            )

    logging.warning(
        "[SnappyMovement bindingdiag] Crouch binding summary "
        f"class={class_path!r} matches={matches}"
    )
    return matches > 0


def _crouch_probe_callback(
    obj: UObject,
    args: WrappedStruct,
    _ret: Any,
    func: BoundFunction,
) -> None:
    pawn = _get_current_pawn()
    movement = _get_move_component(pawn) if pawn is not None else None

    try:
        action = args.Action
    except Exception:
        action = None

    try:
        action_name = str(action.ActionName)
    except Exception:
        action_name = "<unreadable>"

    function_path = _bound_function_path(func)
    if function_path.endswith(_CROUCH_INPUT_FN_4):
        input_event = "IE_Pressed"
    elif function_path.endswith(_CROUCH_INPUT_FN_5):
        input_event = "IE_Released"
    else:
        input_event = "<unknown>"

    logging.warning(
        "[SnappyMovement crouchdiag] event "
        f"input_event={input_event!r} "
        f"func={function_path!r} "
        f"ability={_path(obj)!r} "
        f"action={_path(action)!r} action_name={action_name!r} "
        f"pawn={_path(pawn)!r} "
        f"falling={_is_falling(pawn)} "
        f"wants_crouch={_wants_crouch(pawn)} "
        f"wants_slide={_movement_flag(movement, 'bWantsToSlide')}"
    )


def _crouch_flush_probe(
    obj: UObject,
    _args: WrappedStruct,
    _ret: Any,
    func: BoundFunction,
) -> None:
    pawn = _get_current_pawn()
    movement = _get_move_component(pawn) if pawn is not None else None
    logging.warning(
        "[SnappyMovement crouchdiag] flush "
        f"func={_bound_function_path(func)!r} "
        f"ability={_path(obj)!r} "
        f"pawn={_path(pawn)!r} "
        f"falling={_is_falling(pawn)} "
        f"wants_crouch={_wants_crouch(pawn)} "
        f"wants_slide={_movement_flag(movement, 'bWantsToSlide')}"
    )


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
    except Exception as exc:
        logging.warning(
            "[SnappyMovement crouchdiag] ability search failed "
            f"error={type(exc).__name__}:{exc}"
        )
        return False

    live_abilities = []
    for ability in abilities:
        path = _path(ability)
        if "Default__" in path:
            continue
        live_abilities.append(ability)

    logging.warning(
        "[SnappyMovement crouchdiag] ability search "
        f"total={len(abilities)} live={len(live_abilities)} "
        f"paths={[ _path(x) for x in live_abilities ]!r}"
    )

    if not live_abilities:
        return False

    cls = live_abilities[0].Class
    class_path = _path(cls)
    logging.warning(
        "[SnappyMovement crouchdiag] class "
        f"path={class_path!r}"
    )

    _log_crouch_binding_metadata(cls)

    targets = (
        (_CROUCH_INPUT_FN_4, _crouch_probe_callback),
        (_CROUCH_INPUT_FN_5, _crouch_probe_callback),
        (_CROUCH_FLUSH_FN, _crouch_flush_probe),
    )

    installed: list[tuple[str, str]] = []
    for index, (name, callback) in enumerate(targets):
        path = f"{class_path}:{name}"
        try:
            fn = unrealsdk.find_object("Function", path)
            found = fn is not None
        except Exception:
            found = False

        logging.warning(
            "[SnappyMovement crouchdiag] resolve "
            f"path={path!r} found={found}"
        )
        if not found:
            continue

        identifier = f"{_CROUCH_DYNAMIC_ID_PREFIX}:{index}"
        try:
            add_hook(path, Type.POST, identifier, callback)
        except Exception as exc:
            logging.warning(
                "[SnappyMovement crouchdiag] hook install failed "
                f"path={path!r} error={type(exc).__name__}:{exc}"
            )
            continue

        installed.append((path, identifier))
        logging.warning(
            "[SnappyMovement crouchdiag] hook installed "
            f"path={path!r}"
        )

    _crouch_dynamic_hooks = installed
    return len(installed) >= 2


def _reset_flow_state() -> None:
    global _sprint_chain_armed
    global _resume_sprint_after_landing
    global _restoring_sprint
    global _landing_crouch_pending
    global _landing_transition_pending
    global _air_slide_intent

    _sprint_chain_armed = False
    _resume_sprint_after_landing = False
    _restoring_sprint = False
    _landing_crouch_pending = False
    _landing_transition_pending = False
    _air_slide_intent = False


def _restore_remembered_sprint(pawn: UObject | None, reason: str) -> bool:
    global _resume_sprint_after_landing
    global _restoring_sprint
    global _sprint_chain_armed

    if pawn is None or not bool(remember_sprint_option.value):
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
    logging.warning(f"[SnappyMovement test] Remember Sprint restored after {reason}")
    return True


def _on_enable() -> None:
    _reset_flow_state()
    _apply_current_values()
    controller = _find_local_controller()
    pawn = _get_current_pawn()
    logging.warning(
        "[SnappyMovement test] enabled "
        f"remember_sprint={bool(remember_sprint_option.value)} "
        f"slide_from_landing={bool(slide_from_landing_option.value)} "
        f"controller={_path(controller)!r} pawn={_path(pawn)!r}"
    )
    try:
        _gbx_target = unrealsdk.find_object("Function", _GBX_DISCRETE_ACTION_HOOK)
        _gbx_found = _gbx_target is not None
    except Exception:
        _gbx_found = False
    logging.warning(
        "[SnappyMovement actiondiag] target "
        f"path={_GBX_DISCRETE_ACTION_HOOK!r} found={_gbx_found}"
    )
    _install_crouch_dynamic_hooks()


def _on_disable() -> None:
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

    logging.warning(
        "[SnappyMovement raw] SetWantsToSprint "
        f"obj={_path(obj)!r} current={_path(_get_current_pawn())!r}"
    )

    if _restoring_sprint or not _same_uobject(obj, _get_current_pawn()):
        return

    try:
        requested = bool(args.bNewWantsToSprint)
    except Exception:
        return

    logging.warning(
        "[SnappyMovement test] SetWantsToSprint "
        f"requested={requested} restoring={_restoring_sprint}"
    )

    if requested:
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

    logging.warning("[SnappyMovement test] OnStartSprinting")
    if bool(remember_sprint_option.value):
        _sprint_chain_armed = True


@hook("/Script/OakGame.OakCharacter:OnEndSprinting", Type.POST)
def _on_end_sprinting(
    obj: UObject,
    _args: WrappedStruct,
    _ret: Any,
    _func: BoundFunction,
) -> None:
    global _sprint_chain_armed

    if not _same_uobject(obj, _get_current_pawn()) or not bool(remember_sprint_option.value):
        return

    logging.warning(
        "[SnappyMovement test] OnEndSprinting "
        f"falling={_is_falling(obj)} sliding={_is_sliding(obj)} "
        f"wants={_wants_sprint(obj)}"
    )

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

    logging.warning(
        "[SnappyMovement raw] OnJumped "
        f"obj={_path(obj)!r} current={_path(_get_current_pawn())!r}"
    )
    _install_crouch_dynamic_hooks()

    if not _same_uobject(obj, _get_current_pawn()):
        return

    _landing_crouch_pending = False

    if not bool(remember_sprint_option.value):
        _resume_sprint_after_landing = False
        return

    component = _get_move_component(obj)
    sprint_related = (
        _sprint_chain_armed
        or _wants_sprint(obj)
        or _movement_flag(component, "bIsSprinting")
    )
    _resume_sprint_after_landing = bool(sprint_related)

    logging.warning(
        "[SnappyMovement test] OnJumped "
        f"sprint_related={sprint_related} "
        f"remember_pending={_resume_sprint_after_landing}"
    )

    if _resume_sprint_after_landing:
        logging.warning("[SnappyMovement test] Remember Sprint armed for landing")


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

    logging.warning(
        "[SnappyMovement raw] OnLanded "
        f"obj={_path(obj)!r} current={_path(_get_current_pawn())!r}"
    )

    if not _same_uobject(obj, _get_current_pawn()):
        return

    _landing_transition_pending = True
    _landing_crouch_pending = bool(slide_from_landing_option.value) and (
        _wants_crouch(obj) or _air_slide_intent
    )

    logging.warning(
        "[SnappyMovement test] landing captured POST "
        f"crouch={_landing_crouch_pending} "
        f"air_slide_intent={_air_slide_intent} "
        f"remember_pending={_resume_sprint_after_landing}"
    )


def _finalize_landing_after_walking(pawn: UObject | None, source: str) -> None:
    global _landing_crouch_pending
    global _landing_transition_pending
    global _air_slide_intent

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
    if bool(slide_from_landing_option.value) and _landing_crouch_pending:
        try:
            pawn.SetWantsToSlide(True)
            slide_requested = True
            logging.warning(
                "[SnappyMovement test] Slide from Landing requested "
                f"after {source} MOVE_Walking"
            )
        except Exception as exc:
            _error(f"Slide from Landing: failed to request native slide: {exc}")

    _landing_crouch_pending = False
    _air_slide_intent = False

    if not slide_requested:
        restored = _restore_remembered_sprint(pawn, f"{source} MOVE_Walking")
        logging.warning(
            "[SnappyMovement test] landing finalized "
            f"source={source} remember_restored={restored}"
        )


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

    logging.warning(
        "[SnappyMovement test] K2 movement mode "
        f"new={new_mode} pending={_landing_transition_pending}"
    )

    if new_mode == 1:
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

    logging.warning(
        "[SnappyMovement test] movement component mode "
        f"new={new_mode} pending={_landing_transition_pending}"
    )

    if new_mode == 1:
        _finalize_landing_after_walking(pawn, "SetMovementMode")


@hook("/Script/OakGame.OakCharacter:SetWantsToSlide", Type.POST)
def _set_wants_to_slide(
    obj: UObject,
    args: WrappedStruct,
    _ret: Any,
    _func: BoundFunction,
) -> None:
    global _air_slide_intent

    logging.warning(
        "[SnappyMovement raw] SetWantsToSlide "
        f"obj={_path(obj)!r} current={_path(_get_current_pawn())!r}"
    )

    if not _same_uobject(obj, _get_current_pawn()):
        return

    try:
        requested = bool(args.bNewWantsToSlide)
    except Exception:
        return

    falling = _is_falling(obj)
    logging.warning(
        "[SnappyMovement test] SetWantsToSlide "
        f"requested={requested} falling={falling}"
    )

    if bool(slide_from_landing_option.value) and falling:
        _air_slide_intent = requested

    if requested:
        return

    if _resume_sprint_after_landing and not falling and not _is_sliding(obj):
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


HOOKS = (
    _set_wants_to_sprint,
    _on_start_sprinting,
    _on_end_sprinting,
    _on_jumped,
    _on_landed_post,
    _movement_mode_changed,
    _movement_component_mode_changed,
    _set_wants_to_slide,
    _gbx_discrete_action_probe,
    _client_restart,
)

mod = build_mod(
    options=OPTIONS,
    hooks=HOOKS,
    on_enable=_on_enable,
    on_disable=_on_disable,
)

for _hook_obj in HOOKS:
    try:
        _expected = len(_hook_obj.hook_funcs)
        _active = _hook_obj.get_active_count()
        if mod.is_enabled and _active != _expected:
            _hook_obj.enable()
            _active = _hook_obj.get_active_count()
        logging.warning(
            "[SnappyMovement hookcheck] "
            f"name={_hook_obj.__name__} active={_active}/{_expected}"
        )
    except Exception as exc:
        logging.error(
            "[SnappyMovement hookcheck] "
            f"name={getattr(_hook_obj, '__name__', '<unknown>')} "
            f"error={type(exc).__name__}:{exc}"
        )

# build_mod() loads persisted settings before returning. Attach callbacks afterwards so loading
# old settings does not accidentally turn a saved preset into Custom.
profile_option.set_on_change(_on_profile_change, anytime=True, while_enabled=False)
accel_option.set_on_change(_on_accel_change, anytime=True, while_enabled=False)
brake_option.set_on_change(_on_brake_change, anytime=True, while_enabled=False)

_sanitize_loaded_settings(mod)
