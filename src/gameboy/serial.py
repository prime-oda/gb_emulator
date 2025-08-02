"""
Game Boy Serial Port (Link Cable) Implementation

Handles serial communication for Game Boy test ROMs and multiplayer games.
Primary use case: Blargg test ROM output via serial port.
"""

class SerialPort:
    def __init__(self, memory):
        self.memory = memory
        
        # Serial port state
        self.transfer_in_progress = False
        self.transfer_cycles = 0
        self.transfer_data = 0x00
        
        # Serial port timing
        # Internal clock: 8192 Hz (512 cycles per bit, 4096 cycles per byte)
        # External clock: controlled by other Game Boy
        self.internal_clock_cycles_per_bit = 512
        self.cycles_per_byte = 4096
        
        # Output buffer for test ROM results
        self.output_buffer = []
        self.text_output = ""
        
        # Debug logging
        self.debug = False
        
    def read_register(self, address):
        """Read serial port register"""
        if address == 0xFF01:  # SB - Serial transfer data
            return self.memory.io[0x01]
        elif address == 0xFF02:  # SC - Serial transfer control
            return self.memory.io[0x02]
        return 0xFF
        
    def write_register(self, address, value):
        """Write serial port register"""
        value &= 0xFF
        
        if address == 0xFF01:  # SB - Serial transfer data
            self.memory.io[0x01] = value
            if self.debug:
                print(f"Serial: SB write = 0x{value:02X} ('{chr(value) if 32 <= value <= 126 else '?'}')")
                
        elif address == 0xFF02:  # SC - Serial transfer control
            old_sc = self.memory.io[0x02]
            self.memory.io[0x02] = value & 0x83  # Only bits 0, 1, 7 are used
            
            # Check if transfer is being started
            if (value & 0x80) and not (old_sc & 0x80):  # Bit 7: Transfer start flag
                self.start_transfer()
                
    def start_transfer(self):
        """Start serial transfer"""
        sc = self.memory.io[0x02]
        sb = self.memory.io[0x01]
        
        # Check clock source (bit 0 of SC)
        internal_clock = (sc & 0x01) != 0
        
        if internal_clock:
            # Internal clock - we control the transfer
            self.transfer_in_progress = True
            self.transfer_cycles = 0
            self.transfer_data = sb
            
            if self.debug:
                print(f"Serial: Starting internal transfer, data=0x{sb:02X} ('{chr(sb) if 32 <= sb <= 126 else '?'}')")
                
            # For test ROMs, we can complete transfer immediately
            # Real hardware would take ~4096 cycles
            self.complete_transfer()
        else:
            # External clock - other Game Boy controls transfer
            # For single Game Boy operation, we simulate no response
            if self.debug:
                print(f"Serial: External clock transfer requested (no response)")
            
            # Complete immediately with 0xFF (no device connected)
            self.memory.io[0x01] = 0xFF  # Received data
            self.memory.io[0x02] &= 0x7F  # Clear transfer flag
            
    def complete_transfer(self):
        """Complete serial transfer and trigger interrupt"""
        sb = self.transfer_data
        
        # Store the transmitted byte for output
        self.output_buffer.append(sb)
        
        # Convert to text if printable
        if 32 <= sb <= 126:
            self.text_output += chr(sb)
            print(f"📤 Serial Output: '{chr(sb)}'")
        elif sb == 0x0A:  # Newline
            self.text_output += '\n'
            print(f"📤 Serial Output: [NEWLINE]")
            print(f"📝 Complete Line: \"{self.text_output.rstrip()}\"")
        elif sb == 0x0D:  # Carriage return
            print(f"📤 Serial Output: [CR]")
        else:
            print(f"📤 Serial Output: 0x{sb:02X}")
            
        # For test ROMs, simulate receiving 0xFF (no device)
        self.memory.io[0x01] = 0xFF
        
        # Clear transfer flag (bit 7)
        self.memory.io[0x02] &= 0x7F
        
        # Set serial interrupt flag (bit 3 of IF register)
        if_reg = self.memory.read_byte(0xFF0F)
        if_reg |= 0x08  # Set serial interrupt bit
        self.memory.write_byte(0xFF0F, if_reg)
        
        # Mark transfer as complete
        self.transfer_in_progress = False
        
        if self.debug:
            print(f"Serial: Transfer complete, interrupt triggered")
    
    def update(self, cycles):
        """Update serial port state"""
        if self.transfer_in_progress:
            self.transfer_cycles += cycles
            
            # Check if transfer should complete
            if self.transfer_cycles >= self.cycles_per_byte:
                self.complete_transfer()
                
    def get_output_text(self):
        """Get accumulated text output"""
        return self.text_output
        
    def get_output_bytes(self):
        """Get raw output bytes"""
        return self.output_buffer.copy()
        
    def clear_output(self):
        """Clear output buffers"""
        self.output_buffer.clear()
        self.text_output = ""
        
    def set_debug(self, debug):
        """Enable/disable debug output"""
        self.debug = debug