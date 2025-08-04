"""
Game Boy PPU (Picture Processing Unit)
Handles graphics rendering, LCD timing, and video memory management.
"""

import pygame
import numpy
import logging


class PPU:
    def __init__(self, memory, serial=None, debug=False):
        self.memory = memory
        self.serial = serial  # Reference to serial port for overlay display
        self.debug = debug

        # Configure logging - only to file, not console
        if self.debug:
            logging.basicConfig(
                level=logging.INFO,  # Reduced log level
                format='%(asctime)s [%(levelname)s] %(message)s',
                handlers=[
                    logging.FileHandler('ppu_debug.log'),  # Log to file only
                ]
            )
            self.logger = logging.getLogger()
        else:
            # Disable logging when not in debug mode
            logging.disable(logging.CRITICAL)
            self.logger = None

        # LCD specifications
        self.screen_width = 160
        self.screen_height = 144
        self.scale = 4  # Scale factor for display

        # PPU state
        self.cycles = 0
        self.scan_line = 0
        self.mode = 0  # 0: H-Blank, 1: V-Blank, 2: OAM, 3: VRAM

        # Mode durations (in CPU cycles) - Game Boy accurate timing
        self.mode_2_cycles = 80   # OAM scan
        self.mode_3_cycles = 172  # VRAM scan
        self.mode_0_cycles = 204  # H-Blank
        self.scanline_cycles = 456  # Total cycles per scanline
        self.v_blank_lines = 10   # V-Blank scanlines

        # Palette colors (Game Boy standard: 0=lightest, 3=darkest)
        self.palette = [
            (224, 248, 208),  # Color 0: Lightest green (white-ish)
            (136, 192, 112),  # Color 1: Light green  
            (52, 104, 86),    # Color 2: Dark green
            (8, 24, 32)       # Color 3: Darkest green (black-ish)
        ]

        # Frame buffer
        self.frame_buffer = numpy.zeros((self.screen_height, self.screen_width), dtype=numpy.uint8)

        # Frame skip settings for performance control
        self.frame_skip_rate = 0  # No frame skipping for maximum speed
        self.frame_counter = 0
        
        # Performance monitoring
        self.last_frame_time = 0
        self.target_frame_time = 1.0 / 60.0  # 60 FPS target
        
        # FPS calculation
        self.fps_update_interval = 1.0  # Update FPS display every second
        self.last_fps_update = 0
        self.frame_count_for_fps = 0
        self.current_fps = 0.0

        # Initialize pygame
        import os
        # macOS specific environment variables for better window handling
        os.environ['SDL_VIDEO_WINDOW_POS'] = '200,200'  # Position window away from dock
        os.environ['SDL_VIDEO_CENTERED'] = '1'  # Center the window
        os.environ['SDL_VIDEODRIVER'] = 'cocoa'  # Force Cocoa driver on macOS
        
        pygame.init()
        pygame.display.init()
        
        # Create display with proper flags for macOS visibility
        display_flags = pygame.SHOWN | pygame.RESIZABLE
        self.screen = pygame.display.set_mode((
            self.screen_width * self.scale,
            self.screen_height * self.scale
        ), display_flags)
        
        pygame.display.set_caption("🎮 Game Boy Emulator - CPU Instructions Test")
        
        # Set window icon to make it more visible in dock
        try:
            icon_surface = pygame.Surface((32, 32))
            icon_surface.fill((0, 100, 0))  # Dark green
            pygame.display.set_icon(icon_surface)
        except:
            pass
        
        # Clear screen to distinctive Game Boy green
        self.screen.fill((136, 192, 112))  # Light green like Game Boy
        pygame.display.flip()
        
        # Force immediate screen refresh
        pygame.event.pump()  # Process events to ensure window appears
        
        # Initialize font for FPS display and overlay
        pygame.font.init()
        self.font = pygame.font.Font(None, 24)  # Font for FPS and serial overlay

        print(f"🎮 Pygame window created: {self.screen_width * self.scale}x{self.screen_height * self.scale}")
        print("📺 Look for the Game Boy Emulator window - it should be visible now!")

        # Simplified window activation for macOS
        try:
            import subprocess
            # Just try to activate without timeout issues
            subprocess.Popen(['osascript', '-e', 
                            'tell application "System Events" to keystroke tab using {command down}'])
            print("🔄 Window activation command sent")
        except Exception as e:
            print(f"⚠️ Window activation failed (this is usually OK): {e}")

        self.clock = pygame.time.Clock()

        # Frame rate control
        self.target_fps = 60  # Game Boy native refresh rate  # Game Boy native refresh rate

    def step(self, cpu_cycles):
        """Update PPU state based on CPU cycles"""
        self.cycles += cpu_cycles

