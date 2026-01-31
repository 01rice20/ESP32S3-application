import machine
from machine import I2S, Pin
import network
import time
import struct
import os
import gc
import array
import neopixel
import urequests
import ntptime

# ==========================================
# 1. 參數設定 (Configuration)
# ==========================================
WIFI_SSID = "<your_id>"
WIFI_PASSWORD = "<your_password>"
DISCORD_WEBHOOK_URL = "<your_webhook_url>"

# 錄音設定
SAMPLE_RATE = 16000
# 預設錄音 20 秒
# 注意: 20秒 16bit 音訊約需 640KB RAM。ESP32-S3 若無 PSRAM (SPIRAM) 只有約 300KB 可用。
# 程式會自動檢查記憶體並調整。
RECORD_SECONDS = 20 
WAV_FILE = "/record.wav"
BIT_SHIFT = 15      

# ==========================================
# 2. 硬體定義 (依據電路圖 SK68XXMINI-HS)
# ==========================================
I2S_SCK = 18   # GPIO18
I2S_WS = 17    # GPIO17
I2S_SD = 16    # GPIO16
PIN_BOOT_BTN = 0    
PIN_RGB_LED = 48    #  GPIO48
LED_NUM = 1

# 顏色定義 (RGB 順序)
# 亮度設為 50 (最大255) 以保護眼睛與節能
COLOR_OFF   = (0, 0, 0)
COLOR_RED   = (50, 0, 0)    # 紅
COLOR_GREEN = (0, 50, 0)    # 綠
COLOR_BLUE  = (0, 0, 50)    # 藍
COLOR_WHITE = (20, 20, 20)  # 白 (開機用)

# 狀態變數
state = {
    "req_action": False,
    "last_trigger": 0
}

# ==========================================
# 3. 硬體初始化
# ==========================================
# LED 初始化
# SK68XXMINI-HS 需要 timing=1 (800kHz)
pin_np = machine.Pin(PIN_RGB_LED, machine.Pin.OUT)
np = neopixel.NeoPixel(pin_np, LED_NUM, timing=1)

def set_led(color):
    """設定 LED 顏色並給予緩衝時間"""
    np[0] = color
    np.write()
    # SK6812Reset time > 80us，這裡給 50ms 確保穩定且不被 I2S 中斷干擾
    time.sleep_ms(50)

# 確保開機先關燈
set_led(COLOR_OFF)

# 按鈕
btn_boot = machine.Pin(PIN_BOOT_BTN, machine.Pin.IN, machine.Pin.PULL_UP)

# ==========================================
# 4. 網路與工具函式
# ==========================================
def connect_internet():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if not wlan.isconnected():
        print(f"[WiFi] 連線中: {WIFI_SSID}...")
        wlan.connect(WIFI_SSID, WIFI_PASSWORD)
        retry = 0
        while not wlan.isconnected() and retry < 20:
            time.sleep(0.5)
            retry += 1
            
    if wlan.isconnected():
        print(f"[WiFi] OK! IP: {wlan.ifconfig()[0]}")
        try:
            ntptime.settime()
        except:
            pass
        return True
    return False

