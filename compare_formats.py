"""
Visual comparison: Compact vs JSON message formats
Shows exactly why you should use compact messages for embedded systems
"""

from xbee.core.communication import CommunicationManager

class MockXBee:
    def send_data(self, remote, data):
        return len(data)

def show_comparison():
    mock_xbee = MockXBee()
    mock_remote = MockXBee()
    
    print("=" * 80)
    print("MESSAGE SIZE COMPARISON: Compact vs JSON")
    print("=" * 80)
    
    # Test data
    xbox_values = {
        'LY': b'\x64', 'RY': b'\x64', 
        'A': b'\x00', 'B': b'\x00', 'X': b'\x00', 'Y': b'\x00',
    }
    n64_values = {
        'A': b'\x00', 'B': b'\x00', 'Start': b'\x00',
    }
    
    print("\n📦 CONTROLLER DATA (Xbox + N64)")
    print("-" * 80)
    
    # Legacy compact format
    comm_compact = CommunicationManager(mock_xbee, mock_remote, use_legacy_format=True)
    compact_msg = comm_compact.formatter.create_combined_message(xbox_values, n64_values)
    
    print(f"Compact Format:  {len(compact_msg):3d} bytes  {'█' * len(compact_msg)}")
    
    # JSON format
    comm_json = CommunicationManager(mock_xbee, mock_remote, use_legacy_format=False)
    from xbee.core.message_system import ControllerDataMessage
    json_msg = ControllerDataMessage(xbox_data=xbox_values, n64_data=n64_values)
    json_bytes = json_msg.encode()
    
    print(f"JSON Format:     {len(json_bytes):3d} bytes  {'█' * min(len(json_bytes), 70)}")
    
    print(f"\n💡 JSON is {len(json_bytes) / len(compact_msg):.1f}x LARGER!")
    
    print("\n" + "=" * 80)
    print("📡 CUSTOM MESSAGE EXAMPLES")
    print("=" * 80)
    
    examples = [
        ("Heartbeat", [0xAA, 0x12, 0x34]),
        ("Status Update", [0xB0, 128, 85, 25]),
        ("Error Code", [0xE0, 0x02, 0x2A]),
        ("Motor Command", [0xD5, 200]),
        ("Camera Command", [0xCA, 0x01]),
        ("Drive Mode", [0xDB, 0x01, 76]),
    ]
    
    for name, compact in examples:
        # Simulate JSON equivalent (header + JSON object)
        json_equivalent = 15 + len(f'{{"type":"{name}","data":{compact[1:]}}}')
        
        compact_len = len(compact)
        ratio = json_equivalent / compact_len
        
        print(f"\n{name}:")
        print(f"  Compact: {compact_len:3d} bytes  {'█' * compact_len}")
        print(f"  JSON:    {json_equivalent:3d} bytes  {'█' * min(json_equivalent, 70)}")
        print(f"  💾 Saved: {json_equivalent - compact_len} bytes ({ratio:.1f}x smaller)")
    
    print("\n" + "=" * 80)
    print("📊 BANDWIDTH COMPARISON (30 messages/second)")
    print("=" * 80)
    
    msg_per_sec = 30
    
    compact_bandwidth = 10 * msg_per_sec  # Controller data
    json_bandwidth = 139 * msg_per_sec
    
    print(f"\nCompact Format: {compact_bandwidth:,} bytes/sec = {compact_bandwidth/1024:.2f} KB/sec")
    print(f"JSON Format:    {json_bandwidth:,} bytes/sec = {json_bandwidth/1024:.2f} KB/sec")
    
    savings = json_bandwidth - compact_bandwidth
    print(f"\n💰 Bandwidth Saved: {savings:,} bytes/sec = {savings/1024:.2f} KB/sec")
    print(f"   That's {json_bandwidth/compact_bandwidth:.1f}x less bandwidth needed!")
    
    # Over time
    print("\n⏱️  CUMULATIVE SAVINGS")
    print("-" * 80)
    
    for duration, seconds in [("1 minute", 60), ("1 hour", 3600), ("1 day", 86400)]:
        compact_total = compact_bandwidth * seconds
        json_total = json_bandwidth * seconds
        saved = json_total - compact_total
        
        print(f"{duration:10s}: Save {saved/1024/1024:.2f} MB  "
              f"(Compact: {compact_total/1024/1024:.2f} MB vs JSON: {json_total/1024/1024:.2f} MB)")
    
    print("\n" + "=" * 80)
    print("🎯 CONCLUSION")
    print("=" * 80)
    print("✓ Compact messages are 10-30x smaller")
    print("✓ Save megabytes of bandwidth per hour")
    print("✓ Perfect for embedded systems with limited bandwidth")
    print("✓ Just as easy to use as JSON")
    print("\n💡 Use compact messages for ALL embedded systems communication!")
    print("=" * 80)

if __name__ == "__main__":
    show_comparison()
