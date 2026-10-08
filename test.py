from asyncua.sync import Client

PLC_IP = "192.168.0.1"  # Replace with your PLC IP if different
PLC_PORT = 4840

client = Client(f"opc.tcp://{PLC_IP}:{PLC_PORT}", timeout=3)

try:
    print(f"Connecting to opc.tcp://{PLC_IP}:{PLC_PORT}...")
    client.connect()
    print("--- CONNECTED TO PLC ---")

    objects = client.get_objects_node()
    print("\nBrowsing Objects Folder...")
    
    for child in objects.get_children():
        # Correct sync method: read_display_name()
        display_name = child.read_display_name().Text
        print(f"\n[Node]: {child} | Name: '{display_name}'")
        
        # Recursively inspect nodes inside objects
        try:
            sub_children = child.get_children()
            for sub in sub_children:
                sub_name = sub.read_display_name().Text
                print(f"   └── [Child]: {sub} | Name: '{sub_name}'")
                
                # Check one layer deeper for DB tags
                try:
                    for tag in sub.get_children():
                        tag_name = tag.read_display_name().Text
                        print(f"         └── [Tag Node]: {tag} | Name: '{tag_name}'")
                except Exception:
                    pass
        except Exception:
            pass

except Exception as e:
    print(f"Error: {e}")

finally:
    try:
        client.disconnect()
        print("\nDisconnected.")
    except Exception:
        pass