#        if self.debug:
#            self.logger.info(f"Step: scan_line={self.scan_line}, mode={self.mode}, cycles={self.cycles}")

        if self.scan_line < 144:  # Visible scanlines
            if self.mode == 2 and self.cycles >= self.mode_2_cycles:
                # OAM scan -> VRAM scan
                self.mode = 3
                self.cycles = 0
            elif self.mode == 3 and self.cycles >= self.mode_3_cycles:
                # VRAM scan -> H-Blank
                self.mode = 0
                self.cycles = 0
                self.render_scanline()
            elif self.mode == 0 and self.cycles >= self.mode_0_cycles:
                # H-Blank -> next scanline
                self.scan_line += 1
                self.cycles = 0
                if self.scan_line < 144:
                    self.mode = 2  # Next OAM scan
                else:
                    self.mode = 1  # V-Blank
                    # Trigger V-Blank interrupt
                    self.request_vblank_interrupt()
        else:  # V-Blank period (scanlines 144-153)
            if self.mode == 1 and self.cycles >= self.scanline_cycles:  # Duration of one scanline in V-Blank
                self.scan_line += 1
                self.cycles = 0
                if self.scan_line >= 154:
                    self.scan_line = 0
                    self.mode = 2  # Start new frame  # Start new frame

    def render_scanline(self):
        """Render a single scanline to the temporary buffer"""

        # Removed frequent render_scanline logging

        # Render every scanline - no frame skipping

        if self.scan_line >= self.screen_height:
            return

        # Get LCD control register
        lcdc = self.memory.read_byte(0xFF40)

        # Always render for debugging, even if LCD is disabled
        if not (lcdc & 0x80):
            # LCD disabled - render VRAM content directly for debugging
            self.render_vram_debug()
            return

        # Clear scanline buffer with background color
        # Use color 0 (lightest) as default background (Game Boy standard)
        self.frame_buffer[self.scan_line].fill(0)

        # Render background if enabled
        if lcdc & 0x01:
            self.render_background_scanline()
        else:
            # Clear scanline to darkest color when BG is disabled to see difference
            for x in range(self.screen_width):
                self.frame_buffer[self.scan_line][x] = 3

        # Render window if enabled
        if lcdc & 0x20:
            self.render_window_scanline()

        # Render sprites if enabled
        if lcdc & 0x02:
            self.render_sprites_scanline()

    def render_background_scanline(self):
        """Render background tiles for the current scanline to the temporary buffer"""
        # Get scroll registers
        scy = self.memory.read_byte(0xFF42)  # Scroll Y
        scx = self.memory.read_byte(0xFF43)  # Scroll X

        # Debug output much less frequently for speed
        debug_should_run = (self.scan_line == 0 and 
                           (not hasattr(self, 'bg_debug_counter') or 
                            getattr(self, 'bg_debug_counter', 0) % 3600 == 0))  # Every 60 seconds
        
        if debug_should_run:
            self.bg_debug_counter = getattr(self, 'bg_debug_counter', 0) + 1
            lcdc = self.memory.read_byte(0xFF40)
            bgp = self.memory.read_byte(0xFF47)
            print(f"PPU: LCDC=0x{lcdc:02X}, BGP=0x{bgp:02X}, SCX={scx}, SCY={scy}")
            
            # Check background map first few positions for actual text
            bg_map_base = 0x9C00 if (lcdc & 0x08) else 0x9800
            first_map_row = [self.memory.read_byte(bg_map_base + i) for i in range(16)]
            print(f"BG map first 16: {' '.join(f'{b:02X}' for b in first_map_row)}")
            
            # Check several key tiles for font data
            tiles_to_check = [0x20, 0x21, 0x41, 0x43, 0x50, 0x55]  # space, !, A, C, P, U
            for tile_idx in tiles_to_check:
                tile_data = [self.memory.read_byte(0x8000 + tile_idx * 16 + j) for j in range(8)]
                has_data = any(b != 0 for b in tile_data)
                if has_data:
                    print(f"  Tile 0x{tile_idx:02X}: {' '.join(f'{b:02X}' for b in tile_data[:4])}...")
                    break  # Show first tile with data
            if not any(any(self.memory.read_byte(0x8000 + t * 16 + j) != 0 for j in range(8)) for t in tiles_to_check):
                print("  No font data found in common tiles")

        # Calculate which tile row we're on
        y = (self.scan_line + scy) & 0xFF
        tile_row = y // 8
        tile_line = y % 8

        # Get background tile map base address
        lcdc = self.memory.read_byte(0xFF40)
        bg_map_base = 0x9C00 if (lcdc & 0x08) else 0x9800

        # Get tile data base address
        tile_data_base = 0x8000 if (lcdc & 0x10) else 0x8800

        # Preload the entire tile row from the background map
        tile_map_row_start = bg_map_base + (tile_row * 32)
        tile_map_row = [self.memory.read_byte(tile_map_row_start + i) for i in range(32)]

        for x in range(self.screen_width):
            # Calculate tile position
            pixel_x = (x + scx) & 0xFF
            tile_col = pixel_x // 8
            tile_pixel = pixel_x % 8

            # Get tile index from preloaded row
            tile_index = tile_map_row[tile_col]

            # Calculate tile data address
            if tile_data_base == 0x8000:
                # Unsigned indexing (0x8000-0x8FFF)
                tile_addr = tile_data_base + (tile_index * 16) + (tile_line * 2)
            else:
                # Signed indexing (0x8800-0x97FF, with 0x9000 as center)
                if tile_index > 127:
                    tile_index = tile_index - 256  # Convert to signed
                tile_addr = 0x9000 + (tile_index * 16) + (tile_line * 2)

            # Get tile data (2 bytes per line)
            tile_data_low = self.memory.read_byte(tile_addr)
            tile_data_high = self.memory.read_byte(tile_addr + 1)

            # Extract pixel color (2 bits)
            bit_pos = 7 - tile_pixel
            color_bit_0 = (tile_data_low >> bit_pos) & 1
            color_bit_1 = (tile_data_high >> bit_pos) & 1
            color_index = (color_bit_1 << 1) | color_bit_0

            # Apply background palette
            bgp = self.memory.read_byte(0xFF47)
            
            # If BGP is 0 (all colors map to 0), use default Game Boy palette
            if bgp == 0x00:
                bgp = 0xFC  # Default: 0→0, 1→1, 2→2, 3→3 (normal mapping)
            
            palette_color = (bgp >> (color_index * 2)) & 0x03

            # Store in frame buffer
            self.frame_buffer[self.scan_line][x] = palette_color

    def render_window_scanline(self):
        """Render window layer for the current scanline"""
        # Get window position registers
        wy = self.memory.read_byte(0xFF4A)  # Window Y position
        wx = self.memory.read_byte(0xFF4B)  # Window X position

        # Window X is offset by 7 pixels
        wx = wx - 7

        # Check if window should be rendered on this scanline
        if self.scan_line < wy or wx >= self.screen_width:
            return

        # Calculate window-relative scanline
        window_line = self.scan_line - wy
        tile_row = window_line // 8
        tile_line = window_line % 8

        # Get window tile map base address (bit 6 of LCDC)
        lcdc = self.memory.read_byte(0xFF40)
        window_map_base = 0x9C00 if (lcdc & 0x40) else 0x9800

        # Get tile data base address (bit 4 of LCDC)
        tile_data_base = 0x8000 if (lcdc & 0x10) else 0x8800

        # Render window pixels
        for screen_x in range(max(0, wx), self.screen_width):
            window_x = screen_x - wx
            tile_col = window_x // 8
            tile_pixel = window_x % 8

            # Get tile index from window map
            window_map_addr = window_map_base + (tile_row * 32) + tile_col
            tile_index = self.memory.read_byte(window_map_addr)

            # Calculate tile data address
            if tile_data_base == 0x8000:
                # Unsigned indexing (0x8000-0x8FFF)
                tile_addr = tile_data_base + (tile_index * 16) + (tile_line * 2)
            else:
                # Signed indexing (0x8800-0x97FF, with 0x9000 as center)
                if tile_index > 127:
                    tile_index = tile_index - 256  # Convert to signed
                tile_addr = 0x9000 + (tile_index * 16) + (tile_line * 2)

            # Get tile data (2 bytes per line)
            tile_data_low = self.memory.read_byte(tile_addr)
            tile_data_high = self.memory.read_byte(tile_addr + 1)

            # Extract pixel color (2 bits)
            bit_pos = 7 - tile_pixel
            color_bit_0 = (tile_data_low >> bit_pos) & 1
            color_bit_1 = (tile_data_high >> bit_pos) & 1
            color_index = (color_bit_1 << 1) | color_bit_0

            # Apply background palette (window uses same palette as background)
            bgp = self.memory.read_byte(0xFF47)
            
            # If BGP is 0 (all colors map to 0), use default Game Boy palette
            if bgp == 0x00:
                bgp = 0xFC  # Default: 0→0, 1→1, 2→2, 3→3 (normal mapping)
            
            palette_color = (bgp >> (color_index * 2)) & 0x03

            # Store in frame buffer (window overwrites background)
            self.frame_buffer[self.scan_line][screen_x] = palette_color

    def render_frame(self):
        """Render the complete frame to the screen with adaptive frame skipping"""
        import time
        
        current_time = time.time()
        
        # Increment frame counter
        self.frame_counter += 1
        
        # Adaptive frame skip based on performance
        frame_time = current_time - self.last_frame_time if self.last_frame_time > 0 else 0
        
        # Adjust frame skip rate based on performance
        if frame_time > self.target_frame_time * 1.5:  # Running slow
            self.frame_skip_rate = min(3, self.frame_skip_rate + 1)
        elif frame_time < self.target_frame_time * 0.8:  # Running fast
            self.frame_skip_rate = max(1, self.frame_skip_rate - 1)
        
        # Update FPS calculation for all frames (including skipped ones)
        self.frame_count_for_fps += 1
        
        # Determine if we should skip this frame
        should_skip = (self.frame_counter % self.frame_skip_rate) != 0
        
        if should_skip:
            # Still handle events even when skipping frames - improved event processing
            events_processed = 0
            for event in pygame.event.get():
                events_processed += 1
                if event.type == pygame.QUIT:
                    print("🛑 Window close requested (during frame skip)")
                    pygame.quit()
                    return False
                elif event.type == pygame.KEYDOWN:
                    print(f"⌨️ Key pressed during skip: {pygame.key.name(event.key)}")
                    if event.key == pygame.K_ESCAPE:
                        print("🛑 ESC pressed during skip")
                        pygame.quit()
                        return False
                    self.handle_keydown(event.key)
                elif event.type == pygame.KEYUP:
                    print(f"⌨️ Key released during skip: {pygame.key.name(event.key)}")
                    self.handle_keyup(event.key)
            
            # Ensure events are processed even during frame skip
            pygame.event.pump()
            return True
        
        # Render the frame
        active_buffer = self.frame_buffer

        # Reuse frame_array to avoid creating a new array every frame
        if not hasattr(self, 'frame_array'):
            self.frame_array = numpy.zeros((self.screen_height, self.screen_width, 3), dtype=numpy.uint8)

        # High-performance surface creation and scaling
        palette_array = numpy.array(self.palette, dtype=numpy.uint8)
        
        # Clamp color indices to valid range
        safe_buffer = numpy.clip(active_buffer, 0, len(self.palette)-1)
        
        # Map colors using numpy indexing (much faster than loops)
        rgb_buffer = palette_array[safe_buffer]
        
        # Create surface from array (width, height swapped for pygame)
        frame_surface = pygame.surfarray.make_surface(rgb_buffer.swapaxes(0, 1))
        
        # Scale up efficiently 
        scaled_surface = pygame.transform.scale(
            frame_surface, 
            (self.screen_width * self.scale, self.screen_height * self.scale)
        )
        
        # Blit to screen
        self.screen.blit(scaled_surface, (0, 0))
        
        # Draw serial output overlay if available
        if self.serial:
            serial_output = self.serial.get_output_text()
            if serial_output:
                self._draw_serial_overlay(serial_output)
        
        # Re-enable FPS display for performance monitoring
        self._draw_fps_display(current_time)

        # Force screen update with both flip and update
        pygame.display.flip()  # Use flip for better performance
        pygame.display.update()  # Additional update call for macOS

        # Handle pygame events - improved event processing
        events_processed = 0
        for event in pygame.event.get():
            events_processed += 1
            if event.type == pygame.QUIT:
                print("🛑 Window close requested")
                pygame.quit()
                return False
            elif event.type == pygame.KEYDOWN:
                print(f"⌨️ Key pressed: {pygame.key.name(event.key)} (code: {event.key})")
                if event.key == pygame.K_ESCAPE:  # ESC to close
                    print("🛑 ESC pressed, closing")
                    pygame.quit()
                    return False
                self.handle_keydown(event.key)
            elif event.type == pygame.KEYUP:
                print(f"⌨️ Key released: {pygame.key.name(event.key)} (code: {event.key})")
                self.handle_keyup(event.key)
            elif event.type == pygame.ACTIVEEVENT:
                print(f"🔄 Window activation event: {event}")
            elif event.type == pygame.VIDEORESIZE:
                print(f"📐 Window resize event: {event.size}")
        
        # Ensure pygame processes all events
        pygame.event.pump()
        
        # Debug: Print if no events were processed occasionally
        if not hasattr(self, '_event_debug_counter'):
            self._event_debug_counter = 0
        self._event_debug_counter += 1
        if self._event_debug_counter % 3600 == 0:  # Every ~60 seconds
            print(f"🔧 Event processing: {events_processed} events this frame")

        # Maximum speed mode - no frame rate limit for testing
        # self.clock.tick(60)  # Disabled for max speed
        
        self.last_frame_time = current_time
        return True
    
    def request_vblank_interrupt(self):
        """Request a V-Blank interrupt"""
        if hasattr(self, 'memory'):
            # Set V-Blank interrupt flag (bit 0 of IF register)
            if_reg = self.memory.read_byte(0xFF0F)
            self.memory.write_byte(0xFF0F, if_reg | 0x01)
    
    def handle_keydown(self, key):
        """Handle key press events - improved with debug output"""
        print(f"🎮 Processing key press: {pygame.key.name(key)} (code: {key})")
        
        # Test sound when pressing keys
        if key == pygame.K_t:  # T key for test sound
            print("🔊 Testing sound...")
            self.test_sound()
            
        # Map pygame keys to Game Boy buttons with debug output
        button_pressed = None
        if key == pygame.K_z:  # A button
            button_pressed = "A"
            if hasattr(self.memory, 'press_button'):
                self.memory.press_button(0)  # A = bit 0
            else:
                print("⚠️ Memory doesn't have press_button method")
        elif key == pygame.K_x:  # B button
            button_pressed = "B"
            if hasattr(self.memory, 'press_button'):
                self.memory.press_button(1)  # B = bit 1
            else:
                print("⚠️ Memory doesn't have press_button method")
        elif key == pygame.K_RSHIFT or key == pygame.K_LSHIFT:  # Select
            button_pressed = "SELECT"
            if hasattr(self.memory, 'press_button'):
                self.memory.press_button(2)  # Select = bit 2
            else:
                print("⚠️ Memory doesn't have press_button method")
        elif key == pygame.K_RETURN or key == pygame.K_KP_ENTER:  # Start
            button_pressed = "START"
            if hasattr(self.memory, 'press_button'):
                self.memory.press_button(3)  # Start = bit 3
            else:
                print("⚠️ Memory doesn't have press_button method")
        elif key == pygame.K_RIGHT:  # Right
            button_pressed = "RIGHT"
            if hasattr(self.memory, 'press_direction'):
                self.memory.press_direction(0)  # Right = bit 0
            else:
                print("⚠️ Memory doesn't have press_direction method")
        elif key == pygame.K_LEFT:  # Left
            button_pressed = "LEFT"
            if hasattr(self.memory, 'press_direction'):
                self.memory.press_direction(1)  # Left = bit 1
            else:
                print("⚠️ Memory doesn't have press_direction method")
        elif key == pygame.K_UP:  # Up
            button_pressed = "UP"
            if hasattr(self.memory, 'press_direction'):
                self.memory.press_direction(2)  # Up = bit 2
            else:
                print("⚠️ Memory doesn't have press_direction method")
        elif key == pygame.K_DOWN:  # Down
            button_pressed = "DOWN"
            if hasattr(self.memory, 'press_direction'):
                self.memory.press_direction(3)  # Down = bit 3
            else:
                print("⚠️ Memory doesn't have press_direction method")
        
        if button_pressed:
            print(f"✅ Game Boy button pressed: {button_pressed}")
        else:
            print(f"🔧 Unmapped key: {pygame.key.name(key)}")
            print("🎮 Controls: Z=A, X=B, Shift=Select, Enter=Start, Arrow Keys=D-Pad, T=Test Sound, ESC=Quit")
    
    def handle_keyup(self, key):
        """Handle key release events - improved with debug output"""
        print(f"🎮 Processing key release: {pygame.key.name(key)} (code: {key})")
        
        # Map pygame keys to Game Boy buttons with debug output
        button_released = None
        if key == pygame.K_z:  # A button
            button_released = "A"
            if hasattr(self.memory, 'release_button'):
                self.memory.release_button(0)
            else:
                print("⚠️ Memory doesn't have release_button method")
        elif key == pygame.K_x:  # B button
            button_released = "B"
            if hasattr(self.memory, 'release_button'):
                self.memory.release_button(1)
            else:
                print("⚠️ Memory doesn't have release_button method")
        elif key == pygame.K_RSHIFT or key == pygame.K_LSHIFT:  # Select
            button_released = "SELECT"
            if hasattr(self.memory, 'release_button'):
                self.memory.release_button(2)
            else:
                print("⚠️ Memory doesn't have release_button method")
        elif key == pygame.K_RETURN or key == pygame.K_KP_ENTER:  # Start
            button_released = "START"
            if hasattr(self.memory, 'release_button'):
                self.memory.release_button(3)
            else:
                print("⚠️ Memory doesn't have release_button method")
        elif key == pygame.K_RIGHT:  # Right
            button_released = "RIGHT"
            if hasattr(self.memory, 'release_direction'):
                self.memory.release_direction(0)
            else:
                print("⚠️ Memory doesn't have release_direction method")
        elif key == pygame.K_LEFT:  # Left
            button_released = "LEFT"
            if hasattr(self.memory, 'release_direction'):
                self.memory.release_direction(1)
            else:
                print("⚠️ Memory doesn't have release_direction method")
        elif key == pygame.K_UP:  # Up
            button_released = "UP"
            if hasattr(self.memory, 'release_direction'):
                self.memory.release_direction(2)
            else:
                print("⚠️ Memory doesn't have release_direction method")
        elif key == pygame.K_DOWN:  # Down
            button_released = "DOWN"
            if hasattr(self.memory, 'release_direction'):
                self.memory.release_direction(3)
            else:
                print("⚠️ Memory doesn't have release_direction method")
        
        if button_released:
            print(f"✅ Game Boy button released: {button_released}")
        else:
            print(f"🔧 Unmapped key release: {pygame.key.name(key)}")
    
    def test_sound(self):
        """Test sound by playing a tone"""
        if hasattr(self.memory, 'apu') and self.memory.apu:
            apu = self.memory.apu
            print("Playing test sound...")
            
            # Enable sound system
            apu.write_register(0xFF26, 0x80)  # Enable sound
            apu.write_register(0xFF25, 0x11)  # Enable channel 1 to both speakers  
            apu.write_register(0xFF24, 0x77)  # Set volume
            
            # Configure Channel 1 for test tone
            apu.write_register(0xFF11, 0x80)  # Duty cycle 50%
            apu.write_register(0xFF12, 0xF3)  # Volume = 15, envelope decrease
            apu.write_register(0xFF13, 0x00)  # Frequency low byte (440Hz)
            apu.write_register(0xFF14, 0x87)  # Frequency high, trigger
    
    def _draw_fps_display(self, current_time):
        """Draw FPS information on the screen"""
        # Update FPS calculation every second
        if current_time - self.last_fps_update >= self.fps_update_interval:
            if self.last_fps_update > 0:
                time_elapsed = current_time - self.last_fps_update
                self.current_fps = self.frame_count_for_fps / time_elapsed
            
            self.last_fps_update = current_time
            self.frame_count_for_fps = 0
        
        # Create FPS text (adapted for max speed mode)
        mode_text = "MAX SPEED MODE"
        current_fps_text = f"FPS: {self.current_fps:.0f}"
        skip_rate_text = f"Skip: {self.frame_skip_rate}x"
        
        # Render text surfaces
        mode_surface = self.font.render(mode_text, True, (255, 255, 0))  # Yellow for max speed
        current_surface = self.font.render(current_fps_text, True, (255, 255, 255))
        skip_surface = self.font.render(skip_rate_text, True, (255, 255, 255))
        
        # Calculate position (bottom right corner)
        screen_width = self.screen_width * self.scale
        screen_height = self.screen_height * self.scale
        
        # Position text in bottom right, with some margin
        margin = 10
        line_height = 25
        
        # Draw text with black outline for better visibility
        positions = [
            (screen_width - mode_surface.get_width() - margin, screen_height - line_height * 3 - margin),
            (screen_width - current_surface.get_width() - margin, screen_height - line_height * 2 - margin),
            (screen_width - skip_surface.get_width() - margin, screen_height - line_height - margin)
        ]
        
        texts = [mode_text, current_fps_text, skip_rate_text]
        surfaces = [mode_surface, current_surface, skip_surface]
        
        for i, (surface, (x, y)) in enumerate(zip(surfaces, positions)):
            # Draw black outline for better visibility
            outline_surface = self.font.render(texts[i], True, (0, 0, 0))
            for dx in [-1, 0, 1]:
                for dy in [-1, 0, 1]:
                    if dx != 0 or dy != 0:
                        self.screen.blit(outline_surface, (x + dx, y + dy))
            
            # Draw white text on top
            self.screen.blit(surface, (x, y))

    def _draw_serial_overlay(self, serial_output):
        """Draw serial output as an overlay on the screen"""
        if not serial_output:
            return
        
        # Configuration for overlay appearance
        font_size = 16
        line_height = 18
        margin_x = 10
        margin_y = 10
        max_lines = 20  # Maximum lines to display
        background_alpha = 180  # Semi-transparent background
        
        # Split serial output into lines
        lines = serial_output.split('\n')
        
        # Keep only recent lines if too many
        if len(lines) > max_lines:
            lines = lines[-max_lines:]
        
        if not lines:
            return
        
        # Calculate overlay dimensions
        max_line_width = 0
        for line in lines:
            if line.strip():  # Skip empty lines for width calculation
                text_surface = self.font.render(line, True, (255, 255, 255))
                max_line_width = max(max_line_width, text_surface.get_width())
        
        overlay_width = min(max_line_width + 2 * margin_x, self.screen_width * self.scale - 20)
        overlay_height = len(lines) * line_height + 2 * margin_y
        
        # Position overlay in the top-left area but with some offset
        overlay_x = 10
        overlay_y = 10
        
        # Create semi-transparent background
        overlay_surface = pygame.Surface((overlay_width, overlay_height))
        overlay_surface.set_alpha(background_alpha)
        overlay_surface.fill((0, 0, 0))  # Black background
        
        # Draw background
        self.screen.blit(overlay_surface, (overlay_x, overlay_y))
        
        # Draw border
        pygame.draw.rect(self.screen, (100, 100, 100), 
                        (overlay_x, overlay_y, overlay_width, overlay_height), 2)
        
        # Draw title
        title_text = "Blargg Test Results"
        title_surface = self.font.render(title_text, True, (255, 255, 0))  # Yellow title
        self.screen.blit(title_surface, (overlay_x + margin_x, overlay_y + 5))
        
        # Draw a separator line
        separator_y = overlay_y + 25
        pygame.draw.line(self.screen, (100, 100, 100), 
                        (overlay_x + margin_x, separator_y), 
                        (overlay_x + overlay_width - margin_x, separator_y), 1)
        
        # Draw serial output lines
        y_offset = overlay_y + margin_y + 30  # Start below title and separator
        
        for i, line in enumerate(lines):
            if line.strip():  # Only render non-empty lines
                # Choose color based on content
                text_color = (255, 255, 255)  # Default white
                
                if "cpu_instrs" in line.lower():
                    text_color = (0, 255, 255)  # Cyan for title
                elif "passed" in line.lower():
                    text_color = (0, 255, 0)    # Green for passed
                elif "failed" in line.lower() or "error" in line.lower():
                    text_color = (255, 100, 100)  # Red for failed/error
                elif ":" in line and any(c.isdigit() for c in line):
                    text_color = (200, 200, 255)  # Light blue for test results
                
                # Render text
                text_surface = self.font.render(line[:80], True, text_color)  # Limit line length
                
                # Check if text fits in overlay width
                if text_surface.get_width() > overlay_width - 2 * margin_x:
                    # Truncate long lines
                    truncated_line = line[:60] + "..."
                    text_surface = self.font.render(truncated_line, True, text_color)
                
                self.screen.blit(text_surface, (overlay_x + margin_x, y_offset))
                y_offset += line_height
                
                # Prevent overflow beyond overlay
                if y_offset > overlay_y + overlay_height - margin_y:
                    break
        
        # Draw scroll indicator if there are more lines
        total_lines = len(serial_output.split('\n'))
        if total_lines > max_lines:
            extra_lines = total_lines - max_lines
            scroll_text = f"... ({extra_lines} more lines)"
            scroll_surface = self.font.render(scroll_text, True, (150, 150, 150))
            self.screen.blit(scroll_surface, (overlay_x + margin_x, y_offset))
    
    def set_target_fps(self, fps):
        """Set the target frames per second (FPS)"""
        if fps > 0:
            self.target_fps = fps
            self.target_frame_time = 1.0 / fps
        else:
            raise ValueError("FPS must be greater than 0")
    
    def set_frame_skip_rate(self, rate):
        """Set the frame skip rate manually (1 = no skip, 2 = skip every other frame, etc.)"""
        if rate >= 1:
            self.frame_skip_rate = rate
        else:
            raise ValueError("Frame skip rate must be 1 or greater")
    
    def get_performance_stats(self):
        """Get current performance statistics"""
        frame_time = 0
        if self.last_frame_time > 0:
            frame_time = self.last_frame_time
        
        return {
            'frame_skip_rate': self.frame_skip_rate,
            'frame_counter': self.frame_counter,
            'target_fps': self.target_fps,
            'last_frame_time': frame_time
        }
    
    def get_lcdc(self):
        """Get LCD Control register value"""
        return self.memory.read_byte(0xFF40)
    
    def get_stat(self):
        """Get LCD Status register value"""
        stat = self.memory.read_byte(0xFF41)
        # Update mode bits
        stat = (stat & 0xFC) | self.mode
        return stat
    
    def get_ly(self):
        """Get current scanline (LY register)"""
        return self.scan_line
    
    def render_sprites_scanline(self):
        """Render sprites for current scanline"""
        lcdc = self.memory.read_byte(0xFF40)
        sprite_height = 16 if (lcdc & 0x04) else 8
        
        # Get visible sprites for this scanline (max 10 per scanline)
        visible_sprites = []
        
        # Scan OAM for sprites on this scanline
        for sprite_index in range(40):  # 40 sprites max in OAM
            oam_addr = 0xFE00 + (sprite_index * 4)
            
            # Read sprite attributes
            y_pos = self.memory.read_byte(oam_addr)
            x_pos = self.memory.read_byte(oam_addr + 1)
            tile_index = self.memory.read_byte(oam_addr + 2)
            attributes = self.memory.read_byte(oam_addr + 3)
            
            # Adjust positions (Game Boy uses offset positions)
            y_pos -= 16
            x_pos -= 8
            
            # Check if sprite is visible on this scanline
            if (y_pos <= self.scan_line < y_pos + sprite_height and
                x_pos > -8 and x_pos < self.screen_width):
                
                visible_sprites.append({
                    'x': x_pos,
                    'y': y_pos,
                    'tile': tile_index,
                    'attributes': attributes,
                    'index': sprite_index
                })
                
                # Limit to 10 sprites per scanline
                if len(visible_sprites) >= 10:
                    break
        
        # Render each visible sprite (Game Boy priority is by OAM index, not X position)
        for sprite in visible_sprites:
            self.render_sprite(sprite, sprite_height)
    
    def render_sprite(self, sprite, sprite_height):
        """Render a single sprite on the current scanline"""
        x_pos = sprite['x']
        y_pos = sprite['y']
        tile_index = sprite['tile']
        attributes = sprite['attributes']
        
        # Extract sprite attributes
        palette_num = (attributes >> 4) & 1  # Bit 4: palette number
        x_flip = bool(attributes & 0x20)     # Bit 5: X flip
        y_flip = bool(attributes & 0x40)     # Bit 6: Y flip
        bg_priority = bool(attributes & 0x80) # Bit 7: BG priority
        
        # Calculate which line of the sprite we're rendering
        sprite_line = self.scan_line - y_pos
        if y_flip:
            sprite_line = (sprite_height - 1) - sprite_line
        
        # For 8x16 sprites, use even tile index for top, odd for bottom
        if sprite_height == 16:
            if sprite_line >= 8:
                tile_index = tile_index | 1  # Bottom tile
                sprite_line -= 8
            else:
                tile_index = tile_index & 0xFE  # Top tile
        
        # Calculate tile data address (sprites always use 0x8000 method)
        tile_addr = 0x8000 + (tile_index * 16) + (sprite_line * 2)
        
        # Read tile data
        tile_data_low = self.memory.read_byte(tile_addr)
        tile_data_high = self.memory.read_byte(tile_addr + 1)
        
        # Render pixels
        for pixel_x in range(8):
            screen_x = x_pos + pixel_x
            
            # Check if pixel is on screen
            if screen_x < 0 or screen_x >= self.screen_width:
                continue
            
            # Get pixel position in tile (handle X flip)
            bit_pos = pixel_x if x_flip else (7 - pixel_x)
            
            # Extract pixel color
            color_bit_0 = (tile_data_low >> bit_pos) & 1
            color_bit_1 = (tile_data_high >> bit_pos) & 1
            color_index = (color_bit_1 << 1) | color_bit_0
            
            # Skip transparent pixels (color 0)
            if color_index == 0:
                continue
            
            # Check background priority
            if bg_priority and self.frame_buffer[self.scan_line][screen_x] != 0:
                continue
            
            # Apply sprite palette
            palette_addr = 0xFF48 if palette_num == 0 else 0xFF49
            palette = self.memory.read_byte(palette_addr)
            palette_color = (palette >> (color_index * 2)) & 0x03
            
            # Set pixel in frame buffer
            self.frame_buffer[self.scan_line][screen_x] = palette_color
    
    
    def step(self, cycles):
        """Step PPU by specified cycles for accurate timing"""
        if not hasattr(self, 'ppu_cycles'):
            self.ppu_cycles = 0
        
        self.ppu_cycles += cycles
        
        # Update scanline every 456 cycles
        while self.ppu_cycles >= 456:
            self.ppu_cycles -= 456
            ly = self.memory.read_byte(0xFF44)
            ly = (ly + 1) % 154  # 154 scanlines total
            self.memory.write_byte(0xFF44, ly)
            
            # Set VBlank interrupt when entering VBlank period
            if ly == 144:
                if_reg = self.memory.read_byte(0xFF0F)
                self.memory.write_byte(0xFF0F, if_reg | 0x01)
            elif ly == 0:
                # Reset VBlank interrupt when leaving VBlank
                if_reg = self.memory.read_byte(0xFF0F)
                self.memory.write_byte(0xFF0F, if_reg & ~0x01)

