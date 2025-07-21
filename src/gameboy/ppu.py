"""
Game Boy PPU (Picture Processing Unit)
Handles graphics rendering, LCD timing, and video memory management.
"""

import pygame


class PPU:
    def __init__(self, memory, debug=False):
        self.memory = memory
        self.debug = debug
        
        # LCD specifications
        self.screen_width = 160
        self.screen_height = 144
        self.scale = 4  # Scale factor for display
        
        # PPU state
        self.cycles = 0
        self.scan_line = 0
        self.mode = 0  # 0: H-Blank, 1: V-Blank, 2: OAM, 3: VRAM
        
        # Mode durations (in CPU cycles)
        self.mode_2_cycles = 80   # OAM scan
        self.mode_3_cycles = 172  # VRAM scan
        self.mode_0_cycles = 204  # H-Blank
        self.v_blank_cycles = 4560  # V-Blank (10 scanlines)
        
        # Palette colors (from light to dark)
        self.palette = [
            (155, 188, 15),   # Light green
            (139, 172, 15),   # Medium-light green
            (48, 98, 48),     # Medium-dark green
            (15, 56, 15)      # Dark green
        ]
        
        # Frame buffer
        self.frame_buffer = [[0 for _ in range(self.screen_width)] for _ in range(self.screen_height)]
        
        # Initialize pygame
        pygame.init()
        self.screen = pygame.display.set_mode((
            self.screen_width * self.scale,
            self.screen_height * self.scale
        ))
        pygame.display.set_caption("Game Boy Emulator")
        
        self.clock = pygame.time.Clock()
        
    def step(self, cpu_cycles):
        """Update PPU state based on CPU cycles"""
        self.cycles += cpu_cycles
        
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
                    self.render_frame()
        else:  # V-Blank period (scanlines 144-153)
            if self.cycles >= 456:  # Duration of one scanline in V-Blank
                self.scan_line += 1
                self.cycles = 0
                if self.scan_line >= 154:
                    self.scan_line = 0
                    self.mode = 2  # Start new frame
    
    def render_scanline(self):
        """Render a single scanline"""
        if self.scan_line >= self.screen_height:
            return
            
        # Get LCD control register
        lcdc = self.memory.read_byte(0xFF40)
        
        # Check if LCD is enabled
        if not (lcdc & 0x80):
            return
            
        # Render background if enabled
        if lcdc & 0x01:
            self.render_background_scanline()
    
    def render_background_scanline(self):
        """Render background tiles for current scanline"""
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
        
        for x in range(self.screen_width):
            # Calculate tile position
            pixel_x = (x + scx) & 0xFF
            tile_col = pixel_x // 8
            tile_pixel = pixel_x % 8
            
            # Get tile index from background map
            tile_map_addr = bg_map_base + (tile_row * 32) + tile_col
            tile_index = self.memory.read_byte(tile_map_addr)
            
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
            try:
                tile_data_low = self.memory.read_byte(tile_addr)
                tile_data_high = self.memory.read_byte(tile_addr + 1)
            except:
                tile_data_low = 0
                tile_data_high = 0
            
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
        """Render the complete frame to the screen"""
        # Convert frame buffer to pygame surface
        for y in range(self.screen_height):
            for x in range(self.screen_width):
                color_index = self.frame_buffer[y][x]
                color = self.palette[color_index]
                
                # Draw scaled pixel
                rect = pygame.Rect(
                    x * self.scale,
                    y * self.scale,
                    self.scale,
                    self.scale
                )
                pygame.draw.rect(self.screen, color, rect)
        
        pygame.display.flip()
        
        # Handle pygame events
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                return False
        
        # Limit to ~60 FPS
        self.clock.tick(60)
        return True
    
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