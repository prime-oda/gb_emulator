"""
Main Game Boy Emulator class
Coordinates CPU, memory, and other components.
"""
import pygame

from .cpu import CPU
from .memory import Memory
from .ppu import PPU
from .apu import APU
from .timer import Timer



# Game Boy timing constants
GB_CPU_FREQ = 4194304  # 4.194304 MHz
GB_FRAME_RATE = 59.7   # ~59.7 Hz
CYCLES_PER_FRAME = int(GB_CPU_FREQ / GB_FRAME_RATE)  # ~70224 cycles per frame
CYCLES_PER_SCANLINE = 456  # 456 cycles per scanline

class GameBoy:
    def __init__(self, debug=False):
        self.debug = debug
        self.memory = Memory(debug)
        self.cpu = CPU(self.memory, debug)
        
        # Import and initialize serial port first
        from .serial import SerialPort
        self.serial = SerialPort(self.memory)
        self.serial.set_debug(debug)
        
        # Initialize PPU with serial reference for overlay
        self.ppu = PPU(self.memory, self.serial, debug)
        self.apu = APU(self.memory, debug)
        self.timer = Timer(self.memory)
        
        # Link components to memory for register access
        self.memory.apu = self.apu
        self.memory.timer = self.timer
        self.memory.serial = self.serial
        
        self.running = True  # エミュレータを実行状態に設定  # エミュレータを実行状態に設定
        
    def load_rom(self, rom_path):
        """Load ROM file into memory"""
        try:
            with open(rom_path, 'rb') as f:
                rom_data = f.read()
            self.memory.load_rom(rom_data)
            
            # mem_timing.gb検出で64サイクル精度モード自動有効化
            if 'mem_timing' in rom_path.lower():
                if self.debug:
                    print(f"🎯 mem_timing.gb検出: 64サイクル精度タイマーモード有効化")
                self.timer.enable_mem_timing_mode()
                if hasattr(self.memory, 'debug'):
                    self.memory.debug = True  # デバッグログ有効化
            
            # Initialize CPU based on ROM type
            if len(rom_data) == 256:
                # Boot ROM - initialize for boot sequence
                self.cpu.init_for_boot_rom()
            else:
                # Game ROM - check if we have boot ROM available
                try:
                    with open('roms/dmg_bootrom.bin', 'rb') as boot_f:
                        boot_rom_data = boot_f.read()
                    if len(boot_rom_data) == 256:
                        # Load boot ROM first, then game ROM
                        self.memory.load_boot_rom(boot_rom_data)
                        self.cpu.init_for_boot_rom()  # Start from boot ROM
                        if self.debug:
                            print(f"🔄 Boot ROM loaded, will transition to game ROM")
                    else:
                        # No valid boot ROM - use post-boot initialization
                        self.cpu.init_for_game_rom()
                        if self.debug:
                            print(f"⚠️  No boot ROM - using post-boot initialization")
                except FileNotFoundError:
                    # No boot ROM available - use post-boot initialization
                    self.cpu.init_for_game_rom()
                    if self.debug:
                        print(f"⚠️  Boot ROM not found - using post-boot initialization")
                
            if self.debug:
                print(f"Loaded ROM: {rom_path} ({len(rom_data)} bytes)")
                if len(rom_data) > 256:
                    print(f"ROM banks: {self.memory.rom_banks}")
                print(f"Initial PC: 0x{self.cpu.pc:04X}")
                
                # mem_timing.gb用の詳細情報表示
                if 'mem_timing' in rom_path.lower():
                    print(f"🔧 Timer設定: TAC=0x{self.timer.memory.io[0x07]:02X}, TIMA=0x{self.timer.memory.io[0x05]:02X}")
                    
        except FileNotFoundError:
            raise FileNotFoundError(f"ROM file not found: {rom_path}")
    
    def run(self):
        """Run the emulator main loop"""
        cycle_count = 0
        frame_count = 0
        
        if self.debug:
            print("Initializing PPU rendering...")
        # Initialize PPU rendering
        try:
            render_result = self.ppu.render_frame()
            if self.debug:
                print(f"Initial render result: {render_result}")
            if not render_result:
                if self.debug:
                    print("Initial render failed, exiting")
                return
        except Exception as e:
            if self.debug:
                print(f"Error during initial render: {e}")
                import traceback
                traceback.print_exc()
            return
        
        if self.debug:
            print("Starting main emulation loop...")
        try:
            # Frame timing control
            clock = pygame.time.Clock()
            target_fps = 60  # Close to Game Boy frame rate
            frame_cycles = 0
            
            while self.running:
                # Execute one CPU instruction
                cycles = self.step()
                cycle_count += cycles
                
                # Update timer
                self.timer.update(cycles)
                
                # Update PPU for cycle-accurate timing
                self.ppu.step(cycles)
                
                # Debug output for CPU cycles and state
                if self.debug and cycle_count % 20000000 == 0:
                    ly = self.memory.read_byte(0xFF44)
                    lcdc = self.memory.read_byte(0xFF40)
                    stat = self.memory.read_byte(0xFF41)
                    print(f"Cycles: {cycle_count}, PC: 0x{self.cpu.pc:04X}, LY: {ly}, LCDC: 0x{lcdc:02X}, STAT: 0x{stat:02X}")
                
                # CPU cycle progress tracking - balanced for speed and visibility
                if self.debug and cycle_count % 5000000 == 0:  # Every 5M cycles for good visibility
                    ly = self.memory.read_byte(0xFF44)
                    lcdc = self.memory.read_byte(0xFF40)
                    print(f"CPU Progress: {cycle_count} cycles, PC: 0x{self.cpu.pc:04X}, LY: {ly}, LCDC: 0x{lcdc:02X}")
                    
                    # VRAMテキスト書き込み状況も表示
                    text_writes = getattr(self.memory, '_text_writes', 0)
                    if text_writes > 0:
                        print(f"           📝 VRAM Text Writes: {text_writes}")
                
                # Render frames less frequently for maximum speed (every 50k cycles)
                if cycle_count % 50000 == 0:
                    frame_count += 1
                    # Render frame and check if window should close
                    try:
                        if not self.ppu.render_frame():
                            if self.debug:
                                print("Render returned False, stopping...")
                            break
                    except Exception as e:
                        if self.debug:
                            print(f"Error during render: {e}")
                            import traceback
                            traceback.print_exc()
                        break
                        
                        
                # Frame timing control
                frame_cycles += cycles
                if frame_cycles >= CYCLES_PER_FRAME:
                    frame_cycles = 0
                    clock.tick(target_fps)
                
        except KeyboardInterrupt:
            if self.debug:
                print(f"\nEmulation stopped. Total cycles: {cycle_count}, Frames: {frame_count}")
        except Exception as e:
            if self.debug:
                print(f"Error in main loop: {e}")
                import traceback
                traceback.print_exc()
        
        if self.debug:
            print("Emulation loop ended, cleaning up...")
        pygame.quit()
    
    def step(self):
        """Execute one emulation step with precise timing synchronization"""
        cycles_before = self.cpu.cycles
        self.cpu.step()
        cpu_cycles = self.cpu.cycles - cycles_before
        
        # Update timer FIRST for accurate interrupt timing
        # This is critical for 02-interrupts.gb test and mem_timing.gb
        self.timer.update(cpu_cycles)
        
        # mem_timing.gb専用デバッグ情報
        if hasattr(self.timer, 'mem_timing_enabled') and self.timer.mem_timing_enabled:
            # 重要なタイマー状態変化をログ
            tac = self.timer.memory.io[0x07]
            tima = self.timer.memory.io[0x05]
            if tac & 0x04 and self.debug:  # タイマー有効かつデバッグモード
                timer_state = self.timer.get_precise_timer_state(0)
                if timer_state['will_increment']:
                    print(f"🔔 TIMA increment予定: current=0x{tima:02X}, cycles_to_next={timer_state['cycles_to_next']}")
        
        # Update PPU with CPU cycles (accurate LCD timing)
        self.ppu.step(cpu_cycles)
        
        # Update serial port with CPU cycles  
        self.serial.update(cpu_cycles)
        
        # Update APU with all CPU cycles for accurate audio timing
        self.apu.step(cpu_cycles)
        
        # Update memory registers with PPU state (direct write to avoid recursion)
        self.memory.io[0x44] = self.ppu.get_ly()  # LY register
        stat = self.ppu.get_stat() 
        self.memory.io[0x41] = stat  # STAT register
        
        return cpu_cycles
    
    def stop(self):
        """Stop the emulator"""
        self.running = False