def create_wav_header(sampleRate, bitsPerSample, num_channels, num_samples):
    datasize = num_samples * num_channels * bitsPerSample // 8
    o = bytes("RIFF", "ascii")
    o += struct.pack("<I", datasize + 36)
    o += bytes("WAVE", "ascii")
    o += bytes("fmt ", "ascii")
    o += struct.pack("<I", 16)
    o += struct.pack("<H", 1)
    o += struct.pack("<H", num_channels)
    o += struct.pack("<I", sampleRate)
    o += struct.pack("<I", sampleRate * num_channels * bitsPerSample // 8)
    o += struct.pack("<H", num_channels * bitsPerSample // 8)
    o += struct.pack("<H", bitsPerSample)
    o += bytes("data", "ascii")
    o += struct.pack("<I", datasize)
    return o

# ==========================================
# 5. 錄音功能
# ==========================================
def record_process():
    print("\n[Audio] 準備錄音...")
    
    # 1. 亮紅燈
    set_led(COLOR_RED) 
    print("[Audio] ★ REC (紅燈) ★")

    # 檢查記憶體是否足夠
    required_ram = SAMPLE_RATE * RECORD_SECONDS * 2
    free_ram = gc.mem_free()
    
    # 如果可用記憶體少於需求 (預留 50KB 給系統)，自動縮短時間
    rec_sec = RECORD_SECONDS
    if free_ram < (required_ram + 50000):
        print(f"[System] 警告: 記憶體不足 ({free_ram} bytes)。")
        # 嘗試使用 PSRAM (如果有的話，array 會自動用)
        # 如果沒有，這裡會嘗試分配，若失敗則捕獲
    
    total_samples = SAMPLE_RATE * rec_sec
    
    try:
        # 嘗試分配記憶體
        pcm_buffer = array.array('h', [0] * total_samples)
        print(f"[System] RAM Buffer 分配成功 ({len(pcm_buffer)*2} bytes)")
        
        # I2S 初始化
        audio_in = I2S(
            0,
            sck=Pin(I2S_SCK),
            ws=Pin(I2S_WS),
            sd=Pin(I2S_SD),
            mode=I2S.RX,
            bits=32, 
            format=I2S.MONO,
            rate=SAMPLE_RATE,
            ibuf=40000 
        )

        # 臨時緩衝
        chunk_samples = 1024
        raw_buf_int = array.array('i', [0] * chunk_samples)

        # DC 校正
        dc_offset = 0
        for _ in range(20):
            audio_in.readinto(raw_buf_int)
            dc_offset += (raw_buf_int[0] >> BIT_SHIFT)
        dc_offset //= 20
        
        # 錄音迴圈
        idx = 0
        while idx < total_samples:
            bytes_read = audio_in.readinto(raw_buf_int)
            samples_read = bytes_read // 4
            
            if samples_read == 0: continue
            if idx + samples_read > total_samples:
                samples_read = total_samples - idx

            for i in range(samples_read):
                val = raw_buf_int[i] >> BIT_SHIFT
                val -= dc_offset
                if val > 32767: val = 32767
                elif val < -32768: val = -32768
                pcm_buffer[idx + i] = val
            
            idx += samples_read
            
        print("[Audio] 錄音結束，寫入 Flash...")
        
        # 存檔
        wav_header = create_wav_header(SAMPLE_RATE, 16, 1, total_samples)
        with open(WAV_FILE, "wb") as f:
            f.write(wav_header)
            f.write(pcm_buffer)
        
        # 釋放資源
        audio_in.deinit()
        del pcm_buffer 
        del raw_buf_int
        gc.collect()
        
        return True

    except MemoryError:
        print("[Error] 記憶體嚴重不足！請減少錄音秒數 (RECORD_SECONDS)。")
        set_led(COLOR_OFF)
        return False
    except Exception as e:
        print(f"[Error] 錄音失敗: {e}")
        try:
            audio_in.deinit()
        except:
            pass
        return False

# ==========================================
# 6. 上傳功能
# ==========================================
def upload_discord():
    print("[Discord] 準備上傳...")
    
    # 2. 轉藍燈
    set_led(COLOR_BLUE)
    
    boundary = '---ESP32Boundary'
    content_type = 'multipart/form-data; boundary=' + boundary
    
    body_head = (
        '--' + boundary + '\r\n'
        'Content-Disposition: form-data; name="file"; filename="record.wav"\r\n'
        'Content-Type: audio/wav\r\n\r\n'
    ).encode('utf-8')
    body_tail = ('\r\n--' + boundary + '--\r\n').encode('utf-8')

    try:
        # 檢查檔案
        try:
            os.stat(WAV_FILE)
        except:
            print("[Discord] 找不到錄音檔")
            return False

        with open(WAV_FILE, "rb") as f:
            file_content = f.read()

        payload = body_head + file_content + body_tail
        del file_content
        gc.collect()

        print(f"[Discord] 發送請求...")
        res = urequests.post(
            DISCORD_WEBHOOK_URL,
            headers={'Content-Type': content_type},
            data=payload
        )
        print(f"[Discord] Code: {res.status_code}")
        res.close()
        
        if res.status_code in [200, 204]:
            return True
        return False
            
    except Exception as e:
        print(f"[Discord] 上傳錯誤: {e}")
        return False

# ==========================================
# 7. 主程式
# ==========================================
def handle_interrupt(pin):
    now = time.ticks_ms()
    if time.ticks_diff(now, state["last_trigger"]) > 1000:
        state["last_trigger"] = now
        state["req_action"] = True

def blink_failure():
    """失敗閃爍紅燈"""
    for _ in range(5):
        set_led(COLOR_RED)
        time.sleep(0.2)
        set_led(COLOR_OFF)
        time.sleep(0.2)

def main():
    print("[System] 系統啟動...")
    btn_boot.irq(trigger=machine.Pin.IRQ_FALLING, handler=handle_interrupt)
    
    # 1. 開機連線 (亮白燈)
    set_led(COLOR_WHITE)
    
    if connect_internet():
        # 連線成功：白燈亮 1 秒後熄滅
        time.sleep(1)
        set_led(COLOR_OFF)
        print("[System] 待機中 (滅燈)... 等待 BOOT 按鍵")
    else:
        print("[System] 網路失敗")
        while True:
            set_led(COLOR_RED)
            time.sleep(0.5)
            set_led(COLOR_OFF)
            time.sleep(0.5)

    # 2. 主迴圈
    while True:
        if state["req_action"]:
            state["req_action"] = False
            
            # 流程 A: 錄音 (內含亮紅燈)
            if record_process():
                
                # 確保網路連線
                if not network.WLAN(network.STA_IF).isconnected():
                    connect_internet()
                
                # 流程 B: 上傳 (內含亮藍燈)
                if upload_discord():
                    print("[System] 成功 (綠燈)")
                    set_led(COLOR_GREEN)
                    time.sleep(2)
                    set_led(COLOR_OFF)
                else:
                    print("[System] 上傳失敗")
                    blink_failure()
            else:
                print("[System] 錄音失敗")
                blink_failure()
            
            gc.collect()
            print("[System] 回到待機")

        time.sleep_ms(50)

if __name__ == "__main__":
    main()


