@echo off
echo Creating firewall rules for iPhone Webcam...

REM Allow inbound TCP traffic on common ports
netsh advfirewall firewall add rule name="iPhone Webcam Server (TCP-In) 8080" dir=in action=allow protocol=TCP localport=8080
netsh advfirewall firewall add rule name="iPhone Webcam Server (TCP-In) 8000" dir=in action=allow protocol=TCP localport=8000
netsh advfirewall firewall add rule name="iPhone Webcam Server (TCP-In) Python" dir=in action=allow program="%LOCALAPPDATA%\Programs\Python\Python*\python.exe" enable=yes

REM Allow outbound TCP traffic
netsh advfirewall firewall add rule name="iPhone Webcam Server (TCP-Out) 8080" dir=out action=allow protocol=TCP localport=8080
netsh advfirewall firewall add rule name="iPhone Webcam Server (TCP-Out) 8000" dir=out action=allow protocol=TCP localport=8000
netsh advfirewall firewall add rule name="iPhone Webcam Server (TCP-Out) Python" dir=out action=allow program="%LOCALAPPDATA%\Programs\Python\Python*\python.exe" enable=yes

echo Firewall rules created successfully!
echo.
echo Now checking network interfaces...
ipconfig

echo.
echo Testing network ports...
powershell -Command "Test-NetConnection -ComputerName localhost -Port 8080"
powershell -Command "Test-NetConnection -ComputerName localhost -Port 8000"

pause
