"""
Input event source using the ``inputs`` library.

Provides a cross-platform event stream that emits InputEvent objects without
requiring pygame.  The class enumerates connected gamepads in a background
thread, reads raw events, maps them to controller-agnostic InputEvent values,
and posts them to a thread-safe queue that the main loop polls.

DATA FLOW
---------
OS HID events  -->  inputs library  -->  InputEventSource._event_loop
    -->  _map_raw_event  -->  Queue  -->  poll_events()  -->  BaseStation
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

from xbee.config.constants import CONSTANTS
from xbee.controller.detection import detect_controller_type
from xbee.controller.events import (
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
    """Background input reader backed by the ``inputs`` library.

    Call ``poll_events()`` from your main loop to drain queued events.
    Call ``stop()`` to shut down all background threads.
    """

    _fallback_id_counter = itertools.count(1)

    def __init__(self, enable: Optional[bool] = None):
        if enable is None:
            enable = self._default_enable_flag()

        self.enabled = bool(enable and INPUTS_AVAILABLE)
        self._queue: "queue.Queue[InputEvent]" = queue.Queue(maxsize=2000)
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._monitor_thread: Optional[threading.Thread] = None

        # Device tracking
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
        ).lower() in ("1", "true", "yes")
        allow_blocking = (
            os.getenv("XBEE_INPUTS_ALLOW_BLOCKING_READ") or ""
        ).lower() in ("1", "true", "yes")
        self._allow_blocking_read = allow_blocking and not self._force_nonblocking
        self._axis_range_cache: Dict[Tuple[int, str], Tuple[float, float]] = {}
        self._axis_max_cache: Dict[Tuple[int, str], float] = {}
        self._axis_joystick_mode_cache: Dict[Tuple[int, str], str] = {}
        raw_mode = (os.getenv("XBEE_JOYSTICK_RAW_MODE") or "").strip().lower()
        if raw_mode in ("signed", "unsigned"):
            self._forced_joystick_mode: Optional[str] = raw_mode
        else:
            if raw_mode:
                logger.warning(
                    "Invalid XBEE_JOYSTICK_RAW_MODE=%r; expected 'signed' or 'unsigned'",
                    raw_mode,
                )
            self._forced_joystick_mode = None
        self._fixed_axis_ranges: Dict[str, float] = {
            "ABS_Z": 255.0,
            "ABS_RZ": 255.0,
            "ABS_LT": 255.0,
            "ABS_RT": 255.0,
        }
        self._fixed_joystick_bounds: Dict[str, Tuple[float, float]] = {
            "ABS_X": (-32768.0, 32767.0),
            "ABS_Y": (-32768.0, 32767.0),
            "ABS_RX": (-32768.0, 32767.0),
            "ABS_RY": (-32768.0, 32767.0),
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

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def stop(self) -> None:
        """Signal background threads to stop and wait for them."""
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

    # ------------------------------------------------------------------
    # Defaults
    # ------------------------------------------------------------------

    @staticmethod
    def _default_enable_flag() -> bool:
        if not INPUTS_AVAILABLE:
            return False
        try:
            import sys
            if "pytest" in sys.modules:
                return (os.getenv("XBEE_TEST_ENABLE_INPUTS") or "").lower() in (
                    "1", "true", "yes",
                )
        except Exception:
            pass
        return True

    # ------------------------------------------------------------------
    # Event queue
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Background threads
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Reading raw events
    # ------------------------------------------------------------------

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
                logger.warning("Blocking fallback disabled; no inputs.get_gamepad() calls")
                self._warned_blocking_disabled = True
            return []
        if not self._warned_blocking_fallback:
            logger.warning("inputs.get_gamepad() is blocking; shutdown may be delayed")
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
                    "inputs device.read() does not support timeouts; enabling blocking reads"
                )
            if not self._allow_blocking_read:
                if not self._warned_timeout_unsupported:
                    logger.warning("inputs device.read() does not support timeouts")
                    self._warned_timeout_unsupported = True
                return []
            if not self._warned_blocking_fallback:
                logger.warning("inputs read() is blocking; shutdown may be delayed")
                self._warned_blocking_fallback = True
            events = read_fn()
        return self._coerce_events(events)

    @staticmethod
    def _coerce_events(events: Any) -> List[Any]:
        if events is None:
            return []
        if isinstance(events, (list, tuple)):
            return list(events)
        if isinstance(events, Iterable):
            return list(events)
        return []

    # ------------------------------------------------------------------
    # Device key management
    # ------------------------------------------------------------------

    def _device_key(self, device: Any) -> str:
        with self._device_lock:
            cached_key = self._get_cached_device_key(device)
            if cached_key:
                return cached_key

        base_key = self._get_stable_device_key(device)
        if base_key is None:
            base_key = self._get_fallback_device_key(device)

        return self._cache_device_key(device, base_key)

    @staticmethod
    def _get_stable_device_key(device: Any) -> Optional[str]:
        for attr in ("device_path", "path", "fn", "dev_path"):
            value = getattr(device, attr, None)
            if value:
                return str(value)
        return None

    def _get_fallback_device_key(self, device: Any) -> str:
        name = getattr(device, "name", "unknown")
        stable_parts = [name]
        for attr in ("serial", "vendor", "vendor_id", "product", "product_id", "phys"):
            value = getattr(device, attr, None)
            if value:
                stable_parts.append(str(value))
        if len(stable_parts) > 1:
            digest = hashlib.sha256("|".join(stable_parts).encode("utf-8")).hexdigest()[:8]
            return f"{name}-{digest}"
        return f"{name}-{next(self.__class__._fallback_id_counter)}"

    def _device_signature(self, device: Any) -> Tuple[str, ...]:
        parts = []
        for attr in ("name", "serial", "vendor", "vendor_id", "product", "product_id", "phys"):
            value = getattr(device, attr, None)
            if value is not None:
                parts.append(str(value))
        return tuple(parts)

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

    # ------------------------------------------------------------------
    # Device sync (hotplug)
    # ------------------------------------------------------------------

    def _get_connected_gamepad_devices(self) -> List[Any]:
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
        with self._device_lock:
            ref_keys_to_remove = [
                key for key, ref in self._key_to_device_ref.items()
                if ref() is None or id(ref()) not in current_ids
            ]
            for key in ref_keys_to_remove:
                self._key_to_device_ref.pop(key, None)

            id_keys_to_remove = [
                key for key, device_id in self._key_to_device_id.items()
                if device_id not in current_ids
            ]
            for key in id_keys_to_remove:
                self._key_to_device_id.pop(key, None)

            for device_id in [
                did for did in self._device_object_key_ids
                if did not in current_ids
            ]:
                self._device_object_key_ids.pop(device_id, None)

            self._prune_signature_cache()

    def _sync_devices(self) -> None:
        if not INPUTS_AVAILABLE:
            return

        devices = self._get_connected_gamepad_devices()
        current_keys = {self._device_key(device) for device in devices}
        current_ids = {id(device) for device in devices}

        self._cleanup_device_refs(current_ids)

        with self._device_lock:
            known_keys = set(self._device_map.keys())

        for device in devices:
            key = self._device_key(device)
            if key not in known_keys:
                self._register_device(device, key)

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
                "left": False, "right": False, "up": False, "down": False,
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
                sig_keys = self._signature_to_keys.get(signature)
                if sig_keys is None:
                    self._signature_to_keys[signature] = {key}
                self._signature_last_seen[signature] = time.time()
            for device_id in [
                did for did, cached_key in self._device_object_key_ids.items()
                if cached_key == key
            ]:
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
            self._axis_joystick_mode_cache = {
                k: v for k, v in self._axis_joystick_mode_cache.items() if k[0] != instance_id
            }
        self._enqueue_event(
            InputEvent(
                type=JOYDEVICEREMOVED, instance_id=instance_id, device_index=instance_id
            )
        )

    # ------------------------------------------------------------------
    # Raw event mapping
    # ------------------------------------------------------------------

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

        # Use centralized controller type detection
        controller_type = detect_controller_type(info.get("name", ""))

        event = self._map_raw_event(
            raw_event, instance_id, controller_type,
            info.get("name"), info.get("guid"),
        )
        if event is not None:
            self._enqueue_event(event)

    def _get_fallback_device(self) -> Optional[Any]:
        if inputs is None:
            return None
        try:
            gamepads = inputs.devices.gamepads
            return gamepads[0] if gamepads else self._fallback_device_stub
        except Exception:
            return self._fallback_device_stub

    def _map_raw_event(
        self, raw_event: Any, instance_id: int,
        controller_type: Optional[str], name: Optional[str], guid: Optional[str],
    ) -> Optional[InputEvent]:
        code = getattr(raw_event, "code", None)
        state = getattr(raw_event, "state", None)
        if code is None:
            return None

        # Hat / D-pad events
        hat_event = self._handle_hat_event(code, state, instance_id, name, guid)
        if hat_event is not None:
            return hat_event

        # Axis events
        axis_index = self._map_axis_code(code, controller_type)
        if axis_index is not None:
            value = self._normalize_axis_value(state, code, instance_id)
            return InputEvent(
                type=JOYAXISMOTION, instance_id=instance_id,
                axis=axis_index, value=value,
                name=name, guid=guid, raw_code=code, raw_state=state,
            )

        # Button events
        button_index = self._map_button_code(code, controller_type)
        if button_index is not None:
            pressed = bool(state)
            return InputEvent(
                type=JOYBUTTONDOWN if pressed else JOYBUTTONUP,
                instance_id=instance_id, button=button_index, value=pressed,
                name=name, guid=guid, raw_code=code, raw_state=state,
            )

        return None

    # ------------------------------------------------------------------
    # Hat / D-pad handling
    # ------------------------------------------------------------------

    def _handle_hat_event(
        self, code: str, state: Any, instance_id: int,
        name: Optional[str], guid: Optional[str],
    ) -> Optional[InputEvent]:
        if code not in (
            "ABS_HAT0X", "ABS_HAT0Y",
            "BTN_DPAD_UP", "BTN_DPAD_DOWN", "BTN_DPAD_LEFT", "BTN_DPAD_RIGHT",
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
            type=JOYHATMOTION, instance_id=instance_id,
            value=(x, y), name=name, guid=guid,
            raw_code=code, raw_state=state,
        )

    @staticmethod
    def _apply_hat_axis(code: str, val: int, x: int, y: int) -> Tuple[int, int]:
        if code == "ABS_HAT0X":
            x = max(-1, min(1, val))
        else:
            y = max(-1, min(1, val))
        return x, y

    def _apply_dpad_button(self, code: str, pressed: bool, instance_id: int) -> Tuple[int, int]:
        with self._device_lock:
            return self._apply_dpad_button_unlocked(code, pressed, instance_id)

    def _apply_dpad_button_unlocked(self, code: str, pressed: bool, instance_id: int) -> Tuple[int, int]:
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

        if state["left"] and not state["right"]:
            x = -1
        elif state["right"] and not state["left"]:
            x = 1
        else:
            x = 0
        if state["up"] and not state["down"]:
            y = 1
        elif state["down"] and not state["up"]:
            y = -1
        else:
            y = 0
        return x, y

    # ------------------------------------------------------------------
    # Axis / button code mapping
    # ------------------------------------------------------------------

    @staticmethod
    def _map_axis_code(code: str, controller_type: Optional[str]) -> Optional[int]:
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

    @staticmethod
    def _map_button_code(code: str, controller_type: Optional[str]) -> Optional[int]:
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

    # ------------------------------------------------------------------
    # Axis normalization
    # ------------------------------------------------------------------

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

    def _update_axis_range(self, axis_key: Tuple[int, str], value: float) -> Tuple[float, float]:
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
                key for key in keys
                if key not in self._device_map
                and (now - self._signature_key_last_seen.get(key, now)) > self._signature_ttl_seconds
            ]
            for key in stale_keys:
                keys.discard(key)
                self._signature_key_last_seen.pop(key, None)
            if not keys:
                stale_signatures.append(signature)
        for signature in stale_signatures:
            self._signature_to_keys.pop(signature, None)
            self._signature_last_seen.pop(signature, None)

    def _resolve_joystick_raw_mode(
        self,
        axis_key: Tuple[int, str],
        value: float,
        range_min: float,
        range_max: float,
    ) -> str:
        """Infer whether joystick raw values are signed or unsigned.

        Signed examples:   -32768..32767 (center near 0)
        Unsigned examples: 0..255 (center near 127.5)
        """
        if self._forced_joystick_mode in ("signed", "unsigned"):
            mode = self._forced_joystick_mode
            self._axis_joystick_mode_cache[axis_key] = mode
            return mode

        mode = self._axis_joystick_mode_cache.get(axis_key)

        # Strong evidence for signed mode.
        if range_min < 0.0 or range_max > 255.0:
            mode = "signed"

        if mode == "signed":
            # If we were previously signed, allow promotion to unsigned only
            # when we have clear centered unsigned evidence.
            spread = range_max - range_min
            midpoint = (range_min + range_max) / 2.0
            if (
                range_min >= 0.0
                and range_max <= 255.0
                and spread >= 8.0
                and 64.0 <= midpoint <= 191.0
            ):
                mode = "unsigned"
        elif mode == "unsigned":
            # Keep unsigned unless contradictory evidence appears.
            if range_min < 0.0 or range_max > 255.0:
                mode = "signed"
        else:
            # Initial decision: choose unsigned only for values near expected
            # unsigned center, otherwise default to signed (safer around 0).
            mode = "unsigned" if 64.0 <= value <= 191.0 else "signed"

        self._axis_joystick_mode_cache[axis_key] = mode
        return mode

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

        # Trigger axes: [0, 1]
        if code in ("ABS_Z", "ABS_RZ", "ABS_LT", "ABS_RT"):
            return max(0.0, min(1.0, value / max_val))

        # Joystick axes: [-1, 1]
        range_min, range_max = self._update_axis_range(axis_key, value)
        fixed_bounds = self._fixed_joystick_bounds.get(code)
        if fixed_bounds is not None:
            mode = self._resolve_joystick_raw_mode(
                axis_key, value, range_min, range_max
            )
            if mode == "unsigned":
                center = 127.5
                span = 127.5
            else:
                low, high = fixed_bounds
                center = (low + high) / 2.0
                span = max(high - center, center - low, 1.0)
            return max(-1.0, min(1.0, (value - center) / span))

        # Fallback for unknown joystick axes:
        # use dynamic center but keep a large span floor so tiny deltas near center
        # do not get amplified into large normalized values.
        center = (range_min + range_max) / 2.0
        span = max(
            range_max - center,
            center - range_min,
            abs(range_max),
            abs(range_min),
            1.0,
        )
        return max(-1.0, min(1.0, (value - center) / span))


__all__ = ["InputEventSource", "InputSourceError", "INPUTS_AVAILABLE"]
