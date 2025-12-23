#!/usr/bin/env python3
import os
import time
import threading
from collections import deque
import traceback
import math
import pygame

# -----------------------------
# 1. HARDWARE IMPORTS & SETUP
# -----------------------------
try:
    import smbus2
except ImportError:
    smbus2 = None
    print("WARNING: smbus2 not found. Buttons will not work.")

try:
    import classify  # Your real AI model
except ImportError:
    classify = None
    print("WARNING: classify.py not found. Scanner will fail.")

# Force Pygame to use the Touchscreen/HDMI buffer directly (No Desktop needed)
os.environ["SDL_VIDEODRIVER"] = "kmsdrm"
os.environ["SDL_KMSDRM_DEVICE_INDEX"] = "0"

# -----------------------------
# 2. CONFIGURATION
# -----------------------------
VIRTUAL_W, VIRTUAL_H = 320, 240

# --- ROBOTIC PALETTE ---
COLOR_BG        = (10, 15, 20)      # Very dark blue-black
COLOR_HUD       = (0, 200, 255)     # Cyan/Neon Blue
COLOR_TEXT      = (200, 230, 255)   # White-ish Blue
COLOR_ACCENT    = (0, 255, 100)     # Neon Green
COLOR_ALERT     = (255, 50, 50)     # Neon Red
COLOR_DIM       = (50, 70, 80)      # Dim gray

# --- ADS1115 SETTINGS ---
ADS_ADDR       = 0x48
REG_CONVERSION = 0x00
REG_CONFIG     = 0x01
CONFIG_A0      = 0xC383  # AIN0, 4.096V, 128SPS

if smbus2 is not None:
    BUS = smbus2.SMBus(1)
else:
    BUS = None

# -----------------------------
# 3. HARDWARE FUNCTIONS
# -----------------------------
def read_ads1115():
    """Reads mV from ADS1115 channel A0."""
    if BUS is None: return 9999
    try:
        BUS.write_i2c_block_data(ADS_ADDR, REG_CONFIG, [(CONFIG_A0 >> 8) & 0xFF, CONFIG_A0 & 0xFF])
        time.sleep(0.01)
        data = BUS.read_i2c_block_data(ADS_ADDR, REG_CONVERSION, 2)
        raw = (data[0] << 8) | data[1]
        if raw > 32767: raw -= 65536
        return raw * (4.096 / 32768.0) * 1000
    except:
        return 9999

def detect_button(mv: float):
    """Maps voltage to button name."""
    if mv < 20: return "ENTER"
    elif 70 <= mv <= 160: return "UP"
    elif 200 <= mv <= 350: return "DOWN"
    elif 450 <= mv <= 700: return "RIGHT"
    return None

def safe_init_pygame_display():
    """Retries display init to handle boot race conditions."""
    print("Initializing KMSDRM Display...", flush=True)
    for i in range(30):
        try:
            pygame.display.init()
            screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
            pygame.mouse.set_visible(False)
            print(f"Display Success: {pygame.display.Info().current_w}x{pygame.display.Info().current_h}")
            return screen
        except Exception:
            time.sleep(0.5)
    raise RuntimeError("Display Init Failed")

