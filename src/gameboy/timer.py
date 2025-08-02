"""
Game Boy Timer Implementation
Handles DIV, TIMA, TMA, and TAC registers with proper timing.
"""

class Timer:
    def __init__(self, memory):
        self.memory = memory
        
        # Internal counters
        self.div_counter = 0      # Internal counter for DIV register
        self.tima_counter = 0     # Internal counter for TIMA
        
        # Timer registers (stored in memory IO space)
        # 0xFF04: DIV  - Divider register (read-only, resets on write)
        # 0xFF05: TIMA - Timer counter 
        # 0xFF06: TMA  - Timer modulo (reload value)
        # 0xFF07: TAC  - Timer control
        
        # Timer frequencies based on TAC bits 1-0
        self.frequencies = {
            0: 1024,    # 4096 Hz (CPU clock / 1024)
            1: 16,      # 262144 Hz (CPU clock / 16)  
            2: 64,      # 65536 Hz (CPU clock / 64)
            3: 256      # 16384 Hz (CPU clock / 256)
        }
        
    def read_register(self, address):
        """Read timer register value"""
        if address == 0xFF04:  # DIV
            # DIV register shows upper 8 bits of 16-bit counter
            return (self.div_counter >> 8) & 0xFF
        elif address == 0xFF05:  # TIMA
            return self.memory.io[0x05]
        elif address == 0xFF06:  # TMA
            return self.memory.io[0x06]
        elif address == 0xFF07:  # TAC
            return self.memory.io[0x07]
        return 0xFF
        
    def write_register(self, address, value):
        """Write timer register value"""
        value &= 0xFF
        
        if address == 0xFF04:  # DIV
            # Writing any value to DIV resets it to 0
            self.div_counter = 0
        elif address == 0xFF05:  # TIMA
            self.memory.io[0x05] = value
        elif address == 0xFF06:  # TMA
            self.memory.io[0x06] = value
        elif address == 0xFF07:  # TAC
            self.memory.io[0x07] = value & 0x07  # Only bits 0-2 are used
            
    def update(self, cycles):
        """Update timer state based on CPU cycles"""
        # Update DIV counter (always running at 16384 Hz)
        self.div_counter += cycles
        
        # Check if TIMA timer is enabled (TAC bit 2)
        tac = self.memory.io[0x07]
        if tac & 0x04:  # Timer enabled
            # Get timer frequency from TAC bits 1-0
            freq_select = tac & 0x03
            divider = self.frequencies[freq_select]
            
            # Update TIMA counter
            self.tima_counter += cycles
            
            # Check if we need to increment TIMA
            while self.tima_counter >= divider:
                self.tima_counter -= divider
                
                # Increment TIMA
                tima = self.memory.io[0x05]
                tima += 1
                
                # Check for overflow
                if tima > 0xFF:
                    # TIMA overflow - trigger timer interrupt
                    tima = self.memory.io[0x06]  # Reload with TMA
                    self.memory.io[0x05] = tima
                    
                    # Set timer interrupt flag (bit 2 of IF register)
                    if_reg = self.memory.read_byte(0xFF0F)
                    if_reg |= 0x04  # Set timer interrupt bit
                    self.memory.write_byte(0xFF0F, if_reg)
                else:
                    self.memory.io[0x05] = tima
                    
    def get_div_register(self):
        """Get current DIV register value"""
        return (self.div_counter >> 8) & 0xFF
        
    def get_tima_register(self):
        """Get current TIMA register value"""
        return self.memory.io[0x05]
        
    def is_timer_enabled(self):
        """Check if timer is enabled"""
        return (self.memory.io[0x07] & 0x04) != 0
        
    def get_timer_frequency(self):
        """Get current timer frequency setting"""
        tac = self.memory.io[0x07]
        freq_select = tac & 0x03
        cpu_freq = 4194304  # 4.194304 MHz
        divider = self.frequencies[freq_select]
        return cpu_freq // divider