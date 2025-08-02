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


class GameBoy:
    def __init__(self, debug=False):
        self.debug = debug
        self.memory = Memory()
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
                        print(f"🔄 Boot ROM loaded, will transition to game ROM")
                    else:
                        # No valid boot ROM - use post-boot initialization
                        self.cpu.init_for_game_rom()
                        print(f"⚠️  No boot ROM - using post-boot initialization")
                except FileNotFoundError:
                    # No boot ROM available - use post-boot initialization
                    self.cpu.init_for_game_rom()
                    print(f"⚠️  Boot ROM not found - using post-boot initialization")
                
            if self.debug:
                print(f"Loaded ROM: {rom_path} ({len(rom_data)} bytes)")
                if len(rom_data) > 256:
                    print(f"ROM banks: {self.memory.rom_banks}")
                print(f"Initial PC: 0x{self.cpu.pc:04X}")
        except FileNotFoundError:
            raise FileNotFoundError(f"ROM file not found: {rom_path}")
    
    def run(self):
        """Run the emulator main loop"""
        cycle_count = 0
        frame_count = 0
        
        print("Initializing PPU rendering...")
        # Initialize PPU rendering
        try:
            render_result = self.ppu.render_frame()
            print(f"Initial render result: {render_result}")
            if not render_result:
                print("Initial render failed, exiting")
                return
        except Exception as e:
            print(f"Error during initial render: {e}")
            import traceback
            traceback.print_exc()
            return
        
        print("Starting main emulation loop...")
        try:
            while self.running:
                # Execute one CPU instruction
                cycles = self.step()
                cycle_count += cycles
                
                # Update timer
                self.timer.update(cycles)
                
                # Debug output for CPU cycles and state
                if self.debug and cycle_count % 20000000 == 0:
                    ly = self.memory.read_byte(0xFF44)
                    lcdc = self.memory.read_byte(0xFF40)
                    stat = self.memory.read_byte(0xFF41)
                    print(f"Cycles: {cycle_count}, PC: 0x{self.cpu.pc:04X}, LY: {ly}, LCDC: 0x{lcdc:02X}, STAT: 0x{stat:02X}")
                
                # CPU cycle progress tracking - balanced for speed and visibility
                if cycle_count % 5000000 == 0:  # Every 5M cycles for good visibility
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
                            print("Render returned False, stopping...")
                            break
                    except Exception as e:
                        print(f"Error during render: {e}")
                        import traceback
                        traceback.print_exc()
                        break
                        
        except KeyboardInterrupt:
            print(f"\nEmulation stopped. Total cycles: {cycle_count}, Frames: {frame_count}")
        except Exception as e:
            print(f"Error in main loop: {e}")
            import traceback
            traceback.print_exc()
        
        print("Emulation loop ended, cleaning up...")
        pygame.quit()
    
    def step(self):
        """Execute one emulation step"""
        cycles_before = self.cpu.cycles
        self.cpu.step()
        cpu_cycles = self.cpu.cycles - cycles_before
        
        # Update PPU with CPU cycles
        self.ppu.step(cpu_cycles)
        
        # Update APU with CPU cycles (reduced frequency for performance)
        if cpu_cycles % 10 == 0:  # Update APU less frequently
            self.apu.step(cpu_cycles)
        
        # Update timer with CPU cycles
        self.timer.update(cpu_cycles)
        
        # Update serial port with CPU cycles  
        self.serial.update(cpu_cycles)
        
        # Update memory registers with PPU state (direct write to avoid recursion)
        self.memory.io[0x44] = self.ppu.get_ly()  # LY register
        stat = self.ppu.get_stat() 
        self.memory.io[0x41] = stat  # STAT register
        
        return cpu_cycles
    
    def stop(self):
        """Stop the emulator"""
        self.running = False