import socket
import subprocess
import platform
import sys

def get_network_info():
    print("\n=== Network Information ===")
    
    # Get hostname and IP
    hostname = socket.gethostname()
    print(f"Hostname: {hostname}")
    
    try:
        # Get all IP addresses
        ips = socket.gethostbyname_ex(hostname)[2]
        print("\nIP Addresses:")
        for ip in ips:
            print(f"  - {ip}")
    except Exception as e:
        print(f"Error getting IP addresses: {e}")

    # Get WiFi information (Windows specific)
    try:
        result = subprocess.run(['netsh', 'wlan', 'show', 'interfaces'], 
                              capture_output=True, text=True)
        if result.returncode == 0:
            print("\nWiFi Information:")
            print(result.stdout)
    except Exception as e:
        print(f"Error getting WiFi info: {e}")

def test_port():
    print("\n=== Testing Port 3000 ===")
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        # Try to bind to all interfaces
        sock.bind(('0.0.0.0', 3000))
        print("Port 3000 is available and can be bound to")
        return True
    except socket.error as e:
        print(f"Error binding to port 3000: {e}")
        print("This might mean the port is already in use or blocked")
        return False
    finally:
        sock.close()

def main():
    print("=== Network Diagnostic Tool ===")
    print(f"Operating System: {platform.system()} {platform.release()}")
    
    get_network_info()
    test_port()
    
    print("\n=== Instructions ===")
    print("1. Make sure your iPhone and computer are on the same WiFi network")
    print("2. Check the IP addresses above - you'll need to use one of these in your iPhone")
    print("3. If connection fails, try these steps:")
    print("   a. Run setup_firewall.bat as Administrator")
    print("   b. Temporarily disable Windows Firewall")
    print("   c. Make sure your WiFi network is set to 'Private' in Windows settings")
    
    input("\nPress Enter to exit...")

if __name__ == "__main__":
    main()