def render_vram_debug(self):
        """Debug method to render VRAM content directly when LCD is disabled"""
        if self.scan_line >= self.screen_height:
            return
            
        # Show first tiles of VRAM as a pattern
        tiles_per_row = self.screen_width // 8
        tile_y = self.scan_line // 8
        tile_line = self.scan_line % 8
        
        for tile_x in range(tiles_per_row):
            tile_index = tile_y * tiles_per_row + tile_x
            
            # Get tile data from VRAM (0x8000 base)
            tile_addr = 0x8000 + (tile_index * 16) + (tile_line * 2)
            
            if tile_addr + 1 < 0x9000:  # Within VRAM bounds
                tile_data_low = self.memory.read_byte(tile_addr)
                tile_data_high = self.memory.read_byte(tile_addr + 1)
                
                # Render 8 pixels of this tile line
                for pixel in range(8):
                    screen_x = tile_x * 8 + pixel
                    if screen_x >= self.screen_width:
                        break
                        
                    bit_pos = 7 - pixel
                    color_bit_0 = (tile_data_low >> bit_pos) & 1
                    color_bit_1 = (tile_data_high >> bit_pos) & 1
                    color_index = (color_bit_1 << 1) | color_bit_0
                    
                    self.frame_buffer[self.scan_line][screen_x] = color_index