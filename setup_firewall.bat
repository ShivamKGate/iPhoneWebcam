@echo off
echo Creating firewall rules for iPhone Webcam...

REM Allow inbound TCP traffic on port 3000
netsh advfirewall firewall add rule name="iPhone Webcam Server (TCP-In)" dir=in action=allow protocol=TCP localport=3000

REM Allow outbound TCP traffic on port 3000
netsh advfirewall firewall add rule name="iPhone Webcam Server (TCP-Out)" dir=out action=allow protocol=TCP localport=3000

echo Firewall rules created successfully!
echo.
echo Now checking network interfaces...
ipconfig
pause