# -----------------------------
# 4. MAIN APPLICATION
# -----------------------------
class TFTApp:
    def __init__(self):
        print("==== ROBOTIC UI STARTING ====")
        pygame.init()

        # Init Hardware Screen
        self.real_screen = safe_init_pygame_display()
        self.real_w, self.real_h = self.real_screen.get_size()
        
        # Virtual Canvas
        self.surface = pygame.Surface((VIRTUAL_W, VIRTUAL_H))

        # Fonts
        try:
            self.header_font = pygame.font.Font("robot_font.ttf", 18)
            self.main_font   = pygame.font.Font("robot_font.ttf", 35)
            self.small_font  = pygame.font.Font("robot_font.ttf", 12)
        except:
            self.header_font = pygame.font.SysFont("consolas", 20, bold=True)
            self.main_font   = pygame.font.SysFont("consolas", 40, bold=True)
            self.small_font  = pygame.font.SysFont("consolas", 14)

        # State
        self.running = True
        self.current_screen = "menu"
        self.focus_index = 0
        self.menu_items = ["INITIATE SCAN", "SYSTEM OFF"]

        # Scanner Vars
        self.scan_status = "IDLE"
        self.result_text = ""
        self.conf_text = ""
        self.scan_line_y = 0
        self.scan_direction = 1

        # Input Threading
        self.button_queue = deque()
        self.button_lock = threading.Lock()
        threading.Thread(target=self.poll_buttons, daemon=True).start()

    # ------------- BUTTON LOOP -------------
    def poll_buttons(self):
        last_press = None
        while self.running:
            mv = read_ads1115()
            btn = detect_button(mv)
            if btn != last_press:
                if btn:
                    with self.button_lock:
                        self.button_queue.append(btn)
                last_press = btn
            time.sleep(0.12)

    def get_next_button(self):
        with self.button_lock:
            if self.button_queue: return self.button_queue.popleft()
        return None

    # ------------- INPUT LOGIC -------------
    def handle_input(self, key):
        if self.current_screen == "menu":
            if key == "UP" or key == "DOWN":
                self.focus_index = 1 - self.focus_index
            elif key == "ENTER":
                if self.focus_index == 0:
                    self.current_screen = "scan"
                    self.scan_status = "IDLE"
                else:
                    self.running = False

        elif self.current_screen == "scan":
            if key == "ENTER" and self.scan_status != "SCANNING":
                self.start_scan()
            elif key == "RIGHT": # Back Button
                self.current_screen = "menu"

    # ------------- SCAN LOGIC -------------
    def start_scan(self):
        self.scan_status = "SCANNING"
        
        def worker():
            start_t = time.time()
            try:
                # RUN REAL CLASSIFICATION
                if classify:
                    res, conf, err = classify.main()
                else:
                    # Fallback if classify.py is missing
                    time.sleep(1)
                    res, conf, err = "No Model", 0, "Missing File"

                # Min animation time 1.2s
                elapsed = time.time() - start_t
                if elapsed < 1.2: time.sleep(1.2 - elapsed)

                if err:
                    self.scan_status = "ERROR"
                    self.result_text = "SYS ERR"
                    self.conf_text = str(err)
                elif res == "Undetected" or res == "UNKNOWN":
                    self.scan_status = "RESULT"
                    self.result_text = "UNDETECTED"
                    self.conf_text = "---"
                else:
                    self.scan_status = "RESULT"
                    self.result_text = res.upper()
                    self.conf_text = f"{conf*100:.1f}%"
            except Exception as e:
                self.scan_status = "ERROR"
                self.result_text = "CRASH"
                self.conf_text = str(e)
                traceback.print_exc()

        threading.Thread(target=worker, daemon=True).start()

    # ------------- DRAWING -------------
    def draw_corner_brackets(self, surface, rect, color, thickness=2, length=15):
        x, y, w, h = rect
        # TL
        pygame.draw.line(surface, color, (x, y), (x + length, y), thickness)
        pygame.draw.line(surface, color, (x, y), (x, y + length), thickness)
        # TR
        pygame.draw.line(surface, color, (x + w, y), (x + w - length, y), thickness)
        pygame.draw.line(surface, color, (x + w, y), (x + w, y + length), thickness)
        # BL
        pygame.draw.line(surface, color, (x, y + h), (x + length, y + h), thickness)
        pygame.draw.line(surface, color, (x, y + h), (x, y + h - length), thickness)
        # BR
        pygame.draw.line(surface, color, (x + w, y + h), (x + w - length, y + h), thickness)
        pygame.draw.line(surface, color, (x + w, y + h), (x + w, y + h - length), thickness)

    def draw_grid(self, surface):
        for x in range(0, VIRTUAL_W, 40):
            pygame.draw.line(surface, (20, 30, 40), (x, 0), (x, VIRTUAL_H))
        for y in range(0, VIRTUAL_H, 40):
            pygame.draw.line(surface, (20, 30, 40), (0, y), (VIRTUAL_W, y))

    def draw_menu(self):
        s = self.surface
        s.fill(COLOR_BG)
        self.draw_grid(s)

        # Header
        pygame.draw.rect(s, COLOR_HUD, (0, 0, VIRTUAL_W, 30))
        title = self.header_font.render("SYSTEM MAIN MENU", True, COLOR_BG)
        s.blit(title, (10, 5))

        for i, item in enumerate(self.menu_items):
            center_y = 100 + i * 60
            if i == self.focus_index:
                box_rect = (40, center_y - 20, VIRTUAL_W - 80, 40)
                pygame.draw.rect(s, COLOR_HUD, box_rect, width=2)
                pygame.draw.rect(s, (0, 50, 60), box_rect)
                label = self.header_font.render(f"> {item} <", True, COLOR_ACCENT)
            else:
                label = self.header_font.render(item, True, COLOR_DIM)
            s.blit(label, (VIRTUAL_W//2 - label.get_width()//2, center_y - 10))

    def draw_scan_ui(self):
        s = self.surface
        s.fill(COLOR_BG)
        self.draw_grid(s)

        # Status Bar
        pygame.draw.line(s, COLOR_HUD, (0, 25), (VIRTUAL_W, 25), 1)
        status_txt = self.small_font.render(f"STATUS: {self.scan_status}", True, COLOR_HUD)
        s.blit(status_txt, (10, 8))

        # Box
        box_w, box_h = 200, 140
        box_x = (VIRTUAL_W - box_w) // 2
        box_y = (VIRTUAL_H - box_h) // 2 + 10

        # Color Logic
        draw_color = COLOR_HUD
        if self.scan_status == "ERROR": draw_color = COLOR_ALERT
        elif self.scan_status == "RESULT":
            draw_color = COLOR_ALERT if self.result_text == "UNDETECTED" else COLOR_ACCENT

        self.draw_corner_brackets(s, (box_x, box_y, box_w, box_h), draw_color)

        # Content
        if self.scan_status == "IDLE":
            msg = self.header_font.render("READY", True, COLOR_TEXT)
            s.blit(msg, (VIRTUAL_W//2 - msg.get_width()//2, VIRTUAL_H//2))
            hint = self.small_font.render("[ENTER] TO INITIATE", True, COLOR_DIM)
            s.blit(hint, (VIRTUAL_W//2 - hint.get_width()//2, VIRTUAL_H - 20))

        elif self.scan_status == "SCANNING":
            self.scan_line_y += 3 * self.scan_direction
            if self.scan_line_y > box_h: self.scan_direction = -1
            if self.scan_line_y < 0: self.scan_direction = 1
            
            ly = box_y + self.scan_line_y
            pygame.draw.line(s, COLOR_ACCENT, (box_x + 5, ly), (box_x + box_w - 5, ly), 2)
            
            if (pygame.time.get_ticks() // 200) % 2 == 0:
                txt = self.header_font.render("ANALYZING...", True, COLOR_ACCENT)
                s.blit(txt, (VIRTUAL_W//2 - txt.get_width()//2, box_y - 20))

        elif self.scan_status == "RESULT":
            if self.result_text == "UNDETECTED":
                r_surf = self.main_font.render("UNDETECTED", True, COLOR_ALERT)
                l_surf = self.small_font.render("NO MATCH FOUND", True, COLOR_DIM)
                s.blit(r_surf, (VIRTUAL_W//2 - r_surf.get_width()//2, box_y + 55))
                s.blit(l_surf, (VIRTUAL_W//2 - l_surf.get_width()//2, box_y + 30))
            else:
                r_surf = self.main_font.render(self.result_text, True, COLOR_ACCENT)
                c_surf = self.header_font.render(self.conf_text, True, COLOR_HUD)
                l_surf = self.small_font.render("SUBSTANCE DETECTED", True, COLOR_DIM)
                s.blit(l_surf, (VIRTUAL_W//2 - l_surf.get_width()//2, box_y + 20))
                s.blit(r_surf, (VIRTUAL_W//2 - r_surf.get_width()//2, box_y + 40))
                s.blit(c_surf, (VIRTUAL_W//2 - c_surf.get_width()//2, box_y + 80))

        elif self.scan_status == "ERROR":
            t = self.main_font.render("FAILURE", True, COLOR_ALERT)
            m = self.small_font.render("SENSOR ERROR", True, COLOR_DIM)
            s.blit(t, (VIRTUAL_W//2 - t.get_width()//2, box_y + 40))
            s.blit(m, (VIRTUAL_W//2 - m.get_width()//2, box_y + 80))

    # ------------- LOOP -------------
    def run(self):
        clock = pygame.time.Clock()
        while self.running:
            # Handle Quit Event
            for event in pygame.event.get():
                if event.type == pygame.QUIT: self.running = False

            # Handle Hardware Buttons
            btn = self.get_next_button()
            if btn: self.handle_input(btn)

            # Draw
            if self.current_screen == "menu": self.draw_menu()
            else: self.draw_scan_ui()

            # Render to Real Screen
            scaled = pygame.transform.smoothscale(self.surface, (self.real_w, self.real_h))
            self.real_screen.blit(scaled, (0, 0))
            pygame.display.flip()
            clock.tick(30)
        pygame.quit()

if __name__ == "__main__":
    app = TFTApp()
    app.run()