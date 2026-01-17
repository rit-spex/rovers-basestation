"""
Input event source using the `inputs` library.
Provides a pygame-free event stream compatible with InputEvent.
"""

from __future__ import annotations

import hashlib
import itertools
import logging
import os
import queue
import threading
import time
import weakref
from collections.abc import Iterable
from typing import Any, Dict, List, Optional, Tuple

from .command_codes import CONSTANTS
from .input_events import (
    JOYAXISMOTION,
    JOYBUTTONDOWN,
    JOYBUTTONUP,
    JOYDEVICEADDED,
    JOYDEVICEREMOVED,
    JOYHATMOTION,
    InputEvent,
)

logger = logging.getLogger(__name__)

try:
    import inputs  # type: ignore

    INPUTS_AVAILABLE = True
except Exception:  # pragma: no cover - environment dependent
    inputs = None
    INPUTS_AVAILABLE = False


class InputSourceError(RuntimeError):
    """Raised for recoverable input source errors."""


class InputEventSource:
    """Background input reader backed by `inputs` library."""

    _fallback_id_counter = itertools.count(1)

    def __init__(self, enable: Optional[bool] = None):
        if enable is None:
            enable = self._default_enable_flag()

        self.enabled = bool(enable and INPUTS_AVAILABLE)
        self._queue: "queue.Queue[InputEvent]" = queue.Queue(maxsize=2000)
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._monitor_thread: Optional[threading.Thread] = None
        self._device_map: Dict[str, int] = {}
        self._device_info: Dict[int, Dict[str, Any]] = {}
        self._device_hat_state: Dict[int, Tuple[int, int]] = {}
        self._device_dpad_state: Dict[int, Dict[str, bool]] = {}
        self._device_hat_source: Dict[int, Optional[str]] = {}
        self._device_object_keys: "weakref.WeakKeyDictionary[Any, str]" = (
            weakref.WeakKeyDictionary()
        )
        self._device_object_key_ids: Dict[int, str] = {}
        self._key_to_device_ref: Dict[str, "weakref.ReferenceType[Any]"] = {}
        self._key_to_device_id: Dict[str, int] = {}
        self._device_key_signatures: Dict[str, Tuple[str, ...]] = {}
        self._signature_to_keys: Dict[Tuple[str, ...], set[str]] = {}
        self._signature_last_seen: Dict[Tuple[str, ...], float] = {}
        self._signature_key_last_seen: Dict[str, float] = {}
        self._signature_ttl_seconds = 60.0
        self._read_timeout_seconds = 0.02
        self._warned_timeout_unsupported = False
        self._warned_blocking_fallback = False
        self._warned_blocking_disabled = False
        self._force_nonblocking = (
            os.getenv("XBEE_INPUTS_FORCE_NONBLOCKING") or ""
        ).lower() in (
            "1",
            "true",
            "yes",
        )
        allow_blocking = (
            os.getenv("XBEE_INPUTS_ALLOW_BLOCKING_READ") or ""
        ).lower() in (
            "1",
            "true",
            "yes",
        )
        self._allow_blocking_read = allow_blocking and not self._force_nonblocking
        self._axis_range_cache: Dict[Tuple[int, str], Tuple[float, float]] = {}
        self._axis_max_cache: Dict[Tuple[int, str], float] = {}
        self._fixed_axis_ranges: Dict[str, float] = {
            "ABS_Z": 255.0,
            "ABS_RZ": 255.0,
            "ABS_LT": 255.0,
            "ABS_RT": 255.0,
        }
        self._fallback_device_stub = type(
            "_FallbackInputDevice",
            (),
            {"name": "Unknown", "device_path": "inputs-fallback"},
        )()
        self._instance_counter = 0
        self._device_lock = threading.Lock()

        if self.enabled:
            self._thread = threading.Thread(target=self._event_loop, daemon=True)
            self._monitor_thread = threading.Thread(
                target=self._device_monitor_loop, daemon=True
            )
            self._thread.start()
            self._monitor_thread.start()
        else:
            logger.info("InputEventSource disabled (inputs unavailable or test mode)")

    def _default_enable_flag(self) -> bool:
        if not INPUTS_AVAILABLE:
            return False
        # Default to disabled under pytest unless explicitly overridden.
        try:
            import sys

            if "pytest" in sys.modules:
                return (os.getenv("XBEE_TEST_ENABLE_INPUTS") or "").lower() in (
                    "1",
                    "true",
                    "yes",
                )
        except Exception:
            pass
        return True

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            join_timeout = 1.0 if self._allow_blocking_read else 0.1
            self._thread.join(timeout=join_timeout)
            if self._thread.is_alive():
                logger.warning("Input event thread did not stop within timeout")
        if self._monitor_thread and self._monitor_thread.is_alive():
            self._monitor_thread.join(timeout=1.0)
            if self._monitor_thread.is_alive():
                logger.warning("Input monitor thread did not stop within timeout")

    def poll_events(self, max_events: int = 100) -> List[InputEvent]:
        """Drain queued input events (non-blocking)."""
        events: List[InputEvent] = []
        while len(events) < max_events:
            try:
                events.append(self._queue.get_nowait())
            except queue.Empty:
                break
        return events

    def inject_event(self, event: InputEvent) -> None:
        """Inject a synthetic event (useful for tests)."""
        self._enqueue_event(event)

    def _enqueue_event(self, event: InputEvent) -> None:
        try:
            self._queue.put_nowait(event)
        except queue.Full:
            if event.type in (JOYDEVICEADDED, JOYDEVICEREMOVED):
                try:
                    self._queue.get_nowait()
                except queue.Empty:
                    pass
                try:
                    self._queue.put_nowait(event)
                    return
                except queue.Full:
                    pass
            logger.warning("Input event queue full; dropping event")

    def _device_monitor_loop(self) -> None:
        if not INPUTS_AVAILABLE:
            return
        while not self._stop_event.is_set():
            try:
                self._sync_devices()
            except Exception:
                logger.exception("Input device monitor error")
            time.sleep(0.5)

    def _event_loop(self) -> None:
        if not INPUTS_AVAILABLE or inputs is None:
            return
        while not self._stop_event.is_set():
            try:
                with self._device_lock:
                    has_devices = bool(self._device_map)
                if not has_devices:
                    time.sleep(0.2)
                    continue
                raw_events = self._read_gamepad_events()
                if not raw_events:
                    time.sleep(0.01)
                    continue
                for raw_event in raw_events:
                    self._handle_raw_event(raw_event)
            except Exception as exc:
                if self._stop_event.is_set():
                    break
                logger.debug("Input event loop exception: %s", exc, exc_info=True)
                time.sleep(0.2)

    def _read_gamepad_events(self) -> List[Any]:
        if inputs is None:
            return []
        try:
            events: List[Any] = []
            gamepads = inputs.devices.gamepads
            for device in gamepads:
                events.extend(self._read_device_events(device))
            if gamepads:
                return events
        except Exception:
            pass
        if not self._allow_blocking_read:
            if not self._warned_blocking_disabled:
                logger.warning(
                    "Blocking fallback disabled; no inputs.get_gamepad() calls will be made"
                )
                self._warned_blocking_disabled = True
            return []
        if not self._warned_blocking_fallback:
            logger.warning(
                "inputs.get_gamepad() is blocking; shutdown may be delayed while waiting for input"
            )
            self._warned_blocking_fallback = True
        return self._coerce_events(inputs.get_gamepad())

    def _read_device_events(self, device: Any) -> List[Any]:
        read_fn = getattr(device, "read", None)
        if not callable(read_fn):
            return []
        try:
            events = read_fn(timeout=self._read_timeout_seconds)
        except TypeError:
            if self._stop_event.is_set():
                return []
            if not self._allow_blocking_read and not self._force_nonblocking:
                self._allow_blocking_read = True
                logger.warning(
                    "inputs device.read() does not support timeouts; "
                    "enabling blocking reads (set XBEE_INPUTS_FORCE_NONBLOCKING=1 to disable)"
                )
            if not self._allow_blocking_read:
                if not self._warned_timeout_unsupported:
                    logger.warning(
                        "inputs device.read() does not support timeouts; "
                        "set XBEE_INPUTS_ALLOW_BLOCKING_READ=1 to enable blocking reads "
                        "(unless XBEE_INPUTS_FORCE_NONBLOCKING=1 is set)"
                    )
                    self._warned_timeout_unsupported = True
                return []
            if not self._warned_blocking_fallback:
                logger.warning(
                    "inputs read() is blocking; shutdown may be delayed while waiting for input"
                )
                self._warned_blocking_fallback = True
            events = read_fn()
        return self._coerce_events(events)

    def _coerce_events(self, events: Any) -> List[Any]:
        if events is None:
            return []
        if isinstance(events, list):
            return events
        if isinstance(events, tuple):
            return list(events)
        if isinstance(events, Iterable):
            return list(events)
        return []

    def _device_key(self, device: Any) -> str:
        with self._device_lock:
            cached_key = self._get_cached_device_key(device)
            if cached_key:
                return cached_key

        base_key = self._get_stable_device_key(device)
        if base_key is None:
            base_key = self._get_fallback_device_key(device)

        return self._cache_device_key(device, base_key)

    def _get_stable_device_key(self, device: Any) -> Optional[str]:
        for attr in ("device_path", "path", "fn", "dev_path"):
            value = getattr(device, attr, None)
            if value:
                return str(value)
        return None

    def _get_fallback_device_key(self, device: Any) -> str:
        name = getattr(device, "name", "unknown")
        stable_parts = [name]
        for attr in (
            "serial",
            "vendor",
            "vendor_id",
            "product",
            "product_id",
            "phys",
        ):
            value = getattr(device, attr, None)
            if value:
                stable_parts.append(str(value))
        if len(stable_parts) > 1:
            digest = hashlib.sha256("|".join(stable_parts).encode("utf-8")).hexdigest()[
                :8
            ]
            return f"{name}-{digest}"
        return f"{name}-{next(self.__class__._fallback_id_counter)}"

    def _device_signature(self, device: Any) -> Tuple[str, ...]:
        signature_parts = []
        for attr in (
            "name",
            "serial",
            "vendor",
            "vendor_id",
            "product",
            "product_id",
            "phys",
        ):
            value = getattr(device, attr, None)
            if value is not None:
                signature_parts.append(str(value))
        return tuple(signature_parts)

    def _get_cached_device_key(self, device: Any) -> Optional[str]:
        try:
            return self._device_object_keys.get(device)
        except TypeError:
            return self._device_object_key_ids.get(id(device))

    def _set_cached_device_key(self, device: Any, key: str) -> None:
        try:
            self._device_object_keys[device] = key
        except TypeError:
            self._device_object_key_ids[id(device)] = key

    def _is_same_device_for_key(self, key: str, device: Any) -> bool:
        existing_ref = self._key_to_device_ref.get(key)
        if existing_ref is not None:
            existing_device = existing_ref()
            if existing_device is None:
                return True
            return existing_device is device
        existing_id = self._key_to_device_id.get(key)
        if existing_id is None:
            return True
        return existing_id == id(device)

    def _track_device_key_owner(self, key: str, device: Any) -> None:
        try:
            self._key_to_device_ref[key] = weakref.ref(device)
            self._key_to_device_id.pop(key, None)
        except TypeError:
            self._key_to_device_id[key] = id(device)

    def _cache_device_key(self, device: Any, base_key: str) -> str:
        signature = self._device_signature(device)
        with self._device_lock:
            cached_key = self._get_cached_device_key(device)
            if cached_key:
                return cached_key
            signature_keys = self._signature_to_keys.get(signature, set())
            key = base_key
            if len(signature_keys) == 1:
                key = next(iter(signature_keys))
            else:
                for candidate in sorted(signature_keys):
                    if self._is_same_device_for_key(candidate, device) or (
                        candidate not in self._device_map
                    ):
                        key = candidate
                        break
            existing_keys = set(self._device_object_keys.values()) | set(
                self._device_object_key_ids.values()
            )
            if key in self._device_map or key in existing_keys:
                if not self._is_same_device_for_key(key, device):
                    key = f"{base_key}-{next(self.__class__._fallback_id_counter)}"
            self._set_cached_device_key(device, key)
            self._device_key_signatures[key] = signature
            self._signature_key_last_seen[key] = time.time()
            if signature:
                signature_keys = set(signature_keys)
                signature_keys.add(key)
                self._signature_to_keys[signature] = signature_keys
                self._signature_last_seen[signature] = time.time()
            self._track_device_key_owner(key, device)
            return key

    def _get_connected_gamepad_devices(self) -> List[Any]:
        """Return a stable list of connected gamepad device objects.

        Isolating this logic makes _sync_devices easier to test and keeps the
        device enumeration robust against platform-specific failures.
        """
        if not INPUTS_AVAILABLE or inputs is None:
            return []
        try:
            gamepads = getattr(inputs, "devices", None)
            if gamepads is None:
                return []
            return list(getattr(gamepads, "gamepads", []))
        except Exception:
            return []

    def _cleanup_device_refs(self, current_ids: set[int]) -> None:
        """Remove cached references to devices that are no longer present.

        This consolidates several removal steps that previously lived inside
        _sync_devices and reduces cyclomatic complexity by delegating work.
        """
        with self._device_lock:
            ref_keys_to_remove: List[str] = []
            for key, ref in self._key_to_device_ref.items():
                device = ref()
                if device is None or id(device) not in current_ids:
                    ref_keys_to_remove.append(key)
            for key in ref_keys_to_remove:
                self._key_to_device_ref.pop(key, None)

            id_keys_to_remove = [
                key
                for key, device_id in self._key_to_device_id.items()
                if device_id not in current_ids
            ]
            for key in id_keys_to_remove:
                self._key_to_device_id.pop(key, None)

            device_id_keys_to_remove = [
                device_id
                for device_id in list(self._device_object_key_ids.keys())
                if device_id not in current_ids
            ]
            for device_id in device_id_keys_to_remove:
                self._device_object_key_ids.pop(device_id, None)

            # Prune signature cache while holding the lock to avoid races with other
            # operations that modify signature bookkeeping.
            self._prune_signature_cache()

    def _sync_devices(self) -> None:
        """Synchronize internal device maps with currently connected gamepads.

        This method enumerates connected devices, removes stale cache entries,
        registers new devices, and removes devices that are no longer present.
        The heavier work is delegated to helpers to keep complexity low.
        """
        if not INPUTS_AVAILABLE:
            return

        devices = self._get_connected_gamepad_devices()

        current_keys = {self._device_key(device) for device in devices}
        current_ids = {id(device) for device in devices}

        # Clean up any references to devices no longer present
        self._cleanup_device_refs(current_ids)

        with self._device_lock:
            known_keys = set(self._device_map.keys())

        # Register newly discovered devices
        for device in devices:
            key = self._device_key(device)
            if key not in known_keys:
                self._register_device(device, key)

        # Remove devices that disappeared
        removed_keys = known_keys - current_keys
        for key in removed_keys:
            self._remove_device(key)

    def _register_device(self, device: Any, key: str) -> None:
        with self._device_lock:
            if key in self._device_map:
                return
            self._instance_counter += 1
            instance_id = self._instance_counter
            self._device_map[key] = instance_id

            name = getattr(device, "name", "Unknown")
            guid = str(getattr(device, "device_path", key))
            self._device_info[instance_id] = {"name": name, "guid": guid}
            self._device_hat_state[instance_id] = (0, 0)
            self._device_dpad_state[instance_id] = {
                "left": False,
                "right": False,
                "up": False,
                "down": False,
            }
            self._device_hat_source[instance_id] = None

        self._enqueue_event(
            InputEvent(
                type=JOYDEVICEADDED,
                instance_id=instance_id,
                device_index=instance_id,
                name=name,
                guid=guid,
            )
        )

    def _remove_device(self, key: str) -> None:
        with self._device_lock:
            instance_id = self._device_map.pop(key, None)
            if instance_id is None:
                return
            self._key_to_device_ref.pop(key, None)
            self._key_to_device_id.pop(key, None)
            signature = self._device_key_signatures.pop(key, None)
            self._signature_key_last_seen[key] = time.time()
            if signature:
                signature_keys = self._signature_to_keys.get(signature)
                if signature_keys is None:
                    self._signature_to_keys[signature] = {key}
                self._signature_last_seen[signature] = time.time()
            ids_to_remove = [
                device_id
                for device_id, cached_key in self._device_object_key_ids.items()
                if cached_key == key
            ]
            for device_id in ids_to_remove:
                self._device_object_key_ids.pop(device_id, None)
            self._device_hat_state.pop(instance_id, None)
            self._device_dpad_state.pop(instance_id, None)
            self._device_hat_source.pop(instance_id, None)
            self._device_info.pop(instance_id, None)
            self._axis_max_cache = {
                k: v for k, v in self._axis_max_cache.items() if k[0] != instance_id
            }
            self._axis_range_cache = {
                k: v for k, v in self._axis_range_cache.items() if k[0] != instance_id
            }
        self._enqueue_event(
            InputEvent(
                type=JOYDEVICEREMOVED, instance_id=instance_id, device_index=instance_id
            )
        )

    def _handle_raw_event(self, raw_event: Any) -> None:
        device = getattr(raw_event, "device", None)
        if device is None:
            device = self._get_fallback_device()
        if device is None:
            return
        device_key = self._device_key(device)
        with self._device_lock:
            instance_id = self._device_map.get(device_key)

        if instance_id is None:
            self._register_device(device, device_key)
            with self._device_lock:
                instance_id = self._device_map.get(device_key)

        if instance_id is None:
            return

        with self._device_lock:
            info = self._device_info.get(instance_id, {})
        controller_type = self._detect_controller_type(info.get("name"))

        event = self._map_raw_event(
            raw_event,
            instance_id,
            controller_type,
            info.get("name"),
            info.get("guid"),
        )
        if event is None:
            return

        self._enqueue_event(event)

    def _get_fallback_device(self) -> Optional[Any]:
        if inputs is None:
            return None
        try:
            gamepads = inputs.devices.gamepads
            return gamepads[0] if gamepads else self._fallback_device_stub
        except Exception:
            return self._fallback_device_stub

    def _detect_controller_type(self, name: Optional[str]) -> Optional[str]:
        if not isinstance(name, str):
            return None
        lname = name.lower()
        if "xbox" in lname or "x-box" in lname:
            return CONSTANTS.XBOX.NAME
        if (
            "n64" in lname
            or "dinput" in lname
            or "directinput" in lname
            or "direct input" in lname
        ):
            return CONSTANTS.N64.NAME
        return None

    def _map_raw_event(
        self,
        raw_event: Any,
        instance_id: int,
        controller_type: Optional[str],
        name: Optional[str],
        guid: Optional[str],
    ) -> Optional[InputEvent]:
        code = getattr(raw_event, "code", None)
        state = getattr(raw_event, "state", None)

        if code is None:
            return None

        hat_event = self._handle_hat_event(code, state, instance_id, name, guid)
        if hat_event is not None:
            return hat_event

        axis_index = self._map_axis_code(code, controller_type)
        if axis_index is not None:
            value = self._normalize_axis_value(state, code, instance_id)
            return InputEvent(
                type=JOYAXISMOTION,
                instance_id=instance_id,
                axis=axis_index,
                value=value,
                name=name,
                guid=guid,
                raw_code=code,
                raw_state=state,
            )

        button_index = self._map_button_code(code, controller_type)
        if button_index is not None:
            pressed = bool(state)
            event_type = JOYBUTTONDOWN if pressed else JOYBUTTONUP
            return InputEvent(
                type=event_type,
                instance_id=instance_id,
                button=button_index,
                value=pressed,
                name=name,
                guid=guid,
                raw_code=code,
                raw_state=state,
            )

        return None

    def _handle_hat_event(
        self,
        code: str,
        state: Any,
        instance_id: int,
        name: Optional[str],
        guid: Optional[str],
    ) -> Optional[InputEvent]:
        if code not in (
            "ABS_HAT0X",
            "ABS_HAT0Y",
            "BTN_DPAD_UP",
            "BTN_DPAD_DOWN",
            "BTN_DPAD_LEFT",
            "BTN_DPAD_RIGHT",
        ):
            return None

        try:
            val = int(state)
        except Exception:
            val = 0

        with self._device_lock:
            x, y = self._device_hat_state.get(instance_id, (0, 0))
            source = self._device_hat_source.get(instance_id)
            if code in ("ABS_HAT0X", "ABS_HAT0Y"):
                if source != "axis":
                    self._device_hat_source[instance_id] = "axis"
                    dpad_state = self._device_dpad_state.get(instance_id)
                    if dpad_state is not None:
                        for key in dpad_state:
                            dpad_state[key] = False
                x, y = self._apply_hat_axis(code, val, x, y)
            else:
                if source == "axis":
                    return None
                self._device_hat_source[instance_id] = "button"
                x, y = self._apply_dpad_button_unlocked(code, bool(val), instance_id)
            self._device_hat_state[instance_id] = (x, y)

        return InputEvent(
            type=JOYHATMOTION,
            instance_id=instance_id,
            value=(x, y),
            name=name,
            guid=guid,
            raw_code=code,
            raw_state=state,
        )

    def _apply_hat_axis(self, code: str, val: int, x: int, y: int) -> Tuple[int, int]:
        if code == "ABS_HAT0X":
            x = max(-1, min(1, val))
        else:
            y = max(-1, min(1, val))
        return x, y

    def _apply_dpad_button(
        self, code: str, pressed: bool, instance_id: int
    ) -> Tuple[int, int]:
        with self._device_lock:
            return self._apply_dpad_button_unlocked(code, pressed, instance_id)

    def _apply_dpad_button_unlocked(
        self, code: str, pressed: bool, instance_id: int
    ) -> Tuple[int, int]:
        mapping = {
            "BTN_DPAD_LEFT": "left",
            "BTN_DPAD_RIGHT": "right",
            "BTN_DPAD_UP": "up",
            "BTN_DPAD_DOWN": "down",
        }
        key = mapping.get(code)
        if key is None:
            return (0, 0)
        state = self._device_dpad_state.get(instance_id)
        if state is None:
            state = {"left": False, "right": False, "up": False, "down": False}
            self._device_dpad_state[instance_id] = state
        state[key] = pressed
        left = state["left"]
        right = state["right"]
        up = state["up"]
        down = state["down"]
        x = 0
        if left and not right:
            x = -1
        elif right and not left:
            x = 1

        y = 0
        if up and not down:
            y = 1
        elif down and not up:
            y = -1
        return x, y

    def _map_axis_code(
        self, code: str, controller_type: Optional[str]
    ) -> Optional[int]:
        xbox_map = {
            "ABS_X": CONSTANTS.XBOX.JOYSTICK.AXIS_LX,
            "ABS_Y": CONSTANTS.XBOX.JOYSTICK.AXIS_LY,
            "ABS_RX": CONSTANTS.XBOX.JOYSTICK.AXIS_RX,
            "ABS_RY": CONSTANTS.XBOX.JOYSTICK.AXIS_RY,
            "ABS_Z": CONSTANTS.XBOX.TRIGGER.AXIS_LT,
            "ABS_RZ": CONSTANTS.XBOX.TRIGGER.AXIS_RT,
            "ABS_LT": CONSTANTS.XBOX.TRIGGER.AXIS_LT,
            "ABS_RT": CONSTANTS.XBOX.TRIGGER.AXIS_RT,
        }

        n64_map = {
            "ABS_X": CONSTANTS.N64.JOYSTICK.AXIS_X,
            "ABS_Y": CONSTANTS.N64.JOYSTICK.AXIS_Y,
        }

        if controller_type == CONSTANTS.N64.NAME:
            return n64_map.get(code)
        if controller_type == CONSTANTS.XBOX.NAME or controller_type is None:
            return xbox_map.get(code)
        return None

    def _map_button_code(
        self, code: str, controller_type: Optional[str]
    ) -> Optional[int]:
        xbox_map = {
            "BTN_SOUTH": CONSTANTS.XBOX.BUTTON.A,
            "BTN_EAST": CONSTANTS.XBOX.BUTTON.B,
            "BTN_WEST": CONSTANTS.XBOX.BUTTON.X,
            "BTN_NORTH": CONSTANTS.XBOX.BUTTON.Y,
            "BTN_TL": CONSTANTS.XBOX.BUTTON.LEFT_BUMPER,
            "BTN_TR": CONSTANTS.XBOX.BUTTON.RIGHT_BUMPER,
            "BTN_SELECT": CONSTANTS.XBOX.BUTTON.SELECT,
            "BTN_START": CONSTANTS.XBOX.BUTTON.START,
            "BTN_MODE": CONSTANTS.XBOX.BUTTON.HOME,
            "BTN_THUMBL": CONSTANTS.XBOX.BUTTON.LEFT_STICK,
            "BTN_THUMBR": CONSTANTS.XBOX.BUTTON.RIGHT_STICK,
        }

        n64_map = {
            "BTN_SOUTH": CONSTANTS.N64.BUTTON.A,
            "BTN_EAST": CONSTANTS.N64.BUTTON.B,
            "BTN_NORTH": CONSTANTS.N64.BUTTON.C_UP,
            "BTN_WEST": CONSTANTS.N64.BUTTON.C_LEFT,
            "BTN_TL": CONSTANTS.N64.BUTTON.L,
            "BTN_TR": CONSTANTS.N64.BUTTON.R,
            "BTN_SELECT": CONSTANTS.N64.BUTTON.Z,
            "BTN_START": CONSTANTS.N64.BUTTON.START,
            "BTN_MODE": CONSTANTS.N64.BUTTON.Z,
        }

        if controller_type == CONSTANTS.N64.NAME:
            return n64_map.get(code)
        if controller_type == CONSTANTS.XBOX.NAME or controller_type is None:
            return xbox_map.get(code)
        return None

    def _select_axis_max(self, axis_key: Tuple[int, str], observed: float) -> float:
        with self._device_lock:
            cached = self._axis_max_cache.get(axis_key)
            fixed = self._fixed_axis_ranges.get(axis_key[1], 0.0)
            if cached is None:
                cached = fixed
            if observed > cached:
                cached = observed
            self._axis_max_cache[axis_key] = cached

        return max(cached, 1.0)

    def _update_axis_range(
        self, axis_key: Tuple[int, str], value: float
    ) -> Tuple[float, float]:
        with self._device_lock:
            current = self._axis_range_cache.get(axis_key)
            if current is None:
                current = (value, value)
            else:
                current = (min(current[0], value), max(current[1], value))
            self._axis_range_cache[axis_key] = current
            return current

    def _prune_signature_cache(self) -> None:
        now = time.time()
        stale_signatures: List[Tuple[str, ...]] = []
        for signature, keys in self._signature_to_keys.items():
            stale_keys = [
                key
                for key in keys
                if key not in self._device_map
                and (now - self._signature_key_last_seen.get(key, now))
                > self._signature_ttl_seconds
            ]
            for key in stale_keys:
                keys.discard(key)
                self._signature_key_last_seen.pop(key, None)

            if not keys:
                stale_signatures.append(signature)

        for signature in stale_signatures:
            self._signature_to_keys.pop(signature, None)
            self._signature_last_seen.pop(signature, None)

    def _normalize_axis_value(self, state: Any, code: str, instance_id: int) -> float:
        if state is None:
            return 0.0
        try:
            value = float(state)
        except Exception:
            return 0.0

        axis_key = (instance_id, code)
        max_val = self._select_axis_max(axis_key, abs(value))

        if max_val <= 0:
            return 0.0

        # Trigger axes should map to [0, 1]
        if code in ("ABS_Z", "ABS_RZ", "ABS_LT", "ABS_RT"):
            return max(0.0, min(1.0, value / max_val))

        # Joystick axes map to [-1, 1] around center
        range_min, range_max = self._update_axis_range(axis_key, value)
        center = (range_min + range_max) / 2.0
        span = max(range_max - center, center - range_min, 1.0)
        return max(-1.0, min(1.0, (value - center) / span))
