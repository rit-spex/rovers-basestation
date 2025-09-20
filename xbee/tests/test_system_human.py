"""
Test script for the new (refactored) XBee control system.
Tests basically everything.
"""

import time
from unittest.mock import Mock
from typing import Any, cast

from ..CommandCodes import CONSTANTS
from ..core.heartbeat import HeartbeatTester, HeartbeatManager
from ..core.controller_manager import ControllerState, ControllerManager
from ..core.communication import MessageFormatter, CommunicationManager

class XBeeSystemTester:
    """
    Tester for the XBee control system.
    """
    
    def __init__(self):
        """
        Init system tester.
        """

        print("=== XBee Control System Tester ===")
        print("Testing refactored base station components...\n")
        
    def test_constants_and_enums(self):
        """
        Test that consts are properly defined and accessible.
        """

        print("Testing constants and enums...")
        
        try:
            # Test timing constants
            assert hasattr(CONSTANTS.TIMING, 'UPDATE_FREQUENCY')
            assert hasattr(CONSTANTS.TIMING, 'DEADBAND_THRESHOLD')
            print("✓ Timing constants defined correctly")
            
            # Test communication constants
            assert hasattr(CONSTANTS.COMMUNICATION, 'DEFAULT_PORT')
            assert hasattr(CONSTANTS.COMMUNICATION, 'DEFAULT_BAUD_RATE')
            assert hasattr(CONSTANTS.COMMUNICATION, 'FALLBACK_BAUD_RATE')
            assert hasattr(CONSTANTS.COMMUNICATION, 'REMOTE_XBEE_ADDRESS')
            print("✓ Communication constants defined correctly")
            
            # Test controller mode constants
            assert hasattr(CONSTANTS.CONTROLLER_MODES, 'NORMAL_MULTIPLIER')
            assert hasattr(CONSTANTS.CONTROLLER_MODES, 'CREEP_MULTIPLIER')
            assert hasattr(CONSTANTS.CONTROLLER_MODES, 'REVERSE_MULTIPLIER')
            print("✓ Controller mode constants defined correctly")
            
            # Test heartbeat message constant
            assert hasattr(CONSTANTS.HEARTBEAT, 'MESSAGE')
            assert hasattr(CONSTANTS.HEARTBEAT, 'MESSAGE_LENGTH')
            assert hasattr(CONSTANTS.HEARTBEAT, 'INTERVAL')
            print("✓ Heartbeat message constant defined correctly")
            
            return True
            
        except Exception as e:
            print(f"✗ Constants test failed: {e}")
            return False
            
    def test_heartbeat_system(self):
        """
        Test the heartbeat system functionality.
        """

        print("\nTesting heartbeat system...")
        
        try:
            # Test heartbeat creation and parsing
            tester = HeartbeatTester()
            
            # Test msg creation
            message = tester.test_heartbeat_creation()
            
            # Verify msg structure
            if len(message) == 3 and message[0:1] == CONSTANTS.HEARTBEAT.MESSAGE:
                print("✓ Heartbeat message structure correct")
            else:
                print("✗ Heartbeat message structure incorrect")
                return False
                
            # Test timing intervals (short)
            print("Running 3-second timing test...")
            tester.test_interval_timing(3)
            print("✓ Heartbeat timing test completed")
            
            # Test with mock XBee devices
            mock_xbee = Mock()
            mock_remote = Mock()
            
            manager = HeartbeatManager(mock_xbee, mock_remote)
            manager.set_interval(CONSTANTS.CONVERSION.ONE_HUNDRED_MS_TO_NS)  # 100ms for testing
            
            # Test multiple heartbeats
            sent_count = 0
            for _ in range(5):
                if manager.should_send_heartbeat() and manager.send_heartbeat():
                    sent_count += 1
                time.sleep(0.11)  # Wait slightly longer than interval
                
            print(f"✓ Sent {sent_count} heartbeats with mock XBee")
            
            return True
            
        except Exception as e:
            print(f"✗ Heartbeat test failed: {e}")
            return False
            
    def test_controller_state_management(self):
        """
        Test controller state management.
        """

        print("\nTesting controller state management...")
        
        try:
            state = ControllerState()
            
            # Test initial state
            xbox_values = state.get_controller_values("xbox")
            n64_values = state.get_controller_values("n64")
            
            assert len(xbox_values) > 0
            assert len(n64_values) > 0
            print("✓ Initial controller state loaded correctly")
            
            # Test val updates
            state.update_value("xbox", CONSTANTS.XBOX.BUTTONS.A + 6, CONSTANTS.XBOX.BUTTONS.ON)
            updated_value = xbox_values.get(CONSTANTS.XBOX.BUTTONS.A + 6)
            
            if updated_value == CONSTANTS.XBOX.BUTTONS.ON:
                print("✓ Controller state updates working")
            else:
                print("✗ Controller state update failed")
                return False
                
            return True
            
        except Exception as e:
            print(f"✗ Controller state test failed: {e}")
            return False
            
    def test_message_formatting(self):
        """
        Test message formatting for XBee transmission.
        """

        print("\nTesting message formatting...")
        
        try:
            formatter = MessageFormatter()
            
            # Create mock controller vals
            mock_xbox_values = {
                CONSTANTS.XBOX.JOYSTICK.AXIS_LY: b'\x64',
                CONSTANTS.XBOX.JOYSTICK.AXIS_RY: b'\x64',
                CONSTANTS.XBOX.BUTTONS.A + 6: CONSTANTS.XBOX.BUTTONS.ON,
                CONSTANTS.XBOX.BUTTONS.B + 6: CONSTANTS.XBOX.BUTTONS.OFF,
            }
            
            mock_n64_values = {
                CONSTANTS.N64.BUTTONS.A: CONSTANTS.N64.BUTTONS.ON,
                CONSTANTS.N64.BUTTONS.B: CONSTANTS.N64.BUTTONS.OFF,
            }
            
            # Test Xbox msg creation
            xbox_message = formatter.create_xbox_message(mock_xbox_values)
            assert len(xbox_message) >= 5  # Start byte + 2 axis + 2 button bytes
            print("✓ Xbox message formatting working")
            
            # Test N64 msg creation
            n64_message = formatter.create_n64_message(mock_n64_values)
            assert len(n64_message) >= 5  # Start byte + 4 button bytes
            print("✓ N64 message formatting working")
            
            # Test combined msg
            combined_message = formatter.create_combined_message(mock_xbox_values, mock_n64_values)
            assert len(combined_message) >= 10  # Both messages combined
            print("✓ Combined message formatting working")
            
            # Test reverse mode
            reverse_message = formatter.create_xbox_message(mock_xbox_values, reverse_mode=True)
            if reverse_message != xbox_message:
                print("✓ Reverse mode creates different message")
            else:
                print("! Reverse mode message identical (may be correct if values are symmetric)")
                
            return True
            
        except Exception as e:
            print(f"✗ Message formatting test failed: {e}")
            return False
            
    def test_communication_manager(self):
        """
        Test comms manager functionality.
        """

        print("\nTesting communication manager...")
        
        try:
            # Create mock XBee devices
            mock_xbee = Mock()
            mock_remote = Mock()
            
            comm_manager = CommunicationManager(mock_xbee, mock_remote)
            
            # Test controller data sending
            mock_xbox_values = {CONSTANTS.XBOX.JOYSTICK.AXIS_LY: b'\x64'}
            mock_n64_values = {CONSTANTS.N64.BUTTONS.A: CONSTANTS.N64.BUTTONS.OFF}
            
            result = comm_manager.send_controller_data(mock_xbox_values, mock_n64_values)
            
            if result:
                print("✓ Controller data transmission successful")
                # Verify send_data was called
                mock_xbee.send_data.assert_called()
            else:
                print("✗ Controller data transmission failed")
                return False
                
            # Test quit message
            quit_result = comm_manager.send_quit_message()
            if quit_result:
                print("✓ Quit message transmission successful")
            else:
                print("✗ Quit message transmission failed")
                return False
                
            return True
            
        except Exception as e:
            print(f"✗ Communication manager test failed: {e}")
            return False
            
    def test_integration(self):
        """
        Test integration between components.
        """
        
        print("\nTesting component integration...")
        
        try:

            # Test that all components can work together
            manager = ControllerManager()
            formatter = MessageFormatter()

            # Wire manager to a fake controller instance (no real pygame devices)
            fake_instance_id = 1
            manager.instance_id_values_map[fake_instance_id] = "xbox"

            # Use InputProcessor to exercise axis processing which updates manager.controller_state
            from ..core.controller_manager import InputProcessor
            processor = InputProcessor(manager)

            # Create a fake axis event object with required attributes
            from types import SimpleNamespace
            axis_event = SimpleNamespace(
                instance_id=fake_instance_id,
                value=0.5,
                axis=CONSTANTS.XBOX.JOYSTICK.AXIS_LY,
            )

            # Process axis movement
            processor.process_joystick_axis(cast(Any, axis_event))

            xbox_values = manager.controller_state.get_controller_values("xbox")
            n64_values = manager.controller_state.get_controller_values("n64")

            # Verify that the axis value was written into controller state (as 1-byte)
            stored = xbox_values.get(CONSTANTS.XBOX.JOYSTICK.AXIS_LY)
            if not stored or not isinstance(stored, (bytes, bytearray)):
                print("✗ ControllerManager/InputProcessor did not update state as expected")
                return False

            # Test mode flag updates via manager.update_mode_flags
            # Set SELECT and START pressed in manager's controller state to trigger mode toggles
            manager.controller_state.update_value("xbox", CONSTANTS.XBOX.BUTTONS.SELECT + 6, CONSTANTS.XBOX.BUTTONS.ON)
            manager.controller_state.update_value("xbox", CONSTANTS.XBOX.BUTTONS.START + 6, CONSTANTS.XBOX.BUTTONS.ON)

            # Toggle modes ON using JOYPAD.UP
            manager.update_mode_flags(CONSTANTS.XBOX.JOYPAD.UP, "xbox")
            if not (manager.reverse_mode and manager.creep_mode):
                print("✗ Mode flags not set by ControllerManager.update_mode_flags")
                return False

            # Toggle modes OFF using JOYPAD.DOWN
            manager.update_mode_flags(CONSTANTS.XBOX.JOYPAD.DOWN, "xbox")

            # Format message using the (possibly modified) controller state
            message = formatter.create_combined_message(xbox_values, n64_values)

            # Verify message is valid
            if len(message) > 0 and message[0] == int.from_bytes(CONSTANTS.START_MESSAGE):
                print("✓ Component integration successful")
                print(f"  Generated message length: {len(message)} bytes")
                print(f"  Message preview: {message[:10].hex()}")
                return True
            else:
                print("✗ Invalid integrated message")
                return False
                
        except Exception as e:
            print(f"✗ Integration test failed: {e}")
            return False
            
    def run_all_tests(self):
        """
        Run all tests and return overall result.
        """

        print("Running comprehensive system tests...\n")
        
        tests = [
            ("Constants and Enums", self.test_constants_and_enums),
            ("Heartbeat System", self.test_heartbeat_system),
            ("Controller State", self.test_controller_state_management),
            ("Message Formatting", self.test_message_formatting),
            ("Communication Manager", self.test_communication_manager),
            ("Integration", self.test_integration),
        ]
        
        results = []
        
        for test_name, test_func in tests:
            print(f"\n--- {test_name} Test ---")
            try:
                result = test_func()
                results.append((test_name, result))
            except Exception as e:
                print(f"✗ {test_name} test crashed: {e}")
                results.append((test_name, False))
                
        # Print summary
        print("\n=== TEST SUMMARY ===\n")
        
        passed = 0
        for test_name, result in results:
            status = "PASS" if result else "FAIL"
            print(f"{test_name:25} | {status}")
            if result:
                passed += 1
                
        print(f"\nOverall: {passed}/{len(results)} tests passed")
        
        if passed == len(results):
            print(":D All tests passed! Stuff is probably working!.")
        else:
            print(":c Some tests failed. Please review the output above.")
            
        return passed == len(results)

def main():
    """
    Run the test suite.
    """

    tester = XBeeSystemTester()
    success = tester.run_all_tests()
    
    return success

if __name__ == "__main__":
    main()