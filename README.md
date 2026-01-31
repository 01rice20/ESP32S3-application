# ESP32S3 applications
> Easy samples using ESP32-S3 via MicroPython

## Environment and sensors
- Development Environment: MacOS
- MCU: ESP32-S3
- Microphone: Adafruit SPH0645LM4H

## Setup - download CH34XVCPDriver and burn firmware
### Connect computer and ESP32-S3 with a USB cable
<img width="718" height="167" alt="截圖 2026-01-31 下午8 57 31" src="https://github.com/user-attachments/assets/de8527c9-2d4d-432a-b6d1-5fed8497d780" />

### Download CH343 driver
- Click [link](https://www.wch-ic.com/downloads/CH34XSER_MAC_ZIP.html) to download driver
- and make sure computer can connect with the board
<img width="926" height="644" alt="image" src="https://github.com/user-attachments/assets/7995bd33-e0fb-4ff7-a338-9f4f66121521" />

### Burn firmware
- Ensure that Python3 has been installed
- then download and run the kit to burn firmware
```
git clone https://github.com/Freenove/Freenove_ESP32_S3_WROOM_Board.git
cd ./Python/Python_Firmware
python3 mac.py
```
<img width="1430" height="1304" alt="image" src="https://github.com/user-attachments/assets/82bfc083-f610-46e5-b7dc-4bf232d8180a" />

### Thonny IDE
- Download through the [link](https://thonny.org/)
- Upload the code then set the main code to main.py and run
<img width="1002" height="718" alt="截圖 2026-01-31 下午9 36 16" src="https://github.com/user-attachments/assets/779613fb-409a-46d5-8343-43168ae30561" />

### app1
- Interfacing an I2S microphone with the ESP32-S3 by mapping the LRCK (WS), DOUT, and BCLK signals to specific GPIO pins
- The system is programmed to monitor the BOOT button; once pressed, it triggers a 20-second audio recording sequence
- Upon completion, the device connects to Wi-Fi and utilizes the Discord API to upload the audio file directly to a target channel

[![ESP32-S3 I2S Audio Recorder](https://img.youtube.com/vi/cWclgDHf01E/0.jpg)](https://www.youtube.com/watch?v=cWclgDHf01E)
