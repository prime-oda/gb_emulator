"""
Game Boy PPU (Picture Processing Unit)
Handles graphics rendering, LCD timing, and video memory management.
"""

import pygame
import numpy
import logging


class PPU:
    def __init__(self, memory, debug=False):
        self.memory = memory
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

        # Palette colors (from light to dark)
        self.palette = [
            (155, 188, 15),   # Light green
            (139, 172, 15),   # Medium-light green
            (48, 98, 48),     # Medium-dark green
            (15, 56, 15)      # Dark green
        ]

        # Frame buffer
        self.frame_buffer = numpy.zeros((self.screen_height, self.screen_width), dtype=numpy.uint8)

        # Frame skip settings for performance control
        self.frame_skip_rate = 1  # Skip every N frames (1 = no skip, 2 = skip every other frame)
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
        os.environ['SDL_VIDEO_WINDOW_POS'] = '100,100'  # Position window

        pygame.init()
        self.screen = pygame.display.set_mode((
            self.screen_width * self.scale,
            self.screen_height * self.scale
        ))
        pygame.display.set_caption("Game Boy Emulator - big2small.gb")
        
        # Initialize font for FPS display
        pygame.font.init()
        self.font = pygame.font.Font(None, 24)  # Small font for FPS display

        # Force window to front on macOS
        try:
            import subprocess
            subprocess.run(['osascript', '-e', 
                          'tell application "Python" to activate'], 
                         capture_output=True, timeout=1)
        except:
            pass

        self.clock = pygame.time.Clock()

        # Frame rate control
        self.target_fps = 60  # Game Boy native refresh rate

    def step(self, cpu_cycles):
        """Update PPU state based on CPU cycles"""
        self.cycles += cpu_cycles

        # Remove frequent step logging to improve performance

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
            if self.cycles >= self.scanline_cycles:  # Duration of one scanline in V-Blank
                self.scan_line += 1
                self.cycles = 0
                if self.scan_line >= 154:
                    self.scan_line = 0
                    self.mode = 2  # Start new frame

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
        self.frame_buffer[self.scan_line].fill(0)  # Use color 0 as background

        # Render background if enabled
        if lcdc & 0x01:
            self.render_background_scanline()

        # Render sprites if enabled
        if lcdc & 0x02:
            self.render_sprites_scanline()

    def render_background_scanline(self):
        """Render background tiles for the current scanline to the temporary buffer"""
        # Get scroll registers
        scy = self.memory.read_byte(0xFF42)  # Scroll Y
        scx = self.memory.read_byte(0xFF43)  # Scroll X

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
                # Unsigned indexing
                tile_addr = tile_data_base + (tile_index * 16) + (tile_line * 2)
            else:
                # Signed indexing
                if tile_index > 127:
                    tile_index = tile_index - 256
                tile_addr = tile_data_base + (tile_index * 16) + (tile_line * 2)

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
            palette_color = (bgp >> (color_index * 2)) & 0x03

            # Store in frame buffer
            self.frame_buffer[self.scan_line][x] = palette_color

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
            # Still handle events even when skipping frames
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    return False
                elif event.type == pygame.KEYDOWN:
                    self.handle_keydown(event.key)
                elif event.type == pygame.KEYUP:
                    self.handle_keyup(event.key)
            return True
        
        # Render the frame
        active_buffer = self.frame_buffer

        # Reuse frame_array to avoid creating a new array every frame
        if not hasattr(self, 'frame_array'):
            self.frame_array = numpy.zeros((self.screen_height, self.screen_width, 3), dtype=numpy.uint8)

        # Use numpy vectorized operations for better performance
        palette_array = numpy.array(self.palette)
        self.frame_array = palette_array[active_buffer]

        # Transpose the frame_array to match pygame's expected orientation
        frame_array_transposed = numpy.transpose(self.frame_array, (1, 0, 2))

        # Create a surface from the numpy array
        frame_surface = pygame.surfarray.make_surface(frame_array_transposed)

        # Scale the surface and blit to the screen
        scaled_surface = pygame.transform.scale(
            frame_surface, (self.screen_width * self.scale, self.screen_height * self.scale)
        )
        self.screen.blit(scaled_surface, (0, 0))
        
        # Draw FPS information
        self._draw_fps_display(current_time)

        pygame.display.flip()  # Use flip for better performance

        # Handle pygame events
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                return False
            elif event.type == pygame.KEYDOWN:
                self.handle_keydown(event.key)
            elif event.type == pygame.KEYUP:
                self.handle_keyup(event.key)

        # Frame rate control
        self.clock.tick(self.target_fps)
        
        self.last_frame_time = current_time
        return True
    
    def request_vblank_interrupt(self):
        """Request a V-Blank interrupt"""
        if hasattr(self, 'memory'):
            # Set V-Blank interrupt flag (bit 0 of IF register)
            if_reg = self.memory.read_byte(0xFF0F)
            self.memory.write_byte(0xFF0F, if_reg | 0x01)
    
    def handle_keydown(self, key):
        """Handle key press events"""
        # Map pygame keys to Game Boy buttons
        if key == pygame.K_z:  # A button
            self.memory.press_button(0)  # A = bit 0
        elif key == pygame.K_x:  # B button
            self.memory.press_button(1)  # B = bit 1
        elif key == pygame.K_RSHIFT:  # Select
            self.memory.press_button(2)  # Select = bit 2
        elif key == pygame.K_RETURN:  # Start
            self.memory.press_button(3)  # Start = bit 3
        elif key == pygame.K_RIGHT:  # Right
            self.memory.press_direction(0)  # Right = bit 0
        elif key == pygame.K_LEFT:  # Left
            self.memory.press_direction(1)  # Left = bit 1
        elif key == pygame.K_UP:  # Up
            self.memory.press_direction(2)  # Up = bit 2
        elif key == pygame.K_DOWN:  # Down
            self.memory.press_direction(3)  # Down = bit 3
    
    def handle_keyup(self, key):
        """Handle key release events"""
        # Map pygame keys to Game Boy buttons
        if key == pygame.K_z:  # A button
            self.memory.release_button(0)
        elif key == pygame.K_x:  # B button
            self.memory.release_button(1)
        elif key == pygame.K_RSHIFT:  # Select
            self.memory.release_button(2)
        elif key == pygame.K_RETURN:  # Start
            self.memory.release_button(3)
        elif key == pygame.K_RIGHT:  # Right
            self.memory.release_direction(0)
        elif key == pygame.K_LEFT:  # Left
            self.memory.release_direction(1)
        elif key == pygame.K_UP:  # Up
            self.memory.release_direction(2)
        elif key == pygame.K_DOWN:  # Down
            self.memory.release_direction(3)
    
    def _draw_fps_display(self, current_time):
        """Draw FPS information on the screen"""
        # Update FPS calculation every second
        if current_time - self.last_fps_update >= self.fps_update_interval:
            if self.last_fps_update > 0:
                time_elapsed = current_time - self.last_fps_update
                self.current_fps = self.frame_count_for_fps / time_elapsed
            
            self.last_fps_update = current_time
            self.frame_count_for_fps = 0
        
        # Create FPS text
        target_fps_text = f"Target: {self.target_fps:.0f} FPS"
        current_fps_text = f"Actual: {self.current_fps:.1f} FPS"
        skip_rate_text = f"Skip: {self.frame_skip_rate}x"
        
        # Render text surfaces
        target_surface = self.font.render(target_fps_text, True, (255, 255, 255))
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
            (screen_width - target_surface.get_width() - margin, screen_height - line_height * 3 - margin),
            (screen_width - current_surface.get_width() - margin, screen_height - line_height * 2 - margin),
            (screen_width - skip_surface.get_width() - margin, screen_height - line_height - margin)
        ]
        
        texts = [target_fps_text, current_fps_text, skip_rate_text]
        surfaces = [target_surface, current_surface, skip_surface]
        
        for i, (surface, (x, y)) in enumerate(zip(surfaces, positions)):
            # Draw black outline for better visibility
            outline_surface = self.font.render(texts[i], True, (0, 0, 0))
            for dx in [-1, 0, 1]:
                for dy in [-1, 0, 1]:
                    if dx != 0 or dy != 0:
                        self.screen.blit(outline_surface, (x + dx, y + dy))
            
            # Draw white text on top
            self.screen.blit(surface, (x, y))
    